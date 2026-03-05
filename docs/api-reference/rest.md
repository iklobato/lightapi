---
title: REST API Reference
description: RestEndpoint class, Meta configuration, and async CRUD helpers
---

# REST API Reference

`RestEndpoint` is the single building block of every LightAPI application. A subclass simultaneously acts as the **SQLAlchemy ORM model**, the **Pydantic v2 schema**, and the **HTTP endpoint handler**.

---

## `RestEndpoint`

```python
from lightapi import RestEndpoint, Field
```

### Declaring Fields

```python
from typing import Optional
from decimal import Decimal
from lightapi import RestEndpoint, Field

class ProductEndpoint(RestEndpoint):
    name:        str            = Field(min_length=1, max_length=200)
    price:       Decimal        = Field(ge=0, decimal_places=2)
    category:    str            = Field(min_length=1)
    description: Optional[str] = None
    in_stock:    bool           = Field(default=True)
    supplier_id: int            = Field(foreign_key="suppliers.id")
```

**Python type → SQLAlchemy column mapping:**

| Python annotation | Column type | Nullable |
|---|---|---|
| `str` | `VARCHAR` | No |
| `Optional[str]` | `VARCHAR` | Yes |
| `int` | `INTEGER` | No |
| `Optional[int]` | `INTEGER` | Yes |
| `float` | `FLOAT` | No |
| `bool` | `BOOLEAN` | No |
| `datetime` | `DATETIME` | No |
| `Decimal` | `NUMERIC(scale=N)` | No |
| `UUID` | `UUID` | No |

**LightAPI-specific `Field()` kwargs** (passed in `json_schema_extra`):

| Kwarg | Effect |
|---|---|
| `foreign_key="table.col"` | Adds `ForeignKey` constraint |
| `unique=True` | Adds `UNIQUE` constraint |
| `index=True` | Adds a database index |
| `exclude=True` | Field is excluded from DB and schema entirely |
| `decimal_places=N` | Sets `Numeric(scale=N)` (for `Decimal` fields) |

### Auto-injected Columns

Every `RestEndpoint` subclass automatically receives these columns:

| Column | Type | Value |
|---|---|---|
| `id` | `Integer` PK | autoincrement |
| `created_at` | `DateTime` | `utcnow` on insert |
| `updated_at` | `DateTime` | `utcnow` on insert and update |
| `version` | `Integer` | `1` on insert; incremented on `PUT`/`PATCH` |

These are excluded from create/update input schemas but always included in responses.

---

## `Meta` Inner Class

```python
class MyEndpoint(RestEndpoint):
    class Meta:
        authentication = Authentication(backend=..., permission=...)
        filtering      = Filtering(backends=[...], fields=[...], search=[...], ordering=[...])
        pagination     = Pagination(style="page_number"|"cursor", page_size=20)
        serializer     = Serializer(fields=[...]) | Serializer(read=[...], write=[...])
        cache          = Cache(ttl=60)
        reflect        = False | True | "partial"
        table          = "custom_table_name"
        table_name     = "custom_table_name"   # alias for table
```

---

## Sync CRUD Methods

Override these methods to customise sync behaviour. Used when a sync engine is passed (or when the override is `def`, not `async def`, even on an async engine app):

| Method | Signature | Default behaviour |
|---|---|---|
| `queryset` | `(self, request)` | `select(cls._model_class)` |
| `list` | `(self, request)` | Paginated `SELECT *` |
| `retrieve` | `(self, request, pk)` | `SELECT WHERE id=pk` |
| `create` | `(self, data)` | `INSERT RETURNING` |
| `update` | `(self, data, pk, partial)` | Optimistic-lock `UPDATE` |
| `destroy` | `(self, request, pk)` | `DELETE WHERE id=pk` |

---

## Async CRUD Helpers

When an `AsyncEngine` is passed to `LightApi`, LightAPI dispatches through these internal async methods. You can call them directly from `async def` overrides:

| Helper | Return | Description |
|---|---|---|
| `await self._list_async(request)` | `JSONResponse` | Paginated list with filter/ordering |
| `await self._retrieve_async(request, pk)` | `JSONResponse` / 404 | Single row |
| `await self._create_async(data: dict)` | `JSONResponse(201)` | INSERT + flush + refresh |
| `await self._update_async(data, pk, partial=False)` | `JSONResponse` / 409 / 404 | Optimistic-lock UPDATE |
| `await self._destroy_async(request, pk)` | `Response(204)` / 404 | DELETE |
| `self.background(fn, *args, **kwargs)` | `None` | Schedule a post-response task |

### Example: Async Override with Background Task

```python
import json
from starlette.requests import Request
from starlette.responses import Response
from lightapi import RestEndpoint, Field

async def on_create(item_id: int) -> None:
    ...   # send notification, write audit log

class OrderEndpoint(RestEndpoint):
    amount: float = Field(ge=0)

    async def post(self, request: Request) -> Response:
        data = json.loads(await request.body())
        resp = await self._create_async(data)
        if resp.status_code == 201:
            self.background(on_create, json.loads(resp.body)["id"])
        return resp
```

---

## HTTP Method Overrides

Define `get`, `post`, `put`, `patch`, or `delete` as either sync or async — LightAPI detects and dispatches accordingly:

```python
class MyEndpoint(RestEndpoint):
    name: str = Field(min_length=1)

    # Sync override
    def get(self, request):
        return self.list(request)

    # Async override — detected via asyncio.iscoroutinefunction
    async def post(self, request):
        import json
        return await self._create_async(json.loads(await request.body()))
```

---

## HttpMethod Mixins

Restrict which HTTP verbs are available:

```python
from lightapi import RestEndpoint, HttpMethod, Field

class ReadOnlyEndpoint(RestEndpoint, HttpMethod.GET):
    name: str = Field(min_length=1)

class CreateOnlyEndpoint(RestEndpoint, HttpMethod.POST):
    name: str = Field(min_length=1)

class FullCRUDEndpoint(
    RestEndpoint,
    HttpMethod.GET, HttpMethod.POST,
    HttpMethod.PUT, HttpMethod.PATCH, HttpMethod.DELETE,
):
    name: str = Field(min_length=1)
```

Unregistered methods return `405 Method Not Allowed` with an `Allow` header listing the registered verbs.

---

## Class Attributes

| Attribute | Type | Description |
|---|---|---|
| `_model_class` | `type` | SQLAlchemy-mapped class |
| `_meta` | `dict` | Parsed `Meta` configuration |
| `_allowed_methods` | `set[str]` | Registered HTTP verbs |
| `__schema_create__` | Pydantic model | Input schema for POST/PUT/PATCH |
| `__schema_read__` | Pydantic model | Output schema for GET responses |
| `_background` | `BackgroundTasks \| None` | Starlette BackgroundTasks (set per-request) |
| `_current_request` | `Request \| None` | Current request (set per-request) |

---

## Error Responses

| Scenario | Status | Body |
|---|---|---|
| Validation failure | `422` | `{"detail": [...pydantic errors...]}` |
| Not found | `404` | `{"detail": "not found"}` |
| Optimistic lock conflict | `409` | `{"detail": "version conflict"}` |
| Auth failure | `401` | `{"detail": "Authentication credentials invalid."}` |
| Permission denied | `403` | `{"detail": "You do not have permission to perform this action."}` |
| Method not registered | `405` | `{"detail": "Method Not Allowed. Allowed: GET, POST"}` |

---

## Session Helpers

Exported from `lightapi` for use outside of endpoint methods:

```python
from lightapi import get_sync_session, get_async_session
```

### `get_sync_session(engine)`

Context manager; commits on clean exit, rolls back on exception.

```python
from sqlalchemy import create_engine, select
from lightapi import get_sync_session

engine = create_engine("sqlite:///app.db")
with get_sync_session(engine) as session:
    rows = session.execute(select(MyModel)).scalars().all()
```

### `get_async_session(engine)`

Async context manager; `await commit` on clean exit, `await rollback` on exception.

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from lightapi import get_async_session

engine = create_async_engine("postgresql+asyncpg://...")
async with get_async_session(engine) as session:
    rows = (await session.execute(select(MyModel))).scalars().all()
```
