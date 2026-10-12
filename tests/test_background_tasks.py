"""Tests for US4: self.background() fire-and-forget tasks."""

import asyncio
import json

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import Field as PydanticField
from sqlalchemy.ext.asyncio import create_async_engine

from lightapi import LightApi, RestEndpoint
from lightapi.auth import AllowAny
from lightapi.config import Authentication

# Every background notification lands here; each fixture starts it empty.
_TRACKER: list[int] = []


def _notify(item_id: int) -> None:
    _TRACKER.append(item_id)


async def _notify_async(item_id: int) -> None:
    _TRACKER.append(item_id)


async def _created_id(endpoint: RestEndpoint, request) -> tuple:
    """(response, id) of the row the POST body creates."""
    item = await endpoint._create_async(json.loads(await request.body()))
    return item, json.loads(item.body)["id"]


class BgItem(RestEndpoint):
    name: str = PydanticField(min_length=1)

    class Meta:
        authentication = Authentication(permission=AllowAny)

    async def post(self, request):
        item, item_id = await _created_id(self, request)
        self.background(_notify, item_id)
        return item


class BgAsyncFnItem(RestEndpoint):
    name: str = PydanticField(min_length=1)

    class Meta:
        authentication = Authentication(permission=AllowAny)

    async def post(self, request):
        item, item_id = await _created_id(self, request)
        self.background(_notify_async, item_id)
        return item


class BgMultiItem(RestEndpoint):
    name: str = PydanticField(min_length=1)

    class Meta:
        authentication = Authentication(permission=AllowAny)

    async def post(self, request):
        item, item_id = await _created_id(self, request)
        self.background(_notify, item_id)
        self.background(_notify, item_id + 100)
        return item


def _build_app(endpoint_cls: type[RestEndpoint], engine):
    app = LightApi(engine=engine, mode="async")
    app.register({"/items": endpoint_cls})
    return app.build_app()


@pytest_asyncio.fixture
async def bg_client():
    _TRACKER.clear()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with AsyncClient(
        transport=ASGITransport(app=_build_app(BgItem, engine)), base_url="http://test"
    ) as c:
        yield c, _TRACKER
    await engine.dispose()


@pytest_asyncio.fixture
async def async_fn_client():
    _TRACKER.clear()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with AsyncClient(
        transport=ASGITransport(app=_build_app(BgAsyncFnItem, engine)),
        base_url="http://test",
    ) as c:
        yield c, _TRACKER
    await engine.dispose()


@pytest_asyncio.fixture
async def multi_client():
    _TRACKER.clear()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with AsyncClient(
        transport=ASGITransport(app=_build_app(BgMultiItem, engine)),
        base_url="http://test",
    ) as c:
        yield c, _TRACKER
    await engine.dispose()


async def test_background_fn_runs_after_response(bg_client):
    client, tracker = bg_client
    r = await client.post("/items", json={"name": "widget"})
    assert r.status_code == 201
    await asyncio.sleep(0.1)
    assert len(tracker) >= 1


async def test_sync_background_fn_accepted(bg_client):
    client, tracker = bg_client
    r = await client.post("/items", json={"name": "gadget"})
    assert r.status_code == 201
    await asyncio.sleep(0.1)
    assert len(tracker) >= 1


async def test_async_background_fn_accepted(async_fn_client):
    client, tracker = async_fn_client
    r = await client.post("/items", json={"name": "async-thing"})
    assert r.status_code == 201
    await asyncio.sleep(0.1)
    assert len(tracker) >= 1


async def test_multiple_background_tasks_all_run(multi_client):
    client, tracker = multi_client
    r = await client.post("/items", json={"name": "multi"})
    assert r.status_code == 201
    await asyncio.sleep(0.1)
    assert len(tracker) >= 2


async def test_background_outside_handler_raises():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    class SimpleItem(RestEndpoint):
        name: str = PydanticField(min_length=1)

        class Meta:
            authentication = Authentication(permission=AllowAny)

    app = LightApi(engine=engine)
    app.register({"/items": SimpleItem})

    endpoint = SimpleItem()
    with pytest.raises(RuntimeError, match="outside request handler"):
        endpoint.background(lambda: None)
