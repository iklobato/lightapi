"""T3-02: async CRUD against Postgres over asyncpg, through AsyncSession.run_sync.

The app must be BUILT before any event loop is running (see the `client`
fixture below): LightApi._create_tables() detects a running loop and creates
tables via `asyncio.run()` in a worker thread, which for asyncpg checks out a
connection bound to that thread's loop into the engine's own pool. The next
request on the real loop can then be handed that poisoned connection and
fail with "Future attached to a different loop". Reproduced identically on
the published 0.1.29, so it is a pre-existing bug (see the test plan, B19),
not a regression; this file works around it instead of triggering it.
"""

import asyncio
from decimal import Decimal
from typing import Optional
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text

from lightapi import LightApi, RestEndpoint
from lightapi.fields import Field

from .conftest import PG_SYNC_URL, requires_pg_async

pytestmark = requires_pg_async


class PgaBook(RestEndpoint):
    title: str = Field(min_length=1, max_length=50)
    pages: int = Field(ge=1)
    price: Decimal = Field(decimal_places=2)
    rating: Optional[float] = Field(default=None)
    in_print: bool = Field(default=True)
    uid: Optional[UUID] = Field(default=None)


@pytest.fixture
def built_app(pg_async_engine):
    """Register and create tables with no event loop running (see module docstring)."""
    app = LightApi(engine=pg_async_engine, mode="async", use_test_isolation=True)
    app.register({"/pgabooks": PgaBook})
    sync_engine = create_engine(PG_SYNC_URL)
    app._session_manager.metadata.create_all(bind=sync_engine)
    # The container persists across local runs; start each test from zero rows.
    with sync_engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE pgabooks RESTART IDENTITY"))
        conn.commit()
    sync_engine.dispose()
    return app.build_app()


@pytest.fixture
def client(built_app):
    transport = ASGITransport(app=built_app)
    return AsyncClient(transport=transport, base_url="http://test")


async def test_insert_flush_refresh_returns_generated_columns(client):
    async with client:
        response = await client.post(
            "/pgabooks", json={"title": "Dune", "pages": 412, "price": "9.99"}
        )

    assert response.status_code == 201
    body = response.json()
    assert body["id"] is not None
    assert body["created_at"] is not None
    assert body["updated_at"] is not None
    assert body["version"] == 1


async def test_update_conflict_uses_rowcount(client):
    async with client:
        created = (
            await client.post(
                "/pgabooks", json={"title": "Dune", "pages": 412, "price": "9.99"}
            )
        ).json()
        pk = created["id"]

        ok = await client.put(
            f"/pgabooks/{pk}",
            json={
                "title": "Dune II",
                "pages": 500,
                "price": "11.99",
                "version": created["version"],
            },
        )
        assert ok.status_code == 200
        assert ok.json()["version"] == 2

        stale = await client.put(
            f"/pgabooks/{pk}",
            json={"title": "x", "pages": 1, "price": "1.00", "version": 1},
        )
        assert stale.status_code == 409


async def test_delete_with_returning(client):
    async with client:
        created = (
            await client.post(
                "/pgabooks", json={"title": "Dune", "pages": 412, "price": "9.99"}
            )
        ).json()
        pk = created["id"]

        deleted = await client.delete(f"/pgabooks/{pk}")
        assert deleted.status_code == 204

        again = await client.delete(f"/pgabooks/{pk}")
        assert again.status_code == 404


async def test_decimal_uuid_datetime_bool_round_trip(client):
    uid = "6f1c1f0a-5f0e-4c3b-9d2a-0c7e8f9a1b2c"

    async with client:
        created = await client.post(
            "/pgabooks",
            json={
                "title": "Dune",
                "pages": 412,
                "price": "9.99",
                "rating": 4.5,
                "in_print": False,
                "uid": uid,
            },
        )

    assert created.status_code == 201
    body = created.json()
    assert body["price"] == "9.99"
    assert body["rating"] == 4.5
    assert body["in_print"] is False
    assert body["uid"] == uid


def test_the_pool_poisoning_bug_is_reproducible():
    """Pin B19: building the app from inside a running loop breaks the next request.

    Not a regression (identical on 0.1.29); documents the trap the fixture
    above avoids, so a future change to _create_tables can update this test
    instead of silently losing the coverage. A plain (non-async) test: a sync
    fixture cannot inject an AsyncEngine built by an async fixture into it.
    """
    from sqlalchemy.ext.asyncio import create_async_engine

    from .conftest import PG_ASYNC_URL

    class PgaTrapped(RestEndpoint):
        name: str = Field(min_length=1)

    async def build_and_call_inside_a_loop():
        engine = create_async_engine(PG_ASYNC_URL)
        app = LightApi(engine=engine, mode="async", use_test_isolation=True)
        app.register({"/pgatrapped": PgaTrapped})
        starlette_app = app.build_app()  # a loop is already running here
        transport = ASGITransport(app=starlette_app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/pgatrapped", json={"name": "x"})

    response = asyncio.run(build_and_call_inside_a_loop())

    assert response.status_code == 500
