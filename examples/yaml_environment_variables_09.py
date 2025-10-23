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
import sqlite3
import tempfile
from lightapi import LightApi

def create_sample_database():
    """Create a sample database for environment testing"""
    
    # Create temporary database
    db_file = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    db_path = db_file.name
    db_file.close()
    
    # Connect and create tables
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # API keys table
    cursor.execute('''
        CREATE TABLE api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key_name VARCHAR(100) NOT NULL,
            api_key VARCHAR(255) NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Applications table
    cursor.execute('''
        CREATE TABLE applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(100) NOT NULL,
            version VARCHAR(20),
            environment VARCHAR(20),
            status VARCHAR(20) DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Configuration table
    cursor.execute('''
        CREATE TABLE configuration (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key VARCHAR(100) NOT NULL,
            value TEXT,
            environment VARCHAR(20),
            description TEXT
        )
    ''')
    
    # Insert sample data
    sample_data = [
        "INSERT INTO api_keys (key_name, api_key) VALUES ('development', 'dev_key_12345')",
        "INSERT INTO api_keys (key_name, api_key) VALUES ('production', 'prod_key_67890')",
        "INSERT INTO applications (name, version, environment) VALUES ('MyApp', '1.0.0', 'development')",
        "INSERT INTO applications (name, version, environment) VALUES ('MyApp', '1.2.0', 'production')",
        "INSERT INTO configuration (key, value, environment, description) VALUES ('debug_mode', 'true', 'development', 'Enable debug logging')",
        "INSERT INTO configuration (key, value, environment, description) VALUES ('debug_mode', 'false', 'production', 'Disable debug logging')",
    ]
    
    for query in sample_data:
        cursor.execute(query)
    
    conn.commit()
    conn.close()
    
    return db_path

def create_environment_configs(db_path):
    """Create YAML configurations for different environments"""
    
    configs = {}
    
    # Development Configuration
    dev_config = f"""# Development Environment Configuration
# This configuration uses environment variables for flexible deployment

# Database connection from environment variable
database_url: "${{DATABASE_URL}}"

# API metadata from environment variables
swagger_title: "${{API_TITLE}}"
swagger_version: "${{API_VERSION}}"
swagger_description: |
  ${{API_DESCRIPTION}}
  
  Environment: ${{ENVIRONMENT}}
  Debug Mode: ${{DEBUG_MODE}}
enable_swagger: true

# Tables configuration
tables:
  # Full access in development
  - name: api_keys
    crud:
      - get
      - post
      - put
      - patch
      - delete
  
  - name: applications
    crud:
      - get
      - post
      - put
      - patch
      - delete
  
  - name: configuration
    crud:
      - get
      - post
      - put
      - patch
      - delete
"""
    
    # Staging Configuration
    staging_config = f"""# Staging Environment Configuration
# Limited operations for testing

database_url: "${{DATABASE_URL}}"
swagger_title: "${{API_TITLE}}"
swagger_version: "${{API_VERSION}}"
swagger_description: |
  ${{API_DESCRIPTION}}
  
  Environment: ${{ENVIRONMENT}}
  
  ⚠️ This is a STAGING environment
  - Limited operations available
  - Data may be reset periodically
enable_swagger: true

tables:
  # Limited access in staging
  - name: api_keys
    crud:
      - get
      - post
      - patch  # Can update but not full replace
  
  - name: applications
    crud:
      - get
      - post
      - put
      - patch
  
  - name: configuration
    crud:
      - get
      - patch  # Configuration updates only
"""
    
    # Production Configuration
    production_config = f"""# Production Environment Configuration
# Minimal operations for security

database_url: "${{DATABASE_URL}}"
swagger_title: "${{API_TITLE}}"
swagger_version: "${{API_VERSION}}"
swagger_description: |
  ${{API_DESCRIPTION}}
  
  Environment: ${{ENVIRONMENT}}
  
  🔒 Production Environment
  - Read-only operations for most tables
  - Limited write access
  - Audit logging enabled
enable_swagger: false  # Disabled in production for security

tables:
  # Very limited access in production
  - name: api_keys
    crud:
      - get  # Read-only for security
  
  - name: applications
    crud:
      - get
      - patch  # Status updates only
  
  - name: configuration
    crud:
      - get  # Read-only in production
"""
    
    # Multi-database Configuration
    multi_db_config = f"""# Multi-Database Environment Configuration
# Demonstrates different database types

# Primary database from environment
database_url: "${{PRIMARY_DATABASE_URL}}"

swagger_title: "Multi-Database API"
swagger_version: "${{API_VERSION}}"
swagger_description: |
  Multi-database configuration example
  
  Primary DB: ${{PRIMARY_DATABASE_URL}}
  Environment: ${{ENVIRONMENT}}
  
  Supports:
  - SQLite: sqlite:///path/to/db.db
  - PostgreSQL: postgresql://user:pass@host:port/db
  - MySQL: mysql+pymysql://user:pass@host:port/db
enable_swagger: true

tables:
  - name: api_keys
    crud:
      - get
      - post
      - put
      - delete
  
  - name: applications
    crud:
      - get
      - post
      - put
      - delete
  
  - name: configuration
    crud:
      - get
      - post
      - put
      - delete
"""
    
    configs['development'] = dev_config
    configs['staging'] = staging_config
    configs['production'] = production_config
    configs['multi_database'] = multi_db_config
    
    # Save configuration files
    config_files = {}
    for env_name, config_content in configs.items():
        config_path = f'/workspace/project/lightapi/examples/env_{env_name}_config.yaml'
        with open(config_path, 'w') as f:
            f.write(config_content)
        config_files[env_name] = config_path
    
    return config_files

def setup_environment_variables(db_path, environment='development'):
    """Set up environment variables for the specified environment"""
    
    env_configs = {
        'development': {
            'DATABASE_URL': f'sqlite:///{db_path}',
            'API_TITLE': 'Development API',
            'API_VERSION': '1.0.0-dev',
            'API_DESCRIPTION': 'Development environment API with full access',
            'ENVIRONMENT': 'development',
            'DEBUG_MODE': 'true'
        },
        'staging': {
            'DATABASE_URL': f'sqlite:///{db_path}',
            'API_TITLE': 'Staging API',
            'API_VERSION': '1.0.0-staging',
            'API_DESCRIPTION': 'Staging environment API for testing',
            'ENVIRONMENT': 'staging',
            'DEBUG_MODE': 'true'
        },
        'production': {
            'DATABASE_URL': f'sqlite:///{db_path}',
            'API_TITLE': 'Production API',
            'API_VERSION': '1.0.0',
            'API_DESCRIPTION': 'Production API with limited access',
            'ENVIRONMENT': 'production',
            'DEBUG_MODE': 'false'
        },
        'multi_database': {
            'PRIMARY_DATABASE_URL': f'sqlite:///{db_path}',
            'API_VERSION': '2.0.0',
            'ENVIRONMENT': 'multi-db-demo'
        }
    }
    
    # Set environment variables
    env_vars = env_configs.get(environment, env_configs['development'])
    for key, value in env_vars.items():
        os.environ[key] = value
    
    return env_vars

def run_environment_example():
    """Run the environment variables example"""
    
    print("🚀 LightAPI YAML Configuration with Environment Variables")
    print("=" * 70)
    
    # Step 1: Create sample database
    print("\n📊 Step 1: Creating sample database...")
    db_path = create_sample_database()
    print(f"✅ Database created: {db_path}")
    
    # Step 2: Create environment configurations
    print("\n📝 Step 2: Creating environment-specific configurations...")
    config_files = create_environment_configs(db_path)
    print("✅ Configuration files created:")
    for env, path in config_files.items():
        print(f"   • {env}: {path}")
    
    # Step 3: Demonstrate each environment
    environments = ['development', 'staging', 'production', 'multi_database']
    
    for env_name in environments:
        print(f"\n🌍 Step 3.{environments.index(env_name)+1}: Testing {env_name.title()} Environment")
        print("-" * 50)
        
        # Set up environment variables
        env_vars = setup_environment_variables(db_path, env_name)
        print("📋 Environment Variables Set:")
        for key, value in env_vars.items():
            print(f"   {key}={value}")
        
        # Show configuration content
        config_path = config_files[env_name]
        print(f"\n📄 Configuration File: {config_path}")
        with open(config_path, 'r') as f:
            config_content = f.read()
        
        # Show key parts of the configuration
        lines = config_content.split('\n')
        print("```yaml")
        for i, line in enumerate(lines):
            if i < 10 or 'tables:' in line or (i > lines.index('tables:') if 'tables:' in lines else False):
                print(line)
            elif i == 10:
                print("# ... (description section) ...")
        print("```")
        
        # Create API from configuration
        try:
            app = LightApi.from_config(config_path)
            print(f"✅ API created successfully for {env_name}")
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
            print(f"❌ Error creating API for {env_name}: {e}")
    
    # Step 4: Show deployment examples
    print(f"\n🚀 Step 4: Deployment Examples")
    print("=" * 50)
    
    print("\n📦 Development Deployment:")
    print("```bash")
    print("# Set environment variables")
    print("export DATABASE_URL='sqlite:///dev.db'")
    print("export API_TITLE='My Dev API'")
    print("export API_VERSION='1.0.0-dev'")
    print("export ENVIRONMENT='development'")
    print("")
    print("# Run the API")
    print("python -c \"from lightapi import LightApi; LightApi.from_config('env_development_config.yaml').run()\"")
    print("```")
    
    print("\n🏭 Production Deployment:")
    print("```bash")
    print("# Set environment variables (typically in deployment system)")
    print("export DATABASE_URL='postgresql://user:pass@prod-db:5432/myapp'")
    print("export API_TITLE='Production API'")
    print("export API_VERSION='1.0.0'")
    print("export ENVIRONMENT='production'")
    print("")
    print("# Run with production server")
    print("gunicorn -w 4 -k uvicorn.workers.UvicornWorker \\")
    print("  --bind 0.0.0.0:8000 \\")
    print("  'lightapi:LightApi.from_config(\"env_production_config.yaml\")'")
    print("```")
    
    print("\n🐳 Docker Deployment:")
    print("```dockerfile")
    print("FROM python:3.11-slim")
    print("WORKDIR /app")
    print("COPY requirements.txt .")
    print("RUN pip install -r requirements.txt")
    print("COPY . .")
    print("")
    print("# Environment variables set by Docker/Kubernetes")
    print("ENV DATABASE_URL=${DATABASE_URL}")
    print("ENV API_TITLE=${API_TITLE}")
    print("ENV API_VERSION=${API_VERSION}")
    print("")
    print("CMD [\"python\", \"-c\", \"from lightapi import LightApi; LightApi.from_config('config.yaml').run()\"]")
    print("```")
    
    print("\n☸️  Kubernetes Deployment:")
    print("```yaml")
    print("apiVersion: apps/v1")
    print("kind: Deployment")
    print("metadata:")
    print("  name: lightapi-app")
    print("spec:")
    print("  replicas: 3")
    print("  template:")
    print("    spec:")
    print("      containers:")
    print("      - name: api")
    print("        image: myapp:latest")
    print("        env:")
    print("        - name: DATABASE_URL")
    print("          valueFrom:")
    print("            secretKeyRef:")
    print("              name: db-secret")
    print("              key: url")
    print("        - name: API_TITLE")
    print("          value: \"Production API\"")
    print("```")
    
    # Step 5: Best practices
    print(f"\n💡 Step 5: Environment Variables Best Practices")
    print("=" * 50)
    
    best_practices = [
        "✅ Use ${VARIABLE} syntax in YAML files",
        "✅ Set different permissions per environment",
        "✅ Disable Swagger in production",
        "✅ Use secrets management for sensitive data",
        "✅ Validate environment variables on startup",
        "✅ Use different database URLs per environment",
        "✅ Set appropriate API titles and versions",
        "⚠️  Never commit real credentials to version control",
        "⚠️  Use read-only databases for production when possible",
        "⚠️  Implement proper logging and monitoring"
    ]
    
    for practice in best_practices:
        print(f"  {practice}")
    
    print(f"\n📚 Key Features Demonstrated:")
    print("  ✅ Environment variable substitution")
    print("  ✅ Multi-environment configurations")
    print("  ✅ Database URL flexibility")
    print("  ✅ Environment-specific permissions")
    print("  ✅ Production security considerations")
    print("  ✅ Deployment examples")
    
    return config_files, db_path

if __name__ == "__main__":
    config_files, db_path = run_environment_example()
    
    print(f"\n🎯 Try different environments:")
    for env_name, config_path in config_files.items():
        print(f"  {env_name}: python -c \"from lightapi import LightApi; LightApi.from_config('{config_path}').run()\"")
    
    # Cleanup note
    print(f"\n🧹 Cleanup files:")
    print(f"  • Database: {db_path}")
    for env_name, config_path in config_files.items():
        print(f"  • {env_name} config: {config_path}")