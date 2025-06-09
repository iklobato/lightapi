# LightAPI Examples

This directory contains example applications demonstrating various features of the LightAPI framework.

## Basic Examples

- **user_goal_example.py**: Comprehensive demonstration of intended LightAPI usage patterns
  - Shows the exact API design philosophy and usage as envisioned
  - Demonstrates custom validators with field-specific validation methods
  - Implements JWT authentication with proper configuration
  - Shows multiple endpoints with different authentication requirements
  - Illustrates custom middleware integration (commented for clarity)
  - Includes CORS support and proper environment variable usage
  - **Note**: Some advanced features (caching + pagination) are commented out due to current limitations

- **basic_rest_api.py**: A simple REST API with default CRUD operations
  - Demonstrates minimal setup for a REST endpoint
  - Shows automatic handling of GET, POST, PUT, DELETE operations
  - Illustrates SQLAlchemy model integration with LightAPI

- **validation_example.py**: Data validation with custom validators
  - Shows field-specific validation rules using Validator class
  - Demonstrates error handling for validation failures
  - Illustrates data transformation (price conversion between dollars and cents)

- **auth_example.py**: JWT authentication with protected resources
  - Implements JWT token generation and verification
  - Shows protected endpoints requiring authentication
  - Demonstrates user information extraction from token
  - Includes public and private resource examples

## Advanced Features

- **custom_snippet.py**: Built-in middleware demonstration
  - Shows new `CORSMiddleware` and `AuthenticationMiddleware` classes
  - Demonstrates automatic CORS preflight handling with JWT authentication
  - Illustrates seamless integration of authentication with CORS support
  - Uses built-in middleware for cleaner, more maintainable code

- **middleware_example.py**: Custom middleware implementation for request/response processing
  - Demonstrates request/response lifecycle hooks
  - Includes logging middleware with request timing
  - Shows custom CORS headers management for cross-origin requests
  - Implements rate limiting with custom window controls

- **filtering_pagination_example.py**: Query filtering and result pagination
  - Shows parameter-based filtering for REST endpoints
  - Implements custom filter logic for search and range queries
  - Demonstrates paginated results with metadata
  - Illustrates dynamic sorting by different fields

- **caching_example.py**: Response caching for improved performance
  - Shows Redis cache implementation with automatic JSON serialization
  - Demonstrates cache key generation strategies
  - Includes time-to-live (TTL) management
  - Shows manual cache invalidation (DELETE operations)
  - Implements cache hit/miss HTTP headers
  - Fixed JSON serialization issues for proper caching

- **swagger_example.py**: Enhanced OpenAPI/Swagger documentation
  - Demonstrates docstring-based API documentation
  - Shows custom SwaggerGenerator implementation
  - Illustrates request/response schema documentation
  - Implements API grouping with tags
  - Demonstrates security scheme definitions

- **relationships_example.py**: Complex SQLAlchemy relationships (one-to-many, many-to-many)
  - Shows many-to-many relationships with association tables
  - Demonstrates one-to-many relationships with back references
  - Illustrates cascade behaviors on related objects
  - Shows nested data serialization across relationships
  - Implements relationship handling in POST/PUT operations

## New Built-in Features (Latest Updates)

### CORS Support
All examples now demonstrate improved CORS handling:
- **Automatic OPTIONS request handling**: JWT authentication automatically allows CORS preflight requests
- **Built-in CORSMiddleware**: Simplified CORS configuration with built-in middleware
- **Seamless integration**: CORS and authentication work together without conflicts

### Enhanced Authentication
- **CORS-aware JWT authentication**: Automatically skips OPTIONS requests
- **Global authentication middleware**: Apply authentication to all endpoints with `AuthenticationMiddleware`
- **Consistent error responses**: Standardized error format across all authentication failures
- **Environment variable configuration**: Set JWT secrets via `LIGHTAPI_JWT_SECRET`

### Improved Caching
- **Fixed JSON serialization**: Caching now works properly with complex Python objects
- **Redis integration**: Built-in Redis support with automatic configuration
- **Cache key optimization**: Better cache key generation for improved performance

## Running the Examples

Each example is self-contained and can be run directly:

```bash
# Basic example
python examples/basic_rest_api.py

# Built-in middleware example (demonstrates new features)
LIGHTAPI_JWT_SECRET="your-secret-key" python examples/custom_snippet.py

# Authentication with CORS
LIGHTAPI_JWT_SECRET="your-secret-key" python examples/auth_example.py

# Caching with Redis (requires Redis running)
python examples/caching_example.py
```

Most examples will:
1. Create a SQLite database in the current directory
2. Initialize tables and sample data
3. Start a web server on localhost:8000
4. Generate Swagger documentation at http://localhost:8000/docs

## Testing CORS and Authentication

The examples now include improved CORS and authentication. Test with:

```bash
# Start the custom_snippet example
LIGHTAPI_JWT_SECRET="test-secret-key-123" python examples/custom_snippet.py

# Start the user goal example (comprehensive demonstration)
LIGHTAPI_JWT_SECRET="test-secret-key-123" python examples/user_goal_example.py

# Test CORS preflight (should work without authentication)
curl -X OPTIONS http://localhost:8000/custom -v

# Test without authentication (should get 403)
curl -X GET http://localhost:8000/custom -v

# Generate a JWT token
python3 -c "
import jwt
from datetime import datetime, timedelta
secret = 'test-secret-key-123'
payload = {'user_id': 1, 'exp': datetime.utcnow() + timedelta(hours=1)}
token = jwt.encode(payload, secret, algorithm='HS256')
print(token)
"

# Test with authentication (should work)
curl -X GET http://localhost:8000/custom \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -v
```

## Known Limitations & Troubleshooting

### Current Limitations

1. **Caching + Pagination Compatibility**: Currently, using both `caching_class` and `pagination_class` together in the same endpoint configuration can cause serialization issues. If you need both features, implement them at different layers or use manual caching.

2. **Custom Response Serialization**: When using custom Response objects with complex middleware stacks, ensure proper JSON serialization to avoid `TypeError: memoryview: a bytes-like object is required, not 'dict'` errors.

### Common Issues

**Port Already in Use Error**
```bash
ERROR: [Errno 48] error while attempting to bind on address ('127.0.0.1', 8000): address already in use
```
Solution: Kill existing processes or use a different port:
```bash
# Kill processes using port 8000
lsof -ti:8000 | xargs kill -9

# Or use a different port
export LIGHTAPI_PORT="8001"
```

**JWT Authentication Issues**
- Ensure `LIGHTAPI_JWT_SECRET` environment variable is set
- Verify JWT token format and expiration
- Check that OPTIONS requests are handled properly for CORS

**Content-Length Errors**
If you encounter "Response content longer than Content-Length" errors:
- Avoid mixing complex middleware with custom response handling
- Use built-in Response classes when possible
- Check for proper JSON serialization in custom middleware

### Response Format Options

LightAPI supports multiple response formats for flexibility:

```python
# Tuple format (status code, data)
def get(self, request):
    return {'data': 'ok'}, 200

# Response object (more control)
def post(self, request):
    return Response(
        {'data': 'created'},
        status_code=201,
        content_type='application/json'
    )

# Simple dictionary (assumes 200 status)
def get(self, request):
    return {'data': 'ok'}
```

## Notes