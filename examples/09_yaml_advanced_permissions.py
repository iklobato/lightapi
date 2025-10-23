#!/usr/bin/env python3
"""
Advanced YAML Configuration - Role-Based Permissions Example

This example demonstrates advanced YAML configuration with different permission
levels for different tables, simulating a real-world application with role-based access.

Features demonstrated:
- Different CRUD operations per table
- Read-only tables
- Limited operations (create/update only)
- Administrative vs user permissions
- Complex database schema
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
DEFAULT_PORT = 8000

if __name__ == "__main__":
    # Define SQLAlchemy models in main section
    class User(Base):
        __tablename__ = "users"
        id = Column(Integer, primary_key=True)
        username = Column(String(50), unique=True, nullable=False)
        email = Column(String(100), unique=True, nullable=False)
        role = Column(String(20), default="user")
        is_active = Column(Boolean, default=True)
        created_at = Column(DateTime, default=func.now())

    class Product(Base):
        __tablename__ = "products"
        id = Column(Integer, primary_key=True)
        name = Column(String(200), nullable=False)
        description = Column(Text)
        price = Column(DECIMAL(10, 2), nullable=False)
        category_id = Column(Integer, ForeignKey("categories.id"))
        is_active = Column(Boolean, default=True)
        created_at = Column(DateTime, default=func.now())

    class Category(Base):
        __tablename__ = "categories"
        id = Column(Integer, primary_key=True)
        name = Column(String(100), unique=True, nullable=False)
        description = Column(Text)
        is_active = Column(Boolean, default=True)

    class Order(Base):
        __tablename__ = "orders"
        id = Column(Integer, primary_key=True)
        user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
        total_amount = Column(DECIMAL(10, 2), nullable=False)
        status = Column(String(20), default="pending")
        created_at = Column(DateTime, default=func.now())

    class OrderItem(Base):
        __tablename__ = "order_items"
        id = Column(Integer, primary_key=True)
        order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
        product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
        quantity = Column(Integer, nullable=False)
        unit_price = Column(DECIMAL(10, 2), nullable=False)

    class AuditLog(Base):
        __tablename__ = "audit_logs"
        id = Column(Integer, primary_key=True)
        user_id = Column(Integer, ForeignKey("users.id"))
        action = Column(String(50), nullable=False)
        table_name = Column(String(50), nullable=False)
        record_id = Column(Integer)
        details = Column(Text)
        created_at = Column(DateTime, default=func.now())

    def create_advanced_database():
        """Create a complex database using SQLAlchemy ORM."""
        # Create temporary database
        db_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        db_path = db_file.name
        db_file.close()
        
        # Create engine and tables using ORM
        engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(engine)
        
        return db_path

    def create_yaml_config(db_path):
        """Create advanced YAML configuration file with permissions."""
        config = {
            'database_url': f'sqlite:///{db_path}',
            'tables': [
                {'name': 'users', 'methods': ['GET', 'POST', 'PUT', 'DELETE']},
                {'name': 'products', 'methods': ['GET', 'POST', 'PUT']},
                {'name': 'categories', 'methods': ['GET']},
                {'name': 'orders', 'methods': ['GET', 'POST']},
                {'name': 'order_items', 'methods': ['GET', 'POST']},
                {'name': 'audit_logs', 'methods': ['GET']}
            ]
        }
        
        config_path = os.path.join(os.path.dirname(__file__), 'advanced_permissions_config.yaml')
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        return config_path

    def _print_usage():
        """Print usage instructions."""
        print("🚀 Advanced YAML Configuration - Role-Based Permissions")
        print("=" * 60)
        print("This example demonstrates:")
        print("• Different CRUD operations per table")
        print("• Read-only tables")
        print("• Limited operations (create/update only)")
        print("• Administrative vs user permissions")
        print("• Complex database schema")
        print()
        print("Server running at http://localhost:8000")
        print("API documentation available at http://localhost:8000/docs")
        print()
        print("Available endpoints with permissions:")
        print("• GET/POST/PUT/DELETE /users (admin only)")
        print("• GET/POST/PUT /products (no delete)")
        print("• GET /categories (read-only)")
        print("• GET/POST /orders (user)")
        print("• GET/POST /order_items (user)")
        print("• GET /audit_logs (admin read-only)")
        print()
        print("Try these example queries:")
        print("  curl http://localhost:8000/categories")
        print("  curl http://localhost:8000/products")

    # Create database and configuration
    db_path = create_advanced_database()
    config_path = create_yaml_config(db_path)
    
    # Create LightAPI instance from YAML configuration
    app = LightApi.from_config(config_path)
    
    _print_usage()
    
    # Run the server
    app.run(host="localhost", port=DEFAULT_PORT, debug=True)