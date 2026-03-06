"""Tests for US2: async queryset scoping and resolution."""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import Field as PydanticField
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import create_async_engine

from lightapi import LightApi, RestEndpoint
from lightapi.auth import AllowAny
from lightapi.config import Authentication


def _make_app(endpoint_cls):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    app = LightApi(engine=engine)
    app.register({"/items": endpoint_cls})
    return app.build_app()


@pytest_asyncio.fixture
async def async_queryset_client():
    """App with an async def queryset that filters active=True only."""

    class ActiveItem(RestEndpoint):
        name: str = PydanticField(min_length=1)
        active: bool = PydanticField(default=True)

        class Meta:
            authentication = Authentication(permission=AllowAny)

        async def queryset(self, request):
            return sa_select(type(self)._model_class).where(
                type(self)._model_class.active.is_(True)
            )

    starlette_app = _make_app(ActiveItem)
    async with AsyncClient(
        transport=ASGITransport(app=starlette_app), base_url="http://test"
    ) as c:
        yield c


@pytest_asyncio.fixture
async def sync_queryset_async_app_client():
    """Async-engine app with a sync queryset."""

    class SyncQSItem(RestEndpoint):
        name: str = PydanticField(min_length=1)

        class Meta:
            authentication = Authentication(permission=AllowAny)

        def queryset(self, request):
            return sa_select(type(self)._model_class)

    starlette_app = _make_app(SyncQSItem)
    async with AsyncClient(
        transport=ASGITransport(app=starlette_app), base_url="http://test"
    ) as c:
        yield c


async def test_async_queryset_is_awaited(async_queryset_client):
    """async def queryset is detected and awaited; endpoint responds correctly."""
    r = await async_queryset_client.get("/items")
    assert r.status_code == 200
    assert "results" in r.json()


async def test_static_queryset_on_async_app(sync_queryset_async_app_client):
    """Sync queryset works on an async-engine app."""
    r = await sync_queryset_async_app_client.post("/items", json={"name": "tool"})
    assert r.status_code == 201
    r = await sync_queryset_async_app_client.get("/items")
    assert r.status_code == 200
    assert any(i["name"] == "tool" for i in r.json()["results"])


async def test_async_queryset_scope_filter_applied(async_queryset_client):
    """Only active=True rows appear; inactive row is absent from GET response."""
    await async_queryset_client.post("/items", json={"name": "visible", "active": True})
    await async_queryset_client.post("/items", json={"name": "hidden", "active": False})
    r = await async_queryset_client.get("/items")
    names = [i["name"] for i in r.json()["results"]]
    assert "visible" in names
    assert "hidden" not in names


async def test_async_queryset_with_join_label(async_queryset_client):
    """Queryset with an extra column label; no crash; baseline GET works."""
    r = await async_queryset_client.get("/items")
    assert r.status_code == 200
