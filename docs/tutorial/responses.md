---
title: Working with Responses
description: Response types and patterns in LightAPI v2 method overrides
---

# Working with Responses

LightAPI's built-in CRUD methods return Starlette `Response` objects. When overriding methods, you can return any Starlette response or use the built-in helpers.

## Built-in CRUD returns

The built-in helpers (`self.create`, `self._create_async`, etc.) return a `starlette.responses.Response`:

| Operation | Status |
|-----------|--------|
| `list` / `_list_async` | `200 OK` |
| `retrieve` / `_retrieve_async` | `200 OK` |
| `create` / `_create_async` | `201 Created` |
| `update` / `_update_async` | `200 OK` |
| `destroy` / `_destroy_async` | `204 No Content` |

## Returning JSON responses

Use `starlette.responses.JSONResponse` for custom responses:

```python
from starlette.responses import JSONResponse
from lightapi import RestEndpoint

class OrderEndpoint(RestEndpoint):
    item: str
    quantity: int

    async def post(self, request):
        data = await request.json()
        if data.get("quantity", 0) > 100:
            return JSONResponse(
                {"detail": "Quantity cannot exceed 100"},
                status_code=422,
            )
        return await self._create_async(data)
```

## Using `Response` from lightapi

`lightapi.Response` is re-exported from `lightapi.core` for backward compatibility:

```python
from lightapi import Response

class MyEndpoint(RestEndpoint):
    name: str

    def get(self, request):
        return Response({"message": "Hello"}, status_code=200)
```

## Error responses

```python
from starlette.responses import JSONResponse

# 404 Not Found
return JSONResponse({"detail": "Not found"}, status_code=404)

# 422 Validation error
return JSONResponse({"detail": "Invalid input"}, status_code=422)

# 409 Conflict
return JSONResponse({"detail": "Already exists"}, status_code=409)
```

## Starlette response types

Since LightAPI produces a plain Starlette app, any Starlette response type works:

```python
from starlette.responses import (
    JSONResponse,
    PlainTextResponse,
    FileResponse,
    StreamingResponse,
    RedirectResponse,
)

async def get(self, request):
    return PlainTextResponse("OK")

async def download(self, request):
    return FileResponse("/path/to/file.csv")
```

## Background tasks

Use `self.background(fn, *args, **kwargs)` to schedule work after the response is sent:

```python
def notify_team(item_id: int) -> None:
    print(f"New order #{item_id} created")

class OrderEndpoint(RestEndpoint):
    item: str

    async def post(self, request):
        data = await request.json()
        response = await self._create_async(data)
        if response.status_code == 201:
            import json
            body = json.loads(response.body)
            self.background(notify_team, body["id"])
        return response
```

See [Async Support — Background Tasks](../advanced/async.md#background-tasks) for details.

## Testing responses

When testing with `httpx.AsyncClient`:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from lightapi import LightApi

@pytest.mark.asyncio
async def test_create():
    # ... build app ...
    async with AsyncClient(transport=ASGITransport(app=starlette_app), base_url="http://test") as client:
        resp = await client.post("/orders", json={"item": "Widget", "quantity": 5})
    assert resp.status_code == 201
    assert resp.json()["item"] == "Widget"
```
