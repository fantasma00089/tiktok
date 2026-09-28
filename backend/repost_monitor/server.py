"""API local (FastAPI): endpoint público /status + painel local com atualização em tempo real.

Segurança: somente GET /status, /status.json e /health são públicos (são eles
que o site na Netlify consulta através do tunnel). O painel e as rotas /api/*
só respondem a acessos diretos da própria máquina (loopback, sem cabeçalhos de
proxy/tunnel) ou a quem enviar o ADMIN_TOKEN.
"""

from __future__ import annotations

import asyncio
import contextlib
import hmac
import ipaddress
import json
import logging
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from .config import Settings
from .monitor import Monitor
from .notifiers import open_in_browser, send_desktop_notification

log = logging.getLogger(__name__)

DASHBOARD_DIR = Path(__file__).parent / "dashboard"
PUBLIC_PATHS = {"/status", "/status.json", "/health"}
PROXY_HEADERS = ("x-forwarded-for", "x-forwarded-host", "x-real-ip", "cf-connecting-ip", "forwarded", "ngrok-trace-id")
SSE_KEEPALIVE_SECONDS = 15


def is_local_request(request: Request) -> bool:
    if any(h in request.headers for h in PROXY_HEADERS):
        return False  # veio pelo tunnel (ngrok/cloudflared adicionam esses cabeçalhos)
    host = request.client.host if request.client else ""
    if host in {"localhost", "testclient"}:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def has_admin_token(request: Request, token: str) -> bool:
    if not token:
        return False
    supplied = request.headers.get("x-admin-token") or ""
    auth = request.headers.get("authorization") or ""
    if auth.lower().startswith("bearer "):
        supplied = auth[7:].strip()
    return hmac.compare_digest(supplied, token)


def create_app(settings: Settings, monitor: Monitor | None = None, *, start_monitor: bool = True) -> FastAPI:
    monitor = monitor or Monitor(settings)

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        task = asyncio.create_task(monitor.run_forever()) if start_monitor else None
        try:
            yield
        finally:
            if task:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            await monitor.aclose()

    app = FastAPI(title="TikTok Repost Monitor", version="1.0.0", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.state.monitor = monitor

    @app.middleware("http")
    async def restrict_private_routes(request: Request, call_next):
        if request.url.path not in PUBLIC_PATHS and request.method != "OPTIONS":
            if not (is_local_request(request) or has_admin_token(request, settings.admin_token)):
                return JSONResponse({"detail": "Acesso restrito ao PC do servidor."}, status_code=403)
        return await call_next(request)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET"],
        allow_headers=["*"],  # inclui ngrok-skip-browser-warning
        max_age=600,
    )

    def public_status() -> JSONResponse:
        return JSONResponse(monitor.status(), headers={"Cache-Control": "no-store"})

    @app.get("/status")
    async def status() -> JSONResponse:
        return public_status()

    @app.get("/status.json")
    async def status_json() -> JSONResponse:
        return public_status()

    @app.get("/health")
    async def health() -> dict:
        return {"ok": True, "monitor_online": monitor.running}

    @app.get("/api/state")
    async def api_state() -> dict:
        data = monitor.status()
        data["provedor"] = monitor.provider.name
        data["total_verificacoes"] = monitor.state.total_checks
        data["netlify"] = monitor.netlify.last_result if monitor.netlify else None
        data["webhook_configurado"] = bool(settings.webhook_url)
        data["notificacoes_desktop"] = settings.desktop_notifications
        return data

    @app.get("/api/detections")
    async def api_detections() -> dict:
        return {"alvo": settings.target_label, "deteccoes": monitor.state.detections}

    @app.post("/api/check-now")
    async def api_check_now() -> dict:
        result = await monitor.run_cycle()
        return {**result.to_dict(), "status": monitor.status()}

    @app.post("/api/test-notification")
    async def api_test_notification() -> dict:
        ok = await asyncio.to_thread(
            send_desktop_notification, "Teste do TikTok Repost Monitor",
            f"As notificações de {settings.target_label} estão funcionando.", None,
        )
        return {"ok": ok}

    @app.post("/api/open-latest")
    async def api_open_latest() -> dict:
        latest = monitor.state.latest_detection
        if not latest:
            raise HTTPException(404, "Nenhum repost detectado ainda.")
        ok = await asyncio.to_thread(open_in_browser, latest.url)
        return {"ok": ok, "url": latest.url}

    @app.get("/api/events")
    async def api_events(request: Request) -> StreamingResponse:
        queue = monitor.bus.subscribe()

        async def stream() -> AsyncIterator[str]:
            try:
                yield f"event: status\ndata: {json.dumps(monitor.status(), ensure_ascii=False)}\n\n"
                while not await request.is_disconnected():
                    try:
                        event, data = await asyncio.wait_for(queue.get(), timeout=SSE_KEEPALIVE_SECONDS)
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"
                        continue
                    yield f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
            finally:
                monitor.bus.unsubscribe(queue)

        return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})

    @app.get("/")
    async def dashboard() -> FileResponse:
        return FileResponse(DASHBOARD_DIR / "index.html")

    app.mount("/dashboard", StaticFiles(directory=DASHBOARD_DIR), name="dashboard")
    return app
