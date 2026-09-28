"""Webhook genérico: envia o status em JSON para uma URL quando há repost novo.

Útil para integrar com qualquer serviço (Zapier/Make/n8n, Discord, um
Netlify Function próprio etc.). Se WEBHOOK_SECRET estiver definido, o corpo é
assinado com HMAC-SHA256 no cabeçalho `X-Repost-Signature`.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any

import httpx

from ..config import Settings
from ..http import request_with_retry

log = logging.getLogger(__name__)


def sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


async def send_webhook(settings: Settings, client: httpx.AsyncClient, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json", "User-Agent": "tiktok-repost-monitor"}
    if settings.webhook_secret:
        headers["X-Repost-Signature"] = sign(settings.webhook_secret, body)
    try:
        await request_with_retry(
            client, "POST", settings.webhook_url, content=body, headers=headers,
            attempts=settings.retry_attempts, base_delay=settings.retry_base_delay, timeout=settings.http_timeout,
        )
        log.info("Webhook enviado para %s", settings.webhook_url.split("?", 1)[0])
    except Exception as exc:  # noqa: BLE001
        log.error("Falha ao enviar webhook: %s", exc)
