---
title: Custom Application Example
---

This example demonstrates building a fully custom LightAPI application by composing the core classes:

```python
import time
from lightapi import LightApi, Middleware
from lightapi.auth import JWTAuthentication
from lightapi.cache import RedisCache
from lightapi.filters import ParameterFilter
from lightapi.pagination import Paginator
from lightapi.rest import RestEndpoint, Validator, Response

# 1. Custom Middleware for Logging and Timing
class LoggingMiddleware(Middleware):
    def process(self, request, response):
        # Pre-request: log method and URL
        if response is None:
            request.start_time = time.time()
            print(f"[Request] {request.method} {request.url}")
            return None
        # Post-response: log status and elapsed time
        elapsed = time.time() - request.start_time
        print(f"[Response] {response.status_code} completed in {elapsed:.3f}s")
        return response

# 2. Custom Validator to enforce field rules
class ItemValidator(Validator):
    def validate_name(self, value: str) -> str:
        if not value or len(value) < 3:
            raise ValueError("Item name must be at least 3 characters")
        return value.strip()

# 3. Define a custom RestEndpoint using all pluggable features
class ItemEndpoint(RestEndpoint):
    tablename = 'items'

    class Configuration:
        authentication_class = JWTAuthentication
        caching_class = RedisCache
        caching_method_names = ['get']
        filter_class = ParameterFilter
        pagination_class = Paginator
        validator_class = ItemValidator

    # Override POST to wrap default behavior in a Response
    async def post(self, request):
        body, status = await super().post(request)
        return Response({ 'created': body['result'] }, status_code=status)

# 4. Assemble the application
app = LightApi(
    database_url='sqlite+aiosqlite:///./app.db',
    enable_swagger=True,
    swagger_title='Custom App API',
    swagger_version='1.0.0',
    swagger_description='Demo of custom LightAPI application'
)

# 5. Register middleware and endpoints
app.add_middleware([LoggingMiddleware])
app.register({ '/items': ItemEndpoint })

# 6. Run the server
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True, reload=True)
```

### Key integrations

- **JWTAuthentication**: Secures all `/items` requests.  Issue tokens via `JWTAuthentication.generate_token({...})`.
- **RedisCache**: Caches GET responses to reduce database load.
- **ParameterFilter + Paginator**: Enables query-param filtering and pagination automatically.
- **ItemValidator**: Validates the `name` field on POST/PUT operations.
- **LoggingMiddleware**: Logs each request and response timing.
- **Response**: Builds response with custom status and payload.
- **LightApi**: Configured to serve Swagger UI and OpenAPI schema at `/api/docs` and `/openapi.json`.

With this setup, your `/items` endpoint is authenticated, cached, filterable, paginated, validated, logged, and documented—all with minimal boilerplate. 