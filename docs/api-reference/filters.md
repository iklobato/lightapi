---
title: Filters API Reference
description: Built-in filter backends and BaseFilter interface
---

# Filters API Reference

## Overview

Filtering is enabled via `Meta.filtering` on a `RestEndpoint`:

```python
from lightapi import RestEndpoint, Filtering, FieldFilter, SearchFilter, OrderingFilter

class ArticleEndpoint(RestEndpoint):
    title: str
    published: bool

    class Meta:
        filtering = Filtering(
            backends=[FieldFilter, SearchFilter, OrderingFilter],
            fields=["published"],
            search=["title"],
            ordering=["title", "created_at"],
        )
```

## `Filtering`

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
| `backends` | Filter backend classes applied in order to every list query. |
| `fields` | Column names allowed for `FieldFilter` exact-match. |
| `search` | Column names searched by `SearchFilter`. |
| `ordering` | Column names allowed for `OrderingFilter`. |

## Built-in backends

### `FieldFilter`

Applies exact `WHERE col = value` for query parameters in `fields`.

```
GET /articles?published=true&category=tech
```

**Type coercion**: string query parameter values are automatically converted to the correct Python type (`bool`, `int`, `float`) based on the SQLAlchemy column type. This prevents type errors with strict databases like PostgreSQL.

**Class:** `lightapi.filters.FieldFilter`

### `SearchFilter`

Applies case-insensitive `ILIKE '%value%'` across all `search` columns when `?search=` is present.

```
GET /articles?search=async+python
# WHERE title ILIKE '%async python%' OR body ILIKE '%async python%'
```

**Class:** `lightapi.filters.SearchFilter`

### `OrderingFilter`

Applies `ORDER BY col ASC` or `ORDER BY col DESC` (prefix `-`) via `?ordering=`.

```
GET /articles?ordering=-created_at,title
```

Multiple fields can be comma-separated. Only fields listed in `ordering` are allowed; unknown fields are silently ignored.

**Class:** `lightapi.filters.OrderingFilter`

## Reserved parameters

The following query parameter names are never treated as field filters:

`page`, `page_size`, `cursor`, `search`, `ordering`

## `BaseFilter`

Implement this abstract base class to create custom filter backends:

```python
from lightapi.filters import BaseFilter
from starlette.requests import Request

class DateRangeFilter(BaseFilter):
    def filter_queryset(self, request: Request, queryset, view) -> Any:
        after = request.query_params.get("after")
        before = request.query_params.get("before")
        cls = type(view)
        if after:
            queryset = queryset.where(cls._model_class.created_at >= after)
        if before:
            queryset = queryset.where(cls._model_class.created_at <= before)
        return queryset
```

Register it in `Meta.filtering`:

```python
class EventEndpoint(RestEndpoint):
    name: str

    class Meta:
        filtering = Filtering(
            backends=[FieldFilter, DateRangeFilter, OrderingFilter],
            fields=[],
            ordering=["created_at"],
        )
```

## `_coerce_filter_value` (internal)

LightAPI calls this automatically for `FieldFilter` to coerce string query params to the column's Python type. You can use it in custom backends:

```python
from lightapi.filters import _coerce_filter_value

coerced = _coerce_filter_value(column_attribute, "true")   # → True (bool)
coerced = _coerce_filter_value(column_attribute, "42")     # → 42 (int)
```
