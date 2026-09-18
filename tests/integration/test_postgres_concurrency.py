"""T3-04: optimistic locking under real concurrent writers, sync and async.

A real connection pool (not SQLite's StaticPool) is what run_blocking (sync)
and the async engine actually have to arbitrate concurrent writes through;
this checks the DB, not just the thread the code runs on (that part is
tests/test_sync_offload.py).

The async app is built in a plain (sync) fixture, not inside the async test
body: see the docstring of test_postgres_async.py for why building it while
a loop is running poisons the asyncpg connection pool (B19).
"""

import asyncio
import concurrent.futures

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from starlette.testclient import TestClient

from lightapi import LightApi, RestEndpoint
from lightapi.fields import Field

from .conftest import PG_ASYNC_URL, PG_SYNC_URL

WRITERS = 20


class PgcCounter(RestEndpoint):
    label: str = Field(min_length=1)


class PgacCounter(RestEndpoint):
    """A separate class from PgcCounter: reusing one class across a sync and an
    async app (both use_test_isolation=True) would leave _model_class set from
    the first mapping, and the second app's register() would silently keep
    operating on the first app's table instead of its own."""

    label: str = Field(min_length=1)


@pytest.mark.integration
@pytest.mark.skipif(not PG_SYNC_URL, reason="LIGHTAPI_TEST_PG_SYNC is not set")
def test_sync_optimistic_lock_under_real_parallel_writers():
    engine = create_engine(PG_SYNC_URL, pool_size=WRITERS, max_overflow=0)
    app = LightApi(engine=engine, use_test_isolation=True)
    app.register({"/pgccounters": PgcCounter})
    client = TestClient(app.build_app())
    # The container persists across local runs; start each test from zero rows.
    with engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE pgccounters RESTART IDENTITY"))
        conn.commit()

    created = client.post("/pgccounters", json={"label": "start"}).json()
    pk, version = created["id"], created["version"]

    def attempt(_: int) -> int:
        response = client.put(
            f"/pgccounters/{pk}", json={"label": "updated", "version": version}
        )
        return response.status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=WRITERS) as pool:
        statuses = list(pool.map(attempt, range(WRITERS)))

    assert statuses.count(200) == 1
    assert statuses.count(409) == WRITERS - 1

    final = client.get(f"/pgccounters/{pk}").json()
    assert final["version"] == version + 1
    engine.dispose()


@pytest.fixture
def built_async_app(pg_async_engine):
    app = LightApi(engine=pg_async_engine, mode="async", use_test_isolation=True)
    app.register({"/pgacounters": PgacCounter})
    sync_engine = create_engine(PG_SYNC_URL)
    app._session_manager.metadata.create_all(bind=sync_engine)
    # PgacCounter's default table name is "pgaccounters" (class name + "s").
    with sync_engine.connect() as conn:
        conn.execute(text("TRUNCATE TABLE pgaccounters RESTART IDENTITY"))
        conn.commit()
    sync_engine.dispose()
    return app.build_app()


@pytest.mark.integration
@pytest.mark.skipif(not PG_ASYNC_URL, reason="LIGHTAPI_TEST_PG_ASYNC is not set")
async def test_async_optimistic_lock_under_real_concurrent_requests(built_async_app):
    async with AsyncClient(
        transport=ASGITransport(app=built_async_app), base_url="http://test"
    ) as client:
        created = (await client.post("/pgacounters", json={"label": "start"})).json()
        pk, version = created["id"], created["version"]

        async def attempt(_: int) -> int:
            response = await client.put(
                f"/pgacounters/{pk}", json={"label": "updated", "version": version}
            )
            return response.status_code

        statuses = await asyncio.gather(*(attempt(n) for n in range(WRITERS)))

    assert statuses.count(200) == 1
    assert statuses.count(409) == WRITERS - 1
