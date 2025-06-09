# LightAPI Examples

This directory contains example applications demonstrating various features of the LightAPI framework.

## Basic Examples

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

## Example API Requests

Each example includes instructions for testing the API endpoints using `curl` or through the Swagger UI.

For example, to test the basic REST API:

```bash
# List all users
curl http://localhost:8000/users

# Create a new user
curl -X POST http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{"name": "John Doe", "email": "john@example.com", "role": "admin"}'

# Get a user by ID
curl http://localhost:8000/users/1

# Update a user
curl -X PUT http://localhost:8000/users/1 \
  -H "Content-Type: application/json" \
  -d '{"name": "John Smith", "email": "john.smith@example.com", "role": "admin"}'

# Delete a user
curl -X DELETE http://localhost:8000/users/1
```

## Environment Variables

Many examples now support environment variable configuration:

```bash
# JWT Authentication
export LIGHTAPI_JWT_SECRET="your-secret-key"

# Database
export LIGHTAPI_DATABASE_URL="postgresql://user:pass@localhost/db"

# Redis Caching
export LIGHTAPI_REDIS_HOST="localhost"
export LIGHTAPI_REDIS_PORT="6379"

# Server Configuration
export LIGHTAPI_HOST="0.0.0.0"
export LIGHTAPI_PORT="8000"
export LIGHTAPI_DEBUG="True"

# CORS
export LIGHTAPI_CORS_ORIGINS='["https://myapp.com"]'

# Swagger
export LIGHTAPI_SWAGGER_TITLE="My API"
export LIGHTAPI_ENABLE_SWAGGER="True"
```

## Notes

- These examples are designed for learning and demonstration purposes
- For production use, you should implement proper security, error handling, and database configuration
- The examples use SQLite for simplicity, but LightAPI works with any SQLAlchemy-supported database
- **New**: Built-in middleware reduces boilerplate code and provides better defaults
- **New**: CORS and authentication work seamlessly together
- **New**: Redis caching is more reliable with fixed JSON serialization 