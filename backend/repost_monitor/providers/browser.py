"""Provedor sem API: abre o perfil num navegador local e lê a aba "Reposts".

Como funciona (a cada ciclo):
1. abre o navegador em modo invisível (headless) — no Windows, o Microsoft Edge
   que já vem instalado; nos outros sistemas, o Chromium do Playwright;
2. bloqueia imagens, vídeos e fontes para ficar leve;
3. entra em tiktok.com/@perfil e clica na aba "Reposts";
4. captura a resposta JSON que o próprio site carrega (/api/repost/item_list) e,
   se ela não vier, lê os links de vídeo da aba;
5. fecha o navegador (não fica ocupando memória entre as verificações).

O perfil do navegador fica em data/browser-profile: se o TikTok pedir login ou
captcha, rode `python -m repost_monitor abrir-navegador` (ou abrir-navegador.bat),
resolva na janela e feche-a; os cookies ficam salvos para as próximas verificações.
"""

from __future__ import annotations

import asyncio
import logging
import platform
import re
from pathlib import Path
from typing import Any

from ..http import ProviderError
from ..models import Repost
from .base import RepostProvider, find_items, normalize_items

log = logging.getLogger(__name__)

TIKTOK_URL = "https://www.tiktok.com"
REPOST_API_PATH = "/api/repost/item_list"
TAB_SELECTORS = ('[data-e2e="repost-tab"]', '[data-e2e="reposts-tab"]')
TAB_TEXT = re.compile(r"^\s*(reposts?|republica\w*|repostados?)\s*$", re.IGNORECASE)
DOM_ITEM_LINKS = '[data-e2e*="repost"] a[href*="/video/"]'
CAPTCHA_SELECTORS = '#captcha-verify-container-main-page, [id*="captcha-verify"], iframe[src*="captcha"]'
BLOCKED_RESOURCES = {"image", "media", "font"}
LAUNCH_ARGS = ["--mute-audio", "--disable-blink-features=AutomationControlled", "--no-first-run"]


def default_channel() -> str:
    """Windows: usa o Edge instalado (nada para baixar). Outros: Chromium do Playwright."""
    return "msedge" if platform.system() == "Windows" else ""


class BrowserProvider(RepostProvider):
    name = "browser"

    async def fetch_reposts(self) -> list[Repost]:
        if not self.settings.username:
            raise ProviderError("O modo navegador precisa de TIKTOK_USERNAME (o @ do perfil).")
        try:
            from playwright.async_api import Error as PlaywrightError
        except ImportError as exc:
            raise ProviderError("Playwright não instalado: rode o instalar.bat de novo.") from exc

        try:
            return await asyncio.wait_for(self._read_reposts(), timeout=self.options["timeout"] + 30)
        except asyncio.TimeoutError as exc:
            raise ProviderError("O navegador demorou demais para carregar o perfil.") from exc
        except PlaywrightError as exc:
            message = str(exc).splitlines()[0]
            if "user data directory is already in use" in str(exc).lower() or "ProcessSingleton" in str(exc):
                message = "O perfil do navegador está aberto em outra janela (feche o abrir-navegador)."
            elif "executable doesn't exist" in str(exc).lower() or "chromium distribution" in str(exc).lower():
                message = ("Navegador não encontrado. No Windows, instale/atualize o Microsoft Edge; "
                           "nos outros sistemas rode: python -m playwright install chromium")
            raise ProviderError(f"Falha no navegador: {message}") from exc

    async def _read_reposts(self) -> list[Repost]:
        from playwright.async_api import async_playwright

        opts = self.options
        timeout_ms = opts["timeout"] * 1000
        captured: list[dict[str, Any]] = []
        got_response = asyncio.Event()

        async with async_playwright() as pw:
            context = await launch_context(pw, opts, headless=opts["headless"])
            try:
                page = context.pages[0] if context.pages else await context.new_page()
                page.set_default_timeout(timeout_ms)
                if opts["block_media"]:
                    await page.route("**/*", _block_heavy_resources)

                async def on_response(response) -> None:
                    if REPOST_API_PATH in response.url and response.ok:
                        try:
                            captured.extend(find_items(await response.json()))
                        except Exception as exc:  # noqa: BLE001 - resposta inesperada: tenta o DOM
                            log.debug("Resposta de reposts ilegível: %s", exc)
                        got_response.set()

                page.on("response", on_response)
                await page.goto(f"{opts['base_url']}/@{self.settings.username}", wait_until="domcontentloaded")

                tab = await self._find_repost_tab(page, timeout_ms)
                if tab is None:
                    await self._raise_page_problem(page)
                await tab.click()

                try:
                    await asyncio.wait_for(got_response.wait(), timeout=min(20, opts["timeout"]))
                except asyncio.TimeoutError:
                    pass
                if captured:
                    return normalize_items(captured)
                if got_response.is_set():
                    return []  # a aba carregou e está vazia

                hrefs = await page.eval_on_selector_all(DOM_ITEM_LINKS, "els => els.map(e => e.href)")
                if hrefs:
                    return normalize_items([{"url": h} for h in dict.fromkeys(hrefs)])
                await self._raise_page_problem(page)
            finally:
                await context.close()
        return []  # inalcançável; mantém o verificador de tipos satisfeito

    async def _find_repost_tab(self, page, timeout_ms: int):
        deadline = asyncio.get_running_loop().time() + timeout_ms / 1000
        while asyncio.get_running_loop().time() < deadline:
            for selector in TAB_SELECTORS:
                locator = page.locator(selector).first
                if await locator.count() and await locator.is_visible():
                    return locator
            by_text = page.get_by_text(TAB_TEXT).first
            if await by_text.count() and await by_text.is_visible():
                return by_text
            if await page.locator(CAPTCHA_SELECTORS).count():
                return None
            await asyncio.sleep(0.5)
        return None

    async def _raise_page_problem(self, page) -> None:
        if await page.locator(CAPTCHA_SELECTORS).count():
            raise ProviderError(
                "O TikTok pediu verificação (captcha). Abra o abrir-navegador.bat, resolva e feche a janela."
            )
        raise ProviderError(
            f"Não encontrei a aba de reposts de @{self.settings.username}. Confira o @ no .env e se os "
            "reposts do perfil estão públicos. Se o TikTok estiver pedindo login, use o abrir-navegador.bat."
        )


async def launch_context(pw, opts: dict[str, Any], *, headless: bool):
    profile_dir: Path = opts["profile_dir"]
    profile_dir.mkdir(parents=True, exist_ok=True)
    return await pw.chromium.launch_persistent_context(
        str(profile_dir),
        channel=opts["channel"] or None,
        headless=headless,
        args=LAUNCH_ARGS,
        locale="en-US",
        viewport={"width": 1100, "height": 900},
    )


async def _block_heavy_resources(route) -> None:
    if route.request.resource_type in BLOCKED_RESOURCES:
        await route.abort()
    else:
        await route.continue_()


async def open_visible_browser(opts: dict[str, Any], username: str) -> None:
    """Abre uma janela normal com o mesmo perfil, para login/captcha. Termina quando ela é fechada."""
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        context = await launch_context(pw, opts, headless=False)
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto(f"{opts['base_url']}/@{username}" if username else opts["base_url"])
        closed = asyncio.Event()
        context.on("close", lambda _: closed.set())
        page.on("close", lambda _: closed.set())
        await closed.wait()
        try:
            await context.close()
        except Exception:  # noqa: BLE001 - já fechado pelo usuário
            pass
