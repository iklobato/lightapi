"""Tests for US3: sync endpoint fallback on async app."""

import time

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import Field as PydanticField
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import create_async_engine

from lightapi import LightApi, RestEndpoint
from lightapi.auth import AllowAny
from lightapi.config import Authentication


@pytest_asyncio.fixture
async def mixed_client():
    """App with one async endpoint and one sync endpoint on the same async engine."""

    class AsyncWidget(RestEndpoint):
        name: str = PydanticField(min_length=1)

        class Meta:
            authentication = Authentication(permission=AllowAny)

        async def queryset(self, request):
            return sa_select(type(self)._model_class)

    class SyncCategory(RestEndpoint):
        label: str = PydanticField(min_length=1)

        class Meta:
            authentication = Authentication(permission=AllowAny)

        def queryset(self, request):
            return sa_select(type(self)._model_class)

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    app = LightApi(engine=engine)
    app.register({"/widgets": AsyncWidget, "/cats": SyncCategory})
    starlette_app = app.build_app()
    async with AsyncClient(
        transport=ASGITransport(app=starlette_app), base_url="http://test"
    ) as c:
        yield c


async def test_sync_and_async_endpoints_same_app(mixed_client):
    """Both async and sync endpoints respond correctly on the same app."""
    r_async = await mixed_client.get("/widgets")
    assert r_async.status_code == 200

    r_sync = await mixed_client.get("/cats")
    assert r_sync.status_code == 200


async def test_sync_endpoint_no_latency_penalty(mixed_client):
    """Sync endpoint on async app responds in under 500 ms (no unusual blocking)."""
    start = time.monotonic()
    r = await mixed_client.get("/cats")
    elapsed = time.monotonic() - start
    assert r.status_code == 200
    assert elapsed < 0.5


async def test_async_endpoint_queryset_scoped(mixed_client):
    """Async endpoint with scoped queryset returns only expected rows."""
    await mixed_client.post("/widgets", json={"name": "bolt"})
    r = await mixed_client.get("/widgets")
    assert r.status_code == 200
    names = [i["name"] for i in r.json()["results"]]
    assert "bolt" in names


async def test_sync_endpoint_queryset_scoped(mixed_client):
    """Sync endpoint with queryset on async app returns correct rows."""
    await mixed_client.post("/cats", json={"label": "tools"})
    r = await mixed_client.get("/cats")
    assert r.status_code == 200
    labels = [i["label"] for i in r.json()["results"]]
    assert "tools" in labels
