#!/usr/bin/env python3
"""
LightAPI YAML Configuration Example

This example demonstrates how to use YAML configuration files to define API endpoints,
models, and settings without writing Python code for basic CRUD operations.

Features demonstrated:
- YAML-driven API definition
- Automatic endpoint generation
- Model configuration via YAML
- Validation rules in YAML
- Custom settings and middleware configuration
"""

import os
import yaml
from lightapi import LightApi

# Sample YAML configuration
SAMPLE_CONFIG = """
# LightAPI Configuration File
api:
  title: "YAML-Configured API"
  version: "1.0.0"
  description: "API generated from YAML configuration"
  
database:
  url: "sqlite:///./yaml_api.db"

server:
  host: "localhost"
  port: 8000
  debug: true

cors:
  origins:
    - "http://localhost:3000"
    - "http://localhost:8080"

models:
  User:
    table_name: "users"
    fields:
      id:
        type: "Integer"
        primary_key: true
        auto_increment: true
      username:
        type: "String"
        length: 50
        nullable: false
        unique: true
        validation:
          min_length: 3
          max_length: 50
          pattern: "^[a-zA-Z0-9_]+$"
      email:
        type: "String"
        length: 100
        nullable: false
        unique: true
        validation:
          format: "email"
      full_name:
        type: "String"
        length: 200
        nullable: true
      age:
        type: "Integer"
        nullable: true
        validation:
          min: 0
          max: 150
      is_active:
        type: "Boolean"
        default: true
      created_at:
        type: "DateTime"
        default: "now"
    endpoints:
      - method: "GET"
        path: "/users"
        description: "List all users"
        pagination: true
        filtering:
          - "username"
          - "email"
          - "is_active"
        sorting:
          - "username"
          - "created_at"
      - method: "GET"
        path: "/users/{id}"
        description: "Get user by ID"
      - method: "POST"
        path: "/users"
        description: "Create new user"
        validation: true
      - method: "PUT"
        path: "/users/{id}"
        description: "Update user"
        validation: true
      - method: "DELETE"
        path: "/users/{id}"
        description: "Delete user"

  Product:
    table_name: "products"
    fields:
      id:
        type: "Integer"
        primary_key: true
        auto_increment: true
      name:
        type: "String"
        length: 200
        nullable: false
        validation:
          min_length: 2
          max_length: 200
      description:
        type: "Text"
        nullable: true
      price:
        type: "Float"
        nullable: false
        validation:
          min: 0
          max: 1000000
      category:
        type: "String"
        length: 50
        nullable: false
        validation:
          choices:
            - "electronics"
            - "clothing"
            - "books"
            - "home"
            - "sports"
            - "toys"
      in_stock:
        type: "Boolean"
        default: true
      stock_quantity:
        type: "Integer"
        default: 0
        validation:
          min: 0
      created_at:
        type: "DateTime"
        default: "now"
      updated_at:
        type: "DateTime"
        default: "now"
        auto_update: true
    endpoints:
      - method: "GET"
        path: "/products"
        description: "List all products"
        pagination: true
        filtering:
          - "name"
          - "category"
          - "price"
          - "in_stock"
        sorting:
          - "name"
          - "price"
          - "created_at"
        search:
          fields:
            - "name"
            - "description"
      - method: "GET"
        path: "/products/{id}"
        description: "Get product by ID"
      - method: "POST"
        path: "/products"
        description: "Create new product"
        validation: true
      - method: "PUT"
        path: "/products/{id}"
        description: "Update product"
        validation: true
      - method: "DELETE"
        path: "/products/{id}"
        description: "Delete product"

  Order:
    table_name: "orders"
    fields:
      id:
        type: "Integer"
        primary_key: true
        auto_increment: true
      user_id:
        type: "Integer"
        nullable: false
        foreign_key:
          table: "users"
          field: "id"
      product_id:
        type: "Integer"
        nullable: false
        foreign_key:
          table: "products"
          field: "id"
      quantity:
        type: "Integer"
        nullable: false
        validation:
          min: 1
          max: 1000
      total_price:
        type: "Float"
        nullable: false
        validation:
          min: 0
      status:
        type: "String"
        length: 20
        default: "pending"
        validation:
          choices:
            - "pending"
            - "confirmed"
            - "shipped"
            - "delivered"
            - "cancelled"
      order_date:
        type: "DateTime"
        default: "now"
    endpoints:
      - method: "GET"
        path: "/orders"
        description: "List all orders"
        pagination: true
        filtering:
          - "user_id"
          - "product_id"
          - "status"
        sorting:
          - "order_date"
          - "total_price"
      - method: "GET"
        path: "/orders/{id}"
        description: "Get order by ID"
      - method: "POST"
        path: "/orders"
        description: "Create new order"
        validation: true
      - method: "PUT"
        path: "/orders/{id}"
        description: "Update order"
        validation: true
      - method: "DELETE"
        path: "/orders/{id}"
        description: "Delete order"

middleware:
  - name: "cors"
    enabled: true
  - name: "logging"
    enabled: true
    level: "INFO"
  - name: "rate_limiting"
    enabled: false
    requests_per_minute: 100

authentication:
  enabled: false
  type: "jwt"
  secret_key: "your-secret-key"
  token_expiry: 3600

caching:
  enabled: false
  backend: "redis"
  default_ttl: 300
"""

def create_yaml_config_file():
    """Create a sample YAML configuration file"""
    config_path = "api_config.yaml"
    
    if not os.path.exists(config_path):
        with open(config_path, 'w') as f:
            f.write(SAMPLE_CONFIG)
        print(f"✅ Created sample configuration file: {config_path}")
    else:
        print(f"📄 Configuration file already exists: {config_path}")
    
    return config_path

def load_yaml_config(config_path):
    """Load and parse YAML configuration"""
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        print("✅ YAML configuration loaded successfully")
        return config
    except Exception as e:
        print(f"❌ Error loading YAML config: {e}")
        return None

def create_app_from_yaml(config):
    """Create LightAPI app from YAML configuration"""
    if not config:
        return None
    
    # Extract API settings
    api_config = config.get('api', {})
    db_config = config.get('database', {})
    server_config = config.get('server', {})
    cors_config = config.get('cors', {})
    
    # Create LightAPI app
    app = LightApi(
        database_url=db_config.get('url', 'sqlite:///./yaml_api.db'),
        swagger_title=api_config.get('title', 'YAML API'),
        swagger_version=api_config.get('version', '1.0.0'),
        swagger_description=api_config.get('description', 'API from YAML'),
        cors_origins=cors_config.get('origins', [])
    )
    
    print(f"✅ Created LightAPI app: {api_config.get('title')}")
    
    # Note: In a full implementation, you would:
    # 1. Dynamically create SQLAlchemy models from the YAML model definitions
    # 2. Generate RestEndpoint classes with the specified validation rules
    # 3. Register the models with the app
    # 4. Configure middleware based on the YAML settings
    
    # For this demo, we'll show the structure and provide guidance
    models_config = config.get('models', {})
    
    print(f"📊 Models defined in YAML: {len(models_config)}")
    for model_name, model_config in models_config.items():
        print(f"  - {model_name}: {len(model_config.get('fields', {}))} fields, {len(model_config.get('endpoints', []))} endpoints")
    
    return app, config

def demonstrate_yaml_features(config):
    """Demonstrate the features defined in YAML"""
    print("\n🔍 YAML Configuration Analysis")
    print("=" * 50)
    
    # API Configuration
    api_config = config.get('api', {})
    print(f"📋 API Title: {api_config.get('title')}")
    print(f"📋 API Version: {api_config.get('version')}")
    print(f"📋 API Description: {api_config.get('description')}")
    
    # Database Configuration
    db_config = config.get('database', {})
    print(f"🗄️  Database URL: {db_config.get('url')}")
    
    # Server Configuration
    server_config = config.get('server', {})
    print(f"🌐 Server: {server_config.get('host')}:{server_config.get('port')}")
    print(f"🐛 Debug Mode: {server_config.get('debug')}")
    
    # CORS Configuration
    cors_config = config.get('cors', {})
    origins = cors_config.get('origins', [])
    print(f"🔗 CORS Origins: {len(origins)} configured")
    for origin in origins:
        print(f"    - {origin}")
    
    # Models Analysis
    models_config = config.get('models', {})
    print(f"\n📊 Models Configuration ({len(models_config)} models):")
    
    for model_name, model_config in models_config.items():
        print(f"\n  🏷️  {model_name}:")
        print(f"    Table: {model_config.get('table_name')}")
        
        fields = model_config.get('fields', {})
        print(f"    Fields ({len(fields)}):")
        for field_name, field_config in fields.items():
            field_type = field_config.get('type')
            nullable = field_config.get('nullable', True)
            unique = field_config.get('unique', False)
            validation = field_config.get('validation', {})
            
            constraints = []
            if not nullable:
                constraints.append("NOT NULL")
            if unique:
                constraints.append("UNIQUE")
            if field_config.get('primary_key'):
                constraints.append("PRIMARY KEY")
            if validation:
                constraints.append(f"VALIDATION: {list(validation.keys())}")
            
            constraint_str = f" ({', '.join(constraints)})" if constraints else ""
            print(f"      - {field_name}: {field_type}{constraint_str}")
        
        endpoints = model_config.get('endpoints', [])
        print(f"    Endpoints ({len(endpoints)}):")
        for endpoint in endpoints:
            method = endpoint.get('method')
            path = endpoint.get('path')
            description = endpoint.get('description', '')
            features = []
            
            if endpoint.get('pagination'):
                features.append("pagination")
            if endpoint.get('filtering'):
                features.append("filtering")
            if endpoint.get('sorting'):
                features.append("sorting")
            if endpoint.get('search'):
                features.append("search")
            if endpoint.get('validation'):
                features.append("validation")
            
            feature_str = f" [{', '.join(features)}]" if features else ""
            print(f"      - {method} {path}{feature_str}")
            if description:
                print(f"        {description}")
    
    # Middleware Configuration
    middleware_config = config.get('middleware', [])
    print(f"\n🔧 Middleware Configuration ({len(middleware_config)} items):")
    for middleware in middleware_config:
        name = middleware.get('name')
        enabled = middleware.get('enabled', False)
        status = "✅ ENABLED" if enabled else "❌ DISABLED"
        print(f"    - {name}: {status}")
    
    # Authentication Configuration
    auth_config = config.get('authentication', {})
    if auth_config.get('enabled'):
        print(f"\n🔐 Authentication: ✅ ENABLED")
        print(f"    Type: {auth_config.get('type')}")
        print(f"    Token Expiry: {auth_config.get('token_expiry')} seconds")
    else:
        print(f"\n🔐 Authentication: ❌ DISABLED")
    
    # Caching Configuration
    cache_config = config.get('caching', {})
    if cache_config.get('enabled'):
        print(f"\n💾 Caching: ✅ ENABLED")
        print(f"    Backend: {cache_config.get('backend')}")
        print(f"    Default TTL: {cache_config.get('default_ttl')} seconds")
    else:
        print(f"\n💾 Caching: ❌ DISABLED")

def main():
    """Main function to demonstrate YAML configuration"""
    print("🚀 LightAPI YAML Configuration Demo")
    print("=" * 50)
    
    # Create sample YAML config file
    config_path = create_yaml_config_file()
    
    # Load YAML configuration
    config = load_yaml_config(config_path)
    if not config:
        return
    
    # Analyze and demonstrate YAML features
    demonstrate_yaml_features(config)
    
    # Create app from YAML (basic structure)
    app, config = create_app_from_yaml(config)
    if not app:
        return
    
    print(f"\n🎯 Implementation Notes:")
    print("=" * 30)
    print("This demo shows the YAML configuration structure.")
    print("In a full implementation, LightAPI would:")
    print("  1. Parse YAML model definitions")
    print("  2. Generate SQLAlchemy models dynamically")
    print("  3. Create RestEndpoint classes with validation")
    print("  4. Configure middleware and authentication")
    print("  5. Set up caching and other features")
    print()
    print("📄 Configuration file created: api_config.yaml")
    print("📝 Edit this file to customize your API")
    print()
    print("🔧 To extend this demo:")
    print("  1. Implement dynamic model generation")
    print("  2. Add YAML validation schema")
    print("  3. Create endpoint generators")
    print("  4. Add middleware configuration")
    print("  5. Implement hot-reloading of config")

if __name__ == "__main__":
    main()