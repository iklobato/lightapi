---
title: Rate Limiting
description: Built-in rate limiting for the auto-registered /auth/login endpoint
---

# Rate Limiting

LightAPI ships with a simple in-memory rate limiter that automatically
protects the auto-registered `POST /auth/login` endpoint (also reachable as
`POST /auth/token`). It tracks request counts per client IP across three
sliding windows: per minute, per hour, and per day.

## Default limits

When you configure `Authentication(backend=JWTAuthentication)` or
`Authentication(backend=BasicAuthentication)` on any endpoint, LightAPI
applies these defaults to the login route:

| Window | Default limit |
|---|---|
| per minute | 1000 |
| per hour | 10000 |
| per day | 100000 |

A request that exceeds any limit receives `429 Too Many Requests`.

## Configuring custom limits

Pass either a `RateLimiter` instance or a `dict` to `LightApi(...)`:

```python
from lightapi import LightApi, RateLimiter
from sqlalchemy import create_engine

engine = create_engine("sqlite:///app.db")

# Option 1 — RateLimiter instance
limiter = RateLimiter(
    requests_per_minute=10,
    requests_per_hour=100,
    requests_per_day=1000,
)
app = LightApi(engine=engine, rate_limiter=limiter)

# Option 2 — dict
app = LightApi(
    engine=engine,
    rate_limiter={
        "requests_per_minute": 10,
        "requests_per_hour": 100,
        "requests_per_day": 1000,
    },
)
```

## Resetting between tests

`RateLimiter.reset()` clears all tracked counts. Useful inside test fixtures
to keep tests isolated:

```python
import pytest
from lightapi import RateLimiter

@pytest.fixture
def limiter():
    rl = RateLimiter(requests_per_minute=3)
    yield rl
    rl.reset()
```

## Caveats

- Storage is **in-memory per process**. Behind a multi-worker deployment
  (e.g. Gunicorn) limits apply per worker, not globally.
- The bucket key is the client IP from the Starlette `Request`. Requests
  behind a proxy report the proxy's IP unless you parse `X-Forwarded-For`
  in custom middleware.

## See also

- [Authentication](authentication.md) — login endpoint configuration.
- [Middleware](middleware.md) — write a custom rate limiter for non-auth
  routes using middleware.
