---
title: Core API
---

# Core API Reference

> This page is a compact technical reference. See [Configuration Guide](../getting-started/configuration.md) and [API Reference — Core](../api-reference/core.md) for full documentation.

## `LightApi`

```python
from lightapi import LightApi
```

### Constructor

```python
LightApi(
    engine=None,
    database_url: str | None = None,
    cors_origins: list[str] | None = None,
    middlewares: list[type] | None = None,
)
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `engine` | `Engine \| AsyncEngine` | SQLAlchemy engine (sync or async). |
| `database_url` | `str \| None` | Creates a sync engine when no `engine` is provided. Falls back to `LIGHTAPI_DATABASE_URL`. Raises `ConfigurationError` if none are provided. |
| `cors_origins` | `list[str] \| None` | CORS allowed origins. |
| `middlewares` | `list[type] \| None` | `Middleware` subclasses applied to all requests. |

### Methods

#### `register(mapping: dict[str, type]) → None`

Register endpoint classes and create their database tables.

```python
app.register({
    "/users": UserEndpoint,
    "/posts": PostEndpoint,
})
```

Raises `ConfigurationError` if a value is not a `RestEndpoint` subclass.

#### `build_app() → Starlette`

Return the underlying Starlette ASGI app without starting the server. Useful for testing.

#### `run(host, port, debug, reload) → None`

Start the Uvicorn server.

```python
app.run(host="0.0.0.0", port=8000, debug=False, reload=False)
```

#### `from_config(config_path: str) → LightApi` (classmethod)

Load a `lightapi.yaml` file, validate it with Pydantic v2, and return a configured instance.

```python
app = LightApi.from_config("lightapi.yaml")
```

Uses the declarative format: `database.url` + `endpoints[].route` + inline `fields`.

### Example

```python
from sqlalchemy import create_engine
from lightapi import LightApi, RestEndpoint, Field

class ArticleEndpoint(RestEndpoint):
    title: str = Field(min_length=1, max_length=255)
    body: str

engine = create_engine("sqlite:///articles.db")
app = LightApi(
    engine=engine,
    cors_origins=["https://example.com"],
)
app.register({"/articles": ArticleEndpoint})
app.run()
```
