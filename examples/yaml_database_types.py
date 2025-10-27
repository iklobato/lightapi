#!/usr/bin/env python3
"""
YAML Configuration for Different Database Types Example

This example demonstrates how to configure LightAPI YAML files for different
database systems (SQLite, PostgreSQL, MySQL) with proper connection strings
and database-specific considerations.

Features demonstrated:
- SQLite configuration (file-based)
- PostgreSQL configuration (production database)
- MySQL configuration (alternative production database)
- Database-specific connection parameters
- Environment-based database selection
"""

import os
import tempfile
import yaml
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey, DECIMAL, Float
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
        full_name = Column(String(100))
        age = Column(Integer)
        salary = Column(DECIMAL(10, 2))
        is_active = Column(Boolean, default=True)
        created_at = Column(DateTime, default=func.now())

    class Product(Base):
        __tablename__ = "products"
        id = Column(Integer, primary_key=True)
        name = Column(String(200), nullable=False)
        description = Column(Text)
        price = Column(DECIMAL(10, 2), nullable=False)
        weight = Column(Float)
        category = Column(String(100))
        is_active = Column(Boolean, default=True)
        created_at = Column(DateTime, default=func.now())

    class Order(Base):
        __tablename__ = "orders"
        id = Column(Integer, primary_key=True)
        user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
        total_amount = Column(DECIMAL(10, 2), nullable=False)
        status = Column(String(20), default="pending")
        order_date = Column(DateTime, default=func.now())

    def create_sqlite_database():
        """Create a SQLite database using SQLAlchemy ORM."""
        # Create temporary database
        db_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        db_path = db_file.name
        db_file.close()
        
        # Create engine and tables using ORM
        engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(engine)
        
        return db_path

    def create_sqlite_config(db_path):
        """Create SQLite YAML configuration."""
        config = {
            'database_url': f'sqlite:///{db_path}',
            'tables': [
                {'name': 'users', 'methods': ['GET', 'POST', 'PUT', 'DELETE']},
                {'name': 'products', 'methods': ['GET', 'POST', 'PUT', 'DELETE']},
                {'name': 'orders', 'methods': ['GET', 'POST', 'PUT', 'DELETE']}
            ]
        }
        
        config_path = os.path.join(os.path.dirname(__file__), 'sqlite_config.yaml')
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        return config_path

    def create_postgresql_config():
        """Create PostgreSQL YAML configuration."""
        config = {
            'database': {
                'url': 'postgresql://user:password@localhost:5432/mydb',
                'echo': False,
                'pool_size': 10,
                'max_overflow': 20,
                'pool_pre_ping': True,
                'pool_recycle': 3600
            },
            'swagger': {
                'title': 'PostgreSQL Database API',
                'version': '1.0.0',
                'description': 'API using PostgreSQL database',
                'enabled': True
            },
            'endpoints': {
                'users': {
                    'table': 'users',
                    'methods': ['GET', 'POST', 'PUT', 'DELETE'],
                    'description': 'User management endpoints'
                },
                'products': {
                    'table': 'products',
                    'methods': ['GET', 'POST', 'PUT', 'DELETE'],
                    'description': 'Product management endpoints'
                },
                'orders': {
                    'table': 'orders',
                    'methods': ['GET', 'POST', 'PUT', 'DELETE'],
                    'description': 'Order management endpoints'
                }
            }
        }
        
        config_path = os.path.join(os.path.dirname(__file__), 'postgresql_config.yaml')
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        return config_path

    def create_mysql_config():
        """Create MySQL YAML configuration."""
        config = {
            'database': {
                'url': 'mysql+pymysql://user:password@localhost:3306/mydb',
                'echo': False,
                'pool_size': 10,
                'max_overflow': 20,
                'pool_pre_ping': True,
                'pool_recycle': 3600,
                'charset': 'utf8mb4'
            },
            'swagger': {
                'title': 'MySQL Database API',
                'version': '1.0.0',
                'description': 'API using MySQL database',
                'enabled': True
            },
            'endpoints': {
                'users': {
                    'table': 'users',
                    'methods': ['GET', 'POST', 'PUT', 'DELETE'],
                    'description': 'User management endpoints'
                },
                'products': {
                    'table': 'products',
                    'methods': ['GET', 'POST', 'PUT', 'DELETE'],
                    'description': 'Product management endpoints'
                },
                'orders': {
                    'table': 'orders',
                    'methods': ['GET', 'POST', 'PUT', 'DELETE'],
                    'description': 'Order management endpoints'
                }
            }
        }
        
        config_path = os.path.join(os.path.dirname(__file__), 'mysql_config.yaml')
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        return config_path

    def _print_usage():
        """Print usage instructions."""
        print("🚀 YAML Configuration for Different Database Types")
        print("=" * 60)
        print("This example demonstrates:")
        print("• SQLite configuration (file-based)")
        print("• PostgreSQL configuration (production database)")
        print("• MySQL configuration (alternative production database)")
        print("• Database-specific connection parameters")
        print("• Environment-based database selection")
        print()
        print("Server running at http://localhost:8000")
        print("API documentation available at http://localhost:8000/docs")
        print()
        print("Available endpoints:")
        print("• GET/POST/PUT/DELETE /users")
        print("• GET/POST/PUT/DELETE /products")
        print("• GET/POST/PUT/DELETE /orders")
        print()
        print("Configuration files created:")
        print("• sqlite_config.yaml")
        print("• postgresql_config.yaml")
        print("• mysql_config.yaml")
        print()
        print("Try these example queries:")
        print("  curl http://localhost:8000/users")
        print("  curl http://localhost:8000/products")

    # Create SQLite database and configuration (default)
    db_path = create_sqlite_database()
    config_path = create_sqlite_config(db_path)
    
    # Also create PostgreSQL and MySQL configs for reference
    create_postgresql_config()
    create_mysql_config()
    
    # Create LightAPI instance from YAML configuration
    app = LightApi.from_config(config_path)
    
    _print_usage()
    
    # Run the server
    app.run(host="localhost", port=DEFAULT_PORT, debug=True)