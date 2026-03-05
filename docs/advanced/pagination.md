---
title: Pagination
description: Page-number and cursor-based pagination for list endpoints
---

# Pagination

LightAPI supports two pagination styles, configured via `Meta.pagination`. Pagination is applied automatically to `GET` list responses.

## Quick Start

```python
from lightapi import RestEndpoint, Pagination

class PostEndpoint(RestEndpoint):
    title: str
    body: str

    class Meta:
        pagination = Pagination(style="page_number", page_size=20)
```

```bash
GET /posts        # → page 1, 20 items
GET /posts?page=2 # → page 2, 20 items
```

## `Pagination` constructor

```python
Pagination(
    style: str = "page_number",   # "page_number" or "cursor"
    page_size: int = 20,
)
```

| Parameter | Values | Description |
|-----------|--------|-------------|
| `style` | `"page_number"` | Offset-based pagination with `?page=` param. |
| `style` | `"cursor"` | Cursor-based pagination — efficient for large, append-only datasets. |
| `page_size` | integer ≥ 1 | Default number of items per page. |

## Page-Number Pagination

### Response format

```json
{
  "count": 150,
  "next": "/posts?page=3",
  "previous": "/posts?page=1",
  "results": [...]
}
```

### Query parameters

| Param | Default | Description |
|-------|---------|-------------|
| `page` | `1` | Page number (1-indexed). |

### Example

```python
from lightapi import RestEndpoint, Pagination, Filtering, FieldFilter

class ArticleEndpoint(RestEndpoint):
    title: str
    published: bool

    class Meta:
        pagination = Pagination(style="page_number", page_size=10)
        filtering = Filtering(backends=[FieldFilter], fields=["published"])
```

```bash
GET /articles?published=true&page=2
```

## Cursor Pagination

Cursor pagination uses an opaque cursor instead of page numbers. It is more efficient for large datasets because it avoids `OFFSET` scans.

### Response format

```json
{
  "next": "eyJpZCI6IDEwfQ==",
  "previous": null,
  "results": [...]
}
```

When `next` is `null`, there are no more pages.

### Query parameters

| Param | Description |
|-------|-------------|
| `cursor` | Opaque cursor from a previous response's `next` field. Omit for the first page. |

### Example

```python
class EventEndpoint(RestEndpoint):
    name: str
    timestamp: str

    class Meta:
        pagination = Pagination(style="cursor", page_size=50)
```

```bash
# First page
GET /events

# Next page using the cursor from the previous response
GET /events?cursor=eyJpZCI6IDUwfQ==
```

## Pagination with Filtering

Filtering and pagination compose naturally:

```python
from lightapi import RestEndpoint, Pagination, Filtering, FieldFilter, OrderingFilter

class ProductEndpoint(RestEndpoint):
    name: str
    price: float
    in_stock: bool

    class Meta:
        pagination = Pagination(style="page_number", page_size=25)
        filtering = Filtering(
            backends=[FieldFilter, OrderingFilter],
            fields=["in_stock"],
            ordering=["price", "name"],
        )
```

```bash
GET /products?in_stock=true&ordering=-price&page=2
```

## No Pagination (default)

If `Meta.pagination` is not set, the `GET` list endpoint returns all matching rows as a flat list:

```json
{"results": [...]}
```

This is fine for small datasets. For large tables, always add pagination.
