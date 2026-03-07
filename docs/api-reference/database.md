---
title: Database API Reference
description: Engine setup, session helpers, and reflection in LightAPI v2
---

# Database API Reference

LightAPI delegates all database access to SQLAlchemy 2.x. This page covers the engine setup, session context managers, and reflection helpers exposed by LightAPI.

## Engine

Pass any SQLAlchemy engine (sync or async) to `LightApi`:

```python
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine
from lightapi import LightApi

# Sync
engine = create_engine("sqlite:///app.db")

# Async
engine = create_async_engine("postgresql+asyncpg://user:pass@localhost/db")

app = LightApi(engine=engine)
```

LightAPI detects whether the engine is async and automatically selects the correct session strategy for all built-in CRUD operations.

## `get_sync_session(engine)`

A context manager that yields a `sqlalchemy.orm.Session` with automatic commit and rollback:

```python
from lightapi import get_sync_session
from sqlalchemy import create_engine, select

engine = create_engine("sqlite:///app.db")

with get_sync_session(engine) as session:
    rows = session.execute(select(SomeModel)).scalars().all()
```

- Commits on successful exit.
- Rolls back and re-raises on exception.

**Signature:**

```python
def get_sync_session(engine: Engine) -> ContextManager[Session]: ...
```

## `get_async_session(engine)`

An async context manager that yields a `sqlalchemy.ext.asyncio.AsyncSession`:

```python
from lightapi import get_async_session
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import select

engine = create_async_engine("sqlite+aiosqlite:///app.db")

async with get_async_session(engine) as session:
    rows = (await session.execute(select(SomeModel))).scalars().all()
```

- Commits on successful exit.
- Rolls back and re-raises on exception.
- Uses `expire_on_commit=False` so objects remain usable after commit.

**Signature:**

```python
async def get_async_session(engine: AsyncEngine) -> AsyncContextManager[AsyncSession]: ...
```

## `RestEndpoint._get_engine()`

Returns the underlying sync engine. When an `AsyncEngine` is used, this unwraps to its `.sync_engine`:

```python
engine = self._get_engine()  # always a sync Engine
```

## `RestEndpoint._get_async_engine()`

Returns the raw `AsyncEngine`. Raises `RuntimeError` if the app was not started with an async engine:

```python
engine = self._get_async_engine()  # AsyncEngine
```

## Table creation

Tables are created automatically when `app.register(mapping)` is called:

- **Sync engine**: `metadata.create_all(engine)` is called synchronously during `register()`.
- **Async engine**: table creation is deferred to Starlette's `on_startup` lifecycle hook, where `await conn.run_sync(metadata.create_all)` is called inside the running event loop.

LightApi creates tables automatically when you call `run()` or `build_app()` — you never need to create them yourself.

## Table reflection

Set `Meta.reflect = True` on a `RestEndpoint` to map it to an existing database table:

```python
class LegacyUserEndpoint(RestEndpoint):
    class Meta:
        reflect = True
        table = "users"   # existing table name
```

- No field annotations are required.
- LightAPI reads the column definitions at startup and auto-generates Pydantic schemas.
- For async engines, reflection uses `await conn.run_sync(metadata.reflect)`.

## Supported dialects

| Database | Sync URL scheme | Async URL scheme |
|----------|-----------------|------------------|
| SQLite | `sqlite:///` | `sqlite+aiosqlite:///` |
| PostgreSQL | `postgresql://` | `postgresql+asyncpg://` |
| MySQL | `mysql+pymysql://` | `mysql+aiomysql://` |

Install async extras:

```bash
uv add "lightapi[async]"
# installs: sqlalchemy[asyncio], asyncpg, aiosqlite, greenlet
```
