"""Provedor sem API: abre o perfil num navegador local e lê a aba "Reposts".

Como funciona (a cada ciclo):
1. abre o navegador instalado (no Windows, o Microsoft Edge) como um processo
   NORMAL, com um perfil próprio, e só depois se conecta a ele pelo protocolo de
   depuração (CDP). Assim o navegador não carrega as marcas de automação que o
   TikTok detecta (navigator.webdriver, --enable-automation, "HeadlessEdg");
2. a janela fica fora da área visível da tela (BROWSER_MODE=offscreen);
3. bloqueia imagens, vídeos e fontes para ficar leve;
4. entra em tiktok.com/@perfil, clica na aba "Reposts" e captura a resposta JSON
   que o próprio site carrega (/api/repost/item_list); se ela não vier, lê os
   links de vídeo da aba;
5. fecha o navegador (não fica ocupando memória entre as verificações).

Se o TikTok pedir captcha ou login, `python -m repost_monitor abrir-navegador`
(abrir-navegador.bat) abre o mesmo perfil numa janela comum, sem automação
nenhuma; resolva, feche a janela e os cookies ficam salvos.
"""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import re
import shutil
import socket
import subprocess
from pathlib import Path
from typing import Any

import httpx

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
MODES = {"offscreen", "headless", "visible"}

COMMON_ARGS = [
    "--no-first-run",
    "--no-default-browser-check",
    "--mute-audio",
    "--disable-sync",
    # a página continua ativa mesmo com a janela fora da tela
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--disable-background-timer-throttling",
    "--window-size=1100,900",
]
MODE_ARGS = {
    "offscreen": ["--window-position=-32000,-32000"],
    "headless": ["--headless=new"],
    "visible": [],
}

BROWSER_PATHS = {
    "Windows": {
        "msedge": [r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe",
                   r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe",
                   r"%LocalAppData%\Microsoft\Edge\Application\msedge.exe"],
        "chrome": [r"%ProgramFiles%\Google\Chrome\Application\chrome.exe",
                   r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe",
                   r"%LocalAppData%\Google\Chrome\Application\chrome.exe"],
    },
    "Darwin": {
        "msedge": ["/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"],
        "chrome": ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"],
    },
    "Linux": {
        "msedge": ["microsoft-edge", "microsoft-edge-stable"],
        "chrome": ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser"],
    },
}


def default_channel() -> str:
    """Windows: usa o Edge instalado (nada para baixar). Outros: Chromium do Playwright."""
    return "msedge" if platform.system() == "Windows" else ""


def find_browser(channel: str, explicit: str = "") -> str | None:
    """Caminho do navegador instalado; None = usar o Chromium do Playwright."""
    if explicit:
        return explicit
    for candidate in BROWSER_PATHS.get(platform.system(), {}).get(channel, []):
        path = os.path.expandvars(candidate)
        if os.path.isabs(path):
            if os.path.isfile(path):
                return path
        elif shutil.which(path):
            return shutil.which(path)
    return None


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _launch_process(executable: str, profile_dir: Path, mode: str, url: str, port: int | None) -> subprocess.Popen:
    profile_dir.mkdir(parents=True, exist_ok=True)
    args = [executable, f"--user-data-dir={profile_dir}", *COMMON_ARGS, *MODE_ARGS[mode]]
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        args.append("--no-sandbox")  # Linux como root (containers) exige isso; no Windows não se aplica
    if port:
        args += [f"--remote-debugging-port={port}", "--remote-debugging-address=127.0.0.1"]
    return subprocess.Popen(args + [url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _resolve_executable(opts: dict[str, Any], pw=None) -> str:
    executable = find_browser(opts["channel"], opts.get("executable", ""))
    if executable:
        return executable
    if opts["channel"]:
        raise ProviderError(
            f"Navegador '{opts['channel']}' não encontrado. Instale o Microsoft Edge ou deixe BROWSER_CHANNEL= "
            "(vazio) para usar o Chromium do Playwright."
        )
    if pw is None:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as spw:
            return spw.chromium.executable_path
    return pw.chromium.executable_path


class LocalBrowser:
    """Abre o navegador como processo comum e conecta via CDP; fecha ao sair."""

    def __init__(self, pw, opts: dict[str, Any]):
        self.pw = pw
        self.opts = opts
        self.proc: subprocess.Popen | None = None
        self.browser = None

    async def __aenter__(self) -> "LocalBrowser":
        executable = _resolve_executable(self.opts, self.pw)
        port = _free_port()
        self.proc = _launch_process(executable, self.opts["profile_dir"], self.opts["mode"], "about:blank", port)
        endpoint = f"http://127.0.0.1:{port}"
        loop = asyncio.get_running_loop()
        deadline = loop.time() + 30
        async with httpx.AsyncClient(trust_env=False) as client:
            while True:
                if self.proc.poll() is not None:
                    raise ProviderError(
                        "O navegador do monitor fechou ao abrir. Se a janela do abrir-navegador estiver "
                        "aberta, feche-a; ela usa o mesmo perfil."
                    )
                try:
                    if (await client.get(f"{endpoint}/json/version", timeout=2)).status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                if loop.time() > deadline:
                    raise ProviderError("O navegador não respondeu ao abrir.")
                await asyncio.sleep(0.3)
        self.browser = await self.pw.chromium.connect_over_cdp(endpoint)
        return self

    async def page(self):
        context = self.browser.contexts[0] if self.browser.contexts else await self.browser.new_context()
        return context.pages[0] if context.pages else await context.new_page()

    async def __aexit__(self, *exc) -> None:
        if self.browser is not None:
            try:  # fechamento normal: grava os cookies no perfil
                session = await self.browser.new_browser_cdp_session()
                await session.send("Browser.close")
            except Exception:  # noqa: BLE001
                pass
        if self.proc is not None:
            try:
                await asyncio.to_thread(self.proc.wait, 10)
            except subprocess.TimeoutExpired:
                self.proc.kill()


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
            return await asyncio.wait_for(self._read_reposts(), timeout=self.options["timeout"] + 45)
        except asyncio.TimeoutError as exc:
            raise ProviderError("O navegador demorou demais para carregar o perfil.") from exc
        except PlaywrightError as exc:
            detail = str(exc).splitlines()[0]
            if "ERR_HTTP_RESPONSE_CODE_FAILURE" in detail or "ERR_BLOCKED" in detail:
                raise ProviderError(
                    "O TikTok recusou abrir o perfil. Abra o abrir-navegador.bat, veja se o perfil carrega "
                    "(resolva captcha/login se aparecer) e feche a janela."
                ) from exc
            raise ProviderError(f"Falha no navegador: {detail}") from exc

    async def _read_reposts(self) -> list[Repost]:
        from playwright.async_api import async_playwright

        opts = self.options
        timeout_ms = opts["timeout"] * 1000
        captured: list[dict[str, Any]] = []
        got_response = asyncio.Event()

        async with async_playwright() as pw:
            async with LocalBrowser(pw, opts) as local:
                page = await local.page()
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
        return []  # inalcançável; mantém o verificador de tipos satisfeito

    async def _find_repost_tab(self, page, timeout_ms: int):
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout_ms / 1000
        while loop.time() < deadline:
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
                "O TikTok pediu verificação (captcha). Feche o iniciar.bat, abra o abrir-navegador.bat, "
                "resolva, feche a janela e inicie de novo."
            )
        raise ProviderError(
            f"Não encontrei a aba de reposts de @{self.settings.username}. Confira o @ no .env e se os "
            "reposts do perfil estão públicos. Se o TikTok estiver pedindo login, use o abrir-navegador.bat."
        )


async def _block_heavy_resources(route) -> None:
    if route.request.resource_type in BLOCKED_RESOURCES:
        await route.abort()
    else:
        await route.continue_()


def open_visible_browser(opts: dict[str, Any], username: str) -> int:
    """Abre o navegador comum (sem automação) com o perfil do monitor e espera fechar."""
    executable = _resolve_executable(opts)
    url = f"{opts['base_url']}/@{username}" if username else opts["base_url"]
    proc = _launch_process(executable, opts["profile_dir"], "visible", url, port=None)
    return proc.wait()
