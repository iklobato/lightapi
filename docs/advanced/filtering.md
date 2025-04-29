---
title: Request Filtering
---

LightAPI supports request filtering for list endpoints by plugging in a `filter_class` in your endpoint's `Configuration`. The built-in `ParameterFilter` applies filters based on URL query parameters.

## ParameterFilter

The `ParameterFilter` inspects query parameters (e.g., `?status=completed&category=books`) and applies them to the SQLAlchemy query by matching parameter names to model attributes:

```python
from lightapi.rest import RestEndpoint
from lightapi.filters import ParameterFilter

class TaskEndpoint(RestEndpoint):
    class Configuration:
        filter_class = ParameterFilter

    async def get(self, request):
        # Default GET will apply filters automatically
        return super().get(request)
```

With `GET /tasks/?status=completed`, the `ParameterFilter` adds a filter clause equivalent to:

```python
query.filter(Task.status == "completed")
```

## Custom Filters

For more complex filtering logic, subclass `BaseFilter` and override `filter_queryset`:

```python
from lightapi.filters import BaseFilter

class DateRangeFilter(BaseFilter):
    def filter_queryset(self, queryset, request):
        start = request.query_params.get("start_date")
        end = request.query_params.get("end_date")
        if start and end:
            query = queryset.filter(
                Task.created_at.between(start, end)
            )
            return query
        return queryset

class TaskEndpoint(RestEndpoint):
    class Configuration:
        filter_class = DateRangeFilter
```

Custom filters give you full control over how querysets are restricted based on request data.
