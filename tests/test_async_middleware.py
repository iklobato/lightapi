"""Tests for US5: async and sync middleware coexistence."""
import asyncio

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pydantic import Field as PydanticField
from sqlalchemy.ext.asyncio import create_async_engine
from starlette.responses import JSONResponse, Response

from lightapi import LightApi, RestEndpoint
from lightapi.auth import AllowAny
from lightapi.config import Authentication
from lightapi.core import Middleware


def _make_app(middlewares, engine=None):
    if engine is None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    class Item(RestEndpoint):
        name: str = PydanticField(min_length=1)

        class Meta:
            authentication = Authentication(permission=AllowAny)

    app = LightApi(engine=engine, middlewares=middlewares)
    app.register({"/items": Item})
    return app.build_app()


class AsyncAuditMiddleware(Middleware):
    def __init__(self, log: list):
        self.log = log

    async def process(self, request, response):
        if response is None:
            self.log.append("async-pre")
            return None
        self.log.append("async-post")
        return response


class SyncAuditMiddleware(Middleware):
    def __init__(self, log: list):
        self.log = log

    def process(self, request, response):
        if response is None:
            self.log.append("sync-pre")
            return None
        self.log.append("sync-post")
        return response


class ShortCircuitMiddleware(Middleware):
    async def process(self, request, response):
        if response is None:
            return JSONResponse({"short": "circuited"}, status_code=200)
        return response


async def test_async_process_is_awaited():
    """async def process middleware is awaited and executes correctly."""
    log: list = []

    class _MW(Middleware):
        async def process(self, request, response):
            if response is None:
                log.append("awaited")
            return response

    app = _make_app([_MW])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/items")
    assert r.status_code == 200
    assert "awaited" in log


async def test_sync_middleware_in_async_stack():
    """Sync process() middleware executes alongside async middleware."""
    log: list = []

    class _AsyncMW(Middleware):
        async def process(self, request, response):
            if response is None:
                log.append("a-pre")
            return response

    class _SyncMW(Middleware):
        def process(self, request, response):
            if response is None:
                log.append("s-pre")
            return response

    app = _make_app([_AsyncMW, _SyncMW])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.get("/items")
    assert "a-pre" in log
    assert "s-pre" in log


async def test_middleware_declaration_order_preserved():
    """Pre-request middleware runs A→B→C in declaration order."""
    log: list = []

    class A(Middleware):
        async def process(self, request, response):
            if response is None:
                log.append("A")
            return response

    class B(Middleware):
        def process(self, request, response):
            if response is None:
                log.append("B")
            return response

    class C(Middleware):
        async def process(self, request, response):
            if response is None:
                log.append("C")
            return response

    app = _make_app([A, B, C])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.get("/items")
    pre_indices = [log.index(x) for x in ["A", "B", "C"]]
    assert pre_indices == sorted(pre_indices)


async def test_async_middleware_short_circuit():
    """Middleware returning a Response halts the chain; endpoint is not called."""
    app = _make_app([ShortCircuitMiddleware])
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/items")
    assert r.status_code == 200
    assert r.json() == {"short": "circuited"}
