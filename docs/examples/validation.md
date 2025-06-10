# Validation Example

This example demonstrates how to implement robust data validation in LightAPI to ensure data integrity and provide clear error messages to clients.

## Overview

Learn how to:
- Create custom validator classes with field-specific validation
- Handle validation errors gracefully with appropriate HTTP status codes
- Validate different data types (strings, numbers, custom formats)
- Transform and sanitize input data
- Provide meaningful error messages to API clients

## Complete Example Code

```python
from sqlalchemy import Column, Integer, String
from lightapi.core import LightApi, Response
from lightapi.rest import RestEndpoint, Validator
from lightapi.models import Base, register_model_class

# Define a custom validator with field-specific validation methods
class ProductValidator(Validator):
    def validate_name(self, value):
        if not value or len(value) < 3:
            raise ValueError("Product name must be at least 3 characters")
        return value.strip()
    
    def validate_price(self, value):
        try:
            price = float(value)
            if price <= 0:
                raise ValueError("Price must be greater than zero")
            return price
        except (TypeError, ValueError) as e:
            # If it's our own ValueError, re-raise it 
            if isinstance(e, ValueError) and "must be greater than zero" in str(e):
                raise e
            # Otherwise, raise the generic message
            raise ValueError("Price must be a valid number")
    
    def validate_sku(self, value):
        if not value or not isinstance(value, str) or len(value) != 8:
            raise ValueError("SKU must be an 8-character string")
        return value.upper()

# Define a model that uses the validator
@register_model_class
class Product(RestEndpoint):
    __tablename__ = 'products'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    price = Column(Integer)  # Stored as cents
    sku = Column(String(8), unique=True)
    
    class Configuration:
        validator_class = ProductValidator
    
    # Override POST to handle validation errors gracefully
    def post(self, request):
        try:
            data = getattr(request, 'data', {})
            
            # The validator will raise exceptions if validation fails
            validated_data = self.validator.validate(data)
            
            # Convert price to cents for storage
            if 'price' in validated_data:
                validated_data['price'] = int(validated_data['price'] * 100)
                
            instance = self.__class__(**validated_data)
            self.session.add(instance)
            self.session.commit()
            
            # Return the created instance
            return {
                "id": instance.id,
                "name": instance.name,
                "price": instance.price / 100,  # Convert back to dollars
                "sku": instance.sku
            }, 201
            
        except ValueError as e:
            # Return validation errors with 400 status
            return Response({"error": str(e)}, status_code=400)
        except Exception as e:
            self.session.rollback()
            return Response({"error": str(e)}, status_code=500)
```

## Key Components

### 1. Custom Validator Class

The `ProductValidator` extends the base `Validator` class with field-specific validation methods:

#### Name Validation
```python
def validate_name(self, value):
    if not value or len(value) < 3:
        raise ValueError("Product name must be at least 3 characters")
    return value.strip()  # Remove whitespace
```

**Features:**
- Checks for minimum length requirement
- Strips whitespace from input
- Provides clear error message

#### Price Validation
```python
def validate_price(self, value):
    try:
        price = float(value)
        if price <= 0:
            raise ValueError("Price must be greater than zero")
        return price
    except (TypeError, ValueError) as e:
        if isinstance(e, ValueError) and "must be greater than zero" in str(e):
            raise e
        raise ValueError("Price must be a valid number")
```

**Features:**
- Converts string/numeric input to float
- Validates positive values only
- Distinguishes between type errors and value errors
- Preserves specific error messages

#### SKU Validation
```python
def validate_sku(self, value):
    if not value or not isinstance(value, str) or len(value) != 8:
        raise ValueError("SKU must be an 8-character string")
    return value.upper()  # Normalize to uppercase
```

**Features:**
- Validates exact length requirement
- Ensures string type
- Normalizes to uppercase format

### 2. Model with Validation Integration

The `Product` model integrates validation seamlessly:

```python
class Configuration:
    validator_class = ProductValidator

def post(self, request):
    try:
        data = getattr(request, 'data', {})
        validated_data = self.validator.validate(data)
        
        # Transform data for storage
        if 'price' in validated_data:
            validated_data['price'] = int(validated_data['price'] * 100)
        
        # Create and save instance
        instance = self.__class__(**validated_data)
        self.session.add(instance)
        self.session.commit()
        
        return response_data, 201
    except ValueError as e:
        return Response({"error": str(e)}, status_code=400)
```

**Key Features:**
- Automatic validation on POST requests
- Data transformation (dollars to cents)
- Error handling with appropriate HTTP status codes
- Database rollback on errors

## Usage Examples

### Valid Requests

```bash
# Create a valid product
curl -X POST http://localhost:8000/products \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Gaming Laptop",
    "price": 1299.99,
    "sku": "LAP12345"
  }'
```

**Response (201 Created):**
```json
{
  "id": 1,
  "name": "Gaming Laptop",
  "price": 1299.99,
  "sku": "LAP12345"
}
```

### Validation Error Examples

#### Name Too Short
```bash
curl -X POST http://localhost:8000/products \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "PC",
    "price": 999.99,
    "sku": "PC123456"
  }'
```

**Response (400 Bad Request):**
```json
{
  "error": "Product name must be at least 3 characters"
}
```

#### Invalid Price
```bash
curl -X POST http://localhost:8000/products \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Smartphone",
    "price": -100,
    "sku": "PHN12345"
  }'
```

**Response (400 Bad Request):**
```json
{
  "error": "Price must be greater than zero"
}
```

#### Invalid SKU Length
```bash
curl -X POST http://localhost:8000/products \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Tablet",
    "price": 499.99,
    "sku": "TAB"
  }'
```

**Response (400 Bad Request):**
```json
{
  "error": "SKU must be an 8-character string"
}
```

## Advanced Validation Patterns

### 1. Multiple Field Validation

```python
class AdvancedProductValidator(Validator):
    def validate_name(self, value):
        if not value or len(value) < 3:
            raise ValueError("Product name must be at least 3 characters")
        if len(value) > 100:
            raise ValueError("Product name cannot exceed 100 characters")
        return value.strip().title()  # Title case normalization
    
    def validate_price(self, value):
        try:
            price = float(value)
            if price <= 0:
                raise ValueError("Price must be greater than zero")
            if price > 100000:
                raise ValueError("Price cannot exceed $100,000")
            return round(price, 2)  # Round to 2 decimal places
        except (TypeError, ValueError) as e:
            if isinstance(e, ValueError) and ("greater than zero" in str(e) or "exceed" in str(e)):
                raise e
            raise ValueError("Price must be a valid number")
    
    def validate_sku(self, value):
        import re
        if not value or not isinstance(value, str):
            raise ValueError("SKU is required and must be a string")
        
        # SKU format: 3 letters + 5 digits
        pattern = r'^[A-Z]{3}\d{5}$'
        sku = value.upper()
        
        if not re.match(pattern, sku):
            raise ValueError("SKU must be 3 letters followed by 5 digits (e.g., ABC12345)")
        
        return sku
    
    def validate_category(self, value):
        valid_categories = ['electronics', 'clothing', 'books', 'home', 'sports']
        if not value or value.lower() not in valid_categories:
            raise ValueError(f"Category must be one of: {', '.join(valid_categories)}")
        return value.lower()
    
    def validate(self, data):
        """Override validate method for cross-field validation"""
        validated_data = super().validate(data)
        
        # Cross-field validation
        if 'category' in validated_data and 'price' in validated_data:
            category = validated_data['category']
            price = validated_data['price']
            
            # Category-specific price validation
            if category == 'electronics' and price < 10:
                raise ValueError("Electronics products must be priced at least $10")
            elif category == 'books' and price > 500:
                raise ValueError("Books cannot be priced over $500")
        
        return validated_data
```

### 2. Date and Email Validation

```python
from datetime import datetime
import re

class UserValidator(Validator):
    def validate_email(self, value):
        if not value:
            raise ValueError("Email is required")
        
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, value):
            raise ValueError("Please provide a valid email address")
        
        return value.lower()
    
    def validate_birth_date(self, value):
        if isinstance(value, str):
            try:
                birth_date = datetime.strptime(value, '%Y-%m-%d')
            except ValueError:
                raise ValueError("Birth date must be in YYYY-MM-DD format")
        elif isinstance(value, datetime):
            birth_date = value
        else:
            raise ValueError("Birth date must be a valid date")
        
        # Age validation
        today = datetime.now()
        age = today.year - birth_date.year
        if birth_date.replace(year=today.year) > today:
            age -= 1
        
        if age < 13:
            raise ValueError("Users must be at least 13 years old")
        if age > 120:
            raise ValueError("Please provide a valid birth date")
        
        return birth_date.date()
    
    def validate_phone(self, value):
        if not value:
            return None  # Optional field
        
        # Remove common formatting characters
        phone = re.sub(r'[^\d+]', '', str(value))
        
        # Validate US phone number format
        if phone.startswith('+1'):
            phone = phone[2:]
        
        if len(phone) != 10 or not phone.isdigit():
            raise ValueError("Phone number must be 10 digits (US format)")
        
        return f"+1{phone}"
```

### 3. File Upload Validation

```python
class FileValidator(Validator):
    def validate_image(self, value):
        if not value:
            raise ValueError("Image file is required")
        
        # Check file size (max 5MB)
        max_size = 5 * 1024 * 1024
        if hasattr(value, 'size') and value.size > max_size:
            raise ValueError("Image file must be smaller than 5MB")
        
        # Check file type
        allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
        content_type = getattr(value, 'content_type', '')
        
        if content_type not in allowed_types:
            raise ValueError("Image must be JPEG, PNG, GIF, or WebP format")
        
        return value
    
    def validate_document(self, value):
        if not value:
            return None  # Optional
        
        # Check file size (max 10MB)
        max_size = 10 * 1024 * 1024
        if hasattr(value, 'size') and value.size > max_size:
            raise ValueError("Document must be smaller than 10MB")
        
        # Check file type
        allowed_types = ['application/pdf', 'application/msword', 
                        'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
        content_type = getattr(value, 'content_type', '')
        
        if content_type not in allowed_types:
            raise ValueError("Document must be PDF or Word format")
        
        return value
```

## Error Handling Patterns

### 1. Structured Error Responses

```python
class DetailedProductValidator(Validator):
    def validate(self, data):
        errors = {}
        validated_data = {}
        
        for field_name, value in data.items():
            try:
                method_name = f'validate_{field_name}'
                if hasattr(self, method_name):
                    validator = getattr(self, method_name)
                    validated_data[field_name] = validator(value)
                else:
                    validated_data[field_name] = value
            except ValueError as e:
                errors[field_name] = str(e)
        
        if errors:
            raise ValueError({
                "message": "Validation failed",
                "errors": errors
            })
        
        return validated_data

def post(self, request):
    try:
        data = getattr(request, 'data', {})
        validated_data = self.validator.validate(data)
        
        # Process validated data...
        return response_data, 201
        
    except ValueError as e:
        error_data = e.args[0] if e.args else str(e)
        if isinstance(error_data, dict):
            return Response(error_data, status_code=400)
        else:
            return Response({"error": str(e)}, status_code=400)
```

**Structured Error Response:**
```json
{
  "message": "Validation failed",
  "errors": {
    "name": "Product name must be at least 3 characters",
    "price": "Price must be greater than zero",
    "sku": "SKU must be an 8-character string"
  }
}
```

### 2. Field-Level Error Context

```python
class ContextualValidator(Validator):
    def validate_name(self, value):
        context = {
            "field": "name",
            "value": value,
            "requirements": "3-100 characters, alphanumeric and spaces only"
        }
        
        if not value:
            raise ValueError({
                "message": "Product name is required",
                "context": context
            })
        
        if len(value) < 3:
            raise ValueError({
                "message": "Product name is too short",
                "context": {**context, "minimum_length": 3}
            })
        
        if len(value) > 100:
            raise ValueError({
                "message": "Product name is too long", 
                "context": {**context, "maximum_length": 100}
            })
        
        # Validate character set
        if not re.match(r'^[a-zA-Z0-9\s]+$', value):
            raise ValueError({
                "message": "Product name contains invalid characters",
                "context": {**context, "allowed_characters": "letters, numbers, and spaces"}
            })
        
        return value.strip().title()
```

## Testing Validation

### 1. Unit Tests

```python
import pytest
from your_app import ProductValidator

def test_product_validator():
    validator = ProductValidator()
    
    # Test valid data
    valid_data = {
        "name": "Gaming Laptop",
        "price": 1299.99,
        "sku": "LAP12345"
    }
    result = validator.validate(valid_data)
    assert result["name"] == "Gaming Laptop"
    assert result["price"] == 1299.99
    assert result["sku"] == "LAP12345"
    
    # Test validation errors
    with pytest.raises(ValueError, match="must be at least 3 characters"):
        validator.validate_name("PC")
    
    with pytest.raises(ValueError, match="must be greater than zero"):
        validator.validate_price(-100)
    
    with pytest.raises(ValueError, match="8-character string"):
        validator.validate_sku("SHORT")
```

### 2. Integration Tests

```python
def test_validation_endpoint(client):
    # Test valid request
    response = client.post('/products', json={
        "name": "Gaming Laptop",
        "price": 1299.99,
        "sku": "LAP12345"
    })
    assert response.status_code == 201
    
    # Test validation error
    response = client.post('/products', json={
        "name": "PC",
        "price": -100,
        "sku": "SHORT"
    })
    assert response.status_code == 400
    assert "error" in response.json()
```

## Best Practices

### 1. Validation Rules

- **Fail Fast**: Validate input as early as possible
- **Clear Messages**: Provide specific, actionable error messages
- **Consistent Format**: Use consistent error response format across your API
- **Security**: Sanitize input to prevent injection attacks

### 2. Performance Considerations

- **Minimal Processing**: Keep validation lightweight and fast
- **Avoid External Calls**: Don't make database queries in validators unless necessary
- **Cache Results**: Cache expensive validation results when appropriate

### 3. User Experience

- **Field-Level Errors**: Return errors for all invalid fields, not just the first one
- **Helpful Context**: Include information about valid formats and requirements
- **Internationalization**: Support multiple languages for error messages

## Integration with Other Features

### With Authentication
```python
class AuthenticatedProduct(Product):
    class Configuration:
        validator_class = ProductValidator
        authentication_classes = [JWTAuthentication]
```

### With Caching
```python
class CachedProduct(Product):
    class Configuration:
        validator_class = ProductValidator
        caching_class = RedisCache
```

## Running the Example

```bash
# Start the validation example
python examples/validation_example.py

# Test valid request
curl -X POST http://localhost:8000/products \
  -H 'Content-Type: application/json' \
  -d '{"name": "Gaming Laptop", "price": 1299.99, "sku": "LAP12345"}'

# Test validation error
curl -X POST http://localhost:8000/products \
  -H 'Content-Type: application/json' \
  -d '{"name": "PC", "price": -100, "sku": "SHORT"}'
```

## Next Steps

- **[Filtering and Pagination](filtering-pagination.md)** - Query optimization
- **[Middleware Example](middleware.md)** - Custom middleware development
- **[API Reference](../api-reference/rest.md)** - REST API details
- **[Authentication Example](auth.md)** - Security patterns 