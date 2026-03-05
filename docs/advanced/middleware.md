---
title: Middleware
description: Sync and async request/response middleware for LightAPI v2
---

# Middleware

Middleware intercepts every request before it reaches the endpoint and every response before it is sent to the client. LightAPI v2 supports both **sync** and **async** `process()` methods — they coexist in the same middleware list without any configuration.

---

## Defining Middleware

Subclass `Middleware` from `lightapi.core` and implement `process(request, response)`:

```python
from starlette.requests import Request
from starlette.responses import Response
from lightapi.core import Middleware

class MyMiddleware(Middleware):
    def process(
        self, request: Request, response: Response | None
    ) -> Response | None:
        if response is None:
            # Pre-processing: called before the endpoint
            # Return a Response to short-circuit (skip the endpoint)
            # Return None to continue
            ...
        else:
            # Post-processing: called with the endpoint's response
            # Modify and return it, or return it unchanged
            ...
        return response
```

### Execution Phases

| Phase | `response` value | Return value |
|---|---|---|
| **Pre** (before endpoint) | `None` | `None` → continue; `Response` → short-circuit |
| **Post** (after endpoint) | The endpoint's `Response` | Modified or original `Response` |

Pre-request phase runs middlewares in **declaration order**.  
Post-request phase runs middlewares in **reverse declaration order**.

---

## Registering Middleware

Pass a list of `Middleware` subclasses to `LightApi`:

```python
from lightapi import LightApi

app = LightApi(
    engine=engine,
    middlewares=[AuthMiddleware, LoggingMiddleware, CORSMiddleware],
)
```

---

## Async Middleware

Define `async def process` for middleware that needs to do async I/O:

```python
from lightapi.core import Middleware

class AsyncAuditMiddleware(Middleware):
    async def process(self, request, response):
        if response is None:
            await database.log_request(
                method=request.method,
                path=str(request.url.path),
            )
        return None
```

LightAPI uses `asyncio.iscoroutinefunction(mw.process)` to detect async middleware and awaits it inside the async handler. **No configuration needed** — sync and async middleware coexist transparently.

---

## Practical Examples

### Request Logging (sync)

```python
import logging
from lightapi.core import Middleware

logger = logging.getLogger(__name__)

class RequestLogMiddleware(Middleware):
    def process(self, request, response):
        if response is None:
            logger.info("%s %s", request.method, request.url.path)
        else:
            logger.info("← %s", response.status_code)
        return response if response else None
```

### Response Header Injection (sync)

```python
from lightapi.core import Middleware

class ServerHeaderMiddleware(Middleware):
    def process(self, request, response):
        if response is not None:
            response.headers["X-Powered-By"] = "LightAPI"
        return None
```

### Rate Limiting (async, short-circuit)

```python
from starlette.responses import JSONResponse
from lightapi.core import Middleware

class RateLimitMiddleware(Middleware):
    async def process(self, request, response):
        if response is None:
            ip = request.client.host
            if await _check_rate_limit(ip):          # async Redis call
                return JSONResponse(
                    {"detail": "rate limit exceeded"}, status_code=429
                )
        return None
```

### JWT Extraction (async pre-processing)

```python
import jwt
from lightapi.core import Middleware

class JWTContextMiddleware(Middleware):
    async def process(self, request, response):
        if response is None:
            token = request.headers.get("Authorization", "").removeprefix("Bearer ")
            if token:
                try:
                    payload = jwt.decode(token, SECRET, algorithms=["HS256"])
                    request.state.user = payload
                except jwt.PyJWTError:
                    pass
        return None
```

### Timing Middleware (async post-processing)

```python
import time
from lightapi.core import Middleware

class TimingMiddleware(Middleware):
    async def process(self, request, response):
        if response is None:
            request.state._start = time.monotonic()
        else:
            elapsed_ms = (time.monotonic() - request.state._start) * 1000
            response.headers["X-Response-Time"] = f"{elapsed_ms:.1f}ms"
        return None
```

---

## Mixed Sync + Async Stack

Sync and async middleware coexist freely:

```python
app = LightApi(
    engine=engine,
    middlewares=[
        RateLimitMiddleware,      # async
        JWTContextMiddleware,     # async
        RequestLogMiddleware,     # sync
        ServerHeaderMiddleware,   # sync
        TimingMiddleware,         # async
    ],
)
```

Pre-request order: `RateLimitMiddleware → JWTContextMiddleware → RequestLogMiddleware → ServerHeaderMiddleware → TimingMiddleware`.

Post-request order: `TimingMiddleware → ServerHeaderMiddleware → RequestLogMiddleware → JWTContextMiddleware → RateLimitMiddleware`.

---

## Built-in Middleware

### `CORSMiddleware`

Enable Cross-Origin Resource Sharing by passing `cors_origins` to `LightApi`:

```python
app = LightApi(engine=engine, cors_origins=["https://myapp.com", "http://localhost:3000"])
```

This wraps the Starlette app with `starlette.middleware.cors.CORSMiddleware`.

### `AuthenticationMiddleware`

Re-exported from `lightapi.core` for backward compatibility. Prefer using `Meta.authentication` on individual endpoints for fine-grained control.

---

## Accessing Middleware Inside Tests

Use `httpx.AsyncClient` with `ASGITransport`:

```python
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from lightapi import LightApi, RestEndpoint
from lightapi.auth import AllowAny
from lightapi.config import Authentication
from lightapi.core import Middleware
from pydantic import Field

log = []

class TrackingMiddleware(Middleware):
    def process(self, request, response):
        if response is None:
            log.append(("pre", request.method))
        return None

@pytest_asyncio.fixture
async def client():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    class Item(RestEndpoint):
        name: str = Field(min_length=1)
        class Meta:
            authentication = Authentication(permission=AllowAny)

    app = LightApi(engine=engine, middlewares=[TrackingMiddleware])
    app.register({"/items": Item})
    async with AsyncClient(
        transport=ASGITransport(app=app.build_app()), base_url="http://test"
    ) as c:
        yield c

async def test_middleware_is_called(client):
    await client.get("/items")
    assert ("pre", "GET") in log
```
