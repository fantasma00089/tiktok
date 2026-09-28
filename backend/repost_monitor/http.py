"""Cliente HTTP com retry exponencial para falhas de rede, 429 e 5xx."""

from __future__ import annotations

import asyncio
import logging
import random
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from .models import utcnow

log = logging.getLogger(__name__)

RETRYABLE_STATUS = {408, 425, 429, 500, 502, 503, 504}


class ProviderError(Exception):
    """Falha ao consultar a API de reposts."""


class RateLimitError(ProviderError):
    """A API sinalizou rate-limit (HTTP 429). `retry_after` em segundos, se informado."""

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


def parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        return max(0.0, (parsedate_to_datetime(value) - utcnow()).total_seconds())
    except (TypeError, ValueError):
        return None


async def request_with_retry(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    attempts: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 60.0,
    **kwargs: Any,
) -> httpx.Response:
    """Executa a requisição com até `attempts` tentativas.

    Retorna a resposta de sucesso (2xx) ou levanta ProviderError/RateLimitError.
    Erros 4xx que não sejam transitórios (ex.: 401, 404) não são repetidos.
    """
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        retry_after: float | None = None
        try:
            response = await client.request(method, url, **kwargs)
        except httpx.TransportError as exc:
            last_error = ProviderError(f"Erro de rede em {method} {_safe(url)}: {exc!r}")
        else:
            if response.is_success:
                return response
            retry_after = parse_retry_after(response.headers.get("Retry-After"))
            detail = f"HTTP {response.status_code} em {method} {_safe(url)}: {response.text[:300]}"
            if response.status_code == 429:
                last_error = RateLimitError(detail, retry_after)
            elif response.status_code in RETRYABLE_STATUS:
                last_error = ProviderError(detail)
            else:
                raise ProviderError(detail)

        if attempt == attempts:
            break
        delay = retry_after if retry_after is not None else base_delay * 2 ** (attempt - 1)
        delay = min(max_delay, delay) + random.uniform(0, 0.5)
        log.warning("Tentativa %d/%d falhou (%s). Nova tentativa em %.1fs.", attempt, attempts, last_error, delay)
        await asyncio.sleep(delay)

    assert last_error is not None
    raise last_error


def _safe(url: str) -> str:
    """Remove a query string dos logs (pode conter tokens)."""
    return url.split("?", 1)[0]
