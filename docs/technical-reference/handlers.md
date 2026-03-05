---
title: Request Handlers
---

# Request Handlers

> This page describes how LightAPI v2 routes requests internally. You rarely need to interact with this layer directly — use `RestEndpoint` method overrides instead.

## Routing Architecture

When `app.register({"/items": ItemEndpoint})` is called, LightAPI registers two Starlette `Route` objects per endpoint:

| Route | Methods | Handler |
|-------|---------|---------|
| `/items` | `GET`, `POST` | `_make_collection_handler(cls)` |
| `/items/{id:int}` | `GET`, `PUT`, `PATCH`, `DELETE` | `_make_detail_handler(cls)` |

Both handlers are closures that instantiate the endpoint class per request and dispatch to the appropriate CRUD method.

## Request Dispatch Flow

For each incoming request:

1. **Authentication check** — if `Meta.authentication` is configured, the backend's `authenticate()` is called; on failure, `401` is returned.
2. **Permission check** — the permission class's `has_permission()` is evaluated; on failure, `403` is returned.
3. **Middleware pre-processing** — each `Middleware.process(request, None)` is called in declaration order.
4. **CRUD method dispatch** — the correct sync or async CRUD method is called based on HTTP verb and whether an async engine was detected.
5. **Background tasks** — any tasks registered via `self.background()` are attached to the response.
6. **Middleware post-processing** — each `Middleware.process(request, response)` is called in reverse order.

## Sync vs. Async Dispatch

LightAPI detects at startup whether the registered engine is an `AsyncEngine`. If so, all CRUD requests are dispatched to the `_*_async` methods automatically — no code changes needed.

```python
# Sync engine → list(), retrieve(), create(), update(), destroy()
engine = create_engine("sqlite:///app.db")

# Async engine → _list_async(), _retrieve_async(), _create_async(), etc.
engine = create_async_engine("postgresql+asyncpg://user:pass@db/db")
```

## Session Lifecycle

- **Sync**: A `sqlalchemy.orm.Session` is opened per request inside the CRUD method, committed on success, rolled back on exception.
- **Async**: An `AsyncSession` (`expire_on_commit=False`) is opened per request, committed on success, rolled back on exception.

Use `get_sync_session(engine)` / `get_async_session(engine)` directly in custom `queryset` overrides or service layers.
