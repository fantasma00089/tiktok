"""Linha de comando. Pensada para ser acionada pelo agente (OpenClaw/OpenHands):
cada comando executa uma ação e devolve JSON + código de saída previsível.

Códigos de saída:
  0  sucesso, nenhum repost novo
  10 sucesso, repost(s) novo(s) detectado(s)
  1  erro (API, configuração, rede)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any

import httpx

from .config import Settings
from .logging_setup import setup_logging

EXIT_OK, EXIT_ERROR, EXIT_NEW_REPOST = 0, 1, 10


def _print(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _server_url(settings: Settings, path: str) -> str:
    host = "127.0.0.1" if settings.host in {"0.0.0.0", "::", ""} else settings.host
    return f"http://{host}:{settings.port}{path}"


def _call_server(settings: Settings, method: str, path: str) -> dict | None:
    """Se o servidor (`run`) estiver ativo, delega a ação a ele para não haver dois
    processos escrevendo o mesmo estado. Retorna None se ele não estiver no ar."""
    headers = {"X-Admin-Token": settings.admin_token} if settings.admin_token else {}
    try:
        response = httpx.request(method, _server_url(settings, path), headers=headers, timeout=120)
    except httpx.TransportError:
        return None
    if response.status_code == 404 and path == "/api/open-latest":
        return {"ok": False, "erro": "Nenhum repost detectado ainda."}
    response.raise_for_status()
    return response.json()


def cmd_run(settings: Settings, args: argparse.Namespace) -> int:
    import uvicorn

    from .server import create_app

    problems = settings.validate()
    if problems:
        _print({"ok": False, "erros": problems})
        return EXIT_ERROR
    app = create_app(settings)
    print(f"Painel local: http://127.0.0.1:{settings.port}/   |   Endpoint público: /status")
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="warning")
    return EXIT_OK


def cmd_check(settings: Settings, args: argparse.Namespace) -> int:
    data = None if args.standalone else _call_server(settings, "POST", "/api/check-now")
    if data is None:
        from .monitor import Monitor

        async def once() -> dict:
            monitor = Monitor(settings, notify=not args.no_notify)
            try:
                result = await monitor.run_cycle()
                if result.new_reposts and monitor.netlify:
                    await monitor.netlify.publish(monitor.status())
                return {**result.to_dict(), "status": monitor.status()}
            finally:
                await monitor.aclose()

        data = asyncio.run(once())
    _print(data)
    if not data.get("ok"):
        return EXIT_ERROR
    return EXIT_NEW_REPOST if data.get("novos_reposts") else EXIT_OK


def cmd_status(settings: Settings, args: argparse.Namespace) -> int:
    data = _call_server(settings, "GET", "/api/state")
    if data is None:
        from .state import StateStore
        from .status import build_status

        data = build_status(settings, StateStore(settings.state_file).load(settings.target_label), running=False)
    _print(data)
    return EXIT_OK


def cmd_open_latest(settings: Settings, args: argparse.Namespace) -> int:
    data = _call_server(settings, "POST", "/api/open-latest")
    if data is None:
        from .notifiers import open_in_browser
        from .state import StateStore

        latest = StateStore(settings.state_file).load(settings.target_label).latest_detection
        data = {"ok": False, "erro": "Nenhum repost detectado ainda."}
        if latest:
            data = {"ok": open_in_browser(latest.url), "url": latest.url}
    _print(data)
    return EXIT_OK if data.get("ok") else EXIT_ERROR


def cmd_test_notification(settings: Settings, args: argparse.Namespace) -> int:
    from .notifiers import send_desktop_notification

    ok = send_desktop_notification("Teste do TikTok Repost Monitor",
                                   f"As notificações de {settings.target_label} estão funcionando.")
    _print({"ok": ok})
    return EXIT_OK if ok else EXIT_ERROR


def cmd_simulate(settings: Settings, args: argparse.Namespace) -> int:
    if settings.provider != "mock":
        _print({"ok": False, "erro": "simulate só funciona com PROVIDER=mock."})
        return EXIT_ERROR
    from .providers.mock import add_fake_repost

    item = add_fake_repost(settings.provider_options["file"])
    _print({"ok": True, "repost_simulado": item,
            "dica": "Rode `python -m repost_monitor check` ou aguarde o próximo ciclo."})
    return EXIT_OK


def cmd_publish(settings: Settings, args: argparse.Namespace) -> int:
    from .monitor import Monitor

    async def publish() -> dict:
        monitor = Monitor(settings, notify=False)
        try:
            if not monitor.netlify:
                return {"ok": False, "erro": "Configure NETLIFY_AUTH_TOKEN e NETLIFY_SITE_ID."}
            deploy_id = await monitor.netlify.publish(monitor.status())
            return {"ok": True, "deploy_id": deploy_id}
        finally:
            await monitor.aclose()

    data = asyncio.run(publish())
    _print(data)
    return EXIT_OK if data["ok"] else EXIT_ERROR


def cmd_doctor(settings: Settings, args: argparse.Namespace) -> int:
    from .notifiers.desktop import build_command

    problems = settings.validate()
    _print({
        "ok": not problems,
        "problemas": problems,
        "alvo": settings.target_label,
        "provedor": settings.provider,
        "intervalo_polling_segundos": settings.poll_interval,
        "servidor": f"{settings.host}:{settings.port}",
        "admin_token_definido": bool(settings.admin_token),
        "notificacao_nativa_disponivel": build_command("t", "b", None) is not None,
        "netlify_configurada": bool(settings.netlify_auth_token and settings.netlify_site_id),
        "webhook_configurado": bool(settings.webhook_url),
        "arquivo_estado": str(settings.state_file),
        "log_deteccoes": str(settings.detections_log),
        "servidor_no_ar": _call_server(settings, "GET", "/health") is not None,
    })
    return EXIT_OK if not problems else EXIT_ERROR


COMMANDS = {
    "run": (cmd_run, "Inicia o monitor contínuo + API /status + painel local"),
    "check": (cmd_check, "Executa um único ciclo de polling (saída 10 = repost novo)"),
    "status": (cmd_status, "Mostra o status atual em JSON"),
    "open-latest": (cmd_open_latest, "Abre o último vídeo repostado no navegador"),
    "test-notification": (cmd_test_notification, "Dispara uma notificação nativa de teste"),
    "simulate": (cmd_simulate, "Adiciona um repost falso (PROVIDER=mock) para testes"),
    "publish": (cmd_publish, "Publica o site + status.json na Netlify agora"),
    "doctor": (cmd_doctor, "Valida a configuração"),
}


def _fix_std_streams() -> None:
    """Windows: pythonw.exe não tem stdout/stderr (o uvicorn quebraria ao chamar
    isatty()), e com saída redirecionada o padrão é cp1252, que não codifica emoji
    das legendas. Garantimos streams válidos e em UTF-8."""
    import os

    for name in ("stdout", "stderr"):
        stream = getattr(sys, name)
        if stream is None:
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))
        elif hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def main(argv: list[str] | None = None) -> int:
    _fix_std_streams()
    parser = argparse.ArgumentParser(prog="repost_monitor", description="Monitor de reposts do TikTok")
    parser.add_argument("--env-file", help="Caminho do arquivo .env (padrão: backend/.env)")
    sub = parser.add_subparsers(dest="command", required=True)
    for name, (_, help_text) in COMMANDS.items():
        p = sub.add_parser(name, help=help_text)
        if name == "check":
            p.add_argument("--standalone", action="store_true", help="Não delegar ao servidor em execução")
            p.add_argument("--no-notify", action="store_true", help="Não exibir notificação nativa")
    args = parser.parse_args(argv)

    from pathlib import Path

    try:
        settings = Settings.load(Path(args.env_file) if args.env_file else None)
    except ValueError as exc:
        _print({"ok": False, "erro": str(exc)})
        return EXIT_ERROR
    # Logs vão para stderr/arquivo; stdout fica reservado ao JSON lido pelo agente.
    setup_logging(settings.log_dir, settings.log_level)
    try:
        return COMMANDS[args.command][0](settings, args)
    except KeyboardInterrupt:
        return EXIT_OK
    except httpx.HTTPError as exc:
        _print({"ok": False, "erro": str(exc)})
        return EXIT_ERROR
