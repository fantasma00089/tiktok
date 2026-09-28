"""Provedor oficial: TikTok Research API (endpoint "Query User Reposted Videos").

Requer acesso aprovado ao Research API (programa para pesquisadores).
Docs: https://developers.tiktok.com/doc/research-api-specs-query-user-reposted-videos
"""

from __future__ import annotations

import time

from ..http import ProviderError
from ..models import Repost
from .base import RepostProvider, find_items, normalize_items

TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
REPOSTS_URL = "https://open.tiktokapis.com/v2/research/user/reposted_videos/"


class TikTokResearchProvider(RepostProvider):
    name = "tiktok_research"

    _token: str | None = None
    _token_expires_at: float = 0.0

    async def _access_token(self) -> str:
        if self._token and time.time() < self._token_expires_at - 60:
            return self._token
        opts = self.options
        if not opts.get("client_key") or not opts.get("client_secret"):
            raise ProviderError("Configure TIKTOK_CLIENT_KEY e TIKTOK_CLIENT_SECRET.")
        response = await self.request(
            "POST", TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "client_key": opts["client_key"],
                "client_secret": opts["client_secret"],
                "grant_type": "client_credentials",
            },
        )
        data = response.json()
        if "access_token" not in data:
            raise ProviderError(f"Falha ao obter token do TikTok: {data}")
        self._token = data["access_token"]
        self._token_expires_at = time.time() + float(data.get("expires_in", 7200))
        return self._token

    async def fetch_reposts(self) -> list[Repost]:
        if not self.settings.username:
            raise ProviderError("A Research API exige TIKTOK_USERNAME.")
        token = await self._access_token()
        response = await self.request(
            "POST", REPOSTS_URL,
            params={"fields": self.options.get("fields", "id,create_time")},
            headers={"Authorization": f"Bearer {token}"},
            json={"username": self.settings.username, "max_count": self.options.get("max_count", 20)},
        )
        payload = response.json()
        error = payload.get("error") or {}
        if error.get("code") not in (None, "", "ok"):
            raise ProviderError(f"Research API: {error.get('code')} - {error.get('message')}")
        return normalize_items(find_items(payload, "data.reposted_videos"))
