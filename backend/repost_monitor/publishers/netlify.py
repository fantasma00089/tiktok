"""Webhook reverso para a Netlify: publica o site com um `status.json` atualizado.

Usa a API de deploy por "file digest" da Netlify: enviamos o SHA1 de cada
arquivo do site e só fazemos upload dos que mudaram (na prática, apenas o
status.json). Não há backend na Netlify: o site continua 100% estático e lê
`./status.json` via fetch().

Rate-limit: a Netlify limita a quantidade de deploys por minuto/dia, por isso
só publicamos quando há um repost novo (e, opcionalmente, um heartbeat
periódico) e respeitamos NETLIFY_MIN_INTERVAL_SECONDS entre deploys.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

import httpx

from ..config import Settings
from ..http import request_with_retry

log = logging.getLogger(__name__)

API = "https://api.netlify.com/api/v1"
STATUS_PATH = "/status.json"
EXCLUDED_NAMES = {".DS_Store", "Thumbs.db", "netlify.toml"}


def collect_site_files(site_dir: Path, status: dict[str, Any]) -> dict[str, bytes]:
    """Arquivos do deploy: tudo em `site_dir` + status.json gerado."""
    files: dict[str, bytes] = {}
    for path in sorted(site_dir.rglob("*")):
        if not path.is_file() or path.name in EXCLUDED_NAMES or any(p.startswith(".") for p in path.relative_to(site_dir).parts):
            continue
        files["/" + path.relative_to(site_dir).as_posix()] = path.read_bytes()
    files[STATUS_PATH] = json.dumps(status, ensure_ascii=False, indent=2).encode("utf-8")
    return files


class NetlifyPublisher:
    def __init__(self, settings: Settings, client: httpx.AsyncClient, status_fn: Callable[[], dict[str, Any]]):
        self.settings = settings
        self.client = client
        self.status_fn = status_fn
        self._dirty = asyncio.Event()
        self._last_publish = 0.0
        self.last_result: str | None = None

    @property
    def last_publish_monotonic(self) -> float:
        return self._last_publish

    def request_publish(self) -> None:
        self._dirty.set()

    async def run(self) -> None:
        """Loop que agrupa pedidos de publicação respeitando o intervalo mínimo."""
        while True:
            await self._dirty.wait()
            wait = self.settings.netlify_min_interval - (time.monotonic() - self._last_publish)
            if wait > 0:
                await asyncio.sleep(wait)
            self._dirty.clear()
            try:
                await self.publish(self.status_fn())
            except Exception as exc:  # noqa: BLE001 - nunca derrubar o monitor por causa da Netlify
                self.last_result = f"erro: {exc}"
                log.error("Falha ao publicar na Netlify: %s", exc)
                await asyncio.sleep(30)
                self._dirty.set()  # tenta de novo

    async def publish(self, status: dict[str, Any]) -> str:
        headers = {"Authorization": f"Bearer {self.settings.netlify_auth_token}"}
        files = collect_site_files(self.settings.netlify_site_dir, status)
        digests = {path: hashlib.sha1(content).hexdigest() for path, content in files.items()}

        response = await self._request(
            "POST", f"{API}/sites/{self.settings.netlify_site_id}/deploys",
            headers=headers, json={"files": digests, "draft": False},
        )
        deploy = response.json()
        required = set(deploy.get("required") or [])
        for path, content in files.items():
            if digests[path] in required:
                await self._request(
                    "PUT", f"{API}/deploys/{deploy['id']}/files/{quote(path.lstrip('/'))}",
                    headers={**headers, "Content-Type": "application/octet-stream"}, content=content,
                )
                required.discard(digests[path])
        self._last_publish = time.monotonic()
        self.last_result = f"ok: deploy {deploy['id']}"
        log.info("Site publicado na Netlify (deploy %s, %d arquivo(s) enviados).", deploy["id"], len(set(deploy.get("required") or [])))
        return deploy["id"]

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        return await request_with_retry(
            self.client, method, url,
            attempts=self.settings.retry_attempts, base_delay=self.settings.retry_base_delay,
            timeout=max(60, self.settings.http_timeout), **kwargs,
        )
