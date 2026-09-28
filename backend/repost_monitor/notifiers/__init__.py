"""Notificações locais disparadas quando um repost é detectado."""

from __future__ import annotations

import asyncio
import logging
import webbrowser

from ..config import Settings
from ..models import Repost
from .desktop import send_desktop_notification

log = logging.getLogger(__name__)


def repost_message(settings: Settings, reposts: list[Repost]) -> tuple[str, str]:
    latest = reposts[0]
    title = f"{settings.target_label} repostou um vídeo!"
    if len(reposts) > 1:
        title = f"{settings.target_label} repostou {len(reposts)} vídeos!"
    author = f"de @{latest.author}" if latest.author else ""
    desc = (latest.description or "").strip()
    body = " ".join(p for p in (f"Vídeo {author}".strip(), f"— {desc[:120]}" if desc else "") if p)
    return title, body or latest.url


async def notify_local(settings: Settings, reposts: list[Repost]) -> None:
    """Notificação nativa do SO + (opcional) abrir o vídeo no navegador."""
    if not reposts:
        return
    title, body = repost_message(settings, reposts)
    latest = reposts[0]
    if settings.desktop_notifications:
        await asyncio.to_thread(send_desktop_notification, title, body, latest.url)
    if settings.open_browser_on_repost:
        await asyncio.to_thread(open_in_browser, latest.url)


def open_in_browser(url: str) -> bool:
    try:
        return webbrowser.open(url, new=2)
    except webbrowser.Error as exc:
        log.warning("Não foi possível abrir o navegador: %s", exc)
        return False


__all__ = ["notify_local", "open_in_browser", "repost_message", "send_desktop_notification"]
