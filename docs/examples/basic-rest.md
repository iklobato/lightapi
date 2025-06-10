# Basic REST API Example

This example demonstrates how to create a simple REST API with full CRUD operations using LightAPI.

## Overview

The basic REST API example shows how to:
- Define a simple model with database fields
- Create endpoints with automatic CRUD operations
- Set up Swagger documentation
- Run the development server

## Complete Code

```python
--8<-- "examples/basic_rest_api.py"
```

## Step-by-Step Breakdown

### 1. Model Definition

```python
@register_model_class
class User(RestEndpoint):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    email = Column(String(100))
    role = Column(String(50))
```

**Key Points:**
- `@register_model_class` decorator registers the model with SQLAlchemy
- `__tablename__` defines the database table name
- Inheriting from `RestEndpoint` provides automatic CRUD operations
- Standard SQLAlchemy column definitions

### 2. Application Setup

```python
app = LightApi(
    database_url="sqlite:///basic_example.db",
    swagger_title="Basic REST API Example",
    swagger_version="1.0.0",
    swagger_description="Simple REST API demonstrating basic CRUD operations",
)
```

**Configuration Options:**
- `database_url`: SQLite database for this example
- `swagger_title`: Title shown in API documentation
- `swagger_version`: API version
- `swagger_description`: Description for documentation

### 3. Endpoint Registration

```python
app.register({'/users': User})
```

This single line creates endpoints for:
- `GET /users` - List all users
- `GET /users?id=123` - Get specific user
- `POST /users` - Create new user
- `PUT /users` - Update existing user
- `DELETE /users` - Delete user
- `OPTIONS /users` - Get allowed methods

### 4. Running the Server

```python
app.run(host="localhost", port=8000, debug=True)
```

**Parameters:**
- `host`: Server host address
- `port`: Server port number
- `debug`: Enable debug mode with detailed error messages

## Usage Examples

### Create a User

```bash
curl -X POST http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Doe",
    "email": "john@example.com",
    "role": "admin"
  }'
```

**Response:**
```json
{
  "id": 1,
  "name": "John Doe",
  "email": "john@example.com",
  "role": "admin"
}
```

### Get All Users

```bash
curl http://localhost:8000/users
```

**Response:**
```json
[
  {
    "id": 1,
    "name": "John Doe",
    "email": "john@example.com",
    "role": "admin"
  },
  {
    "id": 2,
    "name": "Jane Smith",
    "email": "jane@example.com",
    "role": "user"
  }
]
```

### Get Specific User

```bash
curl http://localhost:8000/users?id=1
```

**Response:**
```json
[
  {
    "id": 1,
    "name": "John Doe",
    "email": "john@example.com",
    "role": "admin"
  }
]
```

### Update a User

```bash
curl -X PUT http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{
    "id": 1,
    "name": "John Updated",
    "email": "john.updated@example.com",
    "role": "super_admin"
  }'
```

### Delete a User

```bash
curl -X DELETE http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{"id": 1}'
```

## Interactive Documentation

Once the server is running, visit:

- **API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **OpenAPI JSON**: [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

The Swagger UI provides an interactive interface to:
- Explore all available endpoints
- Test API calls directly from the browser
- View request/response schemas
- Download OpenAPI specification

## Database Schema

The example automatically creates this table structure:

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100),
    email VARCHAR(100),
    role VARCHAR(50)
);
```

## Extending the Example

### Add Validation

```python
from lightapi.rest import Validator

class UserValidator(Validator):
    def validate(self, data):
        errors = {}
        
        if not data.get('name'):
            errors['name'] = 'Name is required'
        
        if not data.get('email'):
            errors['email'] = 'Email is required'
        elif '@' not in data['email']:
            errors['email'] = 'Invalid email format'
            
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }

class User(RestEndpoint):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    email = Column(String(100))
    role = Column(String(50))
    
    class Configuration:
        validator_class = UserValidator
```

### Add More Fields

```python
from sqlalchemy import Boolean, DateTime
from datetime import datetime

class User(RestEndpoint):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    role = Column(String(50), default='user')
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### Add Authentication

```python
from lightapi.auth import JWTAuthentication

class User(RestEndpoint):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    email = Column(String(100))
    role = Column(String(50))
    
    class Configuration:
        authentication_class = JWTAuthentication
        http_method_names = ['GET', 'POST', 'PUT', 'DELETE']
```

## Troubleshooting

### Common Issues

1. **Database Connection Error**
   ```
   Solution: Ensure the database URL is correct and the directory is writable
   ```

2. **Port Already in Use**
   ```bash
   # Use a different port
   app.run(host="localhost", port=8001, debug=True)
   ```

3. **Import Errors**
   ```bash
   # Ensure LightAPI is installed
   pip install lightapi
   ```

### Debug Mode

When `debug=True` is enabled:
- Detailed error messages are shown
- Stack traces are included in responses
- Server automatically reloads on code changes

**⚠️ Warning**: Never use `debug=True` in production!

## Next Steps

- **[Authentication Example](auth.md)** - Add JWT authentication
- **[Validation Example](validation.md)** - Add request validation
- **[Caching Example](caching.md)** - Add Redis caching
- **[Filtering Example](filtering-pagination.md)** - Add query filtering and pagination 