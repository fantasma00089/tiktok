import json

import httpx
import pytest

from repost_monitor.config import Settings
from repost_monitor.http import ProviderError, RateLimitError, request_with_retry
from repost_monitor.providers import build_provider
from repost_monitor.providers.base import find_items, normalize_item


def test_normalize_tiktok_web_style_item():
    item = {"aweme_id": "123", "desc": "oi", "author": {"unique_id": "fulano"}, "video": {"cover": "https://c/1.jpg"}}
    repost = normalize_item(item)
    assert repost.item_id == "123"
    assert repost.author == "fulano"
    assert repost.url == "https://www.tiktok.com/@fulano/video/123"
    assert repost.cover_url == "https://c/1.jpg"


def test_normalize_apify_style_item():
    item = {"id": "9", "webVideoUrl": "https://www.tiktok.com/@b/video/9", "authorMeta": {"name": "b"},
            "text": "legenda", "createTime": 1700000000}
    repost = normalize_item(item)
    assert repost.url == "https://www.tiktok.com/@b/video/9"
    assert repost.author == "b"
    assert repost.description == "legenda"
    assert repost.created_at == "2023-11-14T22:13:20Z"


def test_normalize_without_author_uses_id_url():
    assert normalize_item({"id": 55}).url == "https://www.tiktok.com/@/video/55"
    assert normalize_item({"foo": 1}) is None


def test_find_items_auto_and_explicit():
    payload = {"data": {"reposted_videos": [{"id": "1"}], "cursor": 0}}
    assert find_items(payload) == [{"id": "1"}]
    assert find_items({"x": {"y": [{"id": "2"}]}}, "x.y") == [{"id": "2"}]
    with pytest.raises(ProviderError):
        find_items({"nada": 1})


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def _run(coro):
    return await coro


def test_http_provider_with_templates(settings: Settings):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["key"] = request.headers.get("x-api-key")
        return httpx.Response(200, json={"data": {"videos": [{"video_id": "77", "author": "c"}]}})

    settings.provider = "http"
    settings.provider_options = {
        "url": "https://api.test/reposts?u={username}", "method": "GET",
        "headers": {"X-API-Key": "k"}, "body": None, "items_path": "data.videos",
    }
    import asyncio

    async def go():
        async with _client(handler) as client:
            return await build_provider(settings, client).fetch_reposts()

    reposts = asyncio.run(go())
    assert seen == {"url": "https://api.test/reposts?u=alvo_teste", "key": "k"}
    assert [r.item_id for r in reposts] == ["77"]


def test_retry_then_success():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503)
        return httpx.Response(200, json={})

    import asyncio

    async def go():
        async with _client(handler) as client:
            return await request_with_retry(client, "GET", "https://x", attempts=3, base_delay=0)

    assert asyncio.run(go()).status_code == 200
    assert calls["n"] == 3


def test_rate_limit_error_carries_retry_after():
    import asyncio

    async def go():
        async with _client(lambda req: httpx.Response(429, headers={"Retry-After": "0"})) as client:
            await request_with_retry(client, "GET", "https://x", attempts=2, base_delay=0)

    with pytest.raises(RateLimitError) as info:
        asyncio.run(go())
    assert info.value.retry_after == 0


def test_client_error_is_not_retried():
    import asyncio
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(401, text="unauthorized")

    async def go():
        async with _client(handler) as client:
            await request_with_retry(client, "GET", "https://x", attempts=3, base_delay=0)

    with pytest.raises(ProviderError):
        asyncio.run(go())
    assert calls["n"] == 1


def test_tiktok_research_provider(settings: Settings):
    import asyncio

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v2/oauth/token/":
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 7200})
        assert request.headers["authorization"] == "Bearer tok"
        assert json.loads(request.content) == {"username": "alvo_teste", "max_count": 20}
        return httpx.Response(200, json={
            "data": {"reposted_videos": [{"id": 5, "create_time": 1700000000}], "cursor": 1, "has_more": False},
            "error": {"code": "ok", "message": ""},
        })

    settings.provider = "tiktok_research"
    settings.provider_options = {"client_key": "a", "client_secret": "b", "fields": "id,create_time", "max_count": 20}

    async def go():
        async with _client(handler) as client:
            return await build_provider(settings, client).fetch_reposts()

    assert [r.item_id for r in asyncio.run(go())] == ["5"]


def test_apify_defaults_only_need_token(settings: Settings):
    import asyncio
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        seen["timeout"] = request.extensions["timeout"]["read"]
        return httpx.Response(200, json=[
            {"postUrl": "https://www.tiktok.com/@criador/video/7400000000000000001", "author": "criador"},
        ])

    settings.provider = "apify"
    settings.provider_options = {"token": "apify_tok", "actor": "", "input": None, "items_path": ""}

    async def go():
        async with _client(handler) as client:
            return await build_provider(settings, client).fetch_reposts()

    reposts = asyncio.run(go())
    assert seen["path"] == "/v2/acts/maximedupre~tiktok-reposts/run-sync-get-dataset-items"
    assert seen["auth"] == "Bearer apify_tok"
    assert seen["body"] == {"profiles": ["https://www.tiktok.com/@alvo_teste"], "maxItemsPerProfile": 10}
    assert seen["timeout"] >= 300
    assert [r.item_id for r in reposts] == ["7400000000000000001"]  # ID extraído da URL


def test_unrecognized_items_raise_clear_error():
    from repost_monitor.providers.base import normalize_items

    with pytest.raises(ProviderError, match="nenhum com ID"):
        normalize_items([{"foo": 1, "bar": 2}])
    assert normalize_items([]) == []
