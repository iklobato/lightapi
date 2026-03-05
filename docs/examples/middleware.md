---
title: Middleware Examples
---

# Middleware Examples

## Defining middleware

Subclass `Middleware` and implement `process(request, response)`:

```python
from starlette.requests import Request
from starlette.responses import Response
from lightapi.core import Middleware

class RequestLogMiddleware(Middleware):
    def process(
        self, request: Request, response: Response | None
    ) -> Response | None:
        if response is None:
            print(f"→ {request.method} {request.url.path}")
        else:
            print(f"← {response.status_code}")
        return response
```

## Registering middleware

Pass middleware classes to `LightApi`:

```python
from sqlalchemy import create_engine
from lightapi import LightApi

engine = create_engine("sqlite:///app.db")
app = LightApi(
    engine=engine,
    middlewares=[RequestLogMiddleware],
)
```

## Execution order

- **Pre-request** (before the endpoint): middlewares run in **declaration order**.
- **Post-request** (after the endpoint): middlewares run in **reverse declaration order**.

## Timing middleware

```python
import time
from starlette.requests import Request
from starlette.responses import Response
from lightapi.core import Middleware

class TimingMiddleware(Middleware):
    def process(
        self, request: Request, response: Response | None
    ) -> Response | None:
        if response is None:
            request.state.start_time = time.time()
            return None
        elapsed = time.time() - request.state.start_time
        response.headers["X-Response-Time"] = f"{elapsed:.3f}s"
        return response
```

## Short-circuiting (rate limiter example)

Return a `Response` in the pre-request phase to skip the endpoint entirely:

```python
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from lightapi.core import Middleware

_request_counts: dict[str, int] = {}

class RateLimitMiddleware(Middleware):
    LIMIT = 100

    def process(
        self, request: Request, response: Response | None
    ) -> Response | None:
        if response is not None:
            return response
        ip = request.client.host if request.client else "unknown"
        _request_counts[ip] = _request_counts.get(ip, 0) + 1
        if _request_counts[ip] > self.LIMIT:
            return JSONResponse(
                {"detail": "Rate limit exceeded"},
                status_code=429,
            )
        return None
```

## Async middleware

```python
from starlette.requests import Request
from starlette.responses import Response
from lightapi.core import Middleware

class AsyncHeaderMiddleware(Middleware):
    async def process(
        self, request: Request, response: Response | None
    ) -> Response | None:
        if response is None:
            return None
        response.headers["X-App-Version"] = "2.0"
        return response
```

Sync and async middleware coexist in the same list — no special configuration needed.

## Adding security headers

```python
from starlette.requests import Request
from starlette.responses import Response
from lightapi.core import Middleware

class SecurityHeadersMiddleware(Middleware):
    def process(
        self, request: Request, response: Response | None
    ) -> Response | None:
        if response is None:
            return None
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
```

## Complete example

```python
from sqlalchemy import create_engine
from lightapi import LightApi, RestEndpoint, Field

class ArticleEndpoint(RestEndpoint):
    title: str = Field(min_length=1)
    body:  str

engine = create_engine("sqlite:///app.db")
app = LightApi(
    engine=engine,
    middlewares=[
        SecurityHeadersMiddleware,
        TimingMiddleware,
        RequestLogMiddleware,
    ],
)
app.register({"/articles": ArticleEndpoint})
app.run()
```
