#!/usr/bin/env python3
"""
Basic YAML Configuration Example

This example demonstrates the simplest way to create a REST API using YAML configuration.
Perfect for getting started with LightAPI's YAML system.

Features demonstrated:
- Basic YAML structure
- Simple database connection
- Full CRUD operations
- Swagger documentation
"""

import os
import tempfile
import yaml
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
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
        name = Column(String(100), nullable=False)
        email = Column(String(100), unique=True, nullable=False)
        created_at = Column(DateTime, default=func.now())

    class Post(Base):
        __tablename__ = "posts"
        id = Column(Integer, primary_key=True)
        title = Column(String(200), nullable=False)
        content = Column(Text)
        user_id = Column(Integer, ForeignKey("users.id"))
        created_at = Column(DateTime, default=func.now())

    def create_basic_database():
        """Create a simple database using SQLAlchemy ORM."""
        # Create temporary database
        db_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        db_path = db_file.name
        db_file.close()
        
        # Create engine and tables using ORM
        engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(engine)
        
        return db_path

    def create_yaml_config(db_path):
        """Create basic YAML configuration file."""
        config = {
            'database_url': f'sqlite:///{db_path}',
            'tables': [
                {'name': 'users', 'methods': ['GET', 'POST', 'PUT', 'DELETE']},
                {'name': 'posts', 'methods': ['GET', 'POST', 'PUT', 'DELETE']}
            ]
        }
        
        config_path = os.path.join(os.path.dirname(__file__), 'basic_config.yaml')
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        return config_path

    def _print_usage():
        """Print usage instructions."""
        print("🚀 Basic YAML Configuration Example")
        print("=" * 50)
        print("This example demonstrates:")
        print("• Basic YAML structure")
        print("• Simple database connection")
        print("• Full CRUD operations")
        print("• Swagger documentation")
        print()
        print("Server running at http://localhost:8000")
        print("API documentation available at http://localhost:8000/docs")
        print()
        print("Available endpoints:")
        print("• GET/POST/PUT/DELETE /users")
        print("• GET/POST/PUT/DELETE /posts")
        print()
        print("Try these example queries:")
        print("  curl http://localhost:8000/users")
        print("  curl http://localhost:8000/posts")

    # Create database and configuration
    db_path = create_basic_database()
    config_path = create_yaml_config(db_path)
    
    # Create LightAPI instance from YAML configuration
    app = LightApi.from_config(config_path)
    
    _print_usage()
    
    # Run the server
    app.run(host="localhost", port=DEFAULT_PORT, debug=True)