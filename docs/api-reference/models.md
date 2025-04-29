# Models Reference

The Models module provides tools for defining data models, schema validation, and serialization in LightAPI.

## Model Definition

### Basic Model

```python
from lightapi.models import Model, Field

class User(Model):
    name: str = Field(min_length=2, max_length=50)
    email: str = Field(format='email')
    age: int = Field(ge=0, optional=True)
    status: str = Field(choices=['active', 'inactive'])
```

### Field Types

```python
from lightapi.models import (
    StringField,
    IntegerField,
    FloatField,
    BooleanField,
    DateTimeField,
    ListField,
    DictField
)

class Product(Model):
    name: str = StringField(min_length=1)
    price: float = FloatField(gt=0)
    in_stock: bool = BooleanField(default=True)
    created_at: datetime = DateTimeField(auto_now_add=True)
    tags: List[str] = ListField(StringField())
    metadata: Dict = DictField(default={})
```

## Validation

### Basic Validation

```python
# Validate at instantiation
user = User(
    name='John',
    email='john@example.com',
    age=30,
    status='active'
)

# Validate manually
user.validate()
```

### Custom Validators

```python
from lightapi.models import validator

class User(Model):
    username: str = Field()
    password: str = Field()
    
    @validator('password')
    def validate_password(cls, value):
        if len(value) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not any(c.isupper() for c in value):
            raise ValueError('Password must contain uppercase letter')
        return value
```

## Serialization

### Basic Serialization

```python
# To dictionary
data = user.dict()

# To JSON
json_data = user.json()

# From dictionary
user = User.from_dict(data)

# From JSON
user = User.from_json(json_string)
```

### Custom Serialization

```python
class User(Model):
    name: str
    email: str
    password: str

    def dict(self, exclude=None):
        data = super().dict(exclude={'password'})
        return data
```

## Relationships

### Model References

```python
class Post(Model):
    title: str
    content: str
    author: User = Field(reference=True)
```

### Nested Models

```python
class Address(Model):
    street: str
    city: str
    country: str

class User(Model):
    name: str
    email: str
    address: Address
```

## Examples

### Complete Model Example

```python
from lightapi.models import Model, Field, validator
from typing import List, Optional
from datetime import datetime

class User(Model):
    id: int = Field(primary_key=True)
    username: str = Field(min_length=3, max_length=50)
    email: str = Field(format='email')
    password: str = Field(min_length=8)
    status: str = Field(choices=['active', 'inactive'], default='active')
    created_at: datetime = Field(auto_now_add=True)
    last_login: Optional[datetime] = Field(null=True)
    roles: List[str] = Field(default=['user'])

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

    def dict(self, exclude=None):
        # Exclude password from serialization
        data = super().dict(exclude={'password'})
        return data

# Usage example
try:
    user = User(
        username='john_doe',
        email='john@example.com',
        password='SecurePass123',
        roles=['user', 'admin']
    )
    user.validate()
    print(user.dict())
except ValueError as e:
    print(f'Validation error: {e}')
```

## Best Practices

1. Define clear validation rules
2. Use appropriate field types
3. Implement custom validation when needed
4. Handle sensitive data appropriately
5. Use type hints for better IDE support

## See Also

- [Database](database.md) - Database integration
- [REST API](rest.md) - REST endpoint implementation
- [Validation](validation.md) - Request validation 