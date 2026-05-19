"""LightAPI Example 10 - Async Endpoints.

Demonstrates:
- Async engine (create_async_engine)
- mode="async" parameter
- async def queryset for async query execution
- async def post for async operations
- Full async CRUD operations

Notes:
    Uses SQLite+aiosqlite by default. Swap DATABASE_URL for
    `postgresql+asyncpg://...` to run against PostgreSQL.

Run with:
    python examples/10_async.py

Then try:
    # All CRUD operations work the same as sync
    curl http://localhost:8000/books
    curl -X POST http://localhost:8000/books \
        -H 'Content-Type: application/json' \
        -d '{"title":"Async Book","author":"Author","price":25}'
"""

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from lightapi import HttpMethod, LightApi, RestEndpoint
from lightapi.fields import Field

DATABASE_URL = "sqlite+aiosqlite:///:memory:"


class BookEndpoint(
    RestEndpoint,
    HttpMethod.GET,
    HttpMethod.POST,
    HttpMethod.PUT,
    HttpMethod.PATCH,
    HttpMethod.DELETE,
):
    """Async endpoint with full CRUD."""

    title: str = Field(min_length=1)
    author: str = Field(min_length=1)
    price: float = Field(ge=0.0)

    async def queryset(self, request):
        """Async queryset - use await when querying."""
        from sqlalchemy import select

        return select(type(self)._model_class)


if __name__ == "__main__":
    engine = create_async_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    app = LightApi(engine=engine, mode="async")
    app.register({"/books": BookEndpoint})
    app.run(host="0.0.0.0", port=8000, debug=True)
