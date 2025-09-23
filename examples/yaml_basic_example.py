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
import sqlite3
import tempfile
from lightapi import LightApi

def create_basic_database():
    """Create a simple database for the basic example"""
    
    # Create temporary database
    db_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    db_path = db_file.name
    db_file.close()
    
    # Connect and create tables
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Simple users table
    cursor.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(100) NOT NULL,
            email VARCHAR(100) NOT NULL UNIQUE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Simple posts table
    cursor.execute('''
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title VARCHAR(200) NOT NULL,
            content TEXT,
            user_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Insert sample data
    cursor.execute("INSERT INTO users (name, email) VALUES ('John Doe', 'john@example.com')")
    cursor.execute("INSERT INTO users (name, email) VALUES ('Jane Smith', 'jane@example.com')")
    cursor.execute("INSERT INTO posts (title, content, user_id) VALUES ('First Post', 'Hello World!', 1)")
    cursor.execute("INSERT INTO posts (title, content, user_id) VALUES ('Second Post', 'YAML is awesome!', 2)")
    
    conn.commit()
    conn.close()
    
    return db_path

def create_basic_yaml_config(db_path):
    """Create a basic YAML configuration file"""
    
    yaml_content = f"""# Basic YAML Configuration Example
# This is the simplest way to create a REST API with LightAPI

# Database connection - point to your existing database
database_url: "sqlite:///{db_path}"

# API documentation settings
swagger_title: "My First API"
swagger_version: "1.0.0"
swagger_description: "A simple REST API created with YAML configuration"
enable_swagger: true

# Tables to expose as API endpoints
tables:
  # Users table with full CRUD operations
  - name: users
    crud:
      - get     # GET /users/ and GET /users/{{id}}
      - post    # POST /users/
      - put     # PUT /users/{{id}}
      - delete  # DELETE /users/{{id}}
  
  # Posts table with full CRUD operations
  - name: posts
    crud:
      - get
      - post
      - put
      - delete
"""
    
    config_path = '/workspace/project/lightapi/examples/basic_config.yaml'
    with open(config_path, 'w') as f:
        f.write(yaml_content)
    
    return config_path

def run_basic_example():
    """Run the basic YAML configuration example"""
    
    print("🚀 LightAPI Basic YAML Configuration Example")
    print("=" * 60)
    
    # Step 1: Create database
    print("\n📊 Step 1: Creating sample database...")
    db_path = create_basic_database()
    print(f"✅ Database created: {db_path}")
    
    # Step 2: Create YAML configuration
    print("\n📝 Step 2: Creating YAML configuration...")
    config_path = create_basic_yaml_config(db_path)
    print(f"✅ Configuration created: {config_path}")
    
    # Step 3: Show configuration content
    print("\n📋 Step 3: YAML Configuration Content:")
    with open(config_path, 'r') as f:
        config_content = f.read()
    print("```yaml")
    print(config_content)
    print("```")
    
    # Step 4: Create API from YAML
    print("\n🔧 Step 4: Creating API from YAML...")
    app = LightApi.from_config(config_path)
    print(f"✅ API created successfully!")
    print(f"📊 Routes registered: {len(app.aiohttp_routes)}")
    
    # Step 5: Show generated endpoints
    print("\n🔗 Step 5: Generated API Endpoints:")
    
    routes_by_table = {}
    for route in app.aiohttp_routes:
        path_parts = route.path.strip('/').split('/')
        table_name = path_parts[0] if path_parts else 'unknown'
        
        if table_name not in routes_by_table:
            routes_by_table[table_name] = []
        
        routes_by_table[table_name].append(f"{route.method} {route.path}")
    
    for table, routes in routes_by_table.items():
        print(f"  📁 {table.title()} API:")
        for route in routes:
            print(f"    • {route}")
    
    # Step 6: Usage instructions
    print("\n🌐 Step 6: How to use this API:")
    print("```python")
    print("from lightapi import LightApi")
    print("")
    print("# Create and run the API")
    print("app = LightApi.from_config('basic_config.yaml')")
    print("app.run(host='0.0.0.0', port=8000)")
    print("```")
    
    print("\n🔧 Step 7: Sample API requests:")
    print("```bash")
    print("# Get all users")
    print("curl http://localhost:8000/users/")
    print("")
    print("# Create a new user")
    print("curl -X POST http://localhost:8000/users/ \\")
    print("  -H 'Content-Type: application/json' \\")
    print("  -d '{\"name\": \"Alice\", \"email\": \"alice@example.com\"}'")
    print("")
    print("# Get specific user")
    print("curl http://localhost:8000/users/1")
    print("")
    print("# Update user")
    print("curl -X PUT http://localhost:8000/users/1 \\")
    print("  -H 'Content-Type: application/json' \\")
    print("  -d '{\"name\": \"Alice Updated\", \"email\": \"alice.updated@example.com\"}'")
    print("")
    print("# Delete user")
    print("curl -X DELETE http://localhost:8000/users/1")
    print("")
    print("# Get API documentation")
    print("curl http://localhost:8000/docs")
    print("```")
    
    print("\n📚 Key Features Demonstrated:")
    print("  ✅ Simple YAML structure")
    print("  ✅ Database connection configuration")
    print("  ✅ Full CRUD operations (GET, POST, PUT, DELETE)")
    print("  ✅ Automatic Swagger documentation")
    print("  ✅ Foreign key relationships")
    print("  ✅ Sample data included")
    
    print("\n🎯 Next Steps:")
    print("  1. Modify the YAML file to point to your own database")
    print("  2. Add or remove tables as needed")
    print("  3. Customize CRUD operations per table")
    print("  4. Run the API and test with curl or Swagger UI")
    
    return app, config_path, db_path

if __name__ == "__main__":
    app, config_path, db_path = run_basic_example()
    
    print(f"\n🚀 Ready to run! Execute:")
    print(f"python -c \"from lightapi import LightApi; LightApi.from_config('{config_path}').run()\"")
    
    # Cleanup note
    print(f"\n🧹 Cleanup files:")
    print(f"  • Database: {db_path}")
    print(f"  • Config: {config_path}")