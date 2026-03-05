---
title: Middleware Reference
---

# Middleware Reference

> Compact reference. See [Advanced — Middleware](../advanced/middleware.md) for full documentation.

## `Middleware` (`lightapi.core.Middleware`)

Base class for request/response middleware.

```python
from starlette.requests import Request
from starlette.responses import Response
from lightapi.core import Middleware

class MyMiddleware(Middleware):
    def process(
        self, request: Request, response: Response | None
    ) -> Response | None:
        if response is None:
            # Pre-processing — runs before the endpoint
            # Return None to continue; return a Response to short-circuit
            return None
        # Post-processing — runs after the endpoint
        return response
```

| Phase | `response` | Return |
|-------|-----------|--------|
| Pre (before endpoint) | `None` | `None` → continue; `Response` → short-circuit |
| Post (after endpoint) | Endpoint's `Response` | Modified or original `Response` |

### Async middleware

```python
from starlette.requests import Request
from starlette.responses import Response
from lightapi.core import Middleware

class AsyncTimingMiddleware(Middleware):
    async def process(
        self, request: Request, response: Response | None
    ) -> Response | None:
        if response is None:
            import time
            request.state.start = time.time()
            return None
        elapsed = time.time() - request.state.start
        response.headers["X-Response-Time"] = f"{elapsed:.3f}s"
        return response
```

Sync and async middleware can coexist in the same `middlewares` list.

### Registration

```python
from lightapi import LightApi

app = LightApi(
    engine=engine,
    middlewares=[AuthMiddleware, LoggingMiddleware],
)
```

Pre-request: runs in **declaration order**.
Post-request: runs in **reverse declaration order**.

## `CORSMiddleware`

Adds CORS headers to every response.

```python
from lightapi.core import CORSMiddleware

app = LightApi(engine=engine, middlewares=[CORSMiddleware])
```

Use `cors_origins` on `LightApi` for the standard Starlette CORS middleware instead:

```python
app = LightApi(engine=engine, cors_origins=["https://example.com"])
```

## `AuthenticationMiddleware`

Runs authentication for every request using a configurable backend class.

```python
from lightapi.core import AuthenticationMiddleware
```

For per-endpoint authentication, use `Meta.authentication` on `RestEndpoint` instead — it is more granular and the recommended approach.
