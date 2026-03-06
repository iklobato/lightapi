"""Tests for US1: engine swap activates full async CRUD."""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import Field as PydanticField
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import create_async_engine

from lightapi import LightApi, RestEndpoint
from lightapi.auth import AllowAny
from lightapi.config import Authentication


def _make_widget_app(engine):
    """Build a LightApi app with a Widget endpoint."""

    class Widget(RestEndpoint):
        name: str = PydanticField(min_length=1)
        qty: int = PydanticField(default=0)

        class Meta:
            authentication = Authentication(permission=AllowAny)

    app = LightApi(engine=engine)
    app.register({"/widgets": Widget})
    return app


def _make_sync_endpoint_app(engine):
    """Build a LightApi app with a sync-queryset endpoint on an async engine."""

    class Cat(RestEndpoint):
        name: str = PydanticField(min_length=1)

        class Meta:
            authentication = Authentication(permission=AllowAny)

        def queryset(self, request):
            return sa_select(type(self)._model_class)

    app = LightApi(engine=engine)
    app.register({"/cats": Cat})
    return app


@pytest_asyncio.fixture
async def client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    app = _make_widget_app(engine)
    starlette_app = app.build_app()
    async with AsyncClient(
        transport=ASGITransport(app=starlette_app), base_url="http://test"
    ) as c:
        yield c


@pytest_asyncio.fixture
async def sync_client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    app = _make_sync_endpoint_app(engine)
    starlette_app = app.build_app()
    async with AsyncClient(
        transport=ASGITransport(app=starlette_app), base_url="http://test"
    ) as c:
        yield c


# ── Tests ─────────────────────────────────────────────────────────────────────


async def test_async_post_returns_201(client):
    r = await client.post("/widgets", json={"name": "bolt", "qty": 10})
    assert r.status_code == 201
    assert r.json()["name"] == "bolt"
    assert r.json()["qty"] == 10


async def test_async_get_list_returns_200(client):
    await client.post("/widgets", json={"name": "nut"})
    r = await client.get("/widgets")
    assert r.status_code == 200
    assert "results" in r.json()


async def test_async_get_detail_returns_200(client):
    create_r = await client.post("/widgets", json={"name": "washer"})
    pk = create_r.json()["id"]
    r = await client.get(f"/widgets/{pk}")
    assert r.status_code == 200
    assert r.json()["name"] == "washer"


async def test_async_get_detail_returns_404(client):
    r = await client.get("/widgets/99999")
    assert r.status_code == 404


async def test_async_delete_returns_204(client):
    create_r = await client.post("/widgets", json={"name": "pin"})
    pk = create_r.json()["id"]
    r = await client.delete(f"/widgets/{pk}")
    assert r.status_code == 204


async def test_async_delete_again_returns_404(client):
    create_r = await client.post("/widgets", json={"name": "clip"})
    pk = create_r.json()["id"]
    await client.delete(f"/widgets/{pk}")
    r = await client.delete(f"/widgets/{pk}")
    assert r.status_code == 404


async def test_sync_endpoint_on_async_app_returns_200(sync_client):
    r = await sync_client.get("/cats")
    assert r.status_code == 200
    assert "results" in r.json()


async def test_async_put_optimistic_lock_ok(client):
    create_r = await client.post("/widgets", json={"name": "gear"})
    body = create_r.json()
    pk = body["id"]
    version = body["version"]
    r = await client.put(
        f"/widgets/{pk}", json={"name": "gear-v2", "qty": 5, "version": version}
    )
    assert r.status_code == 200
    assert r.json()["name"] == "gear-v2"
    assert r.json()["version"] == version + 1


async def test_async_put_optimistic_lock_conflict(client):
    create_r = await client.post("/widgets", json={"name": "spring"})
    body = create_r.json()
    pk = body["id"]
    r = await client.put(
        f"/widgets/{pk}", json={"name": "spring-v2", "qty": 1, "version": 999}
    )
    assert r.status_code == 409
