"""LightAPI Example 11 - Mixed Sync/Async Endpoints.

Demonstrates:
- Sync endpoint on async app (automatic run_sync)
- async def queryset endpoint
- def queryset (sync) endpoint
- Same app serving both sync and async endpoints

Notes:
    Uses SQLite+aiosqlite by default. Swap DATABASE_URL for
    `postgresql+asyncpg://...` to run against PostgreSQL.

Run with:
    python examples/11_mixed_sync_async.py

Then try:
    # Async endpoint (uses async def queryset)
    curl http://localhost:8000/async-books

    # Sync endpoint (uses def queryset, automatically runs in thread pool)
    curl http://localhost:8000/sync-books
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from lightapi import HttpMethod, LightApi, RestEndpoint
from lightapi.fields import Field

DATABASE_URL = "sqlite+aiosqlite:///:memory:"


class AsyncBookEndpoint(RestEndpoint, HttpMethod.GET, HttpMethod.POST):
    """Async endpoint - uses async def queryset."""

    title: str = Field(min_length=1)
    author: str = Field(min_length=1)

    async def queryset(self, request):
        """Async queryset - uses await."""
        return select(type(self)._model_class)


class SyncBookEndpoint(RestEndpoint, HttpMethod.GET, HttpMethod.POST):
    """Sync endpoint on async app - automatically runs in thread pool."""

    title: str = Field(min_length=1)
    author: str = Field(min_length=1)

    def queryset(self, request):
        """Sync queryset - LightAPI automatically runs this in a thread pool."""
        return select(type(self)._model_class)


if __name__ == "__main__":
    engine = create_async_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    app = LightApi(engine=engine, mode="async")
    app.register(
        {
            "/async-books": AsyncBookEndpoint,
            "/sync-books": SyncBookEndpoint,
        }
    )
    app.run(host="0.0.0.0", port=8000, debug=True)
