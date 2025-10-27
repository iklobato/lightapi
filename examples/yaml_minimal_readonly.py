#!/usr/bin/env python3
"""
YAML Configuration - Minimal and Read-Only Examples

This example demonstrates two important YAML configuration patterns:
1. Minimal configuration - essential operations only
2. Read-only configuration - data viewing APIs

Features demonstrated:
- Minimal CRUD operations
- Read-only APIs for data viewing
- Lightweight configurations
- Analytics and reporting APIs
- Public data access patterns
"""

import os
import tempfile
import yaml
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
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

    class Post(Base):
        __tablename__ = "posts"
        id = Column(Integer, primary_key=True)
        title = Column(String(200), nullable=False)
        content = Column(Text)
        author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
        is_published = Column(Boolean, default=False)
        created_at = Column(DateTime, default=func.now())
        updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    class Comment(Base):
        __tablename__ = "comments"
        id = Column(Integer, primary_key=True)
        post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
        author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
        content = Column(Text, nullable=False)
        is_approved = Column(Boolean, default=False)
        created_at = Column(DateTime, default=func.now())

    class Analytics(Base):
        __tablename__ = "analytics"
        id = Column(Integer, primary_key=True)
        page_views = Column(Integer, default=0)
        unique_visitors = Column(Integer, default=0)
        date = Column(DateTime, default=func.now())
        page_url = Column(String(500))

    def create_blog_database():
        """Create a simple blog database using SQLAlchemy ORM."""
        # Create temporary database
        db_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        db_path = db_file.name
        db_file.close()
        
        # Create engine and tables using ORM
        engine = create_engine(f"sqlite:///{db_path}")
        Base.metadata.create_all(engine)
        
        return db_path

    def create_minimal_config(db_path):
        """Create minimal YAML configuration."""
        config = {
            'database_url': f'sqlite:///{db_path}',
            'tables': [
                {'name': 'users', 'methods': ['GET', 'POST']},
                {'name': 'posts', 'methods': ['GET', 'POST']}
            ]
        }
        
        config_path = os.path.join(os.path.dirname(__file__), 'minimal_config.yaml')
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        return config_path

    def create_readonly_config(db_path):
        """Create read-only YAML configuration."""
        config = {
            'database': {
                'url': f'sqlite:///{db_path}',
                'echo': False
            },
            'swagger': {
                'title': 'Read-Only Analytics API',
                'version': '1.0.0',
                'description': 'Read-only data viewing API',
                'enabled': True
            },
            'endpoints': {
                'users': {
                    'table': 'users',
                    'methods': ['GET'],
                    'description': 'User data (read-only)'
                },
                'posts': {
                    'table': 'posts',
                    'methods': ['GET'],
                    'description': 'Post data (read-only)'
                },
                'comments': {
                    'table': 'comments',
                    'methods': ['GET'],
                    'description': 'Comment data (read-only)'
                },
                'analytics': {
                    'table': 'analytics',
                    'methods': ['GET'],
                    'description': 'Analytics data (read-only)'
                }
            }
        }
        
        config_path = os.path.join(os.path.dirname(__file__), 'readonly_config.yaml')
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        return config_path

    def _print_usage():
        """Print usage instructions."""
        print("🚀 YAML Configuration - Minimal and Read-Only Examples")
        print("=" * 60)
        print("This example demonstrates:")
        print("• Minimal configuration - essential operations only")
        print("• Read-only configuration - data viewing APIs")
        print("• Lightweight configurations")
        print("• Analytics and reporting APIs")
        print("• Public data access patterns")
        print()
        print("Server running at http://localhost:8000")
        print("API documentation available at http://localhost:8000/docs")
        print()
        print("Available endpoints:")
        print("• GET/POST /users (minimal)")
        print("• GET/POST /posts (minimal)")
        print("• GET /comments (read-only)")
        print("• GET /analytics (read-only)")
        print()
        print("Configuration files created:")
        print("• minimal_config.yaml")
        print("• readonly_config.yaml")
        print()
        print("Try these example queries:")
        print("  curl http://localhost:8000/users")
        print("  curl http://localhost:8000/posts")
        print("  curl http://localhost:8000/analytics")

    # Create database and configurations
    db_path = create_blog_database()
    config_path = create_minimal_config(db_path)
    
    # Also create readonly config for reference
    create_readonly_config(db_path)
    
    # Create LightAPI instance from YAML configuration
    app = LightApi.from_config(config_path)
    
    _print_usage()
    
    # Run the server
    app.run(host="localhost", port=DEFAULT_PORT, debug=True)