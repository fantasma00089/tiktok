"""Testa o provedor de navegador contra uma página falsa que imita o perfil do TikTok."""

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest

from repost_monitor.http import ProviderError
from repost_monitor.providers.browser import BrowserProvider

pytest.importorskip("playwright")

ITEMS = {
    "itemList": [
        {"id": "7400000000000000002", "desc": "segundo repost", "author": {"uniqueId": "criador_b"},
         "video": {"cover": "https://p16/cover2.jpg"}, "createTime": 1759000000},
        {"id": "7400000000000000001", "desc": "primeiro repost", "author": {"uniqueId": "criador_a"}},
    ],
    "hasMore": False,
    "statusCode": 0,
}

PROFILE = """<!doctype html><html><body>
<h1>@{user}</h1>
<div role="tablist">
  <p data-e2e="videos-tab">Videos</p>
  {tab}
  <p data-e2e="liked-tab">Liked</p>
</div>
<div id="grid"></div>
<img src="/imagem-pesada.jpg">
<script>
const tab = document.querySelector('[data-e2e="repost-tab"]');
if (tab) tab.addEventListener('click', async () => {{
  const grid = document.getElementById('grid');
  {on_click}
}});
</script>
</body></html>"""

FETCH_API = """
  const data = await (await fetch('/api/repost/item_list/?count=30&secUid=x')).json();
  grid.innerHTML = '<div data-e2e="user-repost-item-list">' + data.itemList.map(
    i => `<div data-e2e="user-repost-item"><a href="/@${i.author.uniqueId}/video/${i.id}">v</a></div>`).join('') + '</div>';
"""
DOM_ONLY = """
  grid.innerHTML = '<div data-e2e="user-repost-item"><a href="/@dom_autor/video/7411111111111111111">v</a></div>';
"""


class FakeTikTok(BaseHTTPRequestHandler):
    requested_paths: list[str] = []

    def log_message(self, *args):
        pass

    def _send(self, body: str, ctype: str = "text/html", status: int = 200):
        data = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        FakeTikTok.requested_paths.append(self.path)
        tab = '<p data-e2e="repost-tab">Reposts</p>'
        if self.path.startswith("/api/repost/item_list"):
            items = {"itemList": [], "statusCode": 0} if "vazio" in self.headers.get("Referer", "") else ITEMS
            return self._send(json.dumps(items), "application/json")
        if self.path == "/@alvo_teste" or self.path == "/@vazio":
            return self._send(PROFILE.format(user=self.path[2:], tab=tab, on_click=FETCH_API))
        if self.path == "/@domonly":
            return self._send(PROFILE.format(user="domonly", tab=tab, on_click=DOM_ONLY))
        if self.path == "/@semaba":
            return self._send(PROFILE.format(user="semaba", tab="", on_click=""))
        if self.path == "/@captcha":
            return self._send('<div id="captcha-verify-container-main-page">Verify</div>')
        return self._send("nada", status=404)


@pytest.fixture(scope="module")
def fake_tiktok():
    server = ThreadingHTTPServer(("127.0.0.1", 0), FakeTikTok)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def _fetch(settings, base_url, username, tmp_path, timeout=10):
    settings.username = username
    settings.provider = "browser"
    settings.provider_options = {
        "channel": "", "headless": True, "block_media": True, "timeout": timeout,
        "profile_dir": tmp_path / "perfil", "base_url": base_url,
    }

    async def go():
        async with httpx.AsyncClient() as client:
            return await BrowserProvider(settings, client).fetch_reposts()

    return asyncio.run(go())


def _browser_available():
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            pw.chromium.launch().close()
        return True
    except Exception:  # noqa: BLE001
        return False


pytestmark = pytest.mark.skipif(not _browser_available(), reason="Chromium do Playwright indisponível")


def test_reads_reposts_from_tiktok_json(settings, fake_tiktok, tmp_path):
    FakeTikTok.requested_paths.clear()
    reposts = _fetch(settings, fake_tiktok, "alvo_teste", tmp_path)
    assert [r.item_id for r in reposts] == ["7400000000000000002", "7400000000000000001"]
    assert reposts[0].author == "criador_b"
    assert reposts[0].url == "https://www.tiktok.com/@criador_b/video/7400000000000000002"
    assert reposts[0].cover_url == "https://p16/cover2.jpg"
    assert "/imagem-pesada.jpg" not in FakeTikTok.requested_paths  # imagens bloqueadas


def test_empty_repost_tab_returns_empty_list(settings, fake_tiktok, tmp_path):
    assert _fetch(settings, fake_tiktok, "vazio", tmp_path) == []


def test_falls_back_to_links_on_page(settings, fake_tiktok, tmp_path):
    reposts = _fetch(settings, fake_tiktok, "domonly", tmp_path)
    assert [(r.item_id, r.author) for r in reposts] == [("7411111111111111111", "dom_autor")]


def test_captcha_is_reported(settings, fake_tiktok, tmp_path):
    with pytest.raises(ProviderError, match="captcha"):
        _fetch(settings, fake_tiktok, "captcha", tmp_path, timeout=5)


def test_missing_tab_is_reported(settings, fake_tiktok, tmp_path):
    with pytest.raises(ProviderError, match="aba de reposts"):
        _fetch(settings, fake_tiktok, "semaba", tmp_path, timeout=3)
