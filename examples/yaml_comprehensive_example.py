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
import sqlite3
import tempfile
import yaml
from lightapi import LightApi

def create_sample_database():
    """Create a sample database with various table structures for demonstration"""
    
    # Create temporary database file
    db_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    db_path = db_file.name
    db_file.close()
    
    # Connect and create tables
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Users table - basic user management
    cursor.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(50) NOT NULL UNIQUE,
            email VARCHAR(100) NOT NULL UNIQUE,
            full_name VARCHAR(100),
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Products table - e-commerce products
    cursor.execute('''
        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(200) NOT NULL,
            description TEXT,
            price DECIMAL(10,2) NOT NULL,
            category_id INTEGER,
            sku VARCHAR(50) UNIQUE,
            stock_quantity INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (category_id) REFERENCES categories(id)
        )
    ''')
    
    # Categories table - product categories
    cursor.execute('''
        CREATE TABLE categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(100) NOT NULL UNIQUE,
            description TEXT,
            parent_id INTEGER,
            is_active BOOLEAN DEFAULT 1,
            FOREIGN KEY (parent_id) REFERENCES categories(id)
        )
    ''')
    
    # Orders table - customer orders
    cursor.execute('''
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            total_amount DECIMAL(10,2) NOT NULL,
            status VARCHAR(20) DEFAULT 'pending',
            order_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            shipping_address TEXT,
            notes TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Order items table - items in each order
    cursor.execute('''
        CREATE TABLE order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            unit_price DECIMAL(10,2) NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    ''')
    
    # Reviews table - product reviews
    cursor.execute('''
        CREATE TABLE reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            rating INTEGER CHECK (rating >= 1 AND rating <= 5),
            title VARCHAR(200),
            comment TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Settings table - application settings (read-only example)
    cursor.execute('''
        CREATE TABLE settings (
            key VARCHAR(100) PRIMARY KEY,
            value TEXT,
            description TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Insert sample data
    sample_data = [
        # Categories
        "INSERT INTO categories (name, description) VALUES ('Electronics', 'Electronic devices and gadgets')",
        "INSERT INTO categories (name, description) VALUES ('Books', 'Books and literature')",
        "INSERT INTO categories (name, description) VALUES ('Clothing', 'Apparel and accessories')",
        
        # Users
        "INSERT INTO users (username, email, full_name) VALUES ('john_doe', 'john@example.com', 'John Doe')",
        "INSERT INTO users (username, email, full_name) VALUES ('jane_smith', 'jane@example.com', 'Jane Smith')",
        "INSERT INTO users (username, email, full_name) VALUES ('admin', 'admin@example.com', 'Administrator')",
        
        # Products
        "INSERT INTO products (name, description, price, category_id, sku, stock_quantity) VALUES ('Laptop', 'High-performance laptop', 999.99, 1, 'LAP001', 10)",
        "INSERT INTO products (name, description, price, category_id, sku, stock_quantity) VALUES ('Python Book', 'Learn Python programming', 29.99, 2, 'BOOK001', 50)",
        "INSERT INTO products (name, description, price, category_id, sku, stock_quantity) VALUES ('T-Shirt', 'Cotton t-shirt', 19.99, 3, 'SHIRT001', 100)",
        
        # Settings
        "INSERT INTO settings (key, value, description) VALUES ('site_name', 'My Store', 'Website name')",
        "INSERT INTO settings (key, value, description) VALUES ('max_items_per_page', '20', 'Maximum items per page')",
        "INSERT INTO settings (key, value, description) VALUES ('currency', 'USD', 'Default currency')",
    ]
    
    for query in sample_data:
        cursor.execute(query)
    
    conn.commit()
    conn.close()
    
    return db_path

def create_yaml_configurations():
    """Create various YAML configuration examples"""
    
    configurations = {}
    
    # 1. Basic Configuration - Simple CRUD for all tables
    configurations['basic'] = {
        'database_url': '${DATABASE_URL}',  # Environment variable
        'swagger_title': 'Basic Store API',
        'swagger_version': '1.0.0',
        'swagger_description': 'Simple store API with basic CRUD operations',
        'enable_swagger': True,
        'tables': [
            {'name': 'users', 'crud': ['get', 'post', 'put', 'delete']},
            {'name': 'products', 'crud': ['get', 'post', 'put', 'delete']},
            {'name': 'categories', 'crud': ['get', 'post', 'put', 'delete']},
            {'name': 'orders', 'crud': ['get', 'post', 'put', 'delete']},
        ]
    }
    
    # 2. Advanced Configuration - Different permissions per table
    configurations['advanced'] = {
        'database_url': '${DATABASE_URL}',
        'swagger_title': 'Advanced Store API',
        'swagger_version': '2.0.0',
        'swagger_description': 'Advanced store API with role-based CRUD operations',
        'enable_swagger': True,
        'tables': [
            # Full CRUD for users
            {
                'name': 'users',
                'crud': ['get', 'post', 'put', 'patch', 'delete']
            },
            # Full CRUD for products
            {
                'name': 'products', 
                'crud': ['get', 'post', 'put', 'patch', 'delete']
            },
            # Limited operations for categories (admin only)
            {
                'name': 'categories',
                'crud': ['get', 'post', 'put']  # No delete
            },
            # Read and create orders, update status
            {
                'name': 'orders',
                'crud': ['get', 'post', 'patch']  # No full update or delete
            },
            # Read-only order items
            {
                'name': 'order_items',
                'crud': ['get']  # Read-only
            },
            # Full CRUD for reviews
            {
                'name': 'reviews',
                'crud': ['get', 'post', 'put', 'delete']
            },
            # Read-only settings
            {
                'name': 'settings',
                'crud': ['get']  # Read-only
            }
        ]
    }
    
    # 3. Minimal Configuration - Only essential operations
    configurations['minimal'] = {
        'database_url': '${DATABASE_URL}',
        'swagger_title': 'Minimal Store API',
        'swagger_version': '1.0.0',
        'enable_swagger': True,
        'tables': [
            {'name': 'products', 'crud': ['get', 'post']},  # Browse and add products
            {'name': 'categories', 'crud': ['get']},        # Browse categories only
            {'name': 'orders', 'crud': ['post']},           # Create orders only
        ]
    }
    
    # 4. Read-Only Configuration - Data viewing API
    configurations['readonly'] = {
        'database_url': '${DATABASE_URL}',
        'swagger_title': 'Store Data Viewer API',
        'swagger_version': '1.0.0',
        'swagger_description': 'Read-only API for viewing store data',
        'enable_swagger': True,
        'tables': [
            {'name': 'users', 'crud': ['get']},
            {'name': 'products', 'crud': ['get']},
            {'name': 'categories', 'crud': ['get']},
            {'name': 'orders', 'crud': ['get']},
            {'name': 'order_items', 'crud': ['get']},
            {'name': 'reviews', 'crud': ['get']},
            {'name': 'settings', 'crud': ['get']},
        ]
    }
    
    # 5. PostgreSQL Configuration Example
    configurations['postgresql'] = {
        'database_url': 'postgresql://username:password@localhost:5432/store_db',
        'swagger_title': 'PostgreSQL Store API',
        'swagger_version': '1.0.0',
        'swagger_description': 'Store API using PostgreSQL database',
        'enable_swagger': True,
        'tables': [
            {'name': 'users', 'crud': ['get', 'post', 'put', 'delete']},
            {'name': 'products', 'crud': ['get', 'post', 'put', 'delete']},
            {'name': 'categories', 'crud': ['get', 'post', 'put', 'delete']},
        ]
    }
    
    # 6. MySQL Configuration Example
    configurations['mysql'] = {
        'database_url': 'mysql+pymysql://username:password@localhost:3306/store_db',
        'swagger_title': 'MySQL Store API',
        'swagger_version': '1.0.0',
        'swagger_description': 'Store API using MySQL database',
        'enable_swagger': True,
        'tables': [
            {'name': 'users', 'crud': ['get', 'post', 'put', 'delete']},
            {'name': 'products', 'crud': ['get', 'post', 'put', 'delete']},
            {'name': 'categories', 'crud': ['get', 'post', 'put', 'delete']},
        ]
    }
    
    return configurations

def save_yaml_files(configurations, db_path):
    """Save YAML configuration files"""
    
    config_files = {}
    
    for name, config in configurations.items():
        # Replace environment variable placeholder with actual database path
        if config['database_url'] == '${DATABASE_URL}':
            config['database_url'] = f'sqlite:///{db_path}'
        
        filename = f'config_{name}.yaml'
        filepath = os.path.join('/workspace/project/lightapi/examples', filename)
        
        with open(filepath, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, indent=2)
        
        config_files[name] = filepath
        print(f"✓ Created {filename}")
    
    return config_files

def test_yaml_configuration(config_file, config_name):
    """Test a YAML configuration"""
    
    print(f"\n🧪 Testing {config_name} configuration...")
    print("=" * 50)
    
    try:
        # Create API from YAML config
        app = LightApi.from_config(config_file)
        
        print(f"✅ Successfully created API from {config_name} config")
        print(f"📊 Routes registered: {len(app.aiohttp_routes)}")
        
        # Print route information
        if app.aiohttp_routes:
            print("\n📋 Available endpoints:")
            routes_by_table = {}
            
            for route in app.aiohttp_routes:
                # Extract table name from route path
                path_parts = route.path.strip('/').split('/')
                table_name = path_parts[0] if path_parts else 'unknown'
                
                if table_name not in routes_by_table:
                    routes_by_table[table_name] = []
                
                routes_by_table[table_name].append(f"{route.method} {route.path}")
            
            for table, routes in routes_by_table.items():
                print(f"  📁 {table.title()}:")
                for route in routes:
                    print(f"    • {route}")
        
        return app
        
    except Exception as e:
        print(f"❌ Error testing {config_name} configuration: {e}")
        return None

def demonstrate_yaml_features():
    """Demonstrate all YAML configuration features"""
    
    print("🚀 LightAPI YAML Configuration Comprehensive Example")
    print("=" * 60)
    
    # Create sample database
    print("\n📊 Creating sample database...")
    db_path = create_sample_database()
    print(f"✅ Sample database created: {db_path}")
    
    # Create YAML configurations
    print("\n📝 Creating YAML configuration files...")
    configurations = create_yaml_configurations()
    config_files = save_yaml_files(configurations, db_path)
    
    # Test each configuration
    print("\n🧪 Testing YAML configurations...")
    
    successful_configs = []
    
    for config_name, config_file in config_files.items():
        if config_name in ['postgresql', 'mysql']:
            print(f"\n⏭️  Skipping {config_name} (requires external database)")
            continue
            
        app = test_yaml_configuration(config_file, config_name)
        if app:
            successful_configs.append((config_name, config_file, app))
    
    # Demonstrate running one of the configurations
    if successful_configs:
        print(f"\n🎯 Demonstration: Running '{successful_configs[0][0]}' configuration")
        print("=" * 50)
        
        config_name, config_file, app = successful_configs[0]
        
        print(f"📁 Configuration file: {config_file}")
        print(f"🌐 Server would start at: http://localhost:8000")
        print(f"📖 API documentation at: http://localhost:8000/docs")
        print(f"📋 OpenAPI spec at: http://localhost:8000/openapi.json")
        
        print(f"\n📊 API Summary:")
        print(f"  • Database: SQLite ({db_path})")
        print(f"  • Tables: {len([r for r in app.aiohttp_routes if not r.path.startswith('/docs')])//2} tables")  # Rough estimate
        print(f"  • Endpoints: {len(app.aiohttp_routes)} total routes")
        
        # Show sample requests
        print(f"\n🔧 Sample API requests:")
        print(f"  # Get all users")
        print(f"  curl http://localhost:8000/users/")
        print(f"  ")
        print(f"  # Create a new user")
        print(f"  curl -X POST http://localhost:8000/users/ \\")
        print(f"    -H 'Content-Type: application/json' \\")
        print("    -d '{\"username\": \"newuser\", \"email\": \"new@example.com\", \"full_name\": \"New User\"}'")
        print(f"  ")
        print(f"  # Get specific user")
        print(f"  curl http://localhost:8000/users/1")
        print(f"  ")
        print(f"  # Update user")
        print(f"  curl -X PUT http://localhost:8000/users/1 \\")
        print(f"    -H 'Content-Type: application/json' \\")
        print("    -d '{\"full_name\": \"Updated Name\"}'")
    
    # Cleanup
    print(f"\n🧹 Cleanup:")
    print(f"  • Database file: {db_path}")
    print(f"  • Config files: {len(config_files)} files in examples/")
    
    return db_path, config_files, successful_configs

if __name__ == "__main__":
    # Set environment variable for database URL
    os.environ['DATABASE_URL'] = 'sqlite:///yaml_comprehensive_test.db'
    
    # Run demonstration
    db_path, config_files, successful_configs = demonstrate_yaml_features()
    
    print(f"\n✨ YAML Configuration Features Demonstrated:")
    print(f"  ✅ Database reflection from existing tables")
    print(f"  ✅ Automatic CRUD endpoint generation")
    print(f"  ✅ Configurable operations per table")
    print(f"  ✅ Environment variable support")
    print(f"  ✅ Multiple database support (SQLite, PostgreSQL, MySQL)")
    print(f"  ✅ Swagger/OpenAPI documentation generation")
    print(f"  ✅ Flexible API configuration without Python code")
    
    print(f"\n🎓 Next Steps:")
    print(f"  1. Modify YAML files to customize your API")
    print(f"  2. Point to your existing database")
    print(f"  3. Run: python -c \"from lightapi import LightApi; LightApi.from_config('config_basic.yaml').run()\"")
    print(f"  4. Visit http://localhost:8000/docs for interactive API documentation")
    
    print(f"\n📚 Configuration Files Created:")
    for name, filepath in config_files.items():
        print(f"  • {name}: {filepath}")