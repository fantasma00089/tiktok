"""Provedor Apify: executa um Actor de scraping do TikTok e lê os itens do dataset.

Escolha na Apify Store um Actor que suporte a aba de reposts de um perfil e
informe o ID em APIFY_ACTOR (ex.: "usuario~nome-do-actor") e a entrada em
APIFY_INPUT (JSON com {username}/{user_id}). O plano gratuito da Apify inclui
créditos mensais suficientes para polling moderado.
"""

from __future__ import annotations

from urllib.parse import quote

from ..http import ProviderError
from ..models import Repost
from .base import RepostProvider, fill_template, find_items, normalize_items

APIFY_RUN_SYNC_URL = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"


class ApifyProvider(RepostProvider):
    name = "apify"

    async def fetch_reposts(self) -> list[Repost]:
        opts = self.options
        if not opts.get("token") or not opts.get("actor"):
            raise ProviderError("Configure APIFY_TOKEN e APIFY_ACTOR.")
        actor_input = opts.get("input") or {"profiles": ["{username}"], "resultsPerPage": 20}
        url = APIFY_RUN_SYNC_URL.format(actor=quote(opts["actor"].replace("/", "~"), safe="~"))
        response = await self.request(
            "POST", url,
            params={"format": "json", "clean": "true"},
            headers={"Authorization": f"Bearer {opts['token']}"},
            json=fill_template(actor_input, self.template_vars()),
        )
        return normalize_items(find_items(response.json(), opts.get("items_path", "")))
