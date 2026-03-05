---
title: Filtering
description: Add query parameter filtering to list endpoints
---

# Filtering

LightAPI provides three built-in filter backends that work via URL query parameters. Filtering is configured via `Meta.filtering` on each `RestEndpoint`.

## Quick Start

```python
from lightapi import (
    RestEndpoint, Field, Filtering,
    FieldFilter, SearchFilter, OrderingFilter,
)

class ArticleEndpoint(RestEndpoint):
    title: str
    body: str
    published: bool = Field(default=False)
    category: str

    class Meta:
        filtering = Filtering(
            backends=[FieldFilter, SearchFilter, OrderingFilter],
            fields=["published", "category"],   # exact-match params
            search=["title", "body"],            # ?search= applies iLIKE
            ordering=["title", "created_at"],    # ?ordering= / ?ordering=-field
        )
```

```bash
GET /articles?published=true
GET /articles?search=django
GET /articles?ordering=-created_at
GET /articles?published=true&search=api&ordering=title
```

## `Filtering` constructor

```python
Filtering(
    backends: list[type] | None = None,
    fields: list[str] | None = None,
    search: list[str] | None = None,
    ordering: list[str] | None = None,
)
```

| Parameter | Description |
|-----------|-------------|
| `backends` | List of filter backend classes to apply, in order. |
| `fields` | Columns allowed for exact-match filtering (`?field=value`). |
| `search` | Columns searched with case-insensitive `LIKE` when `?search=` is present. |
| `ordering` | Columns allowed for ordering via `?ordering=col` or `?ordering=-col`. |

## Filter Backends

### `FieldFilter`

Applies exact-match `WHERE col = value` for each query parameter that appears in `fields`.

```bash
GET /articles?published=true&category=tech
```

Type coercion is automatic — string query params are converted to the correct Python type (bool, int, float) based on the SQLAlchemy column type.

### `SearchFilter`

Applies case-insensitive `LIKE` (`ilike`) across all `search` fields when `?search=` is present.

```bash
GET /articles?search=async
# WHERE title ILIKE '%async%' OR body ILIKE '%async%'
```

### `OrderingFilter`

Orders results by `?ordering=field` (ascending) or `?ordering=-field` (descending). Multiple fields can be comma-separated.

```bash
GET /articles?ordering=-created_at,title
```

Only fields listed in `ordering` are allowed; unknown fields are silently skipped.

## Combining Backends

All enabled backends are applied sequentially. Order matters only if backends conflict.

```python
class ProductEndpoint(RestEndpoint):
    name: str
    price: float
    in_stock: bool = Field(default=True)

    class Meta:
        filtering = Filtering(
            backends=[FieldFilter, SearchFilter, OrderingFilter],
            fields=["in_stock"],
            search=["name"],
            ordering=["price", "name"],
        )
```

```bash
GET /products?in_stock=true&search=widget&ordering=price
```

## Custom queryset scoping

Use a `queryset()` method (or `async def queryset()` for async engines) to pre-scope the query before filters are applied:

```python
from sqlalchemy import select

class MyArticleEndpoint(RestEndpoint):
    title: str
    published: bool = Field(default=False)

    class Meta:
        filtering = Filtering(backends=[FieldFilter], fields=["published"])

    def queryset(self, request):
        cls = type(self)
        return select(cls._model_class).where(cls._model_class.published == True)
```

## Custom Filter Backend

Implement `BaseFilter` to build your own backend:

```python
from lightapi.filters import BaseFilter

class PriceRangeFilter(BaseFilter):
    def filter_queryset(self, request, queryset, view):
        min_price = request.query_params.get("min_price")
        max_price = request.query_params.get("max_price")
        cls = type(view)
        if min_price:
            queryset = queryset.where(cls._model_class.price >= float(min_price))
        if max_price:
            queryset = queryset.where(cls._model_class.price <= float(max_price))
        return queryset
```

Register it alongside the built-in backends:

```python
class ProductEndpoint(RestEndpoint):
    name: str
    price: float

    class Meta:
        filtering = Filtering(
            backends=[FieldFilter, PriceRangeFilter, OrderingFilter],
            fields=[],
            ordering=["price"],
        )
```

## Reserved Query Parameters

The following query parameter names are reserved and will not be treated as field filters even if they appear in `fields`:

- `page`, `page_size` — pagination
- `cursor` — cursor pagination
- `search` — `SearchFilter`
- `ordering` — `OrderingFilter`
