"""Interface comum dos provedores e utilitários para normalizar respostas JSON."""

from __future__ import annotations

import abc
import logging
import re
from datetime import datetime, timezone
from typing import Any, Iterable

import httpx

from ..config import Settings
from ..http import ProviderError
from ..models import Repost, iso, video_url

log = logging.getLogger(__name__)

VIDEO_ID_IN_URL = re.compile(r"/(?:video|photo|v)/(\d{8,})")

# Nomes de campo usados pelas APIs mais comuns (TikTok web, tikwm, Apify, Research API).
ID_FIELDS = (
    "id", "aweme_id", "video_id", "item_id", "post_id", "awemeId", "itemId", "videoId", "postId",
    "video.id", "item.id", "aweme.aweme_id",
)
URL_FIELDS = (
    "webVideoUrl", "share_url", "shareUrl", "url", "video_url", "videoUrl", "postUrl", "post_url",
    "tiktokUrl", "tiktok_url", "link",
)
AUTHOR_FIELDS = (
    "author.unique_id", "author.uniqueId", "authorMeta.name", "author.username",
    "author_unique_id", "username", "author",
)
DESCRIPTION_FIELDS = ("desc", "text", "title", "description", "video_description")
COVER_FIELDS = (
    "cover", "origin_cover", "video.cover", "video.cover.url_list.0",
    "videoMeta.coverUrl", "cover_image_url", "thumbnail",
)
CREATED_FIELDS = ("create_time", "createTime", "createTimeISO", "created_at")
ITEMS_CANDIDATES = (
    "data.reposted_videos", "data.videos", "data.items", "data.aweme_list", "data.itemList",
    "reposted_videos", "videos", "items", "itemList", "aweme_list", "data", "result",
)


class RepostProvider(abc.ABC):
    """Consulta a lista de reposts de um usuário, do mais recente para o mais antigo."""

    name = "base"

    def __init__(self, settings: Settings, client: httpx.AsyncClient):
        self.settings = settings
        self.client = client
        self.options = settings.provider_options

    @abc.abstractmethod
    async def fetch_reposts(self) -> list[Repost]:
        ...

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        from ..http import request_with_retry

        kwargs.setdefault("timeout", self.settings.http_timeout)
        return await request_with_retry(
            self.client, method, url,
            attempts=self.settings.retry_attempts,
            base_delay=self.settings.retry_base_delay,
            **kwargs,
        )

    def template_vars(self) -> dict[str, str]:
        return {"username": self.settings.username, "user_id": self.settings.user_id}


def get_path(data: Any, path: str) -> Any:
    """Acessa `a.b.0.c` em dicts/listas; retorna None se algum trecho não existir."""
    current = data
    for part in path.split("."):
        if current is None:
            return None
        if isinstance(current, list):
            if not part.isdigit() or int(part) >= len(current):
                return None
            current = current[int(part)]
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def first_value(item: dict[str, Any], preferred: str, fallbacks: Iterable[str]) -> Any:
    for path in ([preferred] if preferred else []) + list(fallbacks):
        value = get_path(item, path)
        if value not in (None, "", []):
            return value
    return None


def find_items(payload: Any, items_path: str = "") -> list[dict[str, Any]]:
    """Localiza a lista de vídeos dentro da resposta da API."""
    if items_path:
        items = get_path(payload, items_path)
        if not isinstance(items, list):
            raise ProviderError(f"Caminho '{items_path}' não aponta para uma lista na resposta da API.")
        return [i for i in items if isinstance(i, dict)]
    if isinstance(payload, list):
        return [i for i in payload if isinstance(i, dict)]
    for path in ITEMS_CANDIDATES:
        items = get_path(payload, path)
        if isinstance(items, list) and (not items or isinstance(items[0], dict)):
            return [i for i in items if isinstance(i, dict)]
    raise ProviderError(
        "Não foi possível localizar a lista de reposts na resposta. Configure HTTP_API_ITEMS_PATH."
    )


def _to_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):  # ex.: author como objeto
        for key in ("unique_id", "uniqueId", "username", "name"):
            if value.get(key):
                return str(value[key])
        return None
    if isinstance(value, list):
        return _to_text(value[0]) if value else None
    return str(value)


def _to_iso(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
        ts = float(value)
        if ts > 1e12:  # milissegundos
            ts /= 1000
        return iso(datetime.fromtimestamp(ts, tz=timezone.utc))
    return str(value)


def normalize_item(item: dict[str, Any], fields: dict[str, str] | None = None) -> Repost | None:
    """Converte um item bruto da API em `Repost`. Retorna None se não houver ID."""
    fields = fields or {}
    url = _to_text(first_value(item, fields.get("url_field", ""), URL_FIELDS))
    item_id = _to_text(first_value(item, fields.get("id_field", ""), ID_FIELDS))
    if not item_id and url:
        match = VIDEO_ID_IN_URL.search(url)
        item_id = match.group(1) if match else None
    if not item_id:
        return None
    author = _to_text(first_value(item, fields.get("author_field", ""), AUTHOR_FIELDS))
    author = author.lstrip("@") if author else None
    if not url or not url.startswith("http"):
        url = video_url(item_id, author)
    return Repost(
        item_id=item_id,
        url=url,
        author=author,
        description=_to_text(first_value(item, fields.get("description_field", ""), DESCRIPTION_FIELDS)),
        cover_url=_to_text(first_value(item, fields.get("cover_field", ""), COVER_FIELDS)),
        created_at=_to_iso(first_value(item, "", CREATED_FIELDS)),
    )


def normalize_items(items: list[dict[str, Any]], fields: dict[str, str] | None = None) -> list[Repost]:
    reposts, seen = [], set()
    for raw in items:
        repost = normalize_item(raw, fields)
        if repost and repost.item_id not in seen:
            seen.add(repost.item_id)
            reposts.append(repost)
    if items and not reposts:
        raise ProviderError(
            f"A API devolveu {len(items)} item(ns), mas nenhum com ID de vídeo reconhecido. "
            f"Campos do primeiro item: {', '.join(sorted(items[0])[:25])}. "
            "Configure HTTP_API_ID_FIELD / HTTP_API_URL_FIELD."
        )
    return reposts


def fill_template(value: Any, variables: dict[str, str]) -> Any:
    """Substitui {username}/{user_id} recursivamente em strings, dicts e listas."""
    if isinstance(value, str):
        for key, replacement in variables.items():
            value = value.replace("{" + key + "}", replacement)
        return value
    if isinstance(value, dict):
        return {k: fill_template(v, variables) for k, v in value.items()}
    if isinstance(value, list):
        return [fill_template(v, variables) for v in value]
    return value
