# REST API Reference

The REST module provides the `RestEndpoint` class, which is the foundation for building REST APIs in LightAPI. It combines SQLAlchemy models with HTTP endpoint logic.

## RestEndpoint

::: lightapi.rest.RestEndpoint

The base class for creating REST API endpoints. RestEndpoint automatically provides full CRUD functionality and can be customized through configuration and method overrides.

### Basic Usage

```python
from sqlalchemy import Column, Integer, String, Boolean
from lightapi import RestEndpoint, register_model_class

@register_model_class
class User(RestEndpoint):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    is_active = Column(Boolean, default=True)
```

This automatically creates endpoints for:
- `GET /users` - List all users
- `GET /users?id=123` - Get user by ID
- `POST /users` - Create a new user
- `PUT /users` - Update a user
- `DELETE /users` - Delete a user
- `PATCH /users` - Partial update
- `OPTIONS /users` - Get allowed methods

### Configuration Class

The `Configuration` inner class allows you to customize endpoint behavior:

```python
class User(RestEndpoint):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    email = Column(String(100))
    
    class Configuration:
        http_method_names = ['GET', 'POST', 'PUT', 'DELETE']
        validator_class = UserValidator
        filter_class = UserFilter
        authentication_class = JWTAuthentication
        caching_class = RedisCache
        caching_method_names = ['GET']
        pagination_class = UserPaginator
```

#### Configuration Options

| Option | Type | Description |
|--------|------|-------------|
| `http_method_names` | `List[str]` | Allowed HTTP methods |
| `validator_class` | `Validator` | Request validation class |
| `filter_class` | `BaseFilter` | Query filtering class |
| `authentication_class` | `BaseAuthentication` | Authentication class |
| `caching_class` | `BaseCache` | Caching implementation |
| `caching_method_names` | `List[str]` | Methods to cache |
| `pagination_class` | `Paginator` | Pagination implementation |

---

## HTTP Method Handlers

### GET Method

Retrieves resources from the database with automatic filtering and pagination.

```python
class User(RestEndpoint):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    email = Column(String(100))
    role = Column(String(50))
    
    def get(self, request):
        # Default implementation with custom logic
        query = self.session.query(self.__class__)
        
        # Check for ID filter in query parameters
        object_id = request.query_params.get("id")
        if object_id:
            query = query.filter_by(id=object_id)
            
        # Apply custom filtering
        role = request.query_params.get("role")
        if role:
            query = query.filter_by(role=role)
            
        # Apply configured filters
        if hasattr(self, 'filter'):
            query = self.filter.filter_queryset(query, request)
            
        # Apply pagination
        if hasattr(self, 'paginator'):
            results = self.paginator.paginate(query)
        else:
            results = query.all()
            
        return [result.as_dict() for result in results], 200
```

#### URL Query Parameters

- `id` - Filter by specific ID
- Any model field name - Filter by exact match
- Custom parameters handled by filter classes

#### Examples

```bash
# Get all users
GET /users

# Get specific user
GET /users?id=123

# Filter by role
GET /users?role=admin

# Multiple filters
GET /users?role=admin&is_active=true
```

### POST Method

Creates new resources in the database.

```python
class User(RestEndpoint):
    def post(self, request):
        data = getattr(request, 'data', {})
        
        # Validation (if configured)
        if hasattr(self, 'validator'):
            validation_result = self.validator.validate(data)
            if not validation_result.get('valid', True):
                return Response(
                    {"error": "Validation failed", "details": validation_result['errors']},
                    status_code=400
                )
        
        # Create new instance
        instance = self.__class__(**data)
        self.session.add(instance)
        
        try:
            self.session.commit()
            return instance.as_dict(), 201
        except Exception as e:
            self.session.rollback()
            return Response({"error": "Failed to create resource"}, status_code=400)
```

#### Request Body

```json
{
    "name": "John Doe",
    "email": "john@example.com",
    "role": "user"
}
```

#### Response

```json
{
    "id": 123,
    "name": "John Doe", 
    "email": "john@example.com",
    "role": "user",
    "created_at": "2023-12-01T10:00:00Z"
}
```

### PUT Method

Updates existing resources (full update).

```python
class User(RestEndpoint):
    def put(self, request):
        data = getattr(request, 'data', {})
        object_id = data.get('id')
        
        if not object_id:
            return Response({"error": "ID is required for update"}, status_code=400)
            
        # Find existing instance
        instance = self.session.query(self.__class__).filter_by(id=object_id).first()
        if not instance:
            return Response({"error": "Resource not found"}, status_code=404)
            
        # Validation
        if hasattr(self, 'validator'):
            validation_result = self.validator.validate(data)
            if not validation_result.get('valid', True):
                return Response(
                    {"error": "Validation failed", "details": validation_result['errors']},
                    status_code=400
                )
        
        # Update all fields
        for key, value in data.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        
        try:
            self.session.commit()
            return instance.as_dict(), 200
        except Exception as e:
            self.session.rollback()
            return Response({"error": "Failed to update resource"}, status_code=400)
```

### DELETE Method

Deletes resources from the database.

```python
class User(RestEndpoint):
    def delete(self, request):
        data = getattr(request, 'data', {})
        object_id = data.get('id')
        
        if not object_id:
            return Response({"error": "ID is required for deletion"}, status_code=400)
            
        instance = self.session.query(self.__class__).filter_by(id=object_id).first()
        if not instance:
            return Response({"error": "Resource not found"}, status_code=404)
            
        self.session.delete(instance)
        
        try:
            self.session.commit()
            return {"message": "Resource deleted successfully"}, 200
        except Exception as e:
            self.session.rollback()
            return Response({"error": "Failed to delete resource"}, status_code=400)
```

### PATCH Method

Performs partial updates on resources.

```python
class User(RestEndpoint):
    def patch(self, request):
        data = getattr(request, 'data', {})
        object_id = data.get('id')
        
        if not object_id:
            return Response({"error": "ID is required for update"}, status_code=400)
            
        instance = self.session.query(self.__class__).filter_by(id=object_id).first()
        if not instance:
            return Response({"error": "Resource not found"}, status_code=404)
            
        # Update only provided fields
        for key, value in data.items():
            if key != 'id' and hasattr(instance, key):
                setattr(instance, key, value)
        
        try:
            self.session.commit()
            return instance.as_dict(), 200
        except Exception as e:
            self.session.rollback()
            return Response({"error": "Failed to update resource"}, status_code=400)
```

### OPTIONS Method

Returns allowed HTTP methods for CORS support.

```python
class User(RestEndpoint):
    def options(self, request):
        allowed_methods = getattr(
            self.Configuration, 
            'http_method_names', 
            ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS']
        )
        return {
            "allowed_methods": allowed_methods,
            "description": "User management endpoint"
        }, 200
```

---

## Advanced Examples

### Authentication Protected Endpoint

```python
from lightapi.auth import JWTAuthentication

class ProtectedUser(RestEndpoint):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    email = Column(String(100))
    
    class Configuration:
        authentication_class = JWTAuthentication
        http_method_names = ['GET', 'POST', 'PUT', 'DELETE']
    
    def get(self, request):
        # Access authenticated user
        current_user = request.state.user
        user_id = current_user.get('user_id')
        
        # Only return current user's data
        user = self.session.query(self.__class__).filter_by(id=user_id).first()
        if user:
            return user.as_dict(), 200
        return Response({"error": "User not found"}, status_code=404)
```

### Validated Endpoint

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

class ValidatedUser(RestEndpoint):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    email = Column(String(100))
    
    class Configuration:
        validator_class = UserValidator
```

### Cached Endpoint

```python
from lightapi.cache import RedisCache

class CachedUser(RestEndpoint):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    email = Column(String(100))
    
    class Configuration:
        caching_class = RedisCache
        caching_method_names = ['GET']
    
    # GET responses are automatically cached
    # Cache key includes URL and query parameters
    # Default cache timeout: 300 seconds
```

### Filtered and Paginated Endpoint

```python
from lightapi.filters import ParameterFilter
from lightapi.pagination import Paginator

class CustomPaginator(Paginator):
    limit = 20
    offset = 0
    
    def get_limit(self):
        # Get limit from query parameter
        limit = self.request.query_params.get('limit', self.limit)
        return min(int(limit), 100)  # Max 100 items
    
    def get_offset(self):
        page = int(self.request.query_params.get('page', 1))
        return (page - 1) * self.get_limit()

class FilteredUser(RestEndpoint):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    email = Column(String(100))
    role = Column(String(50))
    
    class Configuration:
        filter_class = ParameterFilter
        pagination_class = CustomPaginator
```

### Custom Business Logic

```python
class BusinessUser(RestEndpoint):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    email = Column(String(100))
    role = Column(String(50))
    last_login = Column(DateTime)
    
    def get(self, request):
        # Custom GET logic
        if request.query_params.get('active_only') == 'true':
            # Return only users who logged in recently
            cutoff_date = datetime.now() - timedelta(days=30)
            query = self.session.query(self.__class__).filter(
                self.__class__.last_login >= cutoff_date
            )
        else:
            query = self.session.query(self.__class__)
            
        results = query.all()
        return [user.as_dict() for user in results], 200
    
    def post(self, request):
        # Custom creation logic
        data = getattr(request, 'data', {})
        
        # Check for duplicate email
        existing = self.session.query(self.__class__).filter_by(
            email=data.get('email')
        ).first()
        
        if existing:
            return Response(
                {"error": "Email already exists"}, 
                status_code=409
            )
        
        # Set default role
        if 'role' not in data:
            data['role'] = 'user'
            
        # Call parent implementation
        return super().post(request)
```

---

## Non-Database Endpoints

You can create endpoints that don't interact with the database:

```python
class HealthCheckEndpoint(RestEndpoint):
    __abstract__ = True  # Not a database model
    
    def get(self, request):
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0"
        }, 200

class StatisticsEndpoint(RestEndpoint):
    __abstract__ = True
    
    class Configuration:
        authentication_class = JWTAuthentication
        http_method_names = ['GET']
    
    def get(self, request):
        # Complex analytics logic
        return {
            "total_users": 1000,
            "active_users": 850,
            "new_signups_today": 25
        }, 200
```

---

## Validator

::: lightapi.rest.Validator

Base class for request data validation.

### Basic Validator

```python
from lightapi.rest import Validator

class UserValidator(Validator):
    def validate(self, data):
        errors = {}
        
        # Required fields
        if not data.get('name'):
            errors['name'] = 'Name is required'
            
        if not data.get('email'):
            errors['email'] = 'Email is required'
        elif not self._is_valid_email(data['email']):
            errors['email'] = 'Invalid email format'
            
        # Optional field validation
        if data.get('age') and data['age'] < 18:
            errors['age'] = 'Age must be 18 or older'
            
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    def _is_valid_email(self, email):
        return '@' in email and '.' in email.split('@')[1]
```

### Advanced Validator

```python
import re
from datetime import datetime

class AdvancedUserValidator(Validator):
    def validate(self, data):
        errors = {}
        
        # Name validation
        name = data.get('name', '').strip()
        if not name:
            errors['name'] = 'Name is required'
        elif len(name) < 2:
            errors['name'] = 'Name must be at least 2 characters'
        elif len(name) > 100:
            errors['name'] = 'Name must be less than 100 characters'
            
        # Email validation
        email = data.get('email', '').strip().lower()
        if not email:
            errors['email'] = 'Email is required'
        elif not self._is_valid_email(email):
            errors['email'] = 'Invalid email format'
        elif len(email) > 255:
            errors['email'] = 'Email is too long'
            
        # Password validation (for creation)
        if 'password' in data:
            password = data['password']
            if len(password) < 8:
                errors['password'] = 'Password must be at least 8 characters'
            elif not re.search(r'[A-Z]', password):
                errors['password'] = 'Password must contain uppercase letter'
            elif not re.search(r'[0-9]', password):
                errors['password'] = 'Password must contain a number'
                
        # Date validation
        if data.get('birth_date'):
            try:
                birth_date = datetime.fromisoformat(data['birth_date'])
                if birth_date > datetime.now():
                    errors['birth_date'] = 'Birth date cannot be in the future'
            except ValueError:
                errors['birth_date'] = 'Invalid date format'
                
        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'cleaned_data': {
                'name': name,
                'email': email,
                **{k: v for k, v in data.items() if k not in ['name', 'email']}
            }
        }
    
    def _is_valid_email(self, email):
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
```

---

## Error Handling

### Built-in Error Responses

RestEndpoint provides standard HTTP error responses:

```python
# 400 Bad Request
{
    "error": "Validation failed",
    "details": {"field": "error message"}
}

# 401 Unauthorized (with authentication)
{"error": "Authentication failed"}

# 404 Not Found
{"error": "Resource not found"}

# 405 Method Not Allowed
{"error": "Method PATCH not allowed"}

# 409 Conflict
{"error": "Resource already exists"}

# 500 Internal Server Error
{"error": "Internal server error"}
```

### Custom Error Handling

```python
class RobustEndpoint(RestEndpoint):
    __tablename__ = 'items'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    
    def get(self, request):
        try:
            return super().get(request)
        except ValueError as e:
            return Response(
                {"error": f"Invalid request: {str(e)}"}, 
                status_code=400
            )
        except PermissionError as e:
            return Response(
                {"error": "Access denied"}, 
                status_code=403
            )
        except Exception as e:
            # Log error for debugging
            print(f"Unexpected error: {e}")
            return Response(
                {"error": "Something went wrong"}, 
                status_code=500
            )
```

---

## Best Practices

### 1. Use Configuration Classes

```python
class User(RestEndpoint):
    class Configuration:
        # Be explicit about allowed methods
        http_method_names = ['GET', 'POST', 'PUT', 'DELETE']
        
        # Add authentication for sensitive endpoints
        authentication_class = JWTAuthentication
        
        # Add validation for data integrity
        validator_class = UserValidator
        
        # Add caching for read-heavy endpoints
        caching_class = RedisCache
        caching_method_names = ['GET']
```

### 2. Override Methods Judiciously

```python
class User(RestEndpoint):
    def get(self, request):
        # Add business logic while preserving functionality
        base_query = self.session.query(self.__class__)
        
        # Apply custom filters
        if request.query_params.get('include_inactive') != 'true':
            base_query = base_query.filter_by(is_active=True)
            
        # Use built-in filtering and pagination
        if hasattr(self, 'filter'):
            base_query = self.filter.filter_queryset(base_query, request)
            
        if hasattr(self, 'paginator'):
            results = self.paginator.paginate(base_query)
        else:
            results = base_query.all()
            
        return [r.as_dict() for r in results], 200
```

### 3. Handle Errors Gracefully

```python
class User(RestEndpoint):
    def post(self, request):
        try:
            return super().post(request)
        except IntegrityError as e:
            self.session.rollback()
            if 'UNIQUE constraint failed' in str(e):
                return Response(
                    {"error": "User with this email already exists"}, 
                    status_code=409
                )
            return Response(
                {"error": "Database constraint violation"}, 
                status_code=400
            )
```

### 4. Use Type Hints

```python
from typing import Dict, Any, Tuple
from starlette.requests import Request

class User(RestEndpoint):
    def get(self, request: Request) -> Tuple[Dict[str, Any], int]:
        # Implementation with proper type hints
        pass
```

## See Also

- [Core API](core.md) - Core framework functionality
- [Models](models.md) - Data models and schemas
- [Filtering](filters.md) - Advanced filtering options
- [Pagination](pagination.md) - Pagination configuration 