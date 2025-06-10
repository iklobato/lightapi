# Middleware Example

This example demonstrates how to create and use custom middleware in LightAPI for cross-cutting concerns like logging, CORS, rate limiting, and request processing.

## Overview

Learn how to:
- Create custom middleware classes for request/response processing
- Implement logging middleware with request tracking
- Add CORS support for cross-origin requests
- Build rate limiting middleware for API protection
- Chain multiple middleware components
- Handle pre-request and post-response processing

## Complete Example Code

```python
from sqlalchemy import Column, Integer, String
from lightapi.core import LightApi, Middleware, Response
from lightapi.rest import RestEndpoint
import time
import uuid

# Logging middleware to track request/response times
class LoggingMiddleware(Middleware):
    """
    Middleware for request logging.
    
    Logs request details and adds a unique ID to each request.
    """
    
    def process(self, request, response=None):
        """
        Process an HTTP request.
        
        If the response is None, this is being called before the request is handled.
        Otherwise, it's being called after the request has been handled.
        """
        if response is None:
            # Generate a unique ID for this request
            request_id = str(uuid.uuid4())
            request.id = request_id  
            
            # Log request details
            print(f"[{request_id}] Request: {request.method} {request.url.path}")
            
            # Continue processing
            return super().process(request, response)
        else:
            # Log response details
            print(f"[{getattr(request, 'id', 'unknown')}] Response: {response.status_code}")
            
            # Add response headers
            if not hasattr(response, 'headers'):
                response.headers = {}
            response.headers['X-Request-ID'] = getattr(request, 'id', 'unknown')
            
            return response

# CORS middleware to handle cross-origin requests
class CORSMiddleware(Middleware):
    """
    Middleware for handling Cross-Origin Resource Sharing (CORS).
    
    Adds CORS headers to responses and handles preflight OPTIONS requests.
    """
    
    # CORS configuration
    allowed_origins = ['*']
    allowed_methods = ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
    allowed_headers = ['Authorization', 'Content-Type']
    max_age = 86400  # 24 hours
    
    def process(self, request, response=None):
        """
        Process an HTTP request.
        
        Adds CORS headers to responses and handles OPTIONS requests.
        """
        if request.method == 'OPTIONS':
            # Handle preflight request
            return Response(
                None,
                status_code=204,
                headers={
                    'Access-Control-Allow-Origin': ','.join(self.allowed_origins),
                    'Access-Control-Allow-Methods': ','.join(self.allowed_methods),
                    'Access-Control-Allow-Headers': ','.join(self.allowed_headers),
                    'Access-Control-Max-Age': str(self.max_age)
                }
            )
        elif response:
            # Add CORS headers to the response
            response.headers['Access-Control-Allow-Origin'] = ','.join(self.allowed_origins)
            return response
        else:
            # Continue processing
            return super().process(request, response)

# Rate limiting middleware
class RateLimitMiddleware(Middleware):
    """
    Middleware for rate limiting requests.
    
    Limits the number of requests per client IP address within a time window.
    """
    
    def __init__(self):
        """Initialize the middleware."""
        self.clients = {}
        self.requests_per_minute = 2  # Maximum 2 requests per minute
        self.window = 60  # 60 second window
        
    def process(self, request, response=None):
        """
        Process an HTTP request.
        
        Rate limits requests based on client IP address.
        """
        if response:
            # Just pass through if we already have a response
            return response
            
        # Get client IP address
        client_ip = getattr(request.client, 'host', '127.0.0.1')
        
        # Get current time
        current_time = time.time()
        
        # Initialize client entry if needed
        if client_ip not in self.clients:
            self.clients[client_ip] = []
        
        # Clean up old requests
        recent_requests = []
        for req_time in self.clients[client_ip]:
            if req_time >= current_time - self.window:
                recent_requests.append(req_time)
        self.clients[client_ip] = recent_requests
        
        # Check rate limit
        if len(self.clients[client_ip]) >= self.requests_per_minute:
            # Rate limit exceeded
            return Response(
                {"error": "Rate limit exceeded. Try again later."},
                status_code=429,
                headers={'Retry-After': str(self.window)}
            )
            
        # Add this request to the list
        self.clients[client_ip].append(current_time)
        
        # Continue processing
        return super().process(request, response)

# A simple resource for testing middleware
class HelloWorldEndpoint(RestEndpoint):
    __abstract__ = True  # Not a database model
    
    def get(self, request):
        # Access the request ID added by middleware
        request_id = getattr(request, 'id', 'unknown')
        
        return {
            "message": "Hello, World!",
            "request_id": request_id,
            "timestamp": time.time()
        }, 200
    
    def post(self, request):
        data = getattr(request, 'data', {})
        name = data.get('name', 'World')
        
        return {
            "message": f"Hello, {name}!",
            "timestamp": time.time()
        }, 201
```

## Key Middleware Components

### 1. Logging Middleware

The `LoggingMiddleware` demonstrates pre and post-request processing:

#### Pre-Request Processing
```python
if response is None:
    # Generate a unique ID for this request
    request_id = str(uuid.uuid4())
    request.id = request_id  
    
    # Log request details
    print(f"[{request_id}] Request: {request.method} {request.url.path}")
    
    # Continue processing
    return super().process(request, response)
```

#### Post-Response Processing
```python
else:
    # Log response details
    print(f"[{getattr(request, 'id', 'unknown')}] Response: {response.status_code}")
    
    # Add response headers
    if not hasattr(response, 'headers'):
        response.headers = {}
    response.headers['X-Request-ID'] = getattr(request, 'id', 'unknown')
    
    return response
```

**Features:**
- Generates unique request IDs for tracking
- Logs request method and path
- Logs response status codes
- Adds tracking headers to responses

### 2. CORS Middleware

The `CORSMiddleware` handles cross-origin resource sharing:

#### Preflight Handling
```python
if request.method == 'OPTIONS':
    # Handle preflight request
    return Response(
        None,
        status_code=204,
        headers={
            'Access-Control-Allow-Origin': ','.join(self.allowed_origins),
            'Access-Control-Allow-Methods': ','.join(self.allowed_methods),
            'Access-Control-Allow-Headers': ','.join(self.allowed_headers),
            'Access-Control-Max-Age': str(self.max_age)
        }
    )
```

#### CORS Headers
```python
elif response:
    # Add CORS headers to the response
    response.headers['Access-Control-Allow-Origin'] = ','.join(self.allowed_origins)
    return response
```

**Configuration Options:**
- `allowed_origins`: List of allowed origin domains
- `allowed_methods`: HTTP methods permitted for CORS
- `allowed_headers`: Headers that can be sent with requests
- `max_age`: How long browsers can cache preflight responses

### 3. Rate Limiting Middleware

The `RateLimitMiddleware` implements IP-based rate limiting:

#### Rate Limit Logic
```python
# Get client IP address
client_ip = getattr(request.client, 'host', '127.0.0.1')

# Clean up old requests outside the time window
recent_requests = []
for req_time in self.clients[client_ip]:
    if req_time >= current_time - self.window:
        recent_requests.append(req_time)
self.clients[client_ip] = recent_requests

# Check rate limit
if len(self.clients[client_ip]) >= self.requests_per_minute:
    return Response(
        {"error": "Rate limit exceeded. Try again later."},
        status_code=429,
        headers={'Retry-After': str(self.window)}
    )
```

**Features:**
- IP-based request tracking
- Configurable time windows and request limits
- Automatic cleanup of expired request records
- HTTP 429 status code for rate limit violations
- Retry-After header for client guidance

## Usage Examples

### Setting Up Middleware

```python
if __name__ == "__main__":
    app = LightApi(
        database_url="sqlite:///middleware_example.db",
        swagger_title="Middleware Example",
        swagger_version="1.0.0",
        swagger_description="Example showing middleware usage with LightAPI",
    )
    
    # Register endpoints
    app.register({
        '/hello': HelloWorldEndpoint,
    })
    
    # Add middleware (order matters - they're processed in sequence)
    app.add_middleware([
        LoggingMiddleware,
        CORSMiddleware,
        RateLimitMiddleware
    ])
    
    app.run(host="localhost", port=8000, debug=True)
```

### Testing the Middleware

#### Basic Request
```bash
curl -X GET http://localhost:8000/hello
```

**Response:**
```json
{
  "message": "Hello, World!",
  "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "timestamp": 1640995200.123
}
```

**Console Output:**
```
[a1b2c3d4-e5f6-7890-abcd-ef1234567890] Request: GET /hello
[a1b2c3d4-e5f6-7890-abcd-ef1234567890] Response: 200
```

#### CORS Preflight Request
```bash
curl -X OPTIONS http://localhost:8000/hello \
  -H "Origin: https://example.com" \
  -H "Access-Control-Request-Method: GET"
```

**Response (204 No Content):**
```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET,POST,PUT,DELETE,OPTIONS
Access-Control-Allow-Headers: Authorization,Content-Type
Access-Control-Max-Age: 86400
```

#### Rate Limiting Test
```bash
# First request - succeeds
curl -X GET http://localhost:8000/hello

# Second request - succeeds  
curl -X GET http://localhost:8000/hello

# Third request - rate limited
curl -X GET http://localhost:8000/hello
```

**Rate Limited Response (429):**
```json
{
  "error": "Rate limit exceeded. Try again later."
}
```

## Advanced Middleware Patterns

### 1. Authentication Middleware

```python
class JWTAuthMiddleware(Middleware):
    """JWT Authentication middleware"""
    
    def __init__(self, secret_key, excluded_paths=None):
        self.secret_key = secret_key
        self.excluded_paths = excluded_paths or ['/docs', '/health']
    
    def process(self, request, response=None):
        if response:
            return response
        
        # Skip authentication for excluded paths
        if request.url.path in self.excluded_paths:
            return super().process(request, response)
        
        # Extract JWT token from Authorization header
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return Response(
                {"error": "Missing or invalid authorization header"},
                status_code=401
            )
        
        token = auth_header[7:]  # Remove 'Bearer ' prefix
        
        try:
            # Decode and validate JWT token
            payload = jwt.decode(token, self.secret_key, algorithms=['HS256'])
            request.user = payload  # Add user info to request
            return super().process(request, response)
        except jwt.InvalidTokenError:
            return Response(
                {"error": "Invalid or expired token"},
                status_code=401
            )
```

### 2. Request Timing Middleware

```python
class TimingMiddleware(Middleware):
    """Request timing and performance monitoring"""
    
    def process(self, request, response=None):
        if response is None:
            # Record start time
            request.start_time = time.time()
            return super().process(request, response)
        else:
            # Calculate and log request duration
            duration = time.time() - getattr(request, 'start_time', time.time())
            
            # Add timing header
            if not hasattr(response, 'headers'):
                response.headers = {}
            response.headers['X-Response-Time'] = f"{duration:.3f}s"
            
            # Log slow requests
            if duration > 1.0:  # Log requests over 1 second
                print(f"SLOW REQUEST: {request.method} {request.url.path} took {duration:.3f}s")
            
            return response
```

### 3. Request Size Limiting Middleware

```python
class RequestSizeLimitMiddleware(Middleware):
    """Middleware to limit request body size"""
    
    def __init__(self, max_size_mb=10):
        self.max_size_bytes = max_size_mb * 1024 * 1024
    
    def process(self, request, response=None):
        if response:
            return response
        
        # Check content length
        content_length = int(request.headers.get('Content-Length', 0))
        
        if content_length > self.max_size_bytes:
            return Response(
                {
                    "error": f"Request body too large. Maximum size is {self.max_size_bytes // 1024 // 1024}MB"
                },
                status_code=413  # Payload Too Large
            )
        
        return super().process(request, response)
```

### 4. Error Handling Middleware

```python
class ErrorHandlingMiddleware(Middleware):
    """Global error handling middleware"""
    
    def process(self, request, response=None):
        if response:
            return response
        
        try:
            # Continue processing
            return super().process(request, response)
        except ValueError as e:
            # Handle validation errors
            return Response(
                {"error": str(e), "type": "validation_error"},
                status_code=400
            )
        except PermissionError as e:
            # Handle permission errors
            return Response(
                {"error": "Insufficient permissions", "type": "permission_error"},
                status_code=403
            )
        except Exception as e:
            # Handle unexpected errors
            print(f"Unexpected error: {e}")
            return Response(
                {"error": "Internal server error", "type": "server_error"},
                status_code=500
            )
```

### 5. Response Compression Middleware

```python
import gzip
import json

class CompressionMiddleware(Middleware):
    """Response compression middleware"""
    
    def process(self, request, response=None):
        if not response:
            return super().process(request, response)
        
        # Check if client accepts gzip
        accept_encoding = request.headers.get('Accept-Encoding', '')
        if 'gzip' not in accept_encoding:
            return response
        
        # Only compress JSON responses
        content_type = response.headers.get('Content-Type', '')
        if 'application/json' not in content_type:
            return response
        
        # Compress response body
        if hasattr(response, 'body') and response.body:
            if isinstance(response.body, dict):
                json_data = json.dumps(response.body).encode('utf-8')
            else:
                json_data = response.body.encode('utf-8')
            
            compressed_data = gzip.compress(json_data)
            
            # Update response
            response.body = compressed_data
            response.headers['Content-Encoding'] = 'gzip'
            response.headers['Content-Length'] = str(len(compressed_data))
        
        return response
```

## Middleware Order and Execution

### Understanding Execution Order

Middleware is processed in the order it's added:

```python
app.add_middleware([
    LoggingMiddleware,      # 1. First to process requests, last to process responses
    CORSMiddleware,        # 2. Second to process requests, second-to-last responses  
    RateLimitMiddleware    # 3. Last to process requests, first to process responses
])
```

**Request Flow:**
1. LoggingMiddleware (pre-request)
2. CORSMiddleware (pre-request)  
3. RateLimitMiddleware (pre-request)
4. Endpoint handler
5. RateLimitMiddleware (post-response)
6. CORSMiddleware (post-response)
7. LoggingMiddleware (post-response)

### Best Practices for Ordering

1. **Security First**: Authentication, authorization, rate limiting
2. **Request Modification**: Body parsing, validation, transformation
3. **Logging/Monitoring**: Request tracking, timing, metrics
4. **Response Modification**: CORS, compression, headers

```python
app.add_middleware([
    # Security layer
    RateLimitMiddleware,
    JWTAuthMiddleware,
    
    # Request processing
    RequestSizeLimitMiddleware,
    ErrorHandlingMiddleware,
    
    # Monitoring
    TimingMiddleware,
    LoggingMiddleware,
    
    # Response processing
    CORSMiddleware,
    CompressionMiddleware
])
```

## Testing Middleware

### Unit Testing

```python
import pytest
from your_app import LoggingMiddleware

def test_logging_middleware():
    middleware = LoggingMiddleware()
    
    # Mock request
    class MockRequest:
        def __init__(self):
            self.method = 'GET'
            self.url = type('URL', (), {'path': '/test'})()
    
    request = MockRequest()
    
    # Test pre-request processing
    result = middleware.process(request, None)
    assert hasattr(request, 'id')
    assert len(request.id) == 36  # UUID length
    
    # Test post-response processing
    class MockResponse:
        def __init__(self):
            self.status_code = 200
            self.headers = {}
    
    response = MockResponse()
    result = middleware.process(request, response)
    assert 'X-Request-ID' in result.headers
```

### Integration Testing

```python
def test_middleware_integration(client):
    # Test that all middleware is working together
    response = client.get('/hello')
    
    # Check logging middleware added request ID
    assert 'X-Request-ID' in response.headers
    
    # Check CORS middleware added headers
    assert 'Access-Control-Allow-Origin' in response.headers
    
    # Check timing middleware added timing header
    assert 'X-Response-Time' in response.headers
```

## Configuration Examples

### Environment-Based Configuration

```python
import os

class ConfigurableCORSMiddleware(CORSMiddleware):
    def __init__(self):
        self.allowed_origins = os.getenv('CORS_ORIGINS', '*').split(',')
        self.allowed_methods = os.getenv('CORS_METHODS', 'GET,POST,PUT,DELETE,OPTIONS').split(',')
        self.allowed_headers = os.getenv('CORS_HEADERS', 'Authorization,Content-Type').split(',')
        self.max_age = int(os.getenv('CORS_MAX_AGE', '86400'))

class ConfigurableRateLimitMiddleware(RateLimitMiddleware):
    def __init__(self):
        super().__init__()
        self.requests_per_minute = int(os.getenv('RATE_LIMIT_RPM', '60'))
        self.window = int(os.getenv('RATE_LIMIT_WINDOW', '60'))
```

### Conditional Middleware

```python
def create_app():
    app = LightApi(database_url="sqlite:///app.db")
    
    middleware_stack = [LoggingMiddleware]
    
    # Add CORS only in development
    if os.getenv('ENVIRONMENT') == 'development':
        middleware_stack.append(CORSMiddleware)
    
    # Add rate limiting in production
    if os.getenv('ENVIRONMENT') == 'production':
        middleware_stack.append(RateLimitMiddleware)
    
    app.add_middleware(middleware_stack)
    return app
```

## Running the Example

```bash
# Start the middleware example
python examples/middleware_example.py

# Test basic functionality
curl -X GET http://localhost:8000/hello

# Test CORS preflight
curl -X OPTIONS http://localhost:8000/hello \
  -H "Origin: https://example.com"

# Test rate limiting (make multiple rapid requests)
for i in {1..5}; do curl -X GET http://localhost:8000/hello; done
```

## Next Steps

- **[Authentication Example](auth.md)** - Security patterns
- **[Caching Example](caching.md)** - Performance optimization
- **[API Reference](../api-reference/core.md)** - Core API details
- **[Filtering and Pagination](filtering-pagination.md)** - Query optimization 