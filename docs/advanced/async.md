---
title: Async Support
description: Full async I/O with AsyncEngine, async querysets, background tasks, and async middleware
---

# Async Support

LightAPI's async support is **opt-in** and activated by one change: passing a `create_async_engine` instead of `create_engine`. Once detected, LightAPI uses `AsyncSession` for every request. Sync endpoints continue to work unchanged on the same app instance.

---

## Installation

```bash
uv add "lightapi[async]"
# or: pip install "lightapi[async]"
```

This installs `sqlalchemy[asyncio]`, `asyncpg`, `aiosqlite`, and `greenlet`.

---

## Enabling Async I/O

=== "PostgreSQL"

    ```python
    from sqlalchemy.ext.asyncio import create_async_engine
    from lightapi import LightApi

    engine = create_async_engine(
        "postgresql+asyncpg://user:pass@localhost:5432/mydb"
    )
    app = LightApi(engine=engine)
    ```

=== "SQLite (testing / dev)"

    ```python
    from sqlalchemy.ext.asyncio import create_async_engine
    from lightapi import LightApi

    engine = create_async_engine("sqlite+aiosqlite:///dev.db")
    app = LightApi(engine=engine)
    ```

LightAPI validates at startup that the async driver (e.g. `asyncpg`, `aiosqlite`) is installed and raises `ConfigurationError` with an install hint if it is not.

---

## Async Queryset

Define `async def queryset` to scope the base query with async I/O or request-level context:

```python
from sqlalchemy import select
from starlette.requests import Request
from lightapi import RestEndpoint, Field
from lightapi.auth import IsAuthenticated
from lightapi.config import Authentication

class OrderEndpoint(RestEndpoint):
    amount: float = Field(ge=0)
    status: str = Field(default="pending")

    class Meta:
        authentication = Authentication(permission=IsAuthenticated)

    async def queryset(self, request: Request):
        user_id = request.state.user["sub"]
        return (
            select(type(self)._model_class)
            .where(type(self)._model_class.owner_id == user_id)
        )
```

LightAPI uses `asyncio.iscoroutinefunction` to detect async querysets and awaits them automatically. A plain `def queryset` still works on an async app.

---

## Async Method Overrides

Override individual HTTP verbs with `async def`:

```python
import json
from starlette.requests import Request
from starlette.responses import Response
from lightapi import RestEndpoint, Field

class ProductEndpoint(RestEndpoint):
    name: str = Field(min_length=1)
    price: float = Field(ge=0)

    async def post(self, request: Request) -> Response:
        data = json.loads(await request.body())
        # custom pre-processing, enrichment, external calls …
        data["created_by"] = request.state.user["sub"]
        return await self._create_async(data)

    async def get(self, request: Request) -> Response:
        # custom filtering beyond Meta.filtering
        return await self._list_async(request)
```

!!! note "Detection"
    LightAPI inspects each override with `asyncio.iscoroutinefunction`. Sync overrides (`def post`) and async overrides (`async def post`) coexist on the same app without configuration.

### Built-in Async CRUD Helpers

Every `RestEndpoint` exposes these helpers when using an async engine:

| Method | Description |
|---|---|
| `await self._list_async(request)` | Paginated `SELECT *` with filter/ordering |
| `await self._retrieve_async(request, pk)` | `SELECT WHERE id=pk` |
| `await self._create_async(data: dict)` | `INSERT`, flush, refresh, serialize → `JSONResponse(201)` |
| `await self._update_async(data, pk, partial=False)` | Optimistic-lock `UPDATE` → `200` or `409` |
| `await self._destroy_async(request, pk)` | `DELETE` → `204` or `404` |

---

## Background Tasks

`self.background(fn, *args, **kwargs)` registers a post-response task via Starlette's `BackgroundTasks`. The task runs after the HTTP response is sent to the client.

```python
import json
from starlette.requests import Request
from starlette.responses import Response
from lightapi import RestEndpoint, Field

async def send_confirmation(order_id: int, email: str) -> None:
    # async I/O — send email, push notification, audit log …
    ...

def write_sync_log(order_id: int) -> None:
    # sync callables are also accepted
    ...

class OrderEndpoint(RestEndpoint):
    amount: float = Field(ge=0)
    email: str = Field(min_length=5)

    async def post(self, request: Request) -> Response:
        data = json.loads(await request.body())
        resp = await self._create_async(data)
        if resp.status_code == 201:
            body = json.loads(resp.body)
            self.background(send_confirmation, body["id"], data["email"])
            self.background(write_sync_log, body["id"])
        return resp
```

!!! warning "Outside request context"
    Calling `self.background()` outside a request handler raises `RuntimeError: background() called outside request handler`.

Both `def` and `async def` callables are accepted by Starlette's `BackgroundTasks`.

---

## Async Middleware

`Middleware.process` can be `async def`. LightAPI detects and awaits it automatically. Sync and async middleware coexist in the same list:

```python
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from lightapi.core import Middleware

class AsyncAuditMiddleware(Middleware):
    """Logs every request to an async store before the endpoint runs."""

    async def process(self, request: Request, response: Response | None):
        if response is None:
            await _write_audit(request.method, str(request.url))
        return None

class SyncHeaderMiddleware(Middleware):
    """Appends a response header (sync — no await needed)."""

    def process(self, request: Request, response: Response | None):
        if response is not None:
            response.headers["X-Powered-By"] = "lightapi"
        return None

class RateLimitMiddleware(Middleware):
    """Short-circuits the request if the client is rate-limited."""

    async def process(self, request: Request, response: Response | None):
        if response is None:
            if await _is_rate_limited(request.client.host):
                return JSONResponse({"detail": "rate limit exceeded"}, status_code=429)
        return None
```

```python
app = LightApi(
    engine=engine,
    middlewares=[RateLimitMiddleware, AsyncAuditMiddleware, SyncHeaderMiddleware],
)
```

Pre-request order: `RateLimitMiddleware → AsyncAuditMiddleware → SyncHeaderMiddleware`.  
Post-request order (reversed): `SyncHeaderMiddleware → AsyncAuditMiddleware → RateLimitMiddleware`.

---

## Sync Endpoints on an Async App

Endpoints that still use sync querysets or sync method overrides work without modification:

```python
from sqlalchemy import select
from starlette.requests import Request
from lightapi import RestEndpoint, Field

class TagEndpoint(RestEndpoint):
    label: str = Field(min_length=1)

    def queryset(self, request: Request):      # sync — unchanged
        return select(type(self)._model_class)
```

LightAPI dispatches to the async path (`_list_async`) when the engine is async, regardless of whether `queryset` is sync or async.

---

## Session Helpers

`get_sync_session` and `get_async_session` are exported from the top-level `lightapi` package for use outside of endpoint methods:

```python
from lightapi import get_sync_session, get_async_session

# --- Sync ---
from sqlalchemy import create_engine, select
engine = create_engine("sqlite:///app.db")

with get_sync_session(engine) as session:
    rows = session.execute(select(MyModel)).scalars().all()

# --- Async ---
from sqlalchemy.ext.asyncio import create_async_engine
async_engine = create_async_engine("postgresql+asyncpg://...")

async with get_async_session(async_engine) as session:
    rows = (await session.execute(select(MyModel))).scalars().all()
```

Both managers commit on clean exit and roll back + re-raise on exception.

---

## Database Reflection with AsyncEngine

`Meta.reflect = True` works with async engines — LightAPI automatically uses `conn.run_sync` internally:

```python
class LegacyOrderEndpoint(RestEndpoint):
    class Meta:
        reflect = True
        table_name = "legacy_orders"   # existing table
```

```python
engine = create_async_engine("postgresql+asyncpg://...")
app = LightApi(engine=engine)
app.register({"/orders": LegacyOrderEndpoint})
app.run()
```

`ConfigurationError` is raised at `app.register()` time if the table does not exist.

---

## Startup Validation

When an `AsyncEngine` is passed, `app.run()` validates:

1. `sqlalchemy[asyncio]` is installed — raises `ConfigurationError` with install hint if not.
2. The dialect's async driver (`asyncpg`, `aiosqlite`, `aiomysql`) is importable — raises `ConfigurationError` with the correct `uv add` command if not.

---

## Table Creation Lifecycle

For async engines, `metadata.create_all` runs inside Starlette's `on_startup` event so it executes within the same event loop that will serve requests (rather than a throwaway thread loop, which would invalidate asyncpg's connection pool).

`build_app()` registers the startup handler automatically:

```python
starlette_app = app.build_app()   # on_startup=[_async_create_tables] added
```

---

## Testing

Use `pytest-asyncio` and `httpx.AsyncClient` with an in-memory `aiosqlite` engine.

**`pytest.ini`**:

```ini
[pytest]
asyncio_mode = auto
```

**Fixture pattern**:

```python
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from pydantic import Field
from lightapi import LightApi, RestEndpoint
from lightapi.auth import AllowAny
from lightapi.config import Authentication

@pytest_asyncio.fixture
async def client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    class Widget(RestEndpoint):
        name: str = Field(min_length=1)
        class Meta:
            authentication = Authentication(permission=AllowAny)

    app = LightApi(engine=engine)
    app.register({"/widgets": Widget})
    async with AsyncClient(
        transport=ASGITransport(app=app.build_app()),
        base_url="http://test",
    ) as c:
        yield c

async def test_create(client):
    r = await client.post("/widgets", json={"name": "bolt"})
    assert r.status_code == 201
    assert r.json()["name"] == "bolt"

async def test_list(client):
    await client.post("/widgets", json={"name": "nut"})
    r = await client.get("/widgets")
    assert r.status_code == 200
    assert len(r.json()["results"]) == 1

async def test_optimistic_lock_conflict(client):
    r = await client.post("/widgets", json={"name": "pin"})
    pk, v = r.json()["id"], r.json()["version"]
    await client.put(f"/widgets/{pk}", json={"name": "pin-v2", "version": v})
    r = await client.put(f"/widgets/{pk}", json={"name": "pin-v3", "version": v})
    assert r.status_code == 409
```

---

## Full Example

See [`examples/postgres_full.py`](https://github.com/iklobato/LightAPI/blob/main/examples/postgres_full.py) for a runnable example demonstrating:

- Async PostgreSQL engine (`asyncpg`)
- `async def queryset` with a `WHERE active=True` scope
- `async def post` with `self.background()` for post-response audit logging
- Sync `def queryset` endpoint (`Tag`) coexisting on the same app
- Mixed `AsyncAuditMiddleware` (async) + `RequestLogMiddleware` (sync)
- Filtering (`FieldFilter` with boolean type coercion), ordering, pagination, serializer
- Optimistic locking: correct version → 200, stale version → 409
- DELETE: 204 on first call, 404 on second

Run it:

```bash
docker run -d --name psql -p 5432:5432 \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_DB=postgres \
  postgres

uv add "lightapi[async]"
uv run python examples/postgres_full.py
```
