"""Tests for US4: self.background() fire-and-forget tasks."""

import asyncio

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import Field as PydanticField
from sqlalchemy.ext.asyncio import create_async_engine

from lightapi import LightApi, RestEndpoint
from lightapi.auth import AllowAny
from lightapi.config import Authentication


def _build_app(tracker: list, use_async_fn: bool = False, multi: bool = False):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    if use_async_fn:

        async def notify(item_id: int) -> None:
            tracker.append(item_id)
    else:

        def notify(item_id: int) -> None:  # type: ignore[misc]
            tracker.append(item_id)

    class BgItem(RestEndpoint):
        name: str = PydanticField(min_length=1)

        class Meta:
            authentication = Authentication(permission=AllowAny)

        async def post(self, request):
            item = await self._create_async(await _read_json(request))
            import json

            body = json.loads(item.body)
            if multi:
                self.background(notify, body["id"])
                self.background(notify, body["id"] + 100)
            else:
                self.background(notify, body["id"])
            return item

    app = LightApi(engine=engine)
    app.register({"/items": BgItem})
    return app.build_app()


async def _read_json(request):
    import json

    return json.loads(await request.body())


@pytest_asyncio.fixture
async def bg_client():
    tracker: list = []
    starlette_app = _build_app(tracker)
    async with AsyncClient(
        transport=ASGITransport(app=starlette_app), base_url="http://test"
    ) as c:
        yield c, tracker


@pytest_asyncio.fixture
async def async_fn_client():
    tracker: list = []
    starlette_app = _build_app(tracker, use_async_fn=True)
    async with AsyncClient(
        transport=ASGITransport(app=starlette_app), base_url="http://test"
    ) as c:
        yield c, tracker


@pytest_asyncio.fixture
async def multi_client():
    tracker: list = []
    starlette_app = _build_app(tracker, multi=True)
    async with AsyncClient(
        transport=ASGITransport(app=starlette_app), base_url="http://test"
    ) as c:
        yield c, tracker


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
