---
title: Pagination API Reference
description: PageNumberPaginator and CursorPaginator reference
---

# Pagination API Reference

## Overview

Pagination is enabled via `Meta.pagination` on a `RestEndpoint`. LightAPI provides two pagination styles.

```python
from lightapi import RestEndpoint, Pagination

class PostEndpoint(RestEndpoint):
    title: str

    class Meta:
        pagination = Pagination(style="page_number", page_size=20)
```

## `Pagination`

```python
Pagination(
    style: str = "page_number",
    page_size: int = 20,
)
```

| Parameter | Values | Description |
|-----------|--------|-------------|
| `style` | `"page_number"` | Offset-based pagination |
| `style` | `"cursor"` | Cursor-based pagination |
| `page_size` | `int ≥ 1` | Default items per page |

Raises `ConfigurationError` if `style` is not one of the valid values or `page_size < 1`.

## Page-Number Style

### Query parameters

| Param | Default | Description |
|-------|---------|-------------|
| `page` | `1` | Page number (1-indexed) |
| `page_size` | Meta value | Override per request |

### Response envelope

```json
{
  "count": 150,
  "next": "/posts?page=3&page_size=20",
  "previous": "/posts?page=1&page_size=20",
  "results": [ ... ]
}
```

## Cursor Style

### Query parameters

| Param | Description |
|-------|-------------|
| `cursor` | Opaque cursor string from a previous response's `next` field. Omit for the first page. |
| `page_size` | Override per request |

### Response envelope

```json
{
  "next": "eyJpZCI6IDIwfQ==",
  "previous": null,
  "results": [ ... ]
}
```

The cursor encodes the last `id` seen. When `next` is `null`, there are no more pages.

## Combining with filtering and ordering

Pagination is applied after filtering and ordering:

```python
class EventEndpoint(RestEndpoint):
    name: str
    timestamp: str

    class Meta:
        filtering = Filtering(backends=[OrderingFilter], ordering=["timestamp"])
        pagination = Pagination(style="cursor", page_size=50)
```

```bash
GET /events?ordering=-timestamp
GET /events?ordering=-timestamp&cursor=eyJpZCI6IDUwfQ==
```

## `PageNumberPaginator` (internal)

Used internally when `style="page_number"`. Also exposed for use in custom `queryset` logic:

```python
from lightapi.pagination import PageNumberPaginator
from sqlalchemy import select

class MyEndpoint(RestEndpoint):
    name: str

    async def get(self, request):
        pager = PageNumberPaginator(page_size=10)
        engine = self._get_async_engine()
        cls = type(self)
        qs = select(cls._model_class)
        from lightapi import get_async_session
        async with get_async_session(engine) as session:
            rows, total = await pager.paginate_async(session, qs, request)
        return {"count": total, "results": [dict(r) for r in rows]}
```

## `CursorPaginator` (internal)

Used internally when `style="cursor"`:

```python
from lightapi.pagination import CursorPaginator
```

Both paginators have `paginate(session, queryset, request)` (sync) and `paginate_async(session, queryset, request)` (async) methods.
