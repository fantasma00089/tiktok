"""Provedores de dados de reposts do TikTok."""

from __future__ import annotations

import httpx

from ..config import Settings
from .apify import ApifyProvider
from .base import RepostProvider
from .browser import BrowserProvider
from .http_json import HttpJsonProvider
from .mock import MockProvider
from .tiktok_research import TikTokResearchProvider

PROVIDERS: dict[str, type[RepostProvider]] = {
    "browser": BrowserProvider,
    "mock": MockProvider,
    "http": HttpJsonProvider,
    "apify": ApifyProvider,
    "tiktok_research": TikTokResearchProvider,
}


def build_provider(settings: Settings, client: httpx.AsyncClient) -> RepostProvider:
    try:
        cls = PROVIDERS[settings.provider]
    except KeyError:
        raise ValueError(f"PROVIDER desconhecido: {settings.provider!r}. Opções: {', '.join(PROVIDERS)}")
    return cls(settings, client)


__all__ = ["RepostProvider", "build_provider", "PROVIDERS"]
