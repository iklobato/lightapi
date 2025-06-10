# Core API Reference

The core module contains the main application class and essential components for building APIs with LightAPI.

## LightApi

::: lightapi.core.LightApi

The main application class for building REST APIs. LightApi orchestrates all components including routing, middleware, database connections, and documentation generation.

### Basic Usage

```python
from lightapi import LightApi

# Simple initialization
app = LightApi()

# With database URL
app = LightApi(database_url="postgresql://user:pass@localhost/db")

# With Swagger documentation
app = LightApi(
    database_url="sqlite:///app.db",
    swagger_title="My API",
    swagger_version="1.0.0",
    swagger_description="A powerful API built with LightAPI",
    enable_swagger=True
)
```

### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `database_url` | `str` | `None` | SQLAlchemy database connection string |
| `swagger_title` | `str` | `None` | Title for Swagger documentation |
| `swagger_version` | `str` | `None` | API version for documentation |
| `swagger_description` | `str` | `None` | Description for API documentation |
| `enable_swagger` | `bool` | `None` | Whether to enable Swagger UI |
| `cors_origins` | `List[str]` | `None` | List of allowed CORS origins |

### Key Methods

#### register()

Registers REST endpoints with the application.

```python
from lightapi import LightApi, RestEndpoint
from sqlalchemy import Column, Integer, String

class User(RestEndpoint):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String(100))

app = LightApi()
app.register({
    '/users': User,
    '/users/{id}': User,  # URL parameters automatically handled
})
```

**Parameters:**
- `endpoints` (Dict[str, Type[RestEndpoint]]): Mapping of URL paths to endpoint classes

#### add_middleware()

Adds middleware to the application processing pipeline.

```python
from lightapi.core import CORSMiddleware, AuthenticationMiddleware
from lightapi.auth import JWTAuthentication

app = LightApi()
app.add_middleware([
    CORSMiddleware(allow_origins=["*"]),
    AuthenticationMiddleware(JWTAuthentication())
])
```

**Parameters:**
- `middleware_classes` (List[Type[Middleware]]): List of middleware classes to add

#### run()

Starts the development server.

```python
app.run(
    host="0.0.0.0",
    port=8000,
    debug=True,
    reload=True
)
```

**Parameters:**
- `host` (str): Server host address
- `port` (int): Server port number
- `debug` (bool): Enable debug mode
- `reload` (bool): Enable auto-reload on code changes

### Advanced Configuration

```python
import os
from lightapi import LightApi
from lightapi.core import CORSMiddleware

# Production configuration
app = LightApi(
    database_url=os.getenv("DATABASE_URL"),
    swagger_title="Production API",
    swagger_version="2.1.0",
    enable_swagger=os.getenv("ENVIRONMENT") != "production",
    cors_origins=[
        "https://myapp.com",
        "https://admin.myapp.com"
    ]
)

# Add security middleware
app.add_middleware([
    CORSMiddleware(
        allow_origins=["https://myapp.com"],
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Authorization", "Content-Type"]
    )
])
```

---

## Response

::: lightapi.core.Response

Enhanced JSON response class with additional functionality for API responses.

### Basic Usage

```python
from lightapi.core import Response

# Simple response
return Response({"message": "Success"})

# Response with custom status code
return Response({"error": "Not found"}, status_code=404)

# Response with headers
return Response(
    {"data": "value"}, 
    headers={"X-Custom-Header": "value"}
)
```

### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `content` | `Any` | `None` | Response body content |
| `status_code` | `int` | `200` | HTTP status code |
| `headers` | `Dict` | `None` | Additional HTTP headers |
| `media_type` | `str` | `None` | Response media type |
| `content_type` | `str` | `None` | Content-Type header value |

### Examples

```python
# Success response
def get_user(self, request):
    user = {"id": 1, "name": "John"}
    return Response(user)

# Error response
def delete_user(self, request):
    if not user_exists:
        return Response(
            {"error": "User not found"}, 
            status_code=404
        )

# Response with custom headers
def api_info(self, request):
    return Response(
        {"version": "1.0.0"}, 
        headers={
            "X-API-Version": "1.0.0",
            "Cache-Control": "max-age=3600"
        }
    )
```

---

## Middleware

::: lightapi.core.Middleware

Base class for creating custom middleware components.

### Creating Custom Middleware

```python
from lightapi.core import Middleware, Response

class LoggingMiddleware(Middleware):
    def process(self, request, response):
        # Pre-processing: runs before endpoint
        print(f"Request: {request.method} {request.url}")
        
        # Return None to continue processing
        # Return Response to short-circuit
        return None

class RateLimitMiddleware(Middleware):
    def __init__(self, max_requests=100):
        self.max_requests = max_requests
        self.request_counts = {}
    
    def process(self, request, response):
        client_ip = request.client.host
        
        # Increment request count
        self.request_counts[client_ip] = self.request_counts.get(client_ip, 0) + 1
        
        # Check rate limit
        if self.request_counts[client_ip] > self.max_requests:
            return Response(
                {"error": "Rate limit exceeded"}, 
                status_code=429
            )
        
        return None  # Continue processing
```

### Using Custom Middleware

```python
app = LightApi()
app.add_middleware([
    LoggingMiddleware(),
    RateLimitMiddleware(max_requests=1000)
])
```

---

## CORSMiddleware

::: lightapi.core.CORSMiddleware

Built-in middleware for handling Cross-Origin Resource Sharing (CORS).

### Basic Usage

```python
from lightapi.core import CORSMiddleware

# Allow all origins (development only)
cors_middleware = CORSMiddleware(allow_origins=["*"])

# Production configuration
cors_middleware = CORSMiddleware(
    allow_origins=[
        "https://myapp.com",
        "https://admin.myapp.com"
    ],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"]
)

app.add_middleware([cors_middleware])
```

### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `allow_origins` | `List[str]` | `["*"]` | Allowed origin domains |
| `allow_methods` | `List[str]` | `["*"]` | Allowed HTTP methods |
| `allow_headers` | `List[str]` | `["*"]` | Allowed request headers |

### Examples

```python
# Development setup
dev_cors = CORSMiddleware(allow_origins=["*"])

# Production setup with specific domains
prod_cors = CORSMiddleware(
    allow_origins=[
        "https://myapp.com",
        "https://app.mycompany.com",
        "https://admin.mycompany.com"
    ],
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type", 
        "X-Requested-With",
        "X-CSRF-Token"
    ]
)

# API-specific CORS
api_cors = CORSMiddleware(
    allow_origins=["https://partner-site.com"],
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"]
)
```

---

## AuthenticationMiddleware

::: lightapi.core.AuthenticationMiddleware

Middleware for applying authentication globally to all endpoints.

### Basic Usage

```python
from lightapi.core import AuthenticationMiddleware
from lightapi.auth import JWTAuthentication

# Apply JWT authentication to all endpoints
auth_middleware = AuthenticationMiddleware(JWTAuthentication())
app.add_middleware([auth_middleware])
```

### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `authentication_class` | `BaseAuthentication` | `None` | Authentication class instance |

### Examples

```python
from lightapi.auth import JWTAuthentication, BaseAuthentication

# JWT authentication for all endpoints
jwt_auth = AuthenticationMiddleware(JWTAuthentication())

# Custom authentication
class APIKeyAuth(BaseAuthentication):
    def authenticate(self, request):
        api_key = request.headers.get("X-API-Key")
        return api_key == "secret-key"

api_key_auth = AuthenticationMiddleware(APIKeyAuth())

# Apply middleware
app.add_middleware([jwt_auth])
```

### Notes

- Middleware-level authentication applies to ALL endpoints
- Endpoint-level authentication (via Configuration class) overrides middleware authentication
- OPTIONS requests are automatically allowed for CORS preflight

---

## Configuration Integration

### Environment Variables

LightAPI uses environment variables for configuration:

```bash
# Database
export LIGHTAPI_DATABASE_URL="postgresql://user:pass@localhost/db"

# JWT
export LIGHTAPI_JWT_SECRET="your-secret-key"

# Swagger
export LIGHTAPI_SWAGGER_TITLE="My API"
export LIGHTAPI_SWAGGER_VERSION="1.0.0"
export LIGHTAPI_SWAGGER_DESCRIPTION="API Description"

# CORS
export LIGHTAPI_CORS_ORIGINS="https://myapp.com,https://admin.myapp.com"
```

### Programmatic Configuration

```python
from lightapi import LightApi
from lightapi.config import config

# Update config before creating app
config.update(
    database_url="sqlite:///app.db",
    jwt_secret="secret-key",
    enable_swagger=True
)

app = LightApi()
```

---

## Error Handling

### Built-in Error Responses

LightAPI provides consistent error responses:

```python
# 400 Bad Request - Validation errors
{
    "error": "Validation failed",
    "details": {"field": "This field is required"}
}

# 401 Unauthorized - Authentication required
{"error": "Authentication failed"}

# 403 Forbidden - Access denied
{"error": "Access denied"}

# 404 Not Found - Resource not found
{"error": "Resource not found"}

# 405 Method Not Allowed
{"error": "Method POST not allowed"}

# 500 Internal Server Error
{"error": "Internal server error"}
```

### Custom Error Handling

```python
from lightapi.core import Response

class CustomEndpoint(RestEndpoint):
    def get(self, request):
        try:
            # Your logic here
            return {"data": "success"}
        except ValueError as e:
            return Response(
                {"error": f"Invalid input: {str(e)}"}, 
                status_code=400
            )
        except Exception as e:
            return Response(
                {"error": "Something went wrong"}, 
                status_code=500
            )
``` 