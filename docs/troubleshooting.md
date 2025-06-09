---
title: Troubleshooting Guide
description: Common issues and solutions for LightAPI
---

# Troubleshooting Guide

This guide covers common issues you might encounter when using LightAPI and their solutions.

## Runtime Errors

### Content-Length Errors

**Error**: `RuntimeError: Response content longer than Content-Length`

**Cause**: This usually occurs when custom middleware modifies response content after Content-Length headers are set.

**Solutions**:
1. Use built-in middleware instead of custom middleware when possible
2. Avoid modifying response content in middleware post-processing
3. Use the Response class consistently throughout your application

```python
# ✅ Good: Use built-in middleware
from lightapi.core import CORSMiddleware

app.add_middleware([CORSMiddleware])

# ❌ Avoid: Custom middleware that modifies headers after content-length calculation
class ProblematicMiddleware(Middleware):
    def process(self, request, response):
        response.headers['Custom-Header'] = 'value'  # This can cause issues
        return response
```

### Memory View Type Errors

**Error**: `TypeError: memoryview: a bytes-like object is required, not 'dict'`

**Cause**: This occurs when response serialization is inconsistent, often with complex middleware stacks.

**Solutions**:
1. Use consistent response formats throughout your application
2. Ensure proper JSON serialization in custom response handling
3. Avoid mixing different response object types

```python
# ✅ Good: Consistent response format
def get(self, request):
    return {'data': 'ok'}, 200

# ✅ Good: Use Response class consistently  
def post(self, request):
    return Response({'data': 'created'}, status_code=201)
```

## Configuration Issues

### JWT Authentication Problems

**Error**: JWT validation fails or `401 Unauthorized` responses

**Common Causes & Solutions**:

1. **Missing JWT Secret**
   ```bash
   # Set the environment variable
   export LIGHTAPI_JWT_SECRET="your-secret-key-here"
   ```

2. **Invalid Token Format**
   ```python
   # ✅ Correct token generation
   import jwt
   from datetime import datetime, timedelta
   
   payload = {
       'user_id': 1,
       'exp': datetime.utcnow() + timedelta(hours=1)
   }
   token = jwt.encode(payload, 'your-secret', algorithm='HS256')
   ```

3. **CORS Preflight Issues**
   ```python
   # ✅ Ensure OPTIONS requests are handled
   class Configuration:
       http_method_names = ['GET', 'POST', 'OPTIONS']  # Include OPTIONS
   ```

### Port Binding Issues

**Error**: `[Errno 48] error while attempting to bind on address ('127.0.0.1', 8000): address already in use`

**Solutions**:
```bash
# Find and kill processes using port 8000
lsof -ti:8000 | xargs kill -9

# Or use a different port
export LIGHTAPI_PORT="8001"
python your_app.py

# Or specify port in code
app.run(port=8001)
```

## Database Issues

### SQLAlchemy Connection Problems

**Error**: Database connection or table creation failures

**Solutions**:
1. **Check Database URL Format**
   ```python
   # ✅ Correct formats
   "sqlite:///./app.db"                    # SQLite
   "postgresql://user:pass@localhost/db"   # PostgreSQL  
   "mysql://user:pass@localhost/db"        # MySQL
   ```

2. **Table Creation Issues**
   ```python
   # ✅ Ensure proper table creation
   app = LightApi(database_url="sqlite:///app.db")
   app.register({'/users': User})
   
   # Tables are created automatically on first run
   # For explicit creation:
   from lightapi.database import Base, engine
   Base.metadata.create_all(engine)
   ```

## Middleware Issues

### Middleware Order

Middleware is processed in the order it's added. Authentication should generally come before CORS:

```python
# ✅ Correct order
app.add_middleware([
    AuthenticationMiddleware(JWTAuthentication),
    CORSMiddleware
])
```

### Custom Middleware Problems

**Issue**: Custom middleware causing response serialization errors

**Solutions**:
1. **Implement Proper Pre/Post Processing**
   ```python
   class CustomMiddleware(Middleware):
       def process(self, request, response):
           if response is None:  # Pre-processing
               # Modify request here
               return None
           
           # Post-processing
           # Avoid modifying response content/headers
           return response
   ```

2. **Use Built-in Middleware When Possible**
   ```python
   # ✅ Prefer built-in middleware
   from lightapi.core import CORSMiddleware, AuthenticationMiddleware
   
   app.add_middleware([
       CORSMiddleware(allow_origins=['*']),
       AuthenticationMiddleware(JWTAuthentication)
   ])
   ```

## Caching Issues

### Redis Connection Problems

**Error**: Redis connection failures

**Solutions**:
1. **Check Redis Configuration**
   ```bash
   # Start Redis server
   redis-server
   
   # Set environment variables
   export LIGHTAPI_REDIS_HOST="localhost"
   export LIGHTAPI_REDIS_PORT="6379"
   ```

2. **Verify Redis Connection**
   ```python
   import redis
   r = redis.Redis(host='localhost', port=6379, decode_responses=True)
   r.ping()  # Should return True
   ```

### Caching + Pagination Compatibility

**Issue**: Using both caching and pagination causes serialization errors

**Current Limitation**: These features have compatibility issues when used together.

**Workarounds**:
1. **Use Manual Caching**
   ```python
   def get(self, request):
       cache_key = f"data_{request.query_params.get('page', 1)}"
       # Implement manual cache logic
   ```

2. **Separate Layers**
   ```python
   # Use caching at application level, pagination at endpoint level
   class CachedEndpoint(RestEndpoint):
       class Configuration:
           caching_class = RedisCache  # No pagination here
   
   # Implement pagination in method
   def get(self, request):
       # Manual pagination logic
   ```

## Performance Issues

### Slow Query Performance

**Solutions**:
1. **Use Proper Indexes**
   ```python
   from sqlalchemy import Index
   
   class User(RestEndpoint):
       email = Column(String, index=True)  # Add index
       name = Column(String)
       
       __table_args__ = (
           Index('idx_user_email_name', 'email', 'name'),
       )
   ```

2. **Optimize Database Queries**
   ```python
   # Use select_related for efficient queries
   # (Implementation depends on your specific ORM usage)
   ```

## Development Tips

### Enable Debug Mode

```python
app = LightApi(debug=True)
app.run(debug=True, reload=True)
```

### Logging Configuration

```python
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### Environment Variables Reference

```bash
# Core Configuration
LIGHTAPI_DEBUG=True
LIGHTAPI_HOST=0.0.0.0
LIGHTAPI_PORT=8000

# Database
LIGHTAPI_DATABASE_URL=sqlite:///app.db

# Authentication
LIGHTAPI_JWT_SECRET=your-secret-key
LIGHTAPI_JWT_ALGORITHM=HS256

# Caching
LIGHTAPI_REDIS_HOST=localhost
LIGHTAPI_REDIS_PORT=6379
LIGHTAPI_REDIS_DB=0

# CORS
LIGHTAPI_CORS_ORIGINS=["*"]
LIGHTAPI_CORS_ALLOW_CREDENTIALS=True

# Swagger
LIGHTAPI_SWAGGER_TITLE="My API"
LIGHTAPI_SWAGGER_VERSION="1.0.0"
LIGHTAPI_ENABLE_SWAGGER=True
```

## Getting Help

If you encounter issues not covered in this guide:

1. **Check the Examples**: Look at `examples/user_goal_example.py` for comprehensive usage patterns
2. **Review Test Cases**: The `tests/` directory contains extensive test cases showing proper usage
3. **Enable Debug Logging**: Use debug mode to get more detailed error information
4. **Isolate the Issue**: Create a minimal reproduction case

## Common Patterns

### Complete Working Example

Here's a minimal but complete example that avoids common pitfalls:

```python
import os
from lightapi import LightApi, RestEndpoint
from lightapi.core import CORSMiddleware
from lightapi.auth import JWTAuthentication
from sqlalchemy import Column, Integer, String

# Set environment variables
os.environ['LIGHTAPI_JWT_SECRET'] = 'test-secret-key-123'

class User(RestEndpoint):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    email = Column(String(255))
    
    class Configuration:
        http_method_names = ['GET', 'POST', 'OPTIONS']
        authentication_class = JWTAuthentication

# Create app with proper configuration
app = LightApi(
    database_url="sqlite:///app.db",
    debug=True
)

# Add middleware in correct order
app.add_middleware([CORSMiddleware])

# Register endpoints
app.register({'/users': User})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)
```

This example follows all best practices and avoids the common issues documented above. 