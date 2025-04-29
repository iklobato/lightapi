# Validation Reference

The Validation module provides powerful tools for validating request data and model fields in LightAPI.

## Request Validation

### Basic Validation

```python
from lightapi.validation import validate_request
from lightapi.models import Model, Field

class UserCreate(Model):
    name: str = Field(min_length=2, max_length=50)
    email: str = Field(format='email')
    age: int = Field(ge=0, optional=True)

@app.route('/users', methods=['POST'])
def create_user(request):
    data = validate_request(request, UserCreate)
    # data is now validated and type-converted
    user = User(**data)
    user.save()
    return user.dict(), 201
```

### Query Parameter Validation

```python
from lightapi.validation import validate_query
from lightapi.models import Model, Field

class UserQuery(Model):
    page: int = Field(ge=1, default=1)
    limit: int = Field(ge=1, le=100, default=10)
    search: str = Field(optional=True)

@app.route('/users')
def list_users(request):
    query = validate_query(request, UserQuery)
    # query contains validated parameters
    users = User.query.paginate(query.page, query.limit)
    return {'users': users}
```

## Field Validation

### Built-in Validators

```python
from lightapi.models import Field

class Product(Model):
    name: str = Field(
        min_length=1,
        max_length=100,
        pattern=r'^[A-Za-z0-9\s\-]+$'
    )
    price: float = Field(
        gt=0,
        le=10000
    )
    category: str = Field(
        choices=['electronics', 'clothing', 'books']
    )
    in_stock: bool = Field(default=True)
```

### Custom Validators

```python
from lightapi.models import validator

class User(Model):
    username: str = Field()
    password: str = Field()
    
    @validator('username')
    def validate_username(cls, value):
        if not value.isalnum():
            raise ValueError('Username must be alphanumeric')
        return value

    @validator('password')
    def validate_password(cls, value):
        if len(value) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not any(c.isupper() for c in value):
            raise ValueError('Password must contain uppercase letter')
        if not any(c.isdigit() for c in value):
            raise ValueError('Password must contain a number')
        return value
```

## Validation Errors

### Error Handling

```python
from lightapi.exceptions import ValidationError

@app.route('/users', methods=['POST'])
def create_user(request):
    try:
        data = validate_request(request, UserCreate)
        user = User(**data)
        user.save()
        return user.dict(), 201
    except ValidationError as e:
        return {
            'error': 'VALIDATION_ERROR',
            'message': str(e),
            'fields': e.fields
        }, 400
```

### Error Format

```python
{
    "error": "VALIDATION_ERROR",
    "message": "Invalid input data",
    "fields": {
        "email": ["Invalid email format"],
        "age": ["Must be greater than or equal to 0"]
    }
}
```

## Advanced Validation

### Nested Validation

```python
class Address(Model):
    street: str = Field()
    city: str = Field()
    country: str = Field()

class User(Model):
    name: str = Field()
    email: str = Field(format='email')
    address: Address
```

### List Validation

```python
class Order(Model):
    items: List[OrderItem] = Field(min_items=1)
    total: float = Field(gt=0)

class OrderItem(Model):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0)
    price: float = Field(gt=0)
```

## Examples

### Complete Validation Example

```python
from lightapi import LightAPI
from lightapi.models import Model, Field, validator
from lightapi.validation import validate_request
from lightapi.exceptions import ValidationError

app = LightAPI()

class UserCreate(Model):
    username: str = Field(
        min_length=3,
        max_length=50,
        pattern=r'^[a-zA-Z0-9_]+$'
    )
    email: str = Field(format='email')
    password: str = Field(min_length=8)
    age: int = Field(ge=0, le=120, optional=True)
    roles: List[str] = Field(
        default=['user'],
        choices=['user', 'admin', 'moderator']
    )

    @validator('username')
    def validate_username(cls, value):
        if not value.isalnum():
            raise ValueError('Username must be alphanumeric')
        return value

    @validator('password')
    def validate_password(cls, value):
        if not any(c.isupper() for c in value):
            raise ValueError('Password must contain uppercase letter')
        if not any(c.isdigit() for c in value):
            raise ValueError('Password must contain a number')
        return value

@app.route('/users', methods=['POST'])
def create_user(request):
    try:
        data = validate_request(request, UserCreate)
        user = User(**data)
        user.save()
        return user.dict(), 201
    except ValidationError as e:
        return {
            'error': 'VALIDATION_ERROR',
            'message': str(e),
            'fields': e.fields
        }, 400
```

## Best Practices

1. Validate all user input
2. Use appropriate validation rules
3. Provide clear error messages
4. Handle validation errors gracefully
5. Use type hints for better IDE support

## See Also

- [Models](models.md) - Data model definitions
- [REST API](rest.md) - REST endpoint implementation
- [Exceptions](exceptions.md) - Error handling 