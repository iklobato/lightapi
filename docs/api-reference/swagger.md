---
title: OpenAPI / Swagger Reference
description: API schema generation in LightAPI v2
---

# OpenAPI / Swagger

## v2 status

LightAPI v2 does **not** include a built-in Swagger UI or OpenAPI schema endpoint. The v2 architecture is a pure Starlette ASGI application — you can integrate any OpenAPI tooling that works with Starlette.

## Adding OpenAPI with Starlette

Starlette has native support for OpenAPI schema generation via `starlette.routing.Route` and the `apispec`/`spectree`/`starlette-openapi` ecosystem.

### Option 1 — `starlette-openapi` (third-party)

```bash
uv add starlette-openapi
```

```python
from sqlalchemy import create_engine
from lightapi import LightApi, RestEndpoint, Field
from starlette_openapi import OpenAPI

class BookEndpoint(RestEndpoint):
    title: str = Field(min_length=1)
    author: str

engine = create_engine("sqlite:///books.db")
app_instance = LightApi(engine=engine)
app_instance.register({"/books": BookEndpoint})

starlette_app = app_instance.build_app()

# Wrap with OpenAPI
openapi = OpenAPI(app=starlette_app, title="Book API", version="1.0.0")
```

### Option 2 — `spectree`

```bash
uv add spectree
```

### Option 3 — Manual schema endpoint

Add a static OpenAPI JSON route directly:

```python
import json
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route
from lightapi import LightApi, RestEndpoint

class BookEndpoint(RestEndpoint):
    title: str
    author: str

engine = create_engine("sqlite:///books.db")
app = LightApi(engine=engine)
app.register({"/books": BookEndpoint})

async def openapi_schema(request: Request):
    schema = {
        "openapi": "3.0.0",
        "info": {"title": "My API", "version": "1.0.0"},
        "paths": {
            "/books": {
                "get":  {"summary": "List books",   "responses": {"200": {"description": "OK"}}},
                "post": {"summary": "Create a book", "responses": {"201": {"description": "Created"}}},
            },
        },
    }
    return JSONResponse(schema)

# Inject extra route before building
app._routes.append(Route("/openapi.json", endpoint=openapi_schema))
starlette_app = app.build_app()
```

## Pydantic v2 schemas

LightAPI internally generates Pydantic v2 `BaseModel` subclasses for every endpoint. You can access them for schema introspection:

```python
from lightapi import RestEndpoint, SchemaFactory, Field

class BookEndpoint(RestEndpoint):
    title: str = Field(min_length=1)
    author: str

schema_create, schema_read = SchemaFactory.build(BookEndpoint)

print(schema_create.model_json_schema())
# {
#   "properties": {
#     "title": {"minLength": 1, "title": "Title", "type": "string"},
#     "author": {"title": "Author", "type": "string"}
#   },
#   "required": ["title", "author"],
#   "title": "BookEndpointCreate",
#   "type": "object"
# }
```

## v1 Swagger (legacy)

The v1 `lightapi.core.LightApi` class includes built-in Swagger UI at `/docs`. If you need this feature, use the v1 class:

```python
from lightapi.core import LightApi as LightApiV1

app = LightApiV1(
    database_url="sqlite:///app.db",
    enable_swagger=True,
    swagger_title="My API",
)
```

Note that `lightapi.core.LightApi` (v1) uses a different endpoint model (`Base + RestEndpoint`) and is not compatible with the v2 `RestEndpoint` syntax.
