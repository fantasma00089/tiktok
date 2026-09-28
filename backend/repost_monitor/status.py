"""Monta o payload público de status (GET /status e status.json na Netlify)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from .config import Settings
from .models import iso, parse_iso, utcnow
from .state import MonitorState

RECENT_LIMIT = 10


def minutes_ago_text(minutes: int) -> str:
    if minutes < 1:
        return "agora mesmo"
    if minutes < 60:
        return f"há {minutes} minuto{'s' if minutes != 1 else ''}"
    hours = minutes // 60
    if hours < 48:
        return f"há {hours} hora{'s' if hours != 1 else ''}"
    return f"há {hours // 24} dias"


def build_status(settings: Settings, state: MonitorState, *, running: bool = True) -> dict[str, Any]:
    now = utcnow()
    latest = state.latest_detection
    detected_at = parse_iso(latest.detected_at) if latest else None
    minutes = int((now - detected_at).total_seconds() // 60) if detected_at else None
    repostou = bool(detected_at and now - detected_at <= timedelta(minutes=settings.alert_window_minutes))

    if repostou:
        code, text = "repost_detectado", f"Repost detectado {minutes_ago_text(minutes)}"
    elif not state.initialized and state.last_error:
        code, text = "erro", "Erro ao consultar a API do TikTok"
    elif not state.initialized:
        code, text = "iniciando", "Iniciando monitoramento"
    else:
        code, text = "aguardando", "Aguardando repost"

    return {
        "repostou": repostou,
        "username": settings.username or None,
        "user_id": settings.user_id or None,
        "alvo": settings.target_label,
        "status": code,
        "mensagem": text,
        "minutos_desde_repost": minutes,
        "ultimo_repost": latest.to_dict() if latest else None,
        "reposts_recentes": state.detections[:RECENT_LIMIT],
        "ultima_verificacao": state.last_check_at,
        "ultima_verificacao_ok": state.last_success_at,
        "proxima_verificacao": state.next_check_at,
        "erro": state.last_error,
        "falhas_consecutivas": state.consecutive_failures,
        "intervalo_polling_segundos": settings.poll_interval,
        "janela_alerta_minutos": settings.alert_window_minutes,
        "monitor_online": running,
        "gerado_em": iso(now),
    }
