"""Meta.cache must also work when the app runs on an AsyncEngine."""

from unittest.mock import patch

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine

from lightapi import Cache, LightApi, RestEndpoint
from lightapi.fields import Field as LField

TTL = 60


class AsyncCachedEndpoint(RestEndpoint):
    name: str = LField(min_length=1)

    class Meta:
        cache = Cache(ttl=TTL)


@pytest_asyncio.fixture
async def client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    app = LightApi(engine=engine, mode="async")
    app.register({"/asynccached": AsyncCachedEndpoint})
    async with AsyncClient(
        transport=ASGITransport(app=app.build_app()), base_url="http://test"
    ) as c:
        yield c
    await engine.dispose()


async def test_async_get_list_cache_hit_returns_cached_body(client):
    cached_body = {"results": [{"id": 1, "name": "from-cache"}]}

    with patch("lightapi.cache_helper.get_cached", return_value=cached_body):
        with patch("lightapi.cache_helper.set_cached") as mock_set:
            response = await client.get("/asynccached")

    assert response.status_code == 200
    assert response.json() == cached_body
    mock_set.assert_not_called()


async def test_async_get_list_cache_miss_stores_response_with_ttl(client):
    with patch("lightapi.cache_helper.get_cached", return_value=None):
        with patch("lightapi.cache_helper.set_cached") as mock_set:
            response = await client.get("/asynccached")

    assert response.status_code == 200
    key, body, ttl = mock_set.call_args.args
    assert "AsyncCachedEndpoint" in key
    assert body == {"results": []}
    assert ttl == TTL


async def test_async_post_invalidates_the_endpoint_prefix(client):
    with patch("lightapi.cache_helper.invalidate_cache_prefix") as mock_invalidate:
        response = await client.post("/asynccached", json={"name": "fresh"})

    assert response.status_code == 201
    mock_invalidate.assert_called_once_with("lightapi:AsyncCachedEndpoint:")


async def test_async_get_does_not_invalidate(client):
    with patch("lightapi.cache_helper.get_cached", return_value=None):
        with patch("lightapi.cache_helper.set_cached"):
            with patch("lightapi.cache_helper.invalidate_cache_prefix") as mock_inv:
                await client.get("/asynccached")

    mock_inv.assert_not_called()
