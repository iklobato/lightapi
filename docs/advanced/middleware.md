---
title: Middleware
---

LightAPI provides a middleware system that lets you process requests and responses globally before and after your endpoint logic. The framework includes built-in middleware for common use cases and supports custom middleware.

## Built-in Middleware

LightAPI provides several built-in middleware classes for common functionality:

### CORSMiddleware

Handles Cross-Origin Resource Sharing (CORS) automatically:

```python
from lightapi.core import LightApi, CORSMiddleware
from lightapi.rest import RestEndpoint

class APIEndpoint(RestEndpoint):
    class Configuration:
        http_method_names = ['GET', 'POST', 'OPTIONS']

app = LightApi()
app.register({'/api': APIEndpoint})

# Basic CORS support
app.add_middleware([CORSMiddleware()])

# Custom CORS configuration
cors_middleware = CORSMiddleware(
    allow_origins=['https://myapp.com', 'https://admin.myapp.com'],
    allow_methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
    allow_headers=['Authorization', 'Content-Type', 'X-API-Key'],
    allow_credentials=True
)
app.add_middleware([cors_middleware])
```

### AuthenticationMiddleware

Applies authentication globally to all endpoints:

```python
from lightapi.core import LightApi, AuthenticationMiddleware
from lightapi.auth import JWTAuthentication
from lightapi.rest import RestEndpoint

class User(RestEndpoint):
    # No need to specify authentication_class here
    pass

class Product(RestEndpoint):
    pass

app = LightApi()

# Apply JWT authentication to all endpoints
app.add_middleware([
    AuthenticationMiddleware(JWTAuthentication)
])

app.register({'/users': User, '/products': Product})
app.run()
```

## Custom Middleware

Create custom middleware by subclassing the `Middleware` base class:

### 1. Creating Middleware

```python
from lightapi.core import Middleware, Response

class TimingMiddleware(Middleware):
    def process(self, request, response):
        import time
        # Before handling (response is None)
        if response is None:
            request.state.start_time = time.time()
            return None

        # After handling
        duration = time.time() - request.state.start_time
        response.headers['X-Process-Time'] = str(round(duration, 4))
        return response

class LoggingMiddleware(Middleware):
    def process(self, request, response):
        # Pre-processing
        if response is None:
            print(f"Request: {request.method} {request.url}")
            return None
        
        # Post-processing
        print(f"Response: {response.status_code}")
        return response

class RateLimitMiddleware(Middleware):
    def __init__(self):
        self.requests = {}
        self.limit = 100  # requests per minute
        
    def process(self, request, response):
        if response is None:
            import time
            client_ip = request.client.host
            current_time = time.time()
            
            # Clean old entries
            minute_ago = current_time - 60
            self.requests = {ip: times for ip, times in self.requests.items() 
                           if any(t > minute_ago for t in times)}
            
            # Check rate limit
            if client_ip not in self.requests:
                self.requests[client_ip] = []
            
            recent_requests = [t for t in self.requests[client_ip] if t > minute_ago]
            
            if len(recent_requests) >= self.limit:
                from starlette.responses import JSONResponse
                return JSONResponse(
                    {"error": "Rate limit exceeded"}, 
                    status_code=429
                )
            
            self.requests[client_ip].append(current_time)
            return None
        
        return response
```

**Important concepts:**

- The `process` method is called twice per request:
  - **Before** the endpoint: `response` is `None` (pre-processing)
  - **After** the endpoint: `response` is the generated response (post-processing)
- To short-circuit the request (e.g., for authentication or rate limiting), return a `Response` directly during pre-processing
- Use `request.state` to store data between pre and post-processing

### 2. Registering Middleware

Add your middleware classes to the application via `add_middleware`:

```python
from lightapi import LightApi
from app.middleware import TimingMiddleware, LoggingMiddleware, RateLimitMiddleware

app = LightApi()

# Register middleware in order of execution
app.add_middleware([
    RateLimitMiddleware,      # Check rate limits first
    LoggingMiddleware,        # Log requests
    TimingMiddleware          # Time processing
])

app.register({'/items': Item})
app.run()
```

## Combining Built-in and Custom Middleware

You can combine built-in and custom middleware:

```python
from lightapi.core import LightApi, CORSMiddleware, AuthenticationMiddleware
from lightapi.auth import JWTAuthentication
from app.middleware import LoggingMiddleware, TimingMiddleware

app = LightApi()

# Middleware order matters - they execute in the order registered
app.add_middleware([
    LoggingMiddleware,                        # Log all requests first
    CORSMiddleware(),                         # Handle CORS
    AuthenticationMiddleware(JWTAuthentication), # Authenticate requests
    TimingMiddleware                          # Time processing last
])

app.register({'/api': APIEndpoint})
app.run()
```

## Middleware Execution Order

Middleware executes in the order it's registered:

1. **Pre-processing**: First to last (top to bottom)
2. **Endpoint execution**
3. **Post-processing**: Last to first (bottom to top)

```python
app.add_middleware([
    MiddlewareA,  # Pre: 1st, Post: 3rd
    MiddlewareB,  # Pre: 2nd, Post: 2nd  
    MiddlewareC   # Pre: 3rd, Post: 1st
])
```

## Advanced Middleware Examples

### Conditional Middleware

Apply middleware only to specific conditions:

```python
class ConditionalMiddleware(Middleware):
    def process(self, request, response):
        # Only apply to API endpoints
        if not request.url.path.startswith('/api/'):
            return response
        
        if response is None:
            # Pre-processing for API endpoints only
            request.state.api_request = True
            return None
        
        # Post-processing for API endpoints
        if hasattr(request.state, 'api_request'):
            response.headers['X-API-Version'] = '1.0'
        return response
```

### Error Handling Middleware

```python
class ErrorHandlingMiddleware(Middleware):
    def process(self, request, response):
        if response is None:
            return None
        
        # Handle different error status codes
        if response.status_code >= 500:
            print(f"Server error: {response.status_code}")
            # Could send to monitoring service
        elif response.status_code >= 400:
            print(f"Client error: {response.status_code}")
        
        return response
```

All incoming requests and outgoing responses will pass through your middleware in the order they are registered.
