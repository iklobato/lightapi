---
title: Filtering and Pagination Examples
---

# Filtering and Pagination

## Filtering

### All three filter backends

```python
from lightapi import (
    RestEndpoint, Field,
    Filtering, FieldFilter, SearchFilter, OrderingFilter,
)

class ArticleEndpoint(RestEndpoint):
    title:     str  = Field(min_length=1, max_length=255)
    body:      str
    published: bool = Field(default=False)
    category:  str  = Field(max_length=50)

    class Meta:
        filtering = Filtering(
            backends=[FieldFilter, SearchFilter, OrderingFilter],
            fields=["published", "category"],    # ?published=true, ?category=news
            search=["title", "body"],             # ?search=python
            ordering=["title", "created_at"],     # ?ordering=-created_at
        )
```

```bash
GET /articles?published=true
GET /articles?search=python
GET /articles?ordering=-created_at
GET /articles?published=true&search=api&ordering=title
```

### Filter backends reference

| Backend | Query param | Behaviour |
|---------|-------------|-----------|
| `FieldFilter` | `?field=value` | Exact match on whitelisted `fields`. |
| `SearchFilter` | `?search=term` | Case-insensitive `LIKE` across `search` fields. |
| `OrderingFilter` | `?ordering=col` or `?ordering=-col` | Ascending / descending on `ordering` fields. |

### Boolean field filtering

Boolean query params accept `true`, `1`, `yes`, `on` (case-insensitive) for `True`; anything else is `False`.

```bash
GET /articles?published=true
GET /articles?published=1
```

## Pagination

### Page-number pagination

```python
from lightapi import Pagination

class PostEndpoint(RestEndpoint):
    title: str
    body:  str

    class Meta:
        pagination = Pagination(style="page_number", page_size=20)
```

```bash
GET /posts        # page 1, 20 items
GET /posts?page=3 # page 3, 20 items
```

**Response envelope:**

```json
{
  "count": 150,
  "pages": 8,
  "next": "/posts?page=4",
  "previous": "/posts?page=2",
  "results": [...]
}
```

### Cursor pagination

Best for large, append-only datasets where offset pagination is too slow.

```python
class EventEndpoint(RestEndpoint):
    name:    str
    payload: str

    class Meta:
        pagination = Pagination(style="cursor", page_size=50)
```

```bash
GET /events            # first page
GET /events?cursor=eyJpZCI6IDUwfQ==   # next page
```

**Response envelope:**

```json
{
  "next": "eyJpZCI6IDEwMH0=",
  "previous": null,
  "results": [...]
}
```

When `next` is `null`, there are no more pages.

## Combining filtering and pagination

```python
from lightapi import (
    RestEndpoint, Field,
    Filtering, Pagination,
    FieldFilter, SearchFilter, OrderingFilter,
)

class ProductEndpoint(RestEndpoint):
    name:     str   = Field(min_length=1, max_length=200)
    price:    float = Field(ge=0)
    category: str
    active:   bool  = Field(default=True)

    class Meta:
        filtering = Filtering(
            backends=[FieldFilter, SearchFilter, OrderingFilter],
            fields=["category", "active"],
            search=["name"],
            ordering=["price", "name"],
        )
        pagination = Pagination(style="page_number", page_size=25)
```

```bash
GET /products?category=electronics&active=true&ordering=-price&page=2
```

## YAML equivalent

```yaml
database:
  url: "${DATABASE_URL}"
endpoints:
  - route: /products
    fields:
      name:     { type: str, max_length: 200 }
      price:    { type: float }
      category: { type: str }
      active:   { type: bool, default: true }
    meta:
      methods: [GET, POST, PUT, DELETE]
      filtering:
        fields:   [category, active]
        search:   [name]
        ordering: [price, name]
      pagination:
        style: page_number
        page_size: 25
```
