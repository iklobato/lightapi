---
title: Core API
---

## LightApi

The `LightApi` class is the central application object that configures routes, middleware, and runs the server.

### Initialization

```python
def __init__(
    self,
    database_url: str = "sqlite:///app.db",
    swagger_title: str = "LightAPI Documentation",
    swagger_version: str = "1.0.0",
    swagger_description: str = "API automatic documentation",
    enable_swagger: bool = True
):
    ...
```

- `database_url` (str): SQLAlchemy database URL (e.g., `sqlite:///app.db`).
- `swagger_title` (str): Title for the Swagger UI.
- `swagger_version` (str): API version for the OpenAPI spec.
- `swagger_description` (str): Description for the OpenAPI spec.
- `enable_swagger` (bool): Mounts Swagger routes when `True`.

Upon initialization, `LightApi` sets up the database engine and session via `setup_database`, and registers OpenAPI routes if enabled.

### Methods

#### register(endpoints: Dict[str, Type[RestEndpoint]]) -> None

Registers endpoint classes and mounts their routes.

- **Parameters:**
  - `endpoints`: Mapping of URL prefixes to `RestEndpoint` subclasses.

Adds each endpoint's routes to the internal Starlette application and registers OpenAPI metadata when available.

Raises `TypeError` if a handler is not a subclass of `RestEndpoint`.

#### add_middleware(middleware_classes: List[Type[Middleware]]) -> None

Adds application-wide middleware.

- **Parameters:**
  - `middleware_classes`: List of `Middleware` subclasses to apply globally.

#### run(host: str = "0.0.0.0", port: int = 8000, debug: bool = False) -> None

Starts the ASGI server using Uvicorn.

- **Parameters:**
  - `host`: Host address to bind (default: `"0.0.0.0"`).
  - `port`: Port number (default: `8000`).
  - `debug`: Toggle Starlette debug mode (default: `False`).

### Example

```python
from lightapi import LightApi
from app.endpoints import UserEndpoint
from app.middleware import AuthMiddleware, TimingMiddleware

app = LightApi(database_url="postgresql+asyncpg://user:pass@db/db")
app.add_middleware([AuthMiddleware, TimingMiddleware])
app.register({"/users": UserEndpoint})
app.run(host="0.0.0.0", port=8000, debug=True)
```
