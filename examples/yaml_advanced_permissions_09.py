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
import sqlite3
import tempfile
from lightapi import LightApi

def create_advanced_database():
    """Create a complex database with multiple tables and relationships"""
    
    # Create temporary database
    db_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    db_path = db_file.name
    db_file.close()
    
    # Connect and create tables
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Users table - full admin access
    cursor.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(50) NOT NULL UNIQUE,
            email VARCHAR(100) NOT NULL UNIQUE,
            full_name VARCHAR(100),
            role VARCHAR(20) DEFAULT 'user',
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Products table - full CRUD for inventory management
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
    
    # Categories table - limited operations (no delete to preserve data integrity)
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
    
    # Orders table - create and status updates only
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
    
    # Order items table - read-only (managed through orders)
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
    
    # Audit log table - read-only for security
    cursor.execute('''
        CREATE TABLE audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_name VARCHAR(50) NOT NULL,
            record_id INTEGER NOT NULL,
            action VARCHAR(20) NOT NULL,
            user_id INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            old_values TEXT,
            new_values TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # System settings table - read-only for most users
    cursor.execute('''
        CREATE TABLE system_settings (
            key VARCHAR(100) PRIMARY KEY,
            value TEXT,
            description TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_by INTEGER,
            FOREIGN KEY (updated_by) REFERENCES users(id)
        )
    ''')
    
    # Insert sample data
    sample_data = [
        # Users
        "INSERT INTO users (username, email, full_name, role) VALUES ('admin', 'admin@company.com', 'System Administrator', 'admin')",
        "INSERT INTO users (username, email, full_name, role) VALUES ('manager', 'manager@company.com', 'Store Manager', 'manager')",
        "INSERT INTO users (username, email, full_name, role) VALUES ('customer1', 'customer1@example.com', 'John Customer', 'customer')",
        
        # Categories
        "INSERT INTO categories (name, description) VALUES ('Electronics', 'Electronic devices and gadgets')",
        "INSERT INTO categories (name, description) VALUES ('Books', 'Books and literature')",
        "INSERT INTO categories (name, description) VALUES ('Clothing', 'Apparel and accessories')",
        
        # Products
        "INSERT INTO products (name, description, price, category_id, sku, stock_quantity) VALUES ('Laptop Pro', 'High-performance laptop', 1299.99, 1, 'ELEC001', 15)",
        "INSERT INTO products (name, description, price, category_id, sku, stock_quantity) VALUES ('Python Guide', 'Complete Python programming guide', 39.99, 2, 'BOOK001', 50)",
        "INSERT INTO products (name, description, price, category_id, sku, stock_quantity) VALUES ('Cotton T-Shirt', 'Premium cotton t-shirt', 24.99, 3, 'CLOTH001', 100)",
        
        # Orders
        "INSERT INTO orders (user_id, total_amount, status, shipping_address) VALUES (3, 1299.99, 'pending', '123 Main St, City, State')",
        "INSERT INTO orders (user_id, total_amount, status, shipping_address) VALUES (3, 64.98, 'shipped', '456 Oak Ave, Town, State')",
        
        # Order items
        "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (1, 1, 1, 1299.99)",
        "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (2, 2, 1, 39.99)",
        "INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES (2, 3, 1, 24.99)",
        
        # Audit log
        "INSERT INTO audit_log (table_name, record_id, action, user_id, new_values) VALUES ('orders', 1, 'CREATE', 3, '{\"total_amount\": 1299.99, \"status\": \"pending\"}')",
        "INSERT INTO audit_log (table_name, record_id, action, user_id, old_values, new_values) VALUES ('orders', 2, 'UPDATE', 2, '{\"status\": \"pending\"}', '{\"status\": \"shipped\"}')",
        
        # System settings
        "INSERT INTO system_settings (key, value, description, updated_by) VALUES ('max_order_amount', '5000.00', 'Maximum order amount allowed', 1)",
        "INSERT INTO system_settings (key, value, description, updated_by) VALUES ('tax_rate', '0.08', 'Default tax rate percentage', 1)",
        "INSERT INTO system_settings (key, value, description, updated_by) VALUES ('shipping_cost', '9.99', 'Standard shipping cost', 1)",
    ]
    
    for query in sample_data:
        cursor.execute(query)
    
    conn.commit()
    conn.close()
    
    return db_path

def create_advanced_yaml_config(db_path):
    """Create an advanced YAML configuration with role-based permissions"""
    
    yaml_content = f"""# Advanced YAML Configuration - Role-Based Permissions
# This configuration demonstrates different permission levels for different tables
# Simulating a real-world e-commerce application with various user roles

# Database connection
database_url: "sqlite:///{db_path}"

# API documentation
swagger_title: "E-commerce Management API"
swagger_version: "2.0.0"
swagger_description: |
  Advanced e-commerce API with role-based permissions
  
  ## Permission Levels
  - **Admin**: Full access to users and system settings
  - **Manager**: Full product and category management, order status updates
  - **Customer**: Order creation, read-only access to products
  - **Public**: Read-only access to products and categories
  
  ## Security Notes
  - Audit logs are read-only for security
  - System settings require admin privileges
  - Order items are managed through orders (read-only direct access)
enable_swagger: true

# Tables with different permission levels
tables:
  # ADMIN LEVEL - Full CRUD access
  - name: users
    crud:
      - get     # List and view users
      - post    # Create new users
      - put     # Update user information
      - patch   # Partial updates (e.g., status changes)
      - delete  # Remove users (admin only)
  
  # MANAGER LEVEL - Full inventory management
  - name: products
    crud:
      - get     # Browse product catalog
      - post    # Add new products
      - put     # Update product details
      - patch   # Quick updates (price, stock)
      - delete  # Remove discontinued products
  
  # MANAGER LEVEL - Category management (no delete for data integrity)
  - name: categories
    crud:
      - get     # Browse categories
      - post    # Create new categories
      - put     # Update category information
      - patch   # Quick updates
      # Note: No delete to preserve product relationships
  
  # CUSTOMER/MANAGER LEVEL - Order management
  - name: orders
    crud:
      - get     # View orders
      - post    # Create new orders
      - patch   # Update order status only
      # Note: No PUT (full update) or DELETE for order integrity
  
  # READ-ONLY - Order items (managed through orders)
  - name: order_items
    crud:
      - get     # View order details only
      # Note: Order items are created/updated through order management
  
  # READ-ONLY - Security audit trail
  - name: audit_log
    crud:
      - get     # View audit trail only
      # Note: Audit logs are system-generated, no manual modifications
  
  # ADMIN READ-ONLY - System configuration
  - name: system_settings
    crud:
      - get     # View system settings
      # Note: Settings updates should go through admin interface
"""
    
    config_path = '/workspace/project/lightapi/examples/advanced_permissions_config.yaml'
    with open(config_path, 'w') as f:
        f.write(yaml_content)
    
    return config_path

def run_advanced_example():
    """Run the advanced YAML configuration example"""
    
    print("🚀 LightAPI Advanced YAML Configuration - Role-Based Permissions")
    print("=" * 70)
    
    # Step 1: Create complex database
    print("\n📊 Step 1: Creating complex database with relationships...")
    db_path = create_advanced_database()
    print(f"✅ Database created: {db_path}")
    print("   Tables: users, products, categories, orders, order_items, audit_log, system_settings")
    
    # Step 2: Create advanced YAML configuration
    print("\n📝 Step 2: Creating advanced YAML configuration...")
    config_path = create_advanced_yaml_config(db_path)
    print(f"✅ Configuration created: {config_path}")
    
    # Step 3: Show configuration content (first part)
    print("\n📋 Step 3: YAML Configuration Structure:")
    with open(config_path, 'r') as f:
        config_content = f.read()
    
    # Show key parts of the configuration
    lines = config_content.split('\n')
    print("```yaml")
    print("# Database and API settings")
    for line in lines[:15]:
        print(line)
    print("\n# ... (documentation section) ...\n")
    print("# Tables with role-based permissions:")
    
    in_tables_section = False
    for line in lines:
        if line.strip().startswith('tables:'):
            in_tables_section = True
        if in_tables_section:
            if line.strip().startswith('- name:') or line.strip().startswith('crud:') or line.strip().startswith('- get'):
                print(line)
    print("```")
    
    # Step 4: Create API from YAML
    print("\n🔧 Step 4: Creating API from advanced configuration...")
    app = LightApi.from_config(config_path)
    print(f"✅ API created successfully!")
    print(f"📊 Routes registered: {len(app.aiohttp_routes)}")
    
    # Step 5: Show permission levels
    print("\n🔐 Step 5: Permission Levels by Table:")
    
    permission_levels = {
        'users': 'ADMIN - Full CRUD (create, read, update, delete)',
        'products': 'MANAGER - Full inventory management',
        'categories': 'MANAGER - No delete (data integrity)',
        'orders': 'CUSTOMER/MANAGER - Create and status updates only',
        'order_items': 'READ-ONLY - Managed through orders',
        'audit_log': 'READ-ONLY - Security audit trail',
        'system_settings': 'ADMIN READ-ONLY - System configuration'
    }
    
    for table, permission in permission_levels.items():
        print(f"  🔒 {table}: {permission}")
    
    # Step 6: Show generated endpoints by permission level
    print("\n🔗 Step 6: Generated Endpoints by Permission Level:")
    
    routes_by_table = {}
    for route in app.aiohttp_routes:
        path_parts = route.path.strip('/').split('/')
        table_name = path_parts[0] if path_parts else 'unknown'
        
        if table_name not in routes_by_table:
            routes_by_table[table_name] = []
        
        routes_by_table[table_name].append(f"{route.method} {route.path}")
    
    # Group by permission level
    admin_tables = ['users']
    manager_tables = ['products', 'categories', 'orders']
    readonly_tables = ['order_items', 'audit_log', 'system_settings']
    
    print("\n  🔴 ADMIN LEVEL:")
    for table in admin_tables:
        if table in routes_by_table:
            print(f"    📁 {table.title()}:")
            for route in routes_by_table[table]:
                print(f"      • {route}")
    
    print("\n  🟡 MANAGER LEVEL:")
    for table in manager_tables:
        if table in routes_by_table:
            print(f"    📁 {table.title()}:")
            for route in routes_by_table[table]:
                print(f"      • {route}")
    
    print("\n  🟢 READ-ONLY LEVEL:")
    for table in readonly_tables:
        if table in routes_by_table:
            print(f"    📁 {table.title()}:")
            for route in routes_by_table[table]:
                print(f"      • {route}")
    
    # Step 7: Usage examples by role
    print("\n🎭 Step 7: Usage Examples by Role:")
    
    print("\n  👑 ADMIN Operations:")
    print("  ```bash")
    print("  # Manage users")
    print("  curl http://localhost:8000/users/")
    print("  curl -X POST http://localhost:8000/users/ \\")
    print("    -H 'Content-Type: application/json' \\")
    print("    -d '{\"username\": \"newuser\", \"email\": \"new@company.com\", \"role\": \"manager\"}'")
    print("  curl -X DELETE http://localhost:8000/users/4")
    print("  ```")
    
    print("\n  👔 MANAGER Operations:")
    print("  ```bash")
    print("  # Manage products")
    print("  curl -X POST http://localhost:8000/products/ \\")
    print("    -H 'Content-Type: application/json' \\")
    print("    -d '{\"name\": \"New Product\", \"price\": 99.99, \"category_id\": 1}'")
    print("  ")
    print("  # Update order status")
    print("  curl -X PATCH http://localhost:8000/orders/1 \\")
    print("    -H 'Content-Type: application/json' \\")
    print("    -d '{\"status\": \"shipped\"}'")
    print("  ```")
    
    print("\n  👤 CUSTOMER Operations:")
    print("  ```bash")
    print("  # Browse products")
    print("  curl http://localhost:8000/products/")
    print("  ")
    print("  # Create order")
    print("  curl -X POST http://localhost:8000/orders/ \\")
    print("    -H 'Content-Type: application/json' \\")
    print("    -d '{\"user_id\": 3, \"total_amount\": 129.99, \"shipping_address\": \"123 Home St\"}'")
    print("  ```")
    
    print("\n  📊 AUDIT/MONITORING:")
    print("  ```bash")
    print("  # View audit trail")
    print("  curl http://localhost:8000/audit_log/")
    print("  ")
    print("  # Check system settings")
    print("  curl http://localhost:8000/system_settings/")
    print("  ```")
    
    # Step 8: Security considerations
    print("\n🛡️  Step 8: Security Considerations:")
    print("  ✅ Audit logs are read-only (tamper-proof)")
    print("  ✅ Order items managed through orders (data integrity)")
    print("  ✅ Categories cannot be deleted (preserve relationships)")
    print("  ✅ System settings are read-only via API")
    print("  ✅ Orders cannot be fully updated or deleted (compliance)")
    print("  ⚠️  Add authentication middleware for production use")
    print("  ⚠️  Implement role-based access control in middleware")
    
    print("\n📚 Key Features Demonstrated:")
    print("  ✅ Role-based CRUD permissions")
    print("  ✅ Data integrity constraints")
    print("  ✅ Audit trail implementation")
    print("  ✅ Complex database relationships")
    print("  ✅ Security-conscious design")
    print("  ✅ Production-ready structure")
    
    return app, config_path, db_path

if __name__ == "__main__":
    app, config_path, db_path = run_advanced_example()
    
    print(f"\n🚀 Ready to run advanced API! Execute:")
    print(f"python -c \"from lightapi import LightApi; LightApi.from_config('{config_path}').run()\"")
    
    print(f"\n📖 Visit http://localhost:8000/docs for interactive documentation")
    
    # Cleanup note
    print(f"\n🧹 Cleanup files:")
    print(f"  • Database: {db_path}")
    print(f"  • Config: {config_path}")