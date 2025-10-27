#!/usr/bin/env python3
"""
LightAPI Advanced Validation Example

This example demonstrates comprehensive validation features in LightAPI.
It shows various validation scenarios, error handling, and custom validation logic.

Features demonstrated:
- Field validation (required, length, format)
- Custom validation methods
- Error handling and responses
- Validation for different HTTP methods
- Edge case handling
"""

from lightapi import LightApi
from lightapi.rest import RestEndpoint
from lightapi.models import Base
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime
from datetime import datetime
import re

class ValidatedUser(Base, RestEndpoint):
    """User model with comprehensive validation"""
    __tablename__ = "validated_users"
    
    id = Column(Integer, primary_key=True)
    username = Column(String(50), nullable=False, unique=True)
    email = Column(String(100), nullable=False, unique=True)
    age = Column(Integer, nullable=False)
    salary = Column(Float, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def validate_data(self, data, method='POST'):
        """Comprehensive validation method"""
        errors = []
        
        # Username validation
        username = data.get('username', '').strip()
        if method == 'POST' and not username:
            errors.append("Username is required")
        elif username:
            if len(username) < 3:
                errors.append("Username must be at least 3 characters long")
            elif len(username) > 50:
                errors.append("Username must be no more than 50 characters long")
            elif not re.match(r'^[a-zA-Z0-9_]+$', username):
                errors.append("Username can only contain letters, numbers, and underscores")
        
        # Email validation
        email = data.get('email', '').strip()
        if method == 'POST' and not email:
            errors.append("Email is required")
        elif email:
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, email):
                errors.append("Invalid email format")
            elif len(email) > 100:
                errors.append("Email must be no more than 100 characters long")
        
        # Age validation
        age = data.get('age')
        if method == 'POST' and age is None:
            errors.append("Age is required")
        elif age is not None:
            try:
                age = int(age)
                if age < 0:
                    errors.append("Age cannot be negative")
                elif age > 150:
                    errors.append("Age cannot be more than 150")
            except (ValueError, TypeError):
                errors.append("Age must be a valid integer")
        
        # Salary validation (optional field)
        salary = data.get('salary')
        if salary is not None:
            try:
                salary = float(salary)
                if salary < 0:
                    errors.append("Salary cannot be negative")
                elif salary > 10000000:  # 10 million limit
                    errors.append("Salary cannot exceed 10,000,000")
            except (ValueError, TypeError):
                errors.append("Salary must be a valid number")
        
        # Boolean validation
        is_active = data.get('is_active')
        if is_active is not None and not isinstance(is_active, bool):
            errors.append("is_active must be a boolean value")
        
        return errors
    
    def post(self, request):
        """Create user with validation"""
        try:
            data = request.data
            
            # Validate input data
            errors = self.validate_data(data, method='POST')
            if errors:
                return {
                    "error": "Validation failed",
                    "details": errors,
                    "received_data": data
                }, 400
            
            # Simulate checking for existing username/email
            username = data.get('username', '').strip()
            email = data.get('email', '').strip()
            
            # Simulate database uniqueness check
            if username.lower() in ['admin', 'root', 'test']:
                return {
                    "error": "Username already exists",
                    "field": "username",
                    "value": username
                }, 409
            
            if email.lower() in ['admin@test.com', 'test@test.com']:
                return {
                    "error": "Email already exists",
                    "field": "email",
                    "value": email
                }, 409
            
            # Create user (simulated)
            new_user = {
                "id": 123,  # Simulated auto-generated ID
                "username": username,
                "email": email,
                "age": int(data['age']),
                "salary": float(data.get('salary', 0)) if data.get('salary') is not None else None,
                "is_active": data.get('is_active', True),
                "created_at": datetime.utcnow().isoformat(),
                "message": "User created successfully"
            }
            
            return new_user, 201
            
        except Exception as e:
            return {
                "error": "Internal server error",
                "message": str(e)
            }, 500
    
    def put(self, request):
        """Update user with validation"""
        try:
            user_id = request.path_params.get('id')
            if not user_id:
                return {"error": "User ID is required"}, 400
            
            try:
                user_id = int(user_id)
            except ValueError:
                return {"error": "Invalid user ID format"}, 400
            
            data = request.data
            
            # Validate input data (PUT allows partial updates)
            errors = self.validate_data(data, method='PUT')
            if errors:
                return {
                    "error": "Validation failed",
                    "details": errors,
                    "received_data": data
                }, 400
            
            # Simulate checking if user exists
            if user_id == 999:
                return {"error": "User not found"}, 404
            
            # Simulate update
            updated_user = {
                "id": user_id,
                "username": data.get('username', f'user_{user_id}'),
                "email": data.get('email', f'user_{user_id}@example.com'),
                "age": int(data.get('age', 25)),
                "salary": float(data.get('salary', 0)) if data.get('salary') is not None else None,
                "is_active": data.get('is_active', True),
                "updated_at": datetime.utcnow().isoformat(),
                "message": "User updated successfully"
            }
            
            return updated_user, 200
            
        except Exception as e:
            return {
                "error": "Internal server error",
                "message": str(e)
            }, 500

class ValidatedProduct(Base, RestEndpoint):
    """Product model with different validation rules"""
    __tablename__ = "validated_products"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    price = Column(Float, nullable=False)
    category = Column(String(50), nullable=False)
    description = Column(String(1000), nullable=True)
    in_stock = Column(Boolean, default=True)
    
    def validate_product_data(self, data, method='POST'):
        """Product-specific validation"""
        errors = []
        
        # Name validation
        name = data.get('name', '').strip()
        if method == 'POST' and not name:
            errors.append("Product name is required")
        elif name:
            if len(name) < 2:
                errors.append("Product name must be at least 2 characters long")
            elif len(name) > 200:
                errors.append("Product name must be no more than 200 characters long")
        
        # Price validation
        price = data.get('price')
        if method == 'POST' and price is None:
            errors.append("Price is required")
        elif price is not None:
            try:
                price = float(price)
                if price < 0:
                    errors.append("Price cannot be negative")
                elif price > 1000000:
                    errors.append("Price cannot exceed 1,000,000")
            except (ValueError, TypeError):
                errors.append("Price must be a valid number")
        
        # Category validation
        category = data.get('category', '').strip()
        valid_categories = ['electronics', 'clothing', 'books', 'home', 'sports', 'toys']
        if method == 'POST' and not category:
            errors.append("Category is required")
        elif category and category.lower() not in valid_categories:
            errors.append(f"Category must be one of: {', '.join(valid_categories)}")
        
        # Description validation (optional)
        description = data.get('description', '').strip()
        if description and len(description) > 1000:
            errors.append("Description must be no more than 1000 characters long")
        
        return errors
    
    def post(self, request):
        """Create product with validation"""
        try:
            data = request.data
            
            # Validate input data
            errors = self.validate_product_data(data, method='POST')
            if errors:
                return {
                    "error": "Product validation failed",
                    "details": errors,
                    "valid_categories": ['electronics', 'clothing', 'books', 'home', 'sports', 'toys']
                }, 400
            
            # Create product (simulated)
            new_product = {
                "id": 456,  # Simulated auto-generated ID
                "name": data['name'].strip(),
                "price": float(data['price']),
                "category": data['category'].lower(),
                "description": data.get('description', '').strip() or None,
                "in_stock": data.get('in_stock', True),
                "created_at": datetime.utcnow().isoformat(),
                "message": "Product created successfully"
            }
            
            return new_product, 201
            
        except Exception as e:
            return {
                "error": "Internal server error",
                "message": str(e)
            }, 500

def create_app():
    """Create the validation demo app"""
    app = LightApi(
        database_url="sqlite:///./validation_demo.db",
        swagger_title="Advanced Validation Demo",
        swagger_version="1.0.0",
        swagger_description="Demonstration of comprehensive validation in LightAPI",
    )
    
    app.register(ValidatedUser)
    app.register(ValidatedProduct)
    
    return app

if __name__ == "__main__":
    app = create_app()
    
    print("🔍 Advanced Validation Demo Server")
    print("=" * 50)
    print("Server running at http://localhost:8000")
    print("API documentation at http://localhost:8000/docs")
    print()
    print("Test validation with these examples:")
    print()
    print("✅ Valid user creation:")
    print('curl -X POST http://localhost:8000/validated_users \\')
    print('  -H "Content-Type: application/json" \\')
    print('  -d \'{"username": "john_doe", "email": "john@example.com", "age": 30, "salary": 50000}\'')
    print()
    print("❌ Invalid user creation (missing required fields):")
    print('curl -X POST http://localhost:8000/validated_users \\')
    print('  -H "Content-Type: application/json" \\')
    print('  -d \'{"username": "jo"}\'')
    print()
    print("❌ Invalid user creation (bad email format):")
    print('curl -X POST http://localhost:8000/validated_users \\')
    print('  -H "Content-Type: application/json" \\')
    print('  -d \'{"username": "jane", "email": "invalid-email", "age": 25}\'')
    print()
    print("❌ Invalid user creation (negative age):")
    print('curl -X POST http://localhost:8000/validated_users \\')
    print('  -H "Content-Type: application/json" \\')
    print('  -d \'{"username": "bob", "email": "bob@example.com", "age": -5}\'')
    print()
    print("✅ Valid product creation:")
    print('curl -X POST http://localhost:8000/validated_products \\')
    print('  -H "Content-Type: application/json" \\')
    print('  -d \'{"name": "Laptop", "price": 999.99, "category": "electronics", "description": "High-performance laptop"}\'')
    print()
    print("❌ Invalid product creation (invalid category):")
    print('curl -X POST http://localhost:8000/validated_products \\')
    print('  -H "Content-Type: application/json" \\')
    print('  -d \'{"name": "Book", "price": 19.99, "category": "invalid_category"}\'')
    
    app.run(host="localhost", port=8000, debug=True)