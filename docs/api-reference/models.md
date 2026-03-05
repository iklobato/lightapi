---
title: Models API Reference
description: RestEndpoint field declarations, Meta options, and auto-injected columns
---

# Models API Reference

In LightAPI v2 there is no separate "model" layer. Your `RestEndpoint` subclass **is** the model — the same class definition creates the SQLAlchemy table, the Pydantic v2 schemas, and the HTTP handler.

## `RestEndpoint`

```python
from lightapi import RestEndpoint, Field
```

Subclass `RestEndpoint` and declare fields as annotated class attributes:

```python
from typing import Optional
from decimal import Decimal
from lightapi import RestEndpoint, Field

class ProductEndpoint(RestEndpoint):
    name: str = Field(min_length=1, max_length=100)
    slug: str = Field(unique=True, index=True)
    price: Decimal = Field(gt=0, decimal_places=2)
    stock: int = Field(ge=0, default=0)
    description: Optional[str] = None
```

## Supported field types

| Python type | SQLAlchemy column | Nullable |
|-------------|-------------------|----------|
| `str` | `String` | No |
| `int` | `Integer` | No |
| `float` | `Float` | No |
| `bool` | `Boolean` | No |
| `Decimal` | `Numeric(scale=N)` | No |
| `datetime.datetime` | `DateTime` | No |
| `Optional[T]` | same as `T` | Yes (nullable=True) |

## `Field(**kwargs)`

`Field` is a re-export of `pydantic.Field` with additional kwargs processed by LightAPI:

| Kwarg | Type | Description |
|-------|------|-------------|
| `min_length` | `int` | Minimum string length (Pydantic constraint) |
| `max_length` | `int` | Maximum string length (Pydantic constraint) |
| `gt`, `ge`, `lt`, `le` | number | Numeric comparisons (Pydantic) |
| `default` | any | Default value for both schema and column |
| `unique=True` | `bool` | Adds `UNIQUE` constraint to the column |
| `index=True` | `bool` | Creates a database index |
| `foreign_key="table.col"` | `str` | Creates a `ForeignKey` reference |
| `decimal_places=N` | `int` | Precision for `Decimal` columns (default: 10) |
| `exclude=True` | `bool` | Skips column creation — field is schema-only |

## Auto-injected columns

Every `RestEndpoint` subclass automatically gets these columns:

| Column | SQLAlchemy type | Notes |
|--------|----------------|-------|
| `id` | `Integer`, PK, autoincrement | Never declared, never writeable by clients |
| `created_at` | `DateTime` | Set on `INSERT` |
| `updated_at` | `DateTime` | Set on `INSERT` and `UPDATE` |
| `version` | `Integer`, default=1 | Optimistic locking counter |

## `Meta` inner class

The optional `Meta` class controls per-endpoint behaviour:

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

    class Meta:
        authentication = Authentication(backend=JWTAuthentication, permission=IsAuthenticated)
        filtering    = Filtering(backends=[FieldFilter, SearchFilter], fields=["published"], search=["title"])
        pagination   = Pagination(style="page_number", page_size=20)
        serializer   = Serializer(read=["id", "title", "created_at"])
        cache        = Cache(ttl=60)
        reflect      = False   # set True to reflect an existing table
        table        = None    # override the inferred table name
```

| Attribute | Type | Description |
|-----------|------|-------------|
| `authentication` | `Authentication` | Auth backend + permission class |
| `filtering` | `Filtering` | Filter backends and field whitelists |
| `pagination` | `Pagination` | Pagination style and default page size |
| `serializer` | `Serializer` | Read/write field sets |
| `cache` | `Cache` | Response caching with TTL |
| `reflect` | `bool` | If `True`, reflect an existing table |
| `table` | `str \| None` | Custom table name (defaults to class-name-derived name) |

## Table name inference

| Class name | Inferred table name |
|------------|---------------------|
| `UserEndpoint` | `users` |
| `BlogPost` | `blog_posts` |
| `Article` | `articles` |
| `APIKey` | `a_p_i_keys` |

Override with `Meta.table = "my_table"`.

## Accessing the underlying SQLAlchemy model

After registration, the generated SQLAlchemy mapped class is available as:

```python
model_cls = ProductEndpoint._model_class
```

Use this inside `queryset()` or method overrides to build custom SELECT statements:

```python
from sqlalchemy import select

class ProductEndpoint(RestEndpoint):
    name: str
    active: bool

    def queryset(self, request):
        cls = type(self)
        return select(cls._model_class).where(cls._model_class.active == True)
```
