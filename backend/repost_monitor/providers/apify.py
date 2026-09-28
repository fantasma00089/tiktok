"""Provedor Apify: executa um Actor de scraping do TikTok e lê os itens do dataset.

Basta APIFY_TOKEN: por padrão usa o Actor "maximedupre/tiktok-reposts", que lê a
aba pública de reposts de um perfil. Para outro Actor, informe APIFY_ACTOR e a
entrada em APIFY_INPUT (JSON com {username}/{user_id}). O plano gratuito da Apify
inclui créditos mensais; veja o preço por resultado na página do Actor.
"""

from __future__ import annotations

from urllib.parse import quote

from ..http import ProviderError
from ..models import Repost
from .base import RepostProvider, fill_template, find_items, normalize_items

APIFY_RUN_SYNC_URL = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"
DEFAULT_ACTOR = "maximedupre/tiktok-reposts"
DEFAULT_INPUT = {"profiles": ["https://www.tiktok.com/@{username}"], "maxItemsPerProfile": 10}
# O Actor roda um navegador a cada chamada; a API síncrona aguarda até 300s.
RUN_TIMEOUT_SECONDS = 300


class ApifyProvider(RepostProvider):
    name = "apify"

    async def fetch_reposts(self) -> list[Repost]:
        opts = self.options
        if not opts.get("token"):
            raise ProviderError("Configure APIFY_TOKEN (Apify → Settings → API & Integrations).")
        if not self.settings.username:
            raise ProviderError("O provedor Apify precisa de TIKTOK_USERNAME.")
        actor = opts.get("actor") or DEFAULT_ACTOR
        actor_input = opts.get("input") or DEFAULT_INPUT
        url = APIFY_RUN_SYNC_URL.format(actor=quote(actor.replace("/", "~"), safe="~"))
        response = await self.request(
            "POST", url,
            timeout=max(self.settings.http_timeout, RUN_TIMEOUT_SECONDS),
            params={"format": "json", "clean": "true"},
            headers={"Authorization": f"Bearer {opts['token']}"},
            json=fill_template(actor_input, self.template_vars()),
        )
        return normalize_items(find_items(response.json(), opts.get("items_path", "")))
