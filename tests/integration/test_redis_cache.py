"""T3-08 / T3-09: Meta.cache against a real Redis, and behaviour when it is down."""

import warnings

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

from lightapi import Cache, LightApi, RestEndpoint
from lightapi.fields import Field

from .conftest import REDIS_URL

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not REDIS_URL, reason="LIGHTAPI_REDIS_URL is not set"),
]


class RcItem(RestEndpoint):
    """Used only by the sync (use_test_isolation) tests below."""

    name: str = Field(min_length=1)

    class Meta:
        cache = Cache(ttl=60)


class RcaItem(RestEndpoint):
    """A separate class for the async (non-isolated) test: reusing RcItem's class
    would leave _model_class already set, so DeclaredTable.map() would short-circuit
    and never map the table into this app's own metadata."""

    name: str = Field(min_length=1)

    class Meta:
        cache = Cache(ttl=60)


@pytest.fixture(autouse=True)
def _fresh_cache_client(monkeypatch):
    """The process-wide Redis client is memoized (lru_cache); rebuild it per test
    so LIGHTAPI_REDIS_URL set by a test actually takes effect."""
    from lightapi import cache as cache_module

    monkeypatch.setenv("LIGHTAPI_REDIS_URL", REDIS_URL)
    cache_module._default_backend.cache_clear()
    yield
    cache_module._default_backend.cache_clear()


@pytest.fixture
def redis_client():
    """The real Redis client the running container serves, flushed before use."""
    import redis as redis_module

    client = redis_module.from_url(REDIS_URL)
    client.flushdb()
    yield client
    client.flushdb()


def _sync_client() -> TestClient:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    app = LightApi(engine=engine, use_test_isolation=True)
    app.register({"/rcitems": RcItem})
    return TestClient(app.build_app())


def test_sync_get_is_served_from_real_redis_after_first_miss(redis_client):
    client = _sync_client()
    client.post("/rcitems", json={"name": "first"})

    miss = client.get("/rcitems")
    assert miss.status_code == 200
    assert len(redis_client.keys("lightapi:*")) == 1

    hit = client.get("/rcitems")
    assert hit.status_code == 200
    assert hit.json() == miss.json()


def test_sync_post_invalidates_the_real_redis_key(redis_client):
    client = _sync_client()
    client.post("/rcitems", json={"name": "first"})
    client.get("/rcitems")  # populate the cache
    assert redis_client.keys("lightapi:*")

    client.post("/rcitems", json={"name": "second"})

    assert redis_client.keys("lightapi:*") == []


async def test_async_cache_hit_and_invalidation_with_real_redis(redis_client):
    engine = create_async_engine("sqlite+aiosqlite://")
    # use_test_isolation avoids the process-wide global metadata, which by this
    # point in a full run also holds the Postgres-typed reflection tests'
    # tables (JSONB etc.) -- create_all against this sqlite engine would then
    # try to build those too and fail to compile them for sqlite.
    app = LightApi(engine=engine, mode="async", use_test_isolation=True)
    app.register({"/rcaitems": RcaItem})
    # Create the table properly on this loop first. LightApi's own async table
    # creation (triggered by build_app() below) does it via asyncio.run() in a
    # worker thread, which is the same pre-existing bug as B19: harmless here
    # once the table already exists (its own attempt just warns and no-ops).
    async with engine.begin() as conn:
        await conn.run_sync(app._session_manager.metadata.create_all)
    starlette_app = app.build_app()

    async with AsyncClient(
        transport=ASGITransport(app=starlette_app), base_url="http://test"
    ) as client:
        await client.post("/rcaitems", json={"name": "first"})
        miss = await client.get("/rcaitems")
        assert redis_client.keys("lightapi:*")

        async with engine.begin() as conn:
            await conn.execute(text("UPDATE rcaitems SET name = 'changed in db'"))

        hit = await client.get("/rcaitems")
        assert hit.json() == miss.json()  # served from cache, not the changed row

        await client.post("/rcaitems", json={"name": "second"})
        assert redis_client.keys("lightapi:*") == []

    await engine.dispose()


def test_redis_unreachable_warns_but_requests_still_succeed(monkeypatch):
    monkeypatch.setenv("LIGHTAPI_REDIS_URL", "redis://127.0.0.1:1/0")  # nothing listens
    from lightapi import cache as cache_module

    cache_module._default_backend.cache_clear()
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    app = LightApi(engine=engine, use_test_isolation=True)
    app.register({"/rcdownitems": RcItem})

    with pytest.warns(RuntimeWarning, match="Redis"):
        client = TestClient(app.build_app())

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        created = client.post("/rcdownitems", json={"name": "x"})
        listed = client.get("/rcdownitems")

    assert created.status_code == 201
    assert listed.status_code == 200
