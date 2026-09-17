---
title: Filters API Reference
description: Built-in filter backends and BaseFilter interface
---

# Filters API Reference

## Overview

Filtering is enabled via `Meta.filtering` on a `RestEndpoint`:

```python
from lightapi import (
    RestEndpoint, Filtering,
    FieldFilter, SearchFilter, OrderingFilter, RangeFilter,
)

class ArticleEndpoint(RestEndpoint):
    title: str
    published: bool
    word_count: int

    class Meta:
        filtering = Filtering(
            backends=[FieldFilter, SearchFilter, OrderingFilter, RangeFilter],
            fields=["published"],
            search=["title"],
            ordering=["title", "created_at"],
            ranges=["word_count", "created_at"],
        )
```

## `Filtering`

```python
Filtering(
    backends: list[type] | None = None,
    fields: list[str] | None = None,
    search: list[str] | None = None,
    ordering: list[str] | None = None,
    ranges: list[str] | None = None,
)
```

| Parameter | Description |
|-----------|-------------|
| `backends` | Filter backend classes applied in order to every list query. |
| `fields` | Column names allowed for `FieldFilter` exact-match. |
| `search` | Column names searched by `SearchFilter`. |
| `ordering` | Column names allowed for `OrderingFilter`. |
| `ranges` | Ordered column names allowed for `RangeFilter` bounds. Validated at class definition time. |

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

**Search input is treated as a literal string.** The characters `%` and `_` (SQL LIKE wildcards) are automatically escaped, so `?search=hello_world` matches only the exact substring `hello_world` — not any single character in place of the underscore. Bare `%` or `_` characters in search terms do not become wildcards.

**Class:** `lightapi.filters.SearchFilter`

### `OrderingFilter`

Applies `ORDER BY col ASC` or `ORDER BY col DESC` (prefix `-`) via `?ordering=`.

```
GET /articles?ordering=-created_at,title
```

Multiple fields can be comma-separated. Only fields explicitly listed in `ordering` are allowed; unknown field names are silently ignored. **When `ordering` is not configured (empty or omitted), the backend ignores all `?ordering=` parameters** — no ordering is applied. This prevents clients from sorting by arbitrary columns when no whitelist has been declared.

**Class:** `lightapi.filters.OrderingFilter`

### `RangeFilter`

Applies inclusive bounds via `?<field>_min=` (`WHERE col >= value`) and
`?<field>_max=` (`WHERE col <= value`) for each column listed in `ranges`.

```
GET /articles?word_count_min=500&word_count_max=2000
# WHERE word_count >= 500 AND word_count <= 2000
```

The bounds are independent: either one, both, or neither may be supplied. Values are
coerced to the column's Python type — `int`, `float`/`Decimal`, `date` and `datetime`
(ISO 8601) are supported:

```
GET /articles?created_at_min=2026-01-01T00:00:00
```

Fields outside the `ranges` whitelist are ignored, and so is a bound that cannot be
coerced to the column's type (`?word_count_min=many`). Auto-injected columns (`id`,
`created_at`, `updated_at`, `version`) may be listed in `ranges`.

**Configuration is validated eagerly.** A name in `ranges` that is not a field of the
endpoint, or one mapped to a type without an ordering (`String`, `Boolean`), raises
`ConfigurationError` when the endpoint class is defined.

**Class:** `lightapi.filters.RangeFilter`

## Reserved parameters

The following query parameter names are never treated as field filters:

`page`, `page_size`, `cursor`, `search`, `ordering`

## `BaseFilter`

Implement this abstract base class to create custom filter backends. (Plain range
bounds are already covered by [`RangeFilter`](#rangefilter) — the example below is kept
as a minimal illustration of the interface.)

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

## `_coerce_range_value` (internal)

The `RangeFilter` counterpart. It coerces a bound to the column's Python type and
returns `None` when the value is unparseable or the column type has no ordering, which
tells the backend to skip that bound:

```python
from lightapi.filters import _coerce_range_value

bound = _coerce_range_value(column_attribute, "42")          # → 42 (int)
bound = _coerce_range_value(column_attribute, "2026-01-15")  # → date(2026, 1, 15)
bound = _coerce_range_value(column_attribute, "many")        # → None (ignored)
```
