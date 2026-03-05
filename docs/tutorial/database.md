---
title: Database Integration
description: Engines, sessions, reflection, and async database setup in LightAPI v2
---

# Database Integration

LightAPI v2 wraps SQLAlchemy 2.x and supports any database that SQLAlchemy supports — SQLite, PostgreSQL, MySQL, and more. Both synchronous and asynchronous engines are supported.

## Creating an engine

### Synchronous

```python
from sqlalchemy import create_engine

# SQLite
engine = create_engine("sqlite:///app.db")

# PostgreSQL (psycopg2)
engine = create_engine("postgresql://user:pass@localhost:5432/mydb")

# MySQL
engine = create_engine("mysql+pymysql://user:pass@localhost:3306/mydb")
```

### Asynchronous

Install the async extras first:

```bash
uv add "lightapi[async]"
```

```python
from sqlalchemy.ext.asyncio import create_async_engine

# PostgreSQL (asyncpg)
engine = create_async_engine("postgresql+asyncpg://user:pass@localhost:5432/mydb")

# SQLite (aiosqlite — useful for tests)
engine = create_async_engine("sqlite+aiosqlite:///app.db")
```

Pass either engine type to `LightApi` — it detects async engines automatically:

```python
from lightapi import LightApi

app = LightApi(engine=engine)
```

## Table creation

When you call `app.register(mapping)`, LightAPI creates any missing tables automatically using the SQLAlchemy `MetaData`. For async engines, table creation runs inside Starlette's `on_startup` lifecycle hook, so the event loop is already running when it executes.

You never need to call `Base.metadata.create_all()` manually.

## Connecting to an existing database (reflection)

Set `Meta.reflect = True` to map a `RestEndpoint` to an existing table without declaring columns:

```python
from lightapi import LightApi, RestEndpoint

class UserEndpoint(RestEndpoint):
    class Meta:
        reflect = True
        table = "users"   # exact table name in the database
```

LightAPI will reflect the table schema at startup and generate a Pydantic read schema from the discovered columns.

## Session management

LightAPI manages sessions internally — you do not need to create sessions for normal CRUD operations. If you need a session inside a method override, use the provided helpers:

### Synchronous session

```python
from lightapi import get_sync_session

class MyEndpoint(RestEndpoint):
    name: str

    def get(self, request):
        engine = self._get_engine()
        with get_sync_session(engine) as session:
            rows = session.execute(...).all()
        return {"results": rows}
```

### Asynchronous session

```python
from lightapi import get_async_session

class MyEndpoint(RestEndpoint):
    name: str

    async def get(self, request):
        engine = self._get_async_engine()
        async with get_async_session(engine) as session:
            rows = (await session.execute(...)).all()
        return {"results": rows}
```

Both context managers automatically commit on success and roll back on exception.

## Supported databases

| Database | Sync driver | Async driver |
|----------|-------------|--------------|
| SQLite | built-in | `aiosqlite` |
| PostgreSQL | `psycopg2` | `asyncpg` |
| MySQL | `pymysql` | `aiomysql` |

## Connection pooling

Pass SQLAlchemy pool options to `create_engine`:

```python
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    "postgresql://user:pass@localhost/mydb",
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)
```

For async engines:

```python
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine(
    "postgresql+asyncpg://user:pass@localhost/mydb",
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)
```

## Environment variable–driven database URL

```python
import os
from sqlalchemy import create_engine
from lightapi import LightApi

engine = create_engine(os.environ["DATABASE_URL"])
app = LightApi(engine=engine)
```

Or in YAML (declarative format):

```yaml
database:
  url: "${DATABASE_URL}"
```

Legacy flat form also works:

```yaml
database:
  url: "${DATABASE_URL}"
```

## Foreign keys and relationships

Declare foreign keys using the `foreign_key` extra kwarg on `Field`:

```python
from typing import Optional
from lightapi import RestEndpoint, Field

class CommentEndpoint(RestEndpoint):
    body: str
    post_id: int = Field(foreign_key="posts.id")
    author_id: Optional[int] = Field(None, foreign_key="users.id")
```

LightAPI creates the foreign key constraint in the database. For fetching related records, write a custom `queryset()` method using SQLAlchemy joins.
