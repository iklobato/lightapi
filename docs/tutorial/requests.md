---
title: Handling Requests
---

LightAPI simplifies request handling by automatically parsing incoming data and making parameters accessible.

## JSON Payloads

For `POST`, `PUT`, and `PATCH` methods, LightAPI reads the request body and attempts to parse it as JSON. Parsed data is available on `request.data`:

```python
async def post(self, request):
    payload = request.data  # Dict from JSON body
    # Use payload directly
```

If the body is empty or invalid JSON, `request.data` will be an empty dict.

## Path Parameters

When defining endpoints with path parameters (e.g., `/items/{id}`), you can access them via `request.path_params` or `request.match_info`:

```python
async def get(self, request):
    item_id = request.path_params.get('id')
    # or
    item_id = request.match_info['id']
```

## Query Parameters

Query parameters (e.g., `?limit=10&sort=asc`) are available via:

```python
params = dict(request.query_params)
limit = params.get('limit')
sort_order = params.get('sort')
```

You can also leverage the built-in `ParameterFilter` (see Advanced → Request Filtering) to automatically apply filters based on query parameters.

## Request Headers

You can inspect headers directly from the `request` object:

```python
auth_header = request.headers.get('Authorization')
user_agent = request.headers.get('User-Agent')
```

This allows you to implement custom authentication, content negotiation, or other header-based logic.
