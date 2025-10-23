#!/usr/bin/env python3
"""
LightAPI Error Handling Example

This example demonstrates comprehensive error handling patterns in LightAPI.
It shows how to create custom exceptions, handle different error types,
and provide meaningful error responses to clients.

Features demonstrated:
- Custom exception classes
- Error response formatting
- HTTP status code handling
- Validation error handling
- Database error handling
"""

from sqlalchemy import Column, Integer, String, Float
from lightapi import LightApi, Response
from lightapi.models import Base
from lightapi.rest import RestEndpoint


class ValidationError(Exception):
    """Custom validation error."""
    def __init__(self, message, field=None):
        self.message = message
        self.field = field
        super().__init__(self.message)


class BusinessLogicError(Exception):
    """Custom business logic error."""
    def __init__(self, message, code=None):
        self.message = message
        self.code = code
        super().__init__(self.message)


class Product(Base, RestEndpoint):
    """Product model with comprehensive error handling."""
    __tablename__ = "error_products"
    __table_args__ = {"extend_existing": True}
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    price = Column(Float, nullable=False)
    stock = Column(Integer, default=0)
    
    def validate_price(self, price):
        """Validate product price."""
        if price <= 0:
            raise ValidationError("Price must be greater than 0", field="price")
        if price > 10000:
            raise ValidationError("Price cannot exceed $10,000", field="price")
        return price
    
    def validate_stock(self, stock):
        """Validate stock quantity."""
        if stock < 0:
            raise ValidationError("Stock cannot be negative", field="stock")
        if stock > 1000:
            raise ValidationError("Stock cannot exceed 1000 units", field="stock")
        return stock
    
    def post(self, request):
        """Create a new product with validation."""
        try:
            data = request.json()
            
            # Validate required fields
            if not data.get('name'):
                raise ValidationError("Product name is required", field="name")
            
            # Validate price
            price = data.get('price')
            if price is None:
                raise ValidationError("Price is required", field="price")
            
            try:
                price = float(price)
                self.validate_price(price)
            except ValueError:
                raise ValidationError("Price must be a valid number", field="price")
            
            # Validate stock
            stock = data.get('stock', 0)
            try:
                stock = int(stock)
                self.validate_stock(stock)
            except ValueError:
                raise ValidationError("Stock must be a valid integer", field="stock")
            
            # Business logic validation
            if price > 5000 and stock > 100:
                raise BusinessLogicError(
                    "High-value products cannot have high stock quantities",
                    code="HIGH_VALUE_HIGH_STOCK"
                )
            
            # Create product
            product = Product(
                name=data['name'],
                price=price,
                stock=stock
            )
            
            # Save to database
            self.db.add(product)
            self.db.commit()
            
            return Response(
                body={
                    "message": "Product created successfully",
                    "product": {
                        "id": product.id,
                        "name": product.name,
                        "price": product.price,
                        "stock": product.stock
                    }
                },
                status_code=201
            )
            
        except ValidationError as e:
            return Response(
                body={
                    "error": "Validation Error",
                    "message": e.message,
                    "field": e.field,
                    "type": "validation_error"
                },
                status_code=400
            )
            
        except BusinessLogicError as e:
            return Response(
                body={
                    "error": "Business Logic Error",
                    "message": e.message,
                    "code": e.code,
                    "type": "business_error"
                },
                status_code=422
            )
            
        except Exception as e:
            return Response(
                body={
                    "error": "Internal Server Error",
                    "message": "An unexpected error occurred",
                    "type": "server_error"
                },
                status_code=500
            )
    
    def get(self, request):
        """Get products with error handling."""
        try:
            products = self.db.query(Product).all()
            
            if not products:
                return Response(
                    body={
                        "message": "No products found",
                        "products": []
                    },
                    status_code=200
                )
            
            return Response(
                body={
                    "message": f"Found {len(products)} products",
                    "products": [
                        {
                            "id": p.id,
                            "name": p.name,
                            "price": p.price,
                            "stock": p.stock
                        }
                        for p in products
                    ]
                },
                status_code=200
            )
            
        except Exception as e:
            return Response(
                body={
                    "error": "Database Error",
                    "message": "Failed to retrieve products",
                    "type": "database_error"
                },
                status_code=500
            )
    
    def get_id(self, request):
        """Get a specific product by ID."""
        try:
            product_id = int(request.path_params['id'])
            product = self.db.query(Product).filter(Product.id == product_id).first()
            
            if not product:
                return Response(
                    body={
                        "error": "Not Found",
                        "message": f"Product with ID {product_id} not found",
                        "type": "not_found"
                    },
                    status_code=404
                )
            
            return Response(
                body={
                    "product": {
                        "id": product.id,
                        "name": product.name,
                        "price": product.price,
                        "stock": product.stock
                    }
                },
                status_code=200
            )
            
        except ValueError:
            return Response(
                body={
                    "error": "Invalid ID",
                    "message": "Product ID must be a valid integer",
                    "type": "validation_error"
                },
                status_code=400
            )
            
        except Exception as e:
            return Response(
                body={
                    "error": "Internal Server Error",
                    "message": "An unexpected error occurred",
                    "type": "server_error"
                },
                status_code=500
            )


if __name__ == "__main__":
    print("🚨 LightAPI Error Handling Example")
    print("=" * 50)
    
    # Initialize the API
    app = LightApi(
        database_url="sqlite:///error_handling_example.db",
        swagger_title="Error Handling API",
        swagger_version="1.0.0",
        swagger_description="Demonstrates comprehensive error handling patterns",
        enable_swagger=True
    )
    
    # Register our endpoint
    app.register(Product)
    
    print("Server running at http://localhost:8000")
    print("API documentation at http://localhost:8000/docs")
    print()
    print("Test error handling with:")
    print("  # Valid product")
    print("  curl -X POST http://localhost:8000/product/ -H 'Content-Type: application/json' -d '{\"name\": \"Test Product\", \"price\": 29.99, \"stock\": 50}'")
    print()
    print("  # Invalid price")
    print("  curl -X POST http://localhost:8000/product/ -H 'Content-Type: application/json' -d '{\"name\": \"Test Product\", \"price\": -10, \"stock\": 50}'")
    print()
    print("  # Missing required field")
    print("  curl -X POST http://localhost:8000/product/ -H 'Content-Type: application/json' -d '{\"price\": 29.99}'")
    print()
    print("  # Business logic error")
    print("  curl -X POST http://localhost:8000/product/ -H 'Content-Type: application/json' -d '{\"name\": \"Expensive Product\", \"price\": 6000, \"stock\": 200}'")
    print()
    print("  # Get non-existent product")
    print("  curl http://localhost:8000/product/999/")
    
    # Run the server
    app.run(host="localhost", port=8000, debug=True)
