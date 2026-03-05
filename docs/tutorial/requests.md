---
title: Handling Requests
description: Working with the Starlette Request object in LightAPI v2 method overrides
---

# Handling Requests

In LightAPI v2, the `request` parameter in method overrides is a standard [Starlette `Request`](https://www.starlette.io/requests/) object.

## JSON Payloads

For `POST`, `PUT`, and `PATCH` overrides, read the body with `await request.body()` (async) or `request.body()` in sync methods, then parse as JSON:

=== "Async"

    ```python
    import json

    class OrderEndpoint(RestEndpoint):
        item: str
        quantity: int

        async def post(self, request):
            data = json.loads(await request.body())
            # data is a plain dict
            return await self._create_async(data)
    ```

=== "Sync"

    ```python
    import json

    class OrderEndpoint(RestEndpoint):
        item: str
        quantity: int

        def post(self, request):
            data = json.loads(request.body())
            return self.create(data)
    ```

You can also use `await request.json()` as a shorthand for async handlers:

```python
async def post(self, request):
    data = await request.json()
    return await self._create_async(data)
```

## Path Parameters

Detail routes (`/items/{id}`) pass `pk` directly to the handler — you rarely need to read it from the request. If you need it manually:

```python
async def get(self, request):
    item_id = request.path_params.get("id")
```

## Query Parameters

Query parameters are available via `request.query_params` (a `QueryParams` mapping):

```python
async def get(self, request):
    page = request.query_params.get("page", "1")
    search = request.query_params.get("search", "")
```

For automatic filtering and pagination, use `Meta.filtering` and `Meta.pagination` instead of manual query parameter parsing.

## Request Headers

```python
async def get(self, request):
    auth_header = request.headers.get("Authorization")
    content_type = request.headers.get("Content-Type")
    user_agent = request.headers.get("User-Agent")
```

## Authenticated user

When `JWTAuthentication` is configured, the decoded token payload is stored in `request.state.user` after successful authentication:

```python
async def post(self, request):
    user = request.state.user   # dict from JWT payload
    user_id = user.get("sub")
    data = await request.json()
    data["author_id"] = int(user_id)
    return await self._create_async(data)
```

## Request method

```python
async def get(self, request):
    print(request.method)    # "GET"
    print(request.url.path)  # "/items"
```
