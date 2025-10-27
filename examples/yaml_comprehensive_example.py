#!/usr/bin/env python3
"""
LightAPI Comprehensive YAML Configuration Example

This example demonstrates the complete YAML configuration system for LightAPI,
showing how to define database-driven APIs using YAML files without writing Python code.

Features demonstrated:
- YAML-driven API generation from existing database tables
- Database reflection and automatic model creation
- CRUD operation configuration per table
- Swagger/OpenAPI documentation generation
- Environment variable support
- Multiple database support
- Advanced table configurations

Prerequisites:
- pip install lightapi pyyaml
- Database with existing tables (SQLite, PostgreSQL, MySQL)
"""

import os
import tempfile
import yaml
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, DECIMAL
from sqlalchemy import create_engine
from sqlalchemy.sql import func
from lightapi import LightApi
from lightapi.models import Base

# Constants
DEFAULT_DB_NAME = "comprehensive_example.db"
DEFAULT_PORT = 8000

if __name__ == "__main__":
    # Define SQLAlchemy models in main section
    class User(Base):
        __tablename__ = "users"
        id = Column(Integer, primary_key=True)
        username = Column(String(50), unique=True, nullable=False)
        email = Column(String(100), unique=True, nullable=False)
        full_name = Column(String(100))
        is_active = Column(Boolean, default=True)
        created_at = Column(DateTime, default=func.now())
        updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    class Category(Base):
        __tablename__ = "categories"
        id = Column(Integer, primary_key=True)
        name = Column(String(100), unique=True, nullable=False)
        description = Column(Text)
        parent_id = Column(Integer, ForeignKey("categories.id"))
        is_active = Column(Boolean, default=True)

    class Product(Base):
        __tablename__ = "products"
        id = Column(Integer, primary_key=True)
        name = Column(String(200), nullable=False)
        description = Column(Text)
        price = Column(DECIMAL(10, 2), nullable=False)
        category_id = Column(Integer, ForeignKey("categories.id"))
        sku = Column(String(50), unique=True)
        stock_quantity = Column(Integer, default=0)
        is_active = Column(Boolean, default=True)
        created_at = Column(DateTime, default=func.now())

    class Order(Base):
        __tablename__ = "orders"
        id = Column(Integer, primary_key=True)
        user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
        total_amount = Column(DECIMAL(10, 2), nullable=False)
        status = Column(String(20), default="pending")
        order_date = Column(DateTime, default=func.now())
        shipping_address = Column(Text)
        notes = Column(Text)

    class OrderItem(Base):
        __tablename__ = "order_items"
        id = Column(Integer, primary_key=True)
        order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
        product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
        quantity = Column(Integer, nullable=False)
        unit_price = Column(DECIMAL(10, 2), nullable=False)
        total_price = Column(DECIMAL(10, 2), nullable=False)

    def create_sample_database():
        """Create sample database using SQLAlchemy ORM."""
        # Create temporary database file
        db_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        db_path = db_file.name
        db_file.close()
        
        # Create engine and tables using ORM
        engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(engine)
        
        return db_path

    def create_yaml_config(db_path):
        """Create YAML configuration file."""
        config = {
            'database_url': f'sqlite:///{db_path}',
            'tables': [
                {'name': 'users', 'methods': ['GET', 'POST', 'PUT', 'DELETE']},
                {'name': 'categories', 'methods': ['GET', 'POST', 'PUT', 'DELETE']},
                {'name': 'products', 'methods': ['GET', 'POST', 'PUT', 'DELETE']},
                {'name': 'orders', 'methods': ['GET', 'POST', 'PUT', 'DELETE']},
                {'name': 'order_items', 'methods': ['GET', 'POST', 'PUT', 'DELETE']}
            ]
        }
        
        config_path = os.path.join(os.path.dirname(__file__), 'comprehensive_config.yaml')
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        return config_path

    def _print_usage():
        """Print usage instructions."""
        print("🚀 Comprehensive YAML Configuration Example")
        print("=" * 60)
        print("This example demonstrates:")
        print("• YAML-driven API generation")
        print("• Database reflection and automatic model creation")
        print("• CRUD operation configuration per table")
        print("• Swagger/OpenAPI documentation generation")
        print()
        print("Server running at http://localhost:8000")
        print("API documentation available at http://localhost:8000/docs")
        print()
        print("Available endpoints:")
        print("• GET/POST/PUT/DELETE /users")
        print("• GET/POST/PUT/DELETE /categories")
        print("• GET/POST/PUT/DELETE /products")
        print("• GET/POST/PUT/DELETE /orders")
        print("• GET/POST/PUT/DELETE /order_items")
        print()
        print("Try these example queries:")
        print("  curl http://localhost:8000/users")
        print("  curl http://localhost:8000/products")
        print("  curl http://localhost:8000/categories")

    # Create database and configuration
    db_path = create_sample_database()
    config_path = create_yaml_config(db_path)
    
    # Create LightAPI instance from YAML configuration
    app = LightApi.from_config(config_path)
    
    _print_usage()
    
    # Run the server
    app.run(host="localhost", port=DEFAULT_PORT, debug=True)