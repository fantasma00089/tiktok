import asyncio
import json

import httpx
from fastapi.testclient import TestClient

from repost_monitor.monitor import Monitor
from repost_monitor.notifiers.desktop import build_command, windows_toast_xml
from repost_monitor.providers.mock import add_fake_repost
from repost_monitor.publishers import collect_site_files, sign
from repost_monitor.server import create_app


def test_full_cycle_detects_and_logs(settings):
    mock_file = settings.provider_options["file"]
    add_fake_repost(mock_file)

    async def go():
        monitor = Monitor(settings, notify=False)
        first = await monitor.run_cycle()          # baseline
        add_fake_repost(mock_file, author="outro")
        second = await monitor.run_cycle()
        status = monitor.status()
        await monitor.aclose()
        return first, second, status

    first, second, status = asyncio.run(go())
    assert first.ok and first.new_reposts == []
    assert [r.author for r in second.new_reposts] == ["outro"]
    assert status["repostou"] is True
    assert status["status"] == "repost_detectado"
    assert status["ultimo_repost"]["author"] == "outro"
    lines = settings.detections_log.read_text().splitlines()
    record = json.loads(lines[0])
    assert record["monitorado"] == "@alvo_teste" and record["url"].endswith(record["item_id"])
    # o estado persiste entre execuções
    assert Monitor(settings, notify=False).state.last_item_id == second.new_reposts[0].item_id


def test_provider_failure_is_recorded_and_backs_off(settings):
    settings.provider_options["file"].write_text("{inválido")

    async def go():
        monitor = Monitor(settings, notify=False)
        result = await monitor.run_cycle()
        delay = monitor.next_delay(result)
        state = monitor.state
        await monitor.aclose()
        return result, delay, state

    result, delay, state = asyncio.run(go())
    assert not result.ok
    assert state.consecutive_failures == 1 and state.last_error
    assert delay >= settings.poll_interval - settings.poll_jitter


def _app(settings):
    return create_app(settings, Monitor(settings, notify=False), start_monitor=False)


def test_status_is_public_but_api_is_local_only(settings):
    with TestClient(_app(settings)) as client:
        assert client.get("/status").json()["alvo"] == "@alvo_teste"
        assert client.get("/api/state").status_code == 200
        # simulando acesso vindo do tunnel
        tunneled = {"X-Forwarded-For": "203.0.113.9"}
        assert client.get("/status", headers=tunneled).status_code == 200
        assert client.get("/api/state", headers=tunneled).status_code == 403
        assert client.post("/api/check-now", headers=tunneled).status_code == 403
        assert client.get("/", headers=tunneled).status_code == 403


def test_admin_token_allows_remote_access(settings):
    settings.admin_token = "segredo"
    with TestClient(_app(settings)) as client:
        headers = {"X-Forwarded-For": "1.2.3.4", "Authorization": "Bearer segredo"}
        assert client.get("/api/state", headers=headers).status_code == 200
        headers["Authorization"] = "Bearer errado"
        assert client.get("/api/state", headers=headers).status_code == 403


def test_cors_preflight_for_ngrok_header(settings):
    with TestClient(_app(settings)) as client:
        res = client.options("/status", headers={
            "Origin": "https://meu-site.netlify.app",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "ngrok-skip-browser-warning",
        })
        assert res.status_code == 200
        assert res.headers["access-control-allow-origin"] in {"*", "https://meu-site.netlify.app"}


def test_check_now_endpoint(settings):
    add_fake_repost(settings.provider_options["file"])
    with TestClient(_app(settings)) as client:
        assert client.post("/api/check-now").json()["ok"] is True
        add_fake_repost(settings.provider_options["file"])
        data = client.post("/api/check-now").json()
        assert len(data["novos_reposts"]) == 1
        assert data["status"]["repostou"] is True
        assert client.get("/").status_code == 200


def test_windows_toast_xml_escapes_content():
    import xml.etree.ElementTree as ET

    url = 'https://x/?a=1&b="2"'
    root = ET.fromstring(windows_toast_xml("Título <b>", "a & b", url))
    assert [t.text for t in root.iter("text")] == ["Título <b>", "a & b"]
    assert root.get("launch") == url
    assert root.find("actions/action").get("arguments") == url


def test_build_command_per_platform():
    assert build_command("t", "b", None, system="Darwin")[0][0] == "osascript"
    argv, env = build_command("t", "b", "https://v", system="Windows")
    assert "RM_TOAST_XML" in env and argv[-2] == "-Command"


def test_netlify_publisher_uploads_only_required_files(settings, tmp_path):
    from repost_monitor.publishers import NetlifyPublisher

    site = settings.netlify_site_dir
    site.mkdir()
    (site / "index.html").write_text("<h1>oi</h1>")
    (site / "status.json").write_text("{}")  # substituído pelo gerado
    settings.netlify_auth_token, settings.netlify_site_id = "tok", "site123"
    uploads = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            files = json.loads(request.content)["files"]
            assert set(files) == {"/index.html", "/status.json"}
            return httpx.Response(200, json={"id": "dep1", "required": [files["/status.json"]]})
        uploads.append((request.url.path, json.loads(request.content)))
        return httpx.Response(200, json={})

    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            publisher = NetlifyPublisher(settings, client, lambda: {"repostou": True})
            return await publisher.publish({"repostou": True})

    assert asyncio.run(go()) == "dep1"
    assert uploads == [("/api/v1/deploys/dep1/files/status.json", {"repostou": True})]
    assert b"repostou" in collect_site_files(site, {"repostou": True})["/status.json"]


def test_webhook_signature():
    assert sign("k", b"{}").startswith("sha256=")


def test_switching_provider_resets_state(settings):
    from repost_monitor.state import StateStore

    add_fake_repost(settings.provider_options["file"])

    async def go():
        monitor = Monitor(settings, notify=False)
        await monitor.run_cycle()
        await monitor.aclose()

    asyncio.run(go())
    store = StateStore(settings.state_file)
    assert store.load(settings.state_key).initialized
    settings.provider = "apify"
    assert not store.load(settings.state_key).initialized  # recomeça com leitura de base


def test_status_flags_simulation(settings):
    with TestClient(_app(settings)) as client:
        assert client.get("/status").json()["modo_simulacao"] is True
    settings.provider = "http"
    settings.provider_options = {"url": "https://x"}
    with TestClient(_app(settings)) as client:
        assert client.get("/status").json()["modo_simulacao"] is False
