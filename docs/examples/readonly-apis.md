---
title: Read-Only APIs
---

# Read-Only APIs

Use `HttpMethod.GET` to expose a resource for reading only — no `POST`, `PUT`, `PATCH`, or `DELETE` routes are generated.

## Basic read-only endpoint

```python
from sqlalchemy import create_engine
from lightapi import LightApi, RestEndpoint, Field, HttpMethod

class ReportEndpoint(RestEndpoint, HttpMethod.GET):
    """Read-only report endpoint."""
    title:   str
    summary: str
    value:   float

engine = create_engine("sqlite:///reports.db")
app = LightApi(engine=engine)
app.register({"/reports": ReportEndpoint})
app.run()
```

Only `GET /reports` and `GET /reports/{id}` are registered. Sending a `POST` returns `405 Method Not Allowed`.

## With filtering and pagination

```python
from lightapi import (
    RestEndpoint, Field, HttpMethod,
    Filtering, Pagination,
    FieldFilter, SearchFilter, OrderingFilter,
)

class MetricEndpoint(RestEndpoint, HttpMethod.GET):
    name:     str  = Field(min_length=1)
    category: str
    value:    float
    active:   bool = Field(default=True)

    class Meta:
        filtering = Filtering(
            backends=[FieldFilter, SearchFilter, OrderingFilter],
            fields=["category", "active"],
            search=["name"],
            ordering=["value", "name"],
        )
        pagination = Pagination(style="page_number", page_size=50)
```

```bash
GET /metrics?category=revenue&active=true&ordering=-value
```

## Read-only with authentication

Protect read access with JWT:

```python
from lightapi import (
    RestEndpoint, HttpMethod,
    Authentication, JWTAuthentication, IsAuthenticated,
)

class SensitiveReportEndpoint(RestEndpoint, HttpMethod.GET):
    title:   str
    payload: str

    class Meta:
        authentication = Authentication(
            backend=JWTAuthentication,
            permission=IsAuthenticated,
        )
```

## Reflecting an existing read-only table

```python
class LegacyViewEndpoint(RestEndpoint, HttpMethod.GET):
    class Meta:
        reflect = True
        table = "vw_sales_summary"
```

## YAML equivalent

```yaml
database:
  url: "${DATABASE_URL}"
endpoints:
  - route: /reports
    fields:
      title:   { type: str }
      summary: { type: str }
      value:   { type: float }
    meta:
      methods: [GET]
      pagination:
        style: page_number
        page_size: 50
```
