---
title: Endpoint Classes
description: Deep dive into RestEndpoint — fields, Meta, method overrides, and HttpMethod mixins
---

# Endpoint Classes

`RestEndpoint` is the foundation of every LightAPI v2 application. This page covers every aspect of defining and customising endpoint classes.

## Defining an endpoint

Annotate class-level attributes with Python types. LightAPI's metaclass turns them into SQLAlchemy columns, Pydantic schema fields, and HTTP handlers simultaneously.

```python
from typing import Optional
from decimal import Decimal
from lightapi import RestEndpoint, Field

class ProductEndpoint(RestEndpoint):
    name: str = Field(min_length=1, max_length=100)
    slug: str = Field(min_length=1, max_length=100, unique=True, index=True)
    price: Decimal = Field(gt=0, decimal_places=2)
    stock: int = Field(ge=0, default=0)
    description: Optional[str] = None
    active: Optional[bool] = Field(None, default=True)
```

## Type map

| Python annotation | SQLAlchemy column type | Nullable |
|-------------------|----------------------|----------|
| `str` | `String` | No |
| `int` | `Integer` | No |
| `float` | `Float` | No |
| `bool` | `Boolean` | No |
| `Decimal` | `Numeric(scale=N)` | No |
| `datetime.datetime` | `DateTime` | No |
| `Optional[T]` | same as `T`, `nullable=True` | Yes |

## Auto-injected columns

Every `RestEndpoint` subclass automatically gets:

| Column | Type | Notes |
|--------|------|-------|
| `id` | `Integer` PK | Never declared, never writeable |
| `created_at` | `DateTime` | Set on INSERT |
| `updated_at` | `DateTime` | Set on INSERT and UPDATE |
| `version` | `Integer` | Optimistic locking — must be included in PUT/PATCH |

## `Field()` extra kwargs

Beyond Pydantic's built-in constraints, LightAPI processes:

| Kwarg | Description |
|-------|-------------|
| `unique=True` | `UNIQUE` constraint |
| `index=True` | Database index |
| `foreign_key="table.col"` | Foreign key reference |
| `decimal_places=N` | Precision for `Decimal` |
| `exclude=True` | Skip column creation; field is schema-only |
| `default=<value>` | Column-level default |

## `Meta` inner class

Control authentication, filtering, pagination, serialisation, caching, and more:

```python
from lightapi import (
    RestEndpoint,
    Authentication, JWTAuthentication, IsAuthenticated,
    Filtering, FieldFilter, SearchFilter, OrderingFilter,
    Pagination, Serializer, Cache,
)

class ArticleEndpoint(RestEndpoint):
    title: str
    body: str
    published: bool

    class Meta:
        authentication = Authentication(
            backend=JWTAuthentication,
            permission=IsAuthenticated,
        )
        filtering = Filtering(
            backends=[FieldFilter, SearchFilter, OrderingFilter],
            fields=["published"],
            search=["title", "body"],
            ordering=["title", "created_at"],
        )
        pagination = Pagination(style="page_number", page_size=20)
        serializer = Serializer(read=["id", "title", "published"])
        cache = Cache(ttl=60)
```

| `Meta` attribute | Type | Description |
|-----------------|------|-------------|
| `authentication` | `Authentication` | Auth backend + permission class/dict |
| `filtering` | `Filtering` | Filter backends and field whitelists |
| `pagination` | `Pagination` | Pagination style and page size |
| `serializer` | `Serializer` | Read/write field sets |
| `cache` | `Cache` | Redis TTL and vary-on params |
| `reflect` | `bool` | Reflect an existing table instead of creating |
| `table` | `str` | Override the inferred table name |

## HTTP method mixins

Use `HttpMethod` mixins to expose only the verbs you need:

```python
from lightapi import RestEndpoint, HttpMethod

class ReadOnlyEndpoint(RestEndpoint, HttpMethod.GET):
    name: str

class CreateListEndpoint(RestEndpoint, HttpMethod.GET, HttpMethod.POST):
    name: str

class NoDeleteEndpoint(
    RestEndpoint,
    HttpMethod.GET, HttpMethod.POST,
    HttpMethod.PUT, HttpMethod.PATCH,
):
    name: str
```

Requests to disallowed methods return `405 Method Not Allowed`.

Available mixins: `HttpMethod.GET`, `HttpMethod.POST`, `HttpMethod.PUT`, `HttpMethod.PATCH`, `HttpMethod.DELETE`.

## Method overrides

Override any HTTP verb to add custom logic. The signature receives the Starlette `Request` object.

```python
import json
from starlette.responses import JSONResponse
from lightapi import RestEndpoint

class OrderEndpoint(RestEndpoint):
    item: str
    quantity: int

    def post(self, request):
        data = json.loads(request.body())
        if data.get("quantity", 0) > 100:
            return JSONResponse({"detail": "Max quantity is 100"}, status_code=422)
        return self.create(data)
```

For async engines, define `async def` overrides and use the `_async` helpers:

```python
class OrderEndpoint(RestEndpoint):
    item: str
    quantity: int

    async def post(self, request):
        data = json.loads(await request.body())
        if data.get("quantity", 0) > 100:
            return JSONResponse({"detail": "Max quantity is 100"}, status_code=422)
        return await self._create_async(data)
```

### Built-in CRUD methods (sync)

| Method | Description |
|--------|-------------|
| `self.list(request)` | List all rows |
| `self.retrieve(request, pk)` | Get one row by `pk` |
| `self.create(data)` | Insert a row |
| `self.update(request, pk, data)` | Full update with optimistic locking |
| `self.destroy(request, pk)` | Delete a row |

### Built-in async CRUD helpers

| Method | Description |
|--------|-------------|
| `await self._list_async(request)` | Async list |
| `await self._retrieve_async(request, pk)` | Async get by pk |
| `await self._create_async(data)` | Async insert |
| `await self._update_async(request, pk, data)` | Async update |
| `await self._destroy_async(request, pk)` | Async delete |

## queryset scoping

Override `queryset()` to pre-filter the base query for all operations on this endpoint:

```python
from sqlalchemy import select

class PublishedArticleEndpoint(RestEndpoint):
    title: str
    published: bool

    def queryset(self, request):
        cls = type(self)
        return select(cls._model_class).where(cls._model_class.published == True)
```

For async engines:

```python
    async def queryset(self, request):
        cls = type(self)
        return select(cls._model_class).where(cls._model_class.published == True)
```

## Table reflection

Set `Meta.reflect = True` to map an endpoint to an existing database table instead of creating a new one:

```python
from sqlalchemy import create_engine
from lightapi import LightApi, RestEndpoint

class LegacyUserEndpoint(RestEndpoint):
    class Meta:
        reflect = True
        table = "users"   # existing table name

engine = create_engine("postgresql://user:pass@localhost/legacy_db")
app = LightApi(engine=engine)
app.register({"/users": LegacyUserEndpoint})
```

## Table name inference

The table name is derived from the class name by converting to snake_case and pluralising:

| Class name | Table name |
|------------|------------|
| `UserEndpoint` | `users` |
| `BlogPost` | `blog_posts` |
| `Article` | `articles` |

Override with `Meta.table = "custom_name"`.
