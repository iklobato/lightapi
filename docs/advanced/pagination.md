---
title: Data Pagination
---

LightAPI includes a built-in pagination utility via the `Paginator` class. You can plug this into any `RestEndpoint` to limit and offset large querysets.

## 1. Enabling Pagination

Add `pagination_class` to your endpoint's `Configuration`:

```python
from lightapi.rest import RestEndpoint
from lightapi.pagination import Paginator

class ItemEndpoint(RestEndpoint):
    class Configuration:
        pagination_class = Paginator

    async def get(self, request):
        # Default GET will use Paginator to limit results
        return super().get(request)
```

## 2. Configuring Limits and Offsets

The `Paginator` uses its `limit` and `offset` attributes to control pagination. You can customize these values at runtime by modifying the instance:

```python
class CustomPaginator(Paginator):
    def get_limit(self) -> int:
        # Read limit from query params or fallback to default
        return int(self.request.query_params.get('limit', self.limit))

    def get_offset(self) -> int:
        return int(self.request.query_params.get('offset', self.offset))
```

Then assign your custom paginator:

```python
class ItemEndpoint(RestEndpoint):
    class Configuration:
        pagination_class = CustomPaginator
```

## 3. Sorting Results

By default, `Paginator.sort` is `False`. Enable sorting in a subclass to apply ordering:

```python
class SortedPaginator(Paginator):
    sort = True
    def apply_sorting(self, queryset):
        # Example: sort by 'created_at' field
        return queryset.order_by(self.model.created_at.desc())
```

Use it in your endpoint:

```python
class ItemEndpoint(RestEndpoint):
    class Configuration:
        pagination_class = SortedPaginator
```

Pagination helps control memory usage and response size when dealing with large datasets.
