#!/usr/bin/env python3
"""
YAML Configuration with Environment Variables Example

This example demonstrates how to use environment variables in YAML configuration
for different deployment environments (development, staging, production).

Features demonstrated:
- Environment variable substitution
- Multiple environment configurations
- Database URL from environment
- API metadata from environment
- Deployment-specific settings
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
        full_name = Column(String(100))
        is_active = Column(Boolean, default=True)
        created_at = Column(DateTime, default=func.now())

    class Product(Base):
        __tablename__ = "products"
        id = Column(Integer, primary_key=True)
        name = Column(String(200), nullable=False)
        description = Column(Text)
        price = Column(DECIMAL(10, 2), nullable=False)
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

    def create_sample_database():
        """Create a sample database using SQLAlchemy ORM."""
        # Create temporary database
        db_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        db_path = db_file.name
        db_file.close()
        
        # Create engine and tables using ORM
        engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(engine)
        
        return db_path

    def create_development_config(db_path):
        """Create development environment YAML configuration."""
        config = {
            'database_url': f'sqlite:///{db_path}',
            'tables': [
                {'name': 'users', 'methods': ['GET', 'POST', 'PUT', 'DELETE']},
                {'name': 'products', 'methods': ['GET', 'POST', 'PUT', 'DELETE']},
                {'name': 'orders', 'methods': ['GET', 'POST', 'PUT', 'DELETE']}
            ]
        }
        
        config_path = os.path.join(os.path.dirname(__file__), 'development_config.yaml')
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        return config_path

    def create_staging_config():
        """Create staging environment YAML configuration."""
        config = {
            'database': {
                'url': '${DATABASE_URL}',
                'echo': False,
                'pool_size': 5,
                'max_overflow': 10,
                'pool_pre_ping': True,
                'pool_recycle': 3600
            },
            'swagger': {
                'title': '${API_TITLE}',
                'version': '${API_VERSION}',
                'description': 'Staging environment API',
                'enabled': True
            },
            'server': {
                'host': '${SERVER_HOST}',
                'port': '${SERVER_PORT}',
                'debug': False
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
        
        config_path = os.path.join(os.path.dirname(__file__), 'staging_config.yaml')
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        return config_path

    def create_production_config():
        """Create production environment YAML configuration."""
        config = {
            'database': {
                'url': '${DATABASE_URL}',
                'echo': False,
                'pool_size': 20,
                'max_overflow': 30,
                'pool_pre_ping': True,
                'pool_recycle': 3600,
                'pool_timeout': 30
            },
            'swagger': {
                'title': '${API_TITLE}',
                'version': '${API_VERSION}',
                'description': 'Production API',
                'enabled': True
            },
            'server': {
                'host': '${SERVER_HOST}',
                'port': '${SERVER_PORT}',
                'debug': False
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
        
        config_path = os.path.join(os.path.dirname(__file__), 'production_config.yaml')
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        return config_path

    def _print_usage():
        """Print usage instructions."""
        print("🚀 YAML Configuration with Environment Variables")
        print("=" * 60)
        print("This example demonstrates:")
        print("• Environment variable substitution")
        print("• Multiple environment configurations")
        print("• Database URL from environment")
        print("• API metadata from environment")
        print("• Deployment-specific settings")
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
        print("• development_config.yaml")
        print("• staging_config.yaml")
        print("• production_config.yaml")
        print()
        print("Environment variables for staging/production:")
        print("  export DATABASE_URL='postgresql://user:pass@host:port/db'")
        print("  export API_TITLE='My Production API'")
        print("  export API_VERSION='1.0.0'")
        print("  export SERVER_HOST='0.0.0.0'")
        print("  export SERVER_PORT='8000'")
        print()
        print("Try these example queries:")
        print("  curl http://localhost:8000/users")
        print("  curl http://localhost:8000/products")

    # Create database and development configuration (default)
    db_path = create_sample_database()
    config_path = create_development_config(db_path)
    
    # Also create staging and production configs for reference
    create_staging_config()
    create_production_config()
    
    # Create LightAPI instance from YAML configuration
    app = LightApi.from_config(config_path)
    
    _print_usage()
    
    # Run the server
    app.run(host="localhost", port=DEFAULT_PORT, debug=True)