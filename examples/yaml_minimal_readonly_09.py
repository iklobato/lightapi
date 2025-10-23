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
import sqlite3
import tempfile
from lightapi import LightApi

def create_blog_database():
    """Create a simple blog database for minimal example"""
    
    # Create temporary database
    db_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    db_path = db_file.name
    db_file.close()
    
    # Connect and create tables
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Simple blog schema
    cursor.execute('''
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title VARCHAR(200) NOT NULL,
            content TEXT,
            author VARCHAR(100),
            published BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            author VARCHAR(100),
            content TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (post_id) REFERENCES posts(id)
        )
    ''')
    
    # Insert sample data
    sample_data = [
        "INSERT INTO posts (title, content, author, published) VALUES ('Welcome to My Blog', 'This is my first blog post!', 'John Doe', 1)",
        "INSERT INTO posts (title, content, author, published) VALUES ('YAML Configuration Guide', 'Learn how to use YAML with LightAPI', 'Jane Smith', 1)",
        "INSERT INTO posts (title, content, author, published) VALUES ('Draft Post', 'This is a draft post', 'John Doe', 0)",
        "INSERT INTO comments (post_id, author, content) VALUES (1, 'Alice', 'Great first post!')",
        "INSERT INTO comments (post_id, author, content) VALUES (1, 'Bob', 'Looking forward to more content')",
        "INSERT INTO comments (post_id, author, content) VALUES (2, 'Charlie', 'Very helpful guide, thanks!')",
    ]
    
    for query in sample_data:
        cursor.execute(query)
    
    conn.commit()
    conn.close()
    
    return db_path

def create_analytics_database():
    """Create an analytics database for read-only example"""
    
    # Create temporary database
    db_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    db_path = db_file.name
    db_file.close()
    
    # Connect and create tables
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Analytics schema
    cursor.execute('''
        CREATE TABLE page_views (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            page_url VARCHAR(255) NOT NULL,
            visitor_ip VARCHAR(45),
            user_agent TEXT,
            referrer VARCHAR(255),
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE user_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id VARCHAR(100) NOT NULL,
            user_id INTEGER,
            start_time DATETIME,
            end_time DATETIME,
            pages_visited INTEGER DEFAULT 0,
            total_time_seconds INTEGER DEFAULT 0
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE sales_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name VARCHAR(200),
            category VARCHAR(100),
            price DECIMAL(10,2),
            quantity INTEGER,
            total_amount DECIMAL(10,2),
            sale_date DATE,
            region VARCHAR(100)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE monthly_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_month VARCHAR(7),  -- YYYY-MM format
            total_revenue DECIMAL(12,2),
            total_orders INTEGER,
            new_customers INTEGER,
            returning_customers INTEGER,
            avg_order_value DECIMAL(10,2),
            generated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Insert sample analytics data
    sample_data = [
        # Page views
        "INSERT INTO page_views (page_url, visitor_ip, user_agent, referrer) VALUES ('/home', '192.168.1.100', 'Mozilla/5.0...', 'https://google.com')",
        "INSERT INTO page_views (page_url, visitor_ip, user_agent, referrer) VALUES ('/products', '192.168.1.101', 'Mozilla/5.0...', '/home')",
        "INSERT INTO page_views (page_url, visitor_ip, user_agent, referrer) VALUES ('/about', '192.168.1.102', 'Mozilla/5.0...', '/home')",
        
        # User sessions
        "INSERT INTO user_sessions (session_id, user_id, start_time, pages_visited, total_time_seconds) VALUES ('sess_001', 1, '2024-01-15 10:00:00', 5, 1200)",
        "INSERT INTO user_sessions (session_id, user_id, start_time, pages_visited, total_time_seconds) VALUES ('sess_002', 2, '2024-01-15 11:30:00', 3, 800)",
        
        # Sales data
        "INSERT INTO sales_data (product_name, category, price, quantity, total_amount, sale_date, region) VALUES ('Laptop Pro', 'Electronics', 1299.99, 1, 1299.99, '2024-01-15', 'North America')",
        "INSERT INTO sales_data (product_name, category, price, quantity, total_amount, sale_date, region) VALUES ('Wireless Mouse', 'Electronics', 29.99, 2, 59.98, '2024-01-15', 'Europe')",
        "INSERT INTO sales_data (product_name, category, price, quantity, total_amount, sale_date, region) VALUES ('Office Chair', 'Furniture', 199.99, 1, 199.99, '2024-01-16', 'Asia')",
        
        # Monthly reports
        "INSERT INTO monthly_reports (report_month, total_revenue, total_orders, new_customers, returning_customers, avg_order_value) VALUES ('2024-01', 125000.00, 450, 120, 330, 277.78)",
        "INSERT INTO monthly_reports (report_month, total_revenue, total_orders, new_customers, returning_customers, avg_order_value) VALUES ('2023-12', 98000.00, 380, 95, 285, 257.89)",
    ]
    
    for query in sample_data:
        cursor.execute(query)
    
    conn.commit()
    conn.close()
    
    return db_path

def create_minimal_config(db_path):
    """Create a minimal YAML configuration"""
    
    yaml_content = f"""# Minimal YAML Configuration
# Perfect for simple applications with essential operations only

# Database connection
database_url: "sqlite:///{db_path}"

# Basic API information
swagger_title: "Simple Blog API"
swagger_version: "1.0.0"
swagger_description: |
  Minimal blog API with essential operations only
  
  ## Features
  - Browse and create blog posts
  - View comments (read-only)
  
  ## Use Cases
  - Simple blog websites
  - Content management systems
  - Prototype applications
  - MVP (Minimum Viable Product) development
enable_swagger: true

# Minimal table configuration
tables:
  # Posts - browse and create only
  - name: posts
    crud:
      - get     # Browse posts: GET /posts/ and GET /posts/{{id}}
      - post    # Create posts: POST /posts/
      # Note: No update or delete - keeps it simple
  
  # Comments - read-only
  - name: comments
    crud:
      - get     # View comments only: GET /comments/ and GET /comments/{{id}}
      # Note: Comments are read-only to prevent spam/abuse
"""
    
    config_path = '/workspace/project/lightapi/examples/minimal_blog_config.yaml'
    with open(config_path, 'w') as f:
        f.write(yaml_content)
    
    return config_path

def create_readonly_config(db_path):
    """Create a read-only YAML configuration"""
    
    yaml_content = f"""# Read-Only YAML Configuration
# Perfect for analytics, reporting, and data viewing APIs

# Database connection
database_url: "sqlite:///{db_path}"

# API information
swagger_title: "Analytics Data API"
swagger_version: "1.0.0"
swagger_description: |
  Read-only analytics and reporting API
  
  ## Features
  - View website analytics data
  - Access sales reports
  - Browse user session data
  - Monthly performance reports
  
  ## Use Cases
  - Business intelligence dashboards
  - Analytics reporting
  - Data visualization tools
  - Public data access
  - Audit and compliance reporting
  
  ## Security
  - All endpoints are read-only
  - No data modification possible
  - Safe for public access
  - Audit-friendly
enable_swagger: true

# Read-only table configuration
tables:
  # Page views - website analytics
  - name: page_views
    crud:
      - get     # View page analytics: GET /page_views/
      # Read-only: Analytics data should not be modified via API
  
  # User sessions - user behavior data
  - name: user_sessions
    crud:
      - get     # View session data: GET /user_sessions/
      # Read-only: Session data is historical and immutable
  
  # Sales data - business metrics
  - name: sales_data
    crud:
      - get     # View sales data: GET /sales_data/
      # Read-only: Sales data comes from other systems
  
  # Monthly reports - aggregated data
  - name: monthly_reports
    crud:
      - get     # View reports: GET /monthly_reports/
      # Read-only: Reports are generated by batch processes
"""
    
    config_path = '/workspace/project/lightapi/examples/readonly_analytics_config.yaml'
    with open(config_path, 'w') as f:
        f.write(yaml_content)
    
    return config_path

def run_minimal_readonly_example():
    """Run the minimal and read-only configuration examples"""
    
    print("🚀 LightAPI YAML Configuration - Minimal and Read-Only Examples")
    print("=" * 70)
    
    # Step 1: Create databases
    print("\n📊 Step 1: Creating sample databases...")
    blog_db_path = create_blog_database()
    analytics_db_path = create_analytics_database()
    print(f"✅ Blog database created: {blog_db_path}")
    print(f"✅ Analytics database created: {analytics_db_path}")
    
    # Step 2: Create configurations
    print("\n📝 Step 2: Creating YAML configurations...")
    minimal_config = create_minimal_config(blog_db_path)
    readonly_config = create_readonly_config(analytics_db_path)
    print(f"✅ Minimal config created: {minimal_config}")
    print(f"✅ Read-only config created: {readonly_config}")
    
    # Step 3: Test minimal configuration
    print(f"\n🧪 Step 3: Testing Minimal Configuration")
    print("=" * 50)
    
    print("📄 Minimal Configuration Content:")
    with open(minimal_config, 'r') as f:
        config_content = f.read()
    
    lines = config_content.split('\n')
    print("```yaml")
    for i, line in enumerate(lines):
        if i < 12 or 'tables:' in line or (i > lines.index('tables:') if 'tables:' in lines else False):
            print(line)
        elif i == 12:
            print("# ... (description section) ...")
    print("```")
    
    # Create API from minimal configuration
    try:
        minimal_app = LightApi.from_config(minimal_config)
        print(f"✅ Minimal API created successfully")
        print(f"📊 Routes registered: {len(minimal_app.aiohttp_routes)}")
        
        # Show available operations
        print("🔗 Available Operations:")
        routes_by_table = {}
        for route in minimal_app.aiohttp_routes:
            path_parts = route.path.strip('/').split('/')
            table_name = path_parts[0] if path_parts else 'unknown'
            
            if table_name not in routes_by_table:
                routes_by_table[table_name] = []
            
            routes_by_table[table_name].append(f"{route.method} {route.path}")
        
        for table, routes in routes_by_table.items():
            print(f"   📁 {table.title()}:")
            for route in routes:
                print(f"     • {route}")
        
        print("\n💡 Minimal API Benefits:")
        print("   ✅ Simple to understand and maintain")
        print("   ✅ Reduced attack surface")
        print("   ✅ Fast development and deployment")
        print("   ✅ Perfect for MVPs and prototypes")
        print("   ✅ Lower resource requirements")
        
    except Exception as e:
        print(f"❌ Error creating minimal API: {e}")
    
    # Step 4: Test read-only configuration
    print(f"\n🧪 Step 4: Testing Read-Only Configuration")
    print("=" * 50)
    
    print("📄 Read-Only Configuration Content:")
    with open(readonly_config, 'r') as f:
        config_content = f.read()
    
    lines = config_content.split('\n')
    print("```yaml")
    for i, line in enumerate(lines):
        if i < 15 or 'tables:' in line or (i > lines.index('tables:') if 'tables:' in lines else False):
            print(line)
        elif i == 15:
            print("# ... (description section) ...")
    print("```")
    
    # Create API from read-only configuration
    try:
        readonly_app = LightApi.from_config(readonly_config)
        print(f"✅ Read-only API created successfully")
        print(f"📊 Routes registered: {len(readonly_app.aiohttp_routes)}")
        
        # Show available operations
        print("🔗 Available Operations:")
        routes_by_table = {}
        for route in readonly_app.aiohttp_routes:
            path_parts = route.path.strip('/').split('/')
            table_name = path_parts[0] if path_parts else 'unknown'
            
            if table_name not in routes_by_table:
                routes_by_table[table_name] = []
            
            routes_by_table[table_name].append(f"{route.method} {route.path}")
        
        for table, routes in routes_by_table.items():
            print(f"   📁 {table.title()}:")
            for route in routes:
                print(f"     • {route}")
        
        print("\n🛡️  Read-Only API Benefits:")
        print("   ✅ Maximum security - no data modification")
        print("   ✅ Safe for public access")
        print("   ✅ Perfect for analytics and reporting")
        print("   ✅ Audit-friendly and compliance-ready")
        print("   ✅ High performance (no write locks)")
        
    except Exception as e:
        print(f"❌ Error creating read-only API: {e}")
    
    # Step 5: Usage examples
    print(f"\n🔧 Step 5: Usage Examples")
    print("=" * 50)
    
    print("\n📝 Minimal Blog API Usage:")
    print("```bash")
    print("# Browse all posts")
    print("curl http://localhost:8000/posts/")
    print("")
    print("# Get specific post")
    print("curl http://localhost:8000/posts/1")
    print("")
    print("# Create new post")
    print("curl -X POST http://localhost:8000/posts/ \\")
    print("  -H 'Content-Type: application/json' \\")
    print("  -d '{")
    print("    \"title\": \"My New Post\",")
    print("    \"content\": \"This is the content of my new post\",")
    print("    \"author\": \"API User\",")
    print("    \"published\": true")
    print("  }'")
    print("")
    print("# View comments (read-only)")
    print("curl http://localhost:8000/comments/")
    print("```")
    
    print("\n📊 Analytics API Usage:")
    print("```bash")
    print("# View page analytics")
    print("curl http://localhost:8000/page_views/")
    print("")
    print("# Get user session data")
    print("curl http://localhost:8000/user_sessions/")
    print("")
    print("# View sales data")
    print("curl http://localhost:8000/sales_data/")
    print("")
    print("# Get monthly reports")
    print("curl http://localhost:8000/monthly_reports/")
    print("")
    print("# All endpoints are read-only - no POST, PUT, DELETE operations")
    print("```")
    
    # Step 6: Use case scenarios
    print(f"\n🎯 Step 6: Use Case Scenarios")
    print("=" * 50)
    
    print("\n📱 Minimal Configuration Use Cases:")
    minimal_use_cases = [
        "🚀 MVP Development - Get started quickly with essential features",
        "📝 Simple Blogs - Basic content creation and viewing",
        "🛍️  E-commerce Prototypes - Product browsing and basic ordering",
        "📋 Task Management - Create and view tasks without complex workflows",
        "🎓 Learning Projects - Focus on core concepts without complexity",
        "🔧 Microservices - Single-purpose services with minimal operations",
        "📊 Data Collection - Simple data entry with read access"
    ]
    
    for use_case in minimal_use_cases:
        print(f"   {use_case}")
    
    print("\n📈 Read-Only Configuration Use Cases:")
    readonly_use_cases = [
        "📊 Business Intelligence - Dashboard data access",
        "📈 Analytics Platforms - Website and user behavior data",
        "📋 Reporting Systems - Financial and operational reports",
        "🔍 Data Exploration - Research and analysis tools",
        "🏛️  Public Data APIs - Government and open data access",
        "🔒 Audit Systems - Compliance and security logging",
        "📱 Mobile Apps - Data consumption without modification",
        "🌐 Content Distribution - News, articles, and media content"
    ]
    
    for use_case in readonly_use_cases:
        print(f"   {use_case}")
    
    # Step 7: Configuration patterns
    print(f"\n📋 Step 7: Configuration Patterns")
    print("=" * 50)
    
    print("\n🎨 Common CRUD Patterns:")
    crud_patterns = {
        "Full CRUD": "crud: [get, post, put, patch, delete]",
        "Create + Read": "crud: [get, post]",
        "Read + Update": "crud: [get, put, patch]",
        "Read Only": "crud: [get]",
        "Write Only": "crud: [post]",
        "No Delete": "crud: [get, post, put, patch]",
        "Status Updates": "crud: [get, patch]"
    }
    
    for pattern_name, pattern_config in crud_patterns.items():
        print(f"   📝 {pattern_name}: {pattern_config}")
    
    print("\n🔒 Security Considerations:")
    security_considerations = [
        "✅ Minimal APIs reduce attack surface",
        "✅ Read-only APIs prevent data tampering",
        "✅ Limited operations reduce complexity",
        "✅ Easier to audit and monitor",
        "⚠️  Still need authentication for sensitive data",
        "⚠️  Consider rate limiting for public APIs",
        "⚠️  Validate all input even for minimal operations"
    ]
    
    for consideration in security_considerations:
        print(f"   {consideration}")
    
    print(f"\n📚 Key Features Demonstrated:")
    print("  ✅ Minimal configuration for simple applications")
    print("  ✅ Read-only configuration for data viewing")
    print("  ✅ Selective CRUD operations per table")
    print("  ✅ Security-conscious design patterns")
    print("  ✅ Use case-specific configurations")
    print("  ✅ Performance-optimized setups")
    
    return {
        'minimal_config': minimal_config,
        'readonly_config': readonly_config,
        'blog_db': blog_db_path,
        'analytics_db': analytics_db_path
    }

if __name__ == "__main__":
    configs = run_minimal_readonly_example()
    
    print(f"\n🚀 Ready to test configurations:")
    print(f"  Minimal Blog API:")
    print(f"    python -c \"from lightapi import LightApi; LightApi.from_config('{configs['minimal_config']}').run()\"")
    print(f"  ")
    print(f"  Read-Only Analytics API:")
    print(f"    python -c \"from lightapi import LightApi; LightApi.from_config('{configs['readonly_config']}').run()\"")
    
    # Cleanup note
    print(f"\n🧹 Cleanup files:")
    print(f"  • Blog database: {configs['blog_db']}")
    print(f"  • Analytics database: {configs['analytics_db']}")
    print(f"  • Minimal config: {configs['minimal_config']}")
    print(f"  • Read-only config: {configs['readonly_config']}")