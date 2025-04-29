# Exceptions Reference

The Exceptions module provides a comprehensive error handling system for LightAPI applications.

## Built-in Exceptions

### HTTP Exceptions

```python
from lightapi.exceptions import (
    HTTPException,
    NotFound,
    BadRequest,
    Unauthorized,
    Forbidden,
    MethodNotAllowed,
    Conflict,
    InternalServerError
)

# Usage
raise NotFound('User not found')
raise BadRequest('Invalid input')
```

### Validation Exceptions

```python
from lightapi.exceptions import (
    ValidationError,
    InvalidField,
    RequiredField,
    InvalidType
)

# Usage
raise ValidationError('Invalid data format')
raise InvalidField('email', 'Invalid email format')
```

### Database Exceptions

```python
from lightapi.exceptions import (
    DatabaseError,
    IntegrityError,
    ConnectionError,
    QueryError
)

# Usage
raise DatabaseError('Database connection failed')
raise IntegrityError('Duplicate entry')
```

## Custom Exceptions

### Creating Custom Exceptions

```python
from lightapi.exceptions import HTTPException

class CustomError(HTTPException):
    status_code = 400
    error_code = 'CUSTOM_ERROR'
    
    def __init__(self, message='Custom error occurred'):
        super().__init__(message)
```

### Exception Handlers

```python
from lightapi import LightAPI
from lightapi.exceptions import HTTPException

app = LightAPI()

@app.error_handler(CustomError)
def handle_custom_error(error):
    return {
        'error': error.error_code,
        'message': str(error)
    }, error.status_code
```

## Error Response Format

### Default Format

```python
{
    "error": "NOT_FOUND",
    "message": "User not found",
    "status_code": 404,
    "details": {
        "resource": "User",
        "id": "123"
    }
}
```

### Custom Format

```python
@app.error_handler(HTTPException)
def format_error(error):
    return {
        'status': 'error',
        'code': error.error_code,
        'description': str(error),
        'timestamp': datetime.now().isoformat()
    }, error.status_code
```

## Examples

### Complete Error Handling Setup

```python
from lightapi import LightAPI
from lightapi.exceptions import (
    HTTPException,
    NotFound,
    ValidationError,
    DatabaseError
)
from datetime import datetime

app = LightAPI()

# Custom exception
class BusinessLogicError(HTTPException):
    status_code = 400
    error_code = 'BUSINESS_LOGIC_ERROR'

# Global error handler
@app.error_handler(HTTPException)
def handle_http_error(error):
    return {
        'status': 'error',
        'code': error.error_code,
        'message': str(error),
        'timestamp': datetime.now().isoformat()
    }, error.status_code

# Specific error handlers
@app.error_handler(ValidationError)
def handle_validation_error(error):
    return {
        'status': 'error',
        'code': 'VALIDATION_ERROR',
        'fields': error.fields,
        'message': str(error)
    }, 400

@app.error_handler(DatabaseError)
def handle_database_error(error):
    return {
        'status': 'error',
        'code': 'DATABASE_ERROR',
        'message': 'An internal error occurred'
    }, 500

# Usage in endpoints
@app.route('/users/<id>')
def get_user(request, id):
    user = User.query.get(id)
    if not user:
        raise NotFound(f'User {id} not found')
    return user.dict()

@app.route('/users', methods=['POST'])
def create_user(request):
    try:
        user = User(**request.json)
        user.save()
    except ValidationError as e:
        raise BadRequest(str(e))
    except IntegrityError:
        raise Conflict('User already exists')
    return user.dict(), 201
```

## Best Practices

1. Use appropriate exception types
2. Implement custom exceptions for business logic
3. Handle all exceptions appropriately
4. Provide meaningful error messages
5. Follow security best practices in error responses

## See Also

- [Core API](core.md) - Core framework functionality
- [REST API](rest.md) - REST endpoint implementation
- [Validation](validation.md) - Request validation 