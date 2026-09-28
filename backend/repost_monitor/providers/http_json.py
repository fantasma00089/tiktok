"""Provedor genérico para qualquer API REST/JSON (PrimeApi, YepAPI, RapidAPI, tikwm...).

Tudo é configurável por variáveis de ambiente (veja docs/CONFIGURACAO.md):
URL com placeholders {username}/{user_id}, método, cabeçalhos, corpo e caminhos
dos campos no JSON de resposta.
"""

from __future__ import annotations

from urllib.parse import quote

from ..http import ProviderError
from ..models import Repost
from .base import RepostProvider, fill_template, find_items, normalize_items


class HttpJsonProvider(RepostProvider):
    name = "http"

    async def fetch_reposts(self) -> list[Repost]:
        opts = self.options
        if not opts.get("url"):
            raise ProviderError("HTTP_API_URL não configurada.")
        variables = self.template_vars()
        url = fill_template(opts["url"], {k: quote(v, safe="") for k, v in variables.items()})
        kwargs = {"headers": fill_template(opts.get("headers") or {}, variables)}
        if opts.get("body") is not None:
            kwargs["json"] = fill_template(opts["body"], variables)

        response = await self.request(opts.get("method", "GET"), url, **kwargs)
        try:
            payload = response.json()
        except ValueError as exc:
            raise ProviderError(f"Resposta da API não é JSON: {response.text[:200]}") from exc
        return normalize_items(find_items(payload, opts.get("items_path", "")), opts)
