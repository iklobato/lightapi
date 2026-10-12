"""Fixtures for the tests that need a real Postgres and a real Redis.

Every test here is @pytest.mark.integration and skips (not errors) when the
required environment variable is not set, so the normal test run is
unaffected:

    export LIGHTAPI_TEST_PG_SYNC="postgresql+psycopg2://postgres:test@127.0.0.1:55432/lightapi"
    export LIGHTAPI_TEST_PG_ASYNC="postgresql+asyncpg://postgres:test@127.0.0.1:55432/lightapi"
    export LIGHTAPI_REDIS_URL="redis://127.0.0.1:56379/0"
    uv run --frozen --extra dev pytest tests/integration -q -m integration
"""

from __future__ import annotations

import os

import pytest
import pytest_asyncio
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine

PG_SYNC_URL = os.environ.get("LIGHTAPI_TEST_PG_SYNC")
PG_ASYNC_URL = os.environ.get("LIGHTAPI_TEST_PG_ASYNC")
REDIS_URL = os.environ.get("LIGHTAPI_REDIS_URL")

# Each test module sets `pytestmark = requires_pg_sync` (etc.); a plain
# @pytest.mark.skipif does not carry the "integration" marker on its own, so
# it is bundled into this list.
requires_pg_sync = [
    pytest.mark.integration,
    pytest.mark.skipif(not PG_SYNC_URL, reason="LIGHTAPI_TEST_PG_SYNC is not set"),
]
requires_pg_async = [
    pytest.mark.integration,
    pytest.mark.skipif(not PG_ASYNC_URL, reason="LIGHTAPI_TEST_PG_ASYNC is not set"),
]
requires_redis = [
    pytest.mark.integration,
    pytest.mark.skipif(not REDIS_URL, reason="LIGHTAPI_REDIS_URL is not set"),
]


@pytest.fixture
def pg_engine():
    """A sync Postgres engine. Endpoints map with use_test_isolation, so
    concurrent runs get distinct table names (SessionManager.table_name_for)
    instead of colliding on a shared 'items' table."""
    engine = create_engine(PG_SYNC_URL)
    yield engine
    engine.dispose()


@pytest_asyncio.fixture
async def pg_async_engine():
    """An async Postgres engine (asyncpg)."""
    engine = create_async_engine(PG_ASYNC_URL)
    yield engine
    await engine.dispose()


@pytest.fixture
def redis_url() -> str:
    return REDIS_URL
