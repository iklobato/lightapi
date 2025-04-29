---
title: Endpoint Classes
---

## RestEndpoint

`RestEndpoint` is the base class for building resource endpoints in LightAPI. It provides default implementations for common HTTP methods (GET, POST, PUT, PATCH, DELETE, OPTIONS) and supports pluggable features:

### Configuration

Each `RestEndpoint` subclass can define an inner `Configuration` class with the following attributes:

- `http_method_names` (List[str]): Allowed HTTP methods (default: `['GET','POST','PUT','DELETE','PATCH','OPTIONS']`).
- `validator_class` (Type[Validator], optional): Class for validating request data.
- `filter_class` (Type[BaseFilter], optional): Class for filtering querysets based on request.
- `authentication_class` (Type[BaseAuthentication], optional): Class for authenticating requests.
- `caching_class` (Type[BaseCache], optional): Class for caching responses.
- `caching_method_names` (List[str], optional): Which methods to cache (e.g., `['get']`).
- `pagination_class` (Type[Paginator], optional): Class for paginating querysets.

### Lifecycle

When a request arrives, `RestEndpoint` handlers:

1. Call `_setup(request, session)` to attach:
   - `self.request`: the incoming request raised by Starlette.
   - `self.session`: the SQLAlchemy session for database operations.
2. Invoke `_setup_auth()`, `_setup_cache()`, `_setup_filter()`, `_setup_validator()`, `_setup_pagination()` to initialize any configured components.
3. Dispatch to the HTTP method handler (e.g., `get`, `post`).

If `authentication_class` is set and `authenticate(request)` returns `False`, the request is short-circuited with a 401 response.

### Default Methods

- `async def get(self, request) -> Tuple[dict, int]`:
  - Lists all records or retrieves one by `id` query parameter.
  - Applies filtering and pagination when configured.
  - Returns `{'results': [...]}, 200`.

- `async def post(self, request) -> Tuple[dict, int]`:
  - Creates a new record from `request.data`.
  - Applies validation when `validator_class` is set.
  - Returns `{'result': {...}}, 201` or `{'error': '...'}, 400` on failure.

- `async def put(self, request) -> Tuple[dict, int]`:
  - Replaces an existing record by `id` path parameter.
  - Returns `{'result': {...}}, 200` or `{'error': '...'}, 404/400`.

- `async def patch(self, request) -> Tuple[dict, int]`:
  - Partially updates fields on an existing record.

- `async def delete(self, request) -> Tuple[dict, int]`:
  - Deletes a record by `id`.
  - Returns `{'result': 'Object deleted'}, 204`.

- `def options(self, request) -> Tuple[dict, int]`:
  - Returns allowed methods from `Configuration.http_method_names`, status 200.

Each handler returns either a `(body, status_code)` tuple, a `Response` instance, or a Python object which is serialized to JSON with status 200.

### Example

```python
from lightapi.rest import RestEndpoint
from lightapi.auth import JWTAuthentication

class UserEndpoint(RestEndpoint):
    class Configuration:
        http_method_names = ['GET', 'POST']
        authentication_class = JWTAuthentication
        pagination_class = CustomPaginator

    # Override GET to add custom logic
    async def get(self, request):
        base_response, status = await super().get(request)
        return {'users': base_response['results']}, status
```
