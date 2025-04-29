---
title: Creating Endpoints
---

LightAPI auto-generates standard CRUD routes when you register SQLAlchemy models, but you can also define custom endpoints by subclassing the `RestEndpoint` class.

## Subclassing RestEndpoint

```python
# app/endpoints/custom_user.py
from lightapi.rest import RestEndpoint

class CustomUserEndpoint(RestEndpoint):
    tablename = 'users'
    # Only allow GET and POST methods
    http_method_names = ['GET', 'POST']

    async def get(self, request):
        return {'message': 'Custom GET endpoint'}

    async def post(self, request):
        data = await request.json()
        return {'received': data}
```

## Registering Custom Endpoints

```python
from lightapi import LightApi
from app.endpoints.custom_user import CustomUserEndpoint

app = LightApi()
app.register({'/custom-users': CustomUserEndpoint})
```

## HTTP Method Configuration

- `http_method_names`: List of allowed HTTP methods.
- `http_exclude`: List of methods to exclude from the default set.

```python
class ReadOnlyEndpoint(RestEndpoint):
    tablename = 'items'
    http_method_names = ['GET']
```

## Accessing Path Parameters

You can retrieve path parameters from `request.match_info`:

```python
async def get(self, request):
    item_id = request.match_info['id']
    # Use item_id in your logic
```

## Custom Route Prefixes

You can add a common prefix to routes when registering:

```python
app.register(
    {'/v2/items': Item},
    prefix='/api'
)
# Endpoints will be mounted at /api/v2/items/...
```
