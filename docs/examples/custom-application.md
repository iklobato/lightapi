---
title: Custom Application Example
---

# Custom Application

A complete example composing multiple LightAPI features: authentication, filtering, pagination, caching, and middleware.

## Endpoint with all features

```python
from typing import Optional
from sqlalchemy import create_engine
from lightapi import (
    LightApi, RestEndpoint, Field,
    Authentication, JWTAuthentication, IsAuthenticated, AllowAny,
    Filtering, FieldFilter, SearchFilter, OrderingFilter,
    Pagination, Serializer, Cache,
)
from lightapi.core import Middleware
from starlette.requests import Request
from starlette.responses import Response

# ── Middleware ────────────────────────────────────────────────────────────────

class RequestIdMiddleware(Middleware):
    import uuid

    def process(self, request: Request, response: Response | None) -> Response | None:
        if response is None:
            import uuid
            request.state.request_id = str(uuid.uuid4())
            return None
        response.headers["X-Request-ID"] = getattr(request.state, "request_id", "")
        return response


# ── Endpoint ──────────────────────────────────────────────────────────────────

class ItemEndpoint(RestEndpoint):
    name:        str            = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    price:       float          = Field(ge=0)
    category:    str            = Field(max_length=50)
    active:      bool           = Field(default=True)

    class Meta:
        authentication = Authentication(
            backend=JWTAuthentication,
            permission={
                "GET":    AllowAny,
                "POST":   IsAuthenticated,
                "PUT":    IsAuthenticated,
                "PATCH":  IsAuthenticated,
                "DELETE": IsAuthenticated,
            },
        )
        filtering = Filtering(
            backends=[FieldFilter, SearchFilter, OrderingFilter],
            fields=["category", "active"],
            search=["name", "description"],
            ordering=["price", "name", "created_at"],
        )
        pagination = Pagination(style="page_number", page_size=25)
        serializer = Serializer(
            read=["id", "name", "price", "category", "active", "created_at"],
        )
        cache = Cache(ttl=60)


# ── Application ───────────────────────────────────────────────────────────────

engine = create_engine("sqlite:///custom.db")

app = LightApi(
    engine=engine,
    cors_origins=["https://myapp.com"],
    middlewares=[RequestIdMiddleware],
)

app.register({"/items": ItemEndpoint})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
```

## Testing it

```bash
export LIGHTAPI_JWT_SECRET="dev-secret"
python main.py
```

```bash
# Public GET — no token needed
curl http://localhost:8000/items

# Authenticated POST — requires JWT
TOKEN=$(python -c "
from lightapi.auth import JWTAuthentication
import os; os.environ['LIGHTAPI_JWT_SECRET']='dev-secret'
auth = JWTAuthentication()
print(auth.generate_token({'sub': '1', 'is_admin': False}))
")

curl -X POST http://localhost:8000/items \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Widget", "price": 9.99, "category": "tools"}'

# Filter + paginate
curl "http://localhost:8000/items?category=tools&active=true&ordering=-price&page=1"

# Search
curl "http://localhost:8000/items?search=widget"
```

## Async variant

Replace the engine with an async one — no other changes needed:

```python
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine("postgresql+asyncpg://user:pass@localhost/mydb")
app = LightApi(engine=engine, middlewares=[RequestIdMiddleware])
```

Install: `uv add "lightapi[async]"`
