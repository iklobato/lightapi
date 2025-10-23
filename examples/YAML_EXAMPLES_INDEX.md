# LightAPI YAML Configuration Examples Index

This directory contains comprehensive examples demonstrating all YAML configuration features of LightAPI. Each example includes detailed documentation, sample databases, and usage instructions.

## 📚 Available Examples

### 1. Basic YAML Configuration (`yaml_basic_example_09.py`)
**Perfect for beginners and simple applications**

```yaml
database_url: "sqlite:///database.db"
swagger_title: "My First API"
enable_swagger: true

tables:
  - name: users
    crud: [get, post, put, delete]
  - name: posts
    crud: [get, post, put, delete]
```

**Features:**
- ✅ Simple YAML structure
- ✅ Basic database connection
- ✅ Full CRUD operations
- ✅ Swagger documentation
- ✅ Sample data included

**Use Cases:**
- Learning LightAPI YAML system
- Simple web applications
- Prototype development
- Getting started tutorials

---

### 2. Advanced Role-Based Permissions (`yaml_advanced_permissions_09.py`)
**Enterprise-ready configuration with role-based access control**

```yaml
database_url: "sqlite:///enterprise.db"
swagger_title: "E-commerce Management API"
swagger_version: "2.0.0"

tables:
  # ADMIN LEVEL - Full access
  - name: users
    crud: [get, post, put, patch, delete]
  
  # MANAGER LEVEL - Inventory management
  - name: products
    crud: [get, post, put, patch, delete]
  
  # LIMITED ACCESS - No delete for data integrity
  - name: categories
    crud: [get, post, put]
  
  # READ-ONLY - Security audit trail
  - name: audit_log
    crud: [get]
```

**Features:**
- ✅ Role-based CRUD permissions
- ✅ Data integrity constraints
- ✅ Audit trail implementation
- ✅ Complex database relationships
- ✅ Security-conscious design

**Use Cases:**
- E-commerce platforms
- Enterprise applications
- Multi-user systems
- Production environments

---

### 3. Environment Variables (`yaml_environment_variables_09.py`)
**Flexible deployment across different environments**

```yaml
# Development Environment
database_url: "${DATABASE_URL}"
swagger_title: "${API_TITLE}"
swagger_version: "${API_VERSION}"
enable_swagger: true

tables:
  - name: api_keys
    crud: [get, post, put, delete]  # Full access in dev

---
# Production Environment  
database_url: "${DATABASE_URL}"
swagger_title: "${API_TITLE}"
enable_swagger: false  # Disabled in production

tables:
  - name: api_keys
    crud: [get]  # Read-only in production
```

**Features:**
- ✅ Environment variable substitution
- ✅ Multi-environment configurations
- ✅ Database URL flexibility
- ✅ Environment-specific permissions
- ✅ Production security considerations

**Use Cases:**
- Development/staging/production deployments
- Docker containerization
- Kubernetes deployments
- CI/CD pipelines

---

### 4. Multiple Database Types (`yaml_database_types_09.py`)
**Support for SQLite, PostgreSQL, and MySQL**

```yaml
# SQLite Configuration
database_url: "sqlite:///company.db"
swagger_title: "SQLite Company API"

# PostgreSQL Configuration  
database_url: "postgresql://user:pass@host:5432/db"
swagger_title: "PostgreSQL Company API"

# MySQL Configuration
database_url: "mysql+pymysql://user:pass@host:3306/db"
swagger_title: "MySQL Company API"

tables:
  - name: companies
    crud: [get, post, put, patch, delete]
  - name: employees  
    crud: [get, post, put, patch, delete]
```

**Features:**
- ✅ SQLite for development
- ✅ PostgreSQL for production
- ✅ MySQL as alternative
- ✅ Database-specific connection strings
- ✅ Multi-database environment support

**Use Cases:**
- Database migration projects
- Multi-database applications
- Development to production transitions
- Database performance comparisons

---

### 5. Minimal and Read-Only APIs (`yaml_minimal_readonly_09.py`)
**Lightweight configurations for specific use cases**

```yaml
# Minimal Configuration
database_url: "sqlite:///blog.db"
swagger_title: "Simple Blog API"

tables:
  - name: posts
    crud: [get, post]  # Browse and create only
  - name: comments
    crud: [get]        # Read-only

---
# Read-Only Configuration
database_url: "sqlite:///analytics.db"  
swagger_title: "Analytics Data API"

tables:
  - name: page_views
    crud: [get]        # Analytics data
  - name: sales_data
    crud: [get]        # Business metrics
  - name: monthly_reports
    crud: [get]        # Generated reports
```

**Features:**
- ✅ Minimal CRUD operations
- ✅ Read-only APIs for data viewing
- ✅ Lightweight configurations
- ✅ Security-focused design
- ✅ Performance-optimized

**Use Cases:**
- MVP development
- Analytics dashboards
- Public data APIs
- Audit and compliance systems

---

### 6. Comprehensive System (`yaml_comprehensive_example_09.py`)
**Complete demonstration with all features**

```yaml
# Multiple configuration patterns in one example
database_url: "${DATABASE_URL}"
swagger_title: "Comprehensive Demo API"
swagger_description: |
  Complete demonstration of all YAML features
  
  ## Features
  - Multiple table configurations
  - Different permission levels
  - Environment variable support
  - Complex database relationships

tables:
  # Full feature demonstration
  - name: users
    crud: [get, post, put, patch, delete]
  - name: products
    crud: [get, post, put, patch, delete]
  - name: categories
    crud: [get, post, put]
  - name: orders
    crud: [get, post, patch]
  - name: order_items
    crud: [get]
  - name: settings
    crud: [get]
```

**Features:**
- ✅ All YAML features demonstrated
- ✅ Multiple configuration patterns
- ✅ Comprehensive testing
- ✅ Real-world examples
- ✅ Performance benchmarking

**Use Cases:**
- Learning all features
- Reference implementation
- Testing and validation
- Feature exploration

---

## 🚀 Quick Start Guide

### 1. Choose Your Example
Pick the example that best matches your use case:
- **Beginner**: Start with `yaml_basic_example_09.py`
- **Production**: Use `yaml_advanced_permissions_09.py`
- **Deployment**: Try `yaml_environment_variables_09.py`
- **Database Migration**: Check `yaml_database_types_09.py`
- **Simple Apps**: Use `yaml_minimal_readonly_09.py`

### 2. Run the Example
```bash
cd /workspace/project/lightapi/examples
python yaml_basic_example_09.py
```

### 3. Test the Generated API
```bash
# The example will show you the exact command, typically:
python -c "from lightapi import LightApi; LightApi.from_config('config.yaml').run()"
```

### 4. Access the API
- **API Endpoints**: http://localhost:8000/
- **Swagger Documentation**: http://localhost:8000/docs
- **OpenAPI Spec**: http://localhost:8000/openapi.json

## 📋 YAML Configuration Reference

### Core Structure
```yaml
# Database connection (required)
database_url: "sqlite:///database.db"

# API metadata (optional)
swagger_title: "My API"
swagger_version: "1.0.0"
swagger_description: "API description"
enable_swagger: true

# Tables configuration (required)
tables:
  - name: table_name
    crud: [get, post, put, patch, delete]
```

### CRUD Operations
| Operation | HTTP Method | Endpoint | Description |
|-----------|-------------|----------|-------------|
| `get` | GET | `/table/` | List all records |
| `get` | GET | `/table/{id}` | Get specific record |
| `post` | POST | `/table/` | Create new record |
| `put` | PUT | `/table/{id}` | Update entire record |
| `patch` | PATCH | `/table/{id}` | Partially update record |
| `delete` | DELETE | `/table/{id}` | Delete record |

### Environment Variables
```yaml
database_url: "${DATABASE_URL}"
swagger_title: "${API_TITLE}"
```

### Database URLs
```yaml
# SQLite
database_url: "sqlite:///path/to/database.db"

# PostgreSQL
database_url: "postgresql://user:pass@host:port/database"

# MySQL
database_url: "mysql+pymysql://user:pass@host:port/database"
```

## 🧪 Testing Your Configuration

### 1. Validate YAML Syntax
```bash
python -c "import yaml; yaml.safe_load(open('config.yaml'))"
```

### 2. Test API Creation
```bash
python -c "from lightapi import LightApi; app = LightApi.from_config('config.yaml'); print('✅ API created successfully')"
```

### 3. Run Validation Tests
```bash
python test_yaml_validation.py
```

## 🎯 Configuration Patterns

### Full CRUD
```yaml
tables:
  - name: users
    crud: [get, post, put, patch, delete]
```

### Read-Only
```yaml
tables:
  - name: analytics
    crud: [get]
```

### Create + Read
```yaml
tables:
  - name: posts
    crud: [get, post]
```

### No Delete (Data Integrity)
```yaml
tables:
  - name: categories
    crud: [get, post, put, patch]
```

### Status Updates Only
```yaml
tables:
  - name: orders
    crud: [get, patch]
```

## 🛡️ Security Best Practices

### Environment Variables
- ✅ Use `${VARIABLE}` syntax for sensitive data
- ✅ Never commit credentials to version control
- ✅ Use different permissions per environment

### Permission Levels
- ✅ Limit operations based on user roles
- ✅ Use read-only for sensitive data
- ✅ Disable Swagger in production

### Database Security
- ✅ Use SSL/TLS connections
- ✅ Configure proper database permissions
- ✅ Enable audit logging

## 📚 Additional Resources

### Documentation
- [YAML_CONFIGURATION_GUIDE.md](../YAML_CONFIGURATION_GUIDE.md) - Complete user guide
- [YAML_SYSTEM_SUMMARY.md](../YAML_SYSTEM_SUMMARY.md) - Implementation summary
- [README.md](../README.md) - Main LightAPI documentation

### Testing
- `test_yaml_validation.py` - Configuration validation tests
- `test_yaml_comprehensive.py` - Functionality tests
- `demo_yaml_server.py` - Live server demonstration

### Generated Configurations
After running examples, you'll find generated YAML files:
- `config_basic.yaml` - Basic configuration
- `config_advanced.yaml` - Advanced permissions
- `env_development_config.yaml` - Development environment
- `env_production_config.yaml` - Production environment
- `db_sqlite_config.yaml` - SQLite configuration
- `db_postgresql_config.yaml` - PostgreSQL configuration
- `minimal_blog_config.yaml` - Minimal blog API
- `readonly_analytics_config.yaml` - Read-only analytics API

## 🎉 Ready to Build Your API?

1. **Choose an example** that matches your needs
2. **Run the example** to see it in action
3. **Modify the YAML** configuration for your database
4. **Deploy your API** using the generated configuration

**Your database-driven REST API is just a YAML file away!** 🚀