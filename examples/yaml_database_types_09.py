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
import sqlite3
import tempfile
from lightapi import LightApi

def create_sqlite_database():
    """Create a SQLite database with sample schema"""
    
    # Create temporary database
    db_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    db_path = db_file.name
    db_file.close()
    
    # Connect and create tables
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Enable foreign keys in SQLite
    cursor.execute("PRAGMA foreign_keys = ON")
    
    # Companies table
    cursor.execute('''
        CREATE TABLE companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(200) NOT NULL UNIQUE,
            industry VARCHAR(100),
            founded_year INTEGER,
            headquarters VARCHAR(200),
            website VARCHAR(255),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Employees table
    cursor.execute('''
        CREATE TABLE employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            first_name VARCHAR(100) NOT NULL,
            last_name VARCHAR(100) NOT NULL,
            email VARCHAR(255) NOT NULL UNIQUE,
            department VARCHAR(100),
            position VARCHAR(100),
            salary DECIMAL(10,2),
            hire_date DATE,
            is_active BOOLEAN DEFAULT 1,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
    ''')
    
    # Projects table
    cursor.execute('''
        CREATE TABLE projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            name VARCHAR(200) NOT NULL,
            description TEXT,
            start_date DATE,
            end_date DATE,
            budget DECIMAL(12,2),
            status VARCHAR(50) DEFAULT 'planning',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        )
    ''')
    
    # Insert sample data
    sample_data = [
        "INSERT INTO companies (name, industry, founded_year, headquarters, website) VALUES ('TechCorp', 'Technology', 2010, 'San Francisco, CA', 'https://techcorp.com')",
        "INSERT INTO companies (name, industry, founded_year, headquarters, website) VALUES ('DataSystems', 'Software', 2015, 'Austin, TX', 'https://datasystems.com')",
        "INSERT INTO companies (name, industry, founded_year, headquarters, website) VALUES ('CloudWorks', 'Cloud Services', 2018, 'Seattle, WA', 'https://cloudworks.com')",
        
        "INSERT INTO employees (company_id, first_name, last_name, email, department, position, salary, hire_date) VALUES (1, 'John', 'Smith', 'john.smith@techcorp.com', 'Engineering', 'Senior Developer', 95000.00, '2020-01-15')",
        "INSERT INTO employees (company_id, first_name, last_name, email, department, position, salary, hire_date) VALUES (1, 'Sarah', 'Johnson', 'sarah.johnson@techcorp.com', 'Marketing', 'Marketing Manager', 75000.00, '2019-03-20')",
        "INSERT INTO employees (company_id, first_name, last_name, email, department, position, salary, hire_date) VALUES (2, 'Mike', 'Davis', 'mike.davis@datasystems.com', 'Engineering', 'Lead Developer', 110000.00, '2021-06-10')",
        
        "INSERT INTO projects (company_id, name, description, start_date, budget, status) VALUES (1, 'Mobile App v2', 'Next generation mobile application', '2024-01-01', 250000.00, 'in_progress')",
        "INSERT INTO projects (company_id, name, description, start_date, budget, status) VALUES (2, 'Data Pipeline', 'Real-time data processing pipeline', '2024-02-15', 180000.00, 'planning')",
        "INSERT INTO projects (company_id, name, description, start_date, budget, status) VALUES (3, 'Cloud Migration', 'Migrate legacy systems to cloud', '2024-03-01', 500000.00, 'planning')",
    ]
    
    for query in sample_data:
        cursor.execute(query)
    
    conn.commit()
    conn.close()
    
    return db_path

def create_database_configs(db_path):
    """Create YAML configurations for different database types"""
    
    configs = {}
    
    # SQLite Configuration
    sqlite_config = f"""# SQLite Database Configuration
# Perfect for development, testing, and small applications

# SQLite connection - file-based database
database_url: "sqlite:///{db_path}"

# API metadata
swagger_title: "SQLite Company API"
swagger_version: "1.0.0"
swagger_description: |
  Company management API using SQLite database
  
  ## Database Features
  - File-based storage
  - ACID compliance
  - Foreign key support
  - Perfect for development and small applications
  
  ## Connection Details
  - Database file: {os.path.basename(db_path)}
  - Foreign keys: Enabled
  - WAL mode: Recommended for production
enable_swagger: true

# Tables configuration
tables:
  # Companies - full CRUD
  - name: companies
    crud:
      - get     # List and view companies
      - post    # Create new companies
      - put     # Update company information
      - patch   # Partial updates
      - delete  # Remove companies
  
  # Employees - full CRUD with foreign key to companies
  - name: employees
    crud:
      - get
      - post
      - put
      - patch
      - delete
  
  # Projects - full CRUD with foreign key to companies
  - name: projects
    crud:
      - get
      - post
      - put
      - patch
      - delete
"""
    
    # PostgreSQL Configuration
    postgresql_config = f"""# PostgreSQL Database Configuration
# Production-ready relational database with advanced features

# PostgreSQL connection string
# Format: postgresql://username:password@host:port/database
database_url: "${{POSTGRESQL_URL}}"

# Alternative formats:
# database_url: "postgresql+psycopg2://user:pass@localhost:5432/company_db"
# database_url: "postgresql://user:pass@db.example.com:5432/company_db?sslmode=require"

swagger_title: "PostgreSQL Company API"
swagger_version: "2.0.0"
swagger_description: |
  Enterprise company management API using PostgreSQL
  
  ## Database Features
  - ACID compliance with advanced isolation levels
  - JSON/JSONB support for flexible data
  - Full-text search capabilities
  - Advanced indexing (B-tree, Hash, GiST, GIN)
  - Partitioning and sharding support
  - Concurrent connections and connection pooling
  
  ## Production Features
  - High availability with replication
  - Point-in-time recovery
  - Advanced security features
  - Extensive monitoring and logging
  
  ## Connection Details
  - Host: ${{DB_HOST}}
  - Port: ${{DB_PORT}}
  - Database: ${{DB_NAME}}
  - SSL: Required in production
enable_swagger: true

tables:
  # Full CRUD for all tables in PostgreSQL
  - name: companies
    crud:
      - get
      - post
      - put
      - patch
      - delete
  
  - name: employees
    crud:
      - get
      - post
      - put
      - patch
      - delete
  
  - name: projects
    crud:
      - get
      - post
      - put
      - patch
      - delete
"""
    
    # MySQL Configuration
    mysql_config = f"""# MySQL Database Configuration
# Popular open-source relational database

# MySQL connection string
# Format: mysql+pymysql://username:password@host:port/database
database_url: "${{MYSQL_URL}}"

# Alternative formats:
# database_url: "mysql://user:pass@localhost:3306/company_db"
# database_url: "mysql+mysqlconnector://user:pass@mysql.example.com:3306/company_db"

swagger_title: "MySQL Company API"
swagger_version: "2.0.0"
swagger_description: |
  Company management API using MySQL database
  
  ## Database Features
  - InnoDB storage engine with ACID compliance
  - Row-level locking for high concurrency
  - Foreign key constraints
  - Full-text indexing
  - Replication support (master-slave, master-master)
  - Partitioning capabilities
  
  ## Performance Features
  - Query cache for improved performance
  - Multiple storage engines (InnoDB, MyISAM, Memory)
  - Connection pooling
  - Optimized for read-heavy workloads
  
  ## Connection Details
  - Host: ${{DB_HOST}}
  - Port: ${{DB_PORT}}
  - Database: ${{DB_NAME}}
  - Charset: utf8mb4 (recommended)
enable_swagger: true

tables:
  # Full CRUD operations for MySQL
  - name: companies
    crud:
      - get
      - post
      - put
      - patch
      - delete
  
  - name: employees
    crud:
      - get
      - post
      - put
      - patch
      - delete
  
  - name: projects
    crud:
      - get
      - post
      - put
      - patch
      - delete
"""
    
    # Multi-Database Configuration
    multi_db_config = f"""# Multi-Database Configuration
# Demonstrates switching between database types using environment variables

# Database URL determined by environment
database_url: "${{DATABASE_URL}}"

swagger_title: "Multi-Database Company API"
swagger_version: "3.0.0"
swagger_description: |
  Flexible company management API supporting multiple database backends
  
  ## Supported Databases
  
  ### SQLite (Development)
  ```
  DATABASE_URL=sqlite:///company.db
  ```
  - File-based storage
  - Zero configuration
  - Perfect for development and testing
  
  ### PostgreSQL (Production)
  ```
  DATABASE_URL=postgresql://user:pass@host:port/db
  ```
  - Enterprise-grade features
  - Advanced SQL support
  - High availability options
  
  ### MySQL (Alternative Production)
  ```
  DATABASE_URL=mysql+pymysql://user:pass@host:port/db
  ```
  - High performance
  - Wide ecosystem support
  - Proven scalability
  
  ## Environment Variables
  - `DATABASE_URL`: Database connection string
  - `DB_TYPE`: Database type (sqlite|postgresql|mysql)
  - `DB_HOST`: Database host
  - `DB_PORT`: Database port
  - `DB_NAME`: Database name
  - `DB_USER`: Database username
  - `DB_PASS`: Database password
enable_swagger: true

tables:
  # Universal table configuration works with all database types
  - name: companies
    crud:
      - get
      - post
      - put
      - patch
      - delete
  
  - name: employees
    crud:
      - get
      - post
      - put
      - patch
      - delete
  
  - name: projects
    crud:
      - get
      - post
      - put
      - patch
      - delete
"""
    
    configs['sqlite'] = sqlite_config
    configs['postgresql'] = postgresql_config
    configs['mysql'] = mysql_config
    configs['multi_database'] = multi_db_config
    
    # Save configuration files
    config_files = {}
    for db_type, config_content in configs.items():
        config_path = f'/workspace/project/lightapi/examples/db_{db_type}_config.yaml'
        with open(config_path, 'w') as f:
            f.write(config_content)
        config_files[db_type] = config_path
    
    return config_files

def setup_database_environment_variables(db_path):
    """Set up environment variables for database connections"""
    
    # SQLite (using actual file)
    os.environ['SQLITE_URL'] = f'sqlite:///{db_path}'
    
    # PostgreSQL (example - would need real database)
    os.environ['POSTGRESQL_URL'] = 'postgresql://username:password@localhost:5432/company_db'
    os.environ['DB_HOST'] = 'localhost'
    os.environ['DB_PORT'] = '5432'
    os.environ['DB_NAME'] = 'company_db'
    
    # MySQL (example - would need real database)
    os.environ['MYSQL_URL'] = 'mysql+pymysql://username:password@localhost:3306/company_db'
    
    # Multi-database (defaults to SQLite for demo)
    os.environ['DATABASE_URL'] = f'sqlite:///{db_path}'
    os.environ['DB_TYPE'] = 'sqlite'

def run_database_types_example():
    """Run the database types example"""
    
    print("🚀 LightAPI YAML Configuration for Different Database Types")
    print("=" * 70)
    
    # Step 1: Create SQLite database
    print("\n📊 Step 1: Creating SQLite database with sample data...")
    db_path = create_sqlite_database()
    print(f"✅ SQLite database created: {db_path}")
    print("   Tables: companies, employees, projects")
    
    # Step 2: Set up environment variables
    print("\n🌍 Step 2: Setting up environment variables...")
    setup_database_environment_variables(db_path)
    print("✅ Environment variables configured for all database types")
    
    # Step 3: Create database-specific configurations
    print("\n📝 Step 3: Creating database-specific configurations...")
    config_files = create_database_configs(db_path)
    print("✅ Configuration files created:")
    for db_type, path in config_files.items():
        print(f"   • {db_type}: {path}")
    
    # Step 4: Test SQLite configuration (the only one that will actually work)
    print(f"\n🧪 Step 4: Testing SQLite Configuration")
    print("-" * 50)
    
    sqlite_config = config_files['sqlite']
    
    # Show configuration content
    with open(sqlite_config, 'r') as f:
        config_content = f.read()
    
    print("📄 SQLite Configuration:")
    lines = config_content.split('\n')
    print("```yaml")
    for i, line in enumerate(lines):
        if i < 15 or 'tables:' in line or (i > lines.index('tables:') if 'tables:' in lines else False):
            print(line)
        elif i == 15:
            print("# ... (description section) ...")
    print("```")
    
    # Create API from SQLite configuration
    try:
        app = LightApi.from_config(sqlite_config)
        print(f"✅ SQLite API created successfully")
        print(f"📊 Routes registered: {len(app.aiohttp_routes)}")
        
        # Show available operations
        routes_by_table = {}
        for route in app.aiohttp_routes:
            path_parts = route.path.strip('/').split('/')
            table_name = path_parts[0] if path_parts else 'unknown'
            
            if table_name not in routes_by_table:
                routes_by_table[table_name] = []
            
            routes_by_table[table_name].append(route.method)
        
        print("🔗 Available Operations:")
        for table, methods in routes_by_table.items():
            unique_methods = list(set(methods))
            print(f"   • {table}: {', '.join(unique_methods)}")
        
    except Exception as e:
        print(f"❌ Error creating SQLite API: {e}")
    
    # Step 5: Show database-specific features
    print(f"\n🗄️  Step 5: Database-Specific Features")
    print("=" * 50)
    
    database_features = {
        'SQLite': [
            "✅ File-based storage - no server required",
            "✅ ACID compliance with WAL mode",
            "✅ Foreign key support (must be enabled)",
            "✅ Full-text search with FTS extensions",
            "✅ JSON support (JSON1 extension)",
            "⚠️  Single writer limitation",
            "⚠️  No network access (file-based only)"
        ],
        'PostgreSQL': [
            "✅ Advanced SQL features (CTEs, window functions)",
            "✅ JSON/JSONB support with indexing",
            "✅ Full-text search built-in",
            "✅ Advanced indexing (GiST, GIN, SP-GiST)",
            "✅ Concurrent connections and connection pooling",
            "✅ Replication and high availability",
            "✅ Extensive extension ecosystem"
        ],
        'MySQL': [
            "✅ High performance with InnoDB engine",
            "✅ Row-level locking for concurrency",
            "✅ Replication (master-slave, master-master)",
            "✅ Partitioning for large tables",
            "✅ Query cache for performance",
            "✅ Multiple storage engines",
            "⚠️  Limited JSON support (compared to PostgreSQL)"
        ]
    }
    
    for db_type, features in database_features.items():
        print(f"\n📋 {db_type} Features:")
        for feature in features:
            print(f"   {feature}")
    
    # Step 6: Connection string examples
    print(f"\n🔗 Step 6: Connection String Examples")
    print("=" * 50)
    
    connection_examples = {
        'SQLite': [
            "# Local file",
            "sqlite:///path/to/database.db",
            "",
            "# Relative path",
            "sqlite:///./data/app.db",
            "",
            "# In-memory (testing only)",
            "sqlite:///:memory:"
        ],
        'PostgreSQL': [
            "# Basic connection",
            "postgresql://username:password@localhost:5432/database",
            "",
            "# With SSL",
            "postgresql://user:pass@host:5432/db?sslmode=require",
            "",
            "# With connection pool",
            "postgresql+psycopg2://user:pass@host:5432/db",
            "",
            "# Cloud database (example)",
            "postgresql://user:pass@db.amazonaws.com:5432/prod_db"
        ],
        'MySQL': [
            "# Basic connection",
            "mysql+pymysql://username:password@localhost:3306/database",
            "",
            "# Alternative driver",
            "mysql+mysqlconnector://user:pass@host:3306/db",
            "",
            "# With charset",
            "mysql://user:pass@host:3306/db?charset=utf8mb4",
            "",
            "# Cloud database (example)",
            "mysql://user:pass@mysql.amazonaws.com:3306/prod_db"
        ]
    }
    
    for db_type, examples in connection_examples.items():
        print(f"\n📝 {db_type} Connection Strings:")
        print("```")
        for example in examples:
            print(example)
        print("```")
    
    # Step 7: Deployment examples
    print(f"\n🚀 Step 7: Deployment Examples")
    print("=" * 50)
    
    print("\n🐳 Docker Compose Example:")
    print("```yaml")
    print("version: '3.8'")
    print("services:")
    print("  # PostgreSQL database")
    print("  postgres:")
    print("    image: postgres:15")
    print("    environment:")
    print("      POSTGRES_DB: company_db")
    print("      POSTGRES_USER: api_user")
    print("      POSTGRES_PASSWORD: secure_password")
    print("    volumes:")
    print("      - postgres_data:/var/lib/postgresql/data")
    print("  ")
    print("  # LightAPI application")
    print("  api:")
    print("    build: .")
    print("    environment:")
    print("      DATABASE_URL: postgresql://api_user:secure_password@postgres:5432/company_db")
    print("      API_TITLE: Company API")
    print("    ports:")
    print("      - \"8000:8000\"")
    print("    depends_on:")
    print("      - postgres")
    print("")
    print("volumes:")
    print("  postgres_data:")
    print("```")
    
    print("\n☸️  Kubernetes Example:")
    print("```yaml")
    print("apiVersion: v1")
    print("kind: Secret")
    print("metadata:")
    print("  name: database-secret")
    print("data:")
    print("  url: cG9zdGdyZXNxbDovL3VzZXI6cGFzc0BkYjozMzA2L2FwcA==  # base64 encoded")
    print("---")
    print("apiVersion: apps/v1")
    print("kind: Deployment")
    print("metadata:")
    print("  name: company-api")
    print("spec:")
    print("  replicas: 3")
    print("  template:")
    print("    spec:")
    print("      containers:")
    print("      - name: api")
    print("        image: company-api:latest")
    print("        env:")
    print("        - name: DATABASE_URL")
    print("          valueFrom:")
    print("            secretKeyRef:")
    print("              name: database-secret")
    print("              key: url")
    print("```")
    
    # Step 8: Best practices
    print(f"\n💡 Step 8: Database Configuration Best Practices")
    print("=" * 50)
    
    best_practices = [
        "✅ Use environment variables for connection strings",
        "✅ Enable SSL/TLS for production databases",
        "✅ Configure connection pooling appropriately",
        "✅ Set up database monitoring and logging",
        "✅ Use read replicas for read-heavy workloads",
        "✅ Implement proper backup and recovery procedures",
        "✅ Use database migrations for schema changes",
        "⚠️  Never hardcode credentials in configuration files",
        "⚠️  Test database failover scenarios",
        "⚠️  Monitor connection pool exhaustion"
    ]
    
    for practice in best_practices:
        print(f"  {practice}")
    
    print(f"\n📚 Key Features Demonstrated:")
    print("  ✅ SQLite configuration for development")
    print("  ✅ PostgreSQL configuration for production")
    print("  ✅ MySQL configuration as alternative")
    print("  ✅ Multi-database environment support")
    print("  ✅ Database-specific connection strings")
    print("  ✅ Environment variable integration")
    print("  ✅ Production deployment examples")
    
    return config_files, db_path

if __name__ == "__main__":
    config_files, db_path = run_database_types_example()
    
    print(f"\n🎯 Test different database configurations:")
    print(f"  SQLite (working): python -c \"from lightapi import LightApi; LightApi.from_config('{config_files['sqlite']}').run()\"")
    print(f"  PostgreSQL: Requires real PostgreSQL database")
    print(f"  MySQL: Requires real MySQL database")
    
    # Cleanup note
    print(f"\n🧹 Cleanup files:")
    print(f"  • Database: {db_path}")
    for db_type, config_path in config_files.items():
        print(f"  • {db_type} config: {config_path}")