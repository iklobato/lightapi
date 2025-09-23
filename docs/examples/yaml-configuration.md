# YAML Configuration Guide

LightAPI's YAML configuration system allows you to create fully functional REST APIs without writing any Python code. Simply define your database connection and table operations in a YAML file, and LightAPI will automatically generate all the necessary endpoints.

## Overview

The YAML configuration system uses **database reflection** to automatically discover your existing database tables and their schemas, then generates REST endpoints based on your configuration. This approach is perfect for:

- **Rapid prototyping** - Get an API running in minutes
- **Legacy database integration** - Expose existing databases as modern REST APIs
- **Microservices** - Create lightweight, single-purpose APIs
- **Analytics and reporting** - Read-only APIs for data visualization
- **Multi-environment deployment** - Different configurations for dev/staging/production

## Basic Structure

Every YAML configuration file follows this basic structure:

```yaml
# Database connection (required)
database_url: "sqlite:///my_database.db"

# API metadata (optional)
swagger_title: "My API"
swagger_version: "1.0.0"
swagger_description: "API description"
enable_swagger: true

# Tables to expose as API endpoints (required)
tables:
  - name: users
    crud: [get, post, put, delete]
  - name: posts
    crud: [get, post]
```

## Configuration Options

### Database Connection

The `database_url` field specifies how to connect to your database:

```yaml
# SQLite (file-based)
database_url: "sqlite:///path/to/database.db"

# PostgreSQL
database_url: "postgresql://username:password@host:port/database"

# MySQL
database_url: "mysql+pymysql://username:password@host:port/database"

# Environment variables
database_url: "${DATABASE_URL}"
```

### API Documentation

Configure the automatically generated Swagger/OpenAPI documentation:

```yaml
swagger_title: "My Company API"
swagger_version: "2.0.0"
swagger_description: |
  Complete API for managing company resources
  
  ## Features
  - User management
  - Product catalog
  - Order processing
enable_swagger: true  # Set to false in production
```

### Table Configuration

The `tables` section defines which database tables to expose as REST endpoints:

```yaml
tables:
  # Full CRUD operations
  - name: users
    crud: [get, post, put, patch, delete]
  
  # Limited operations
  - name: posts
    crud: [get, post, put]  # No delete
  
  # Read-only
  - name: analytics
    crud: [get]
  
  # Create-only (like logs)
  - name: audit_log
    crud: [post]
```

## CRUD Operations

Each CRUD operation maps to specific HTTP methods and endpoints:

| CRUD Operation | HTTP Method | Endpoint | Description |
|----------------|-------------|----------|-------------|
| `get` | GET | `/table/` | List all records |
| `get` | GET | `/table/{id}` | Get specific record |
| `post` | POST | `/table/` | Create new record |
| `put` | PUT | `/table/{id}` | Update entire record |
| `patch` | PATCH | `/table/{id}` | Partially update record |
| `delete` | DELETE | `/table/{id}` | Delete record |

## Environment Variables

Use environment variables for flexible deployment across different environments:

```yaml
# Development configuration
database_url: "${DEV_DATABASE_URL}"
swagger_title: "${API_TITLE}"
enable_swagger: true

tables:
  - name: users
    crud: [get, post, put, patch, delete]  # Full access in dev
```

```yaml
# Production configuration  
database_url: "${PROD_DATABASE_URL}"
swagger_title: "${API_TITLE}"
enable_swagger: false  # Disabled in production

tables:
  - name: users
    crud: [get, patch]  # Limited access in production
```

Set environment variables before running:

```bash
export DEV_DATABASE_URL="sqlite:///dev.db"
export PROD_DATABASE_URL="postgresql://user:pass@prod-db:5432/app"
export API_TITLE="Company API"
```

## Complete Examples

### 1. Basic Blog API

```yaml
# blog_api.yaml
database_url: "sqlite:///blog.db"
swagger_title: "Simple Blog API"
swagger_version: "1.0.0"
enable_swagger: true

tables:
  # Posts - full management
  - name: posts
    crud: [get, post, put, delete]
  
  # Comments - read-only to prevent spam
  - name: comments
    crud: [get]
  
  # Users - limited operations
  - name: users
    crud: [get, post, patch]
```

**Usage:**
```python
from lightapi import LightApi

app = LightApi.from_config('blog_api.yaml')
app.run()
```

### 2. E-commerce API with Role-Based Permissions

```yaml
# ecommerce_api.yaml
database_url: "${DATABASE_URL}"
swagger_title: "E-commerce Management API"
swagger_version: "2.0.0"
swagger_description: |
  E-commerce API with role-based permissions
  
  ## Permission Levels
  - Admin: Full user management
  - Manager: Product and inventory management  
  - Customer: Order creation and viewing
enable_swagger: true

tables:
  # ADMIN LEVEL - Full user management
  - name: users
    crud: [get, post, put, patch, delete]
  
  # MANAGER LEVEL - Product management
  - name: products
    crud: [get, post, put, patch, delete]
  
  # MANAGER LEVEL - Category management (no delete for data integrity)
  - name: categories
    crud: [get, post, put, patch]
  
  # CUSTOMER LEVEL - Order management
  - name: orders
    crud: [get, post, patch]  # Create orders, update status only
  
  # READ-ONLY - Order details (managed through orders)
  - name: order_items
    crud: [get]
  
  # READ-ONLY - Audit trail for security
  - name: audit_log
    crud: [get]
```

### 3. Analytics API (Read-Only)

```yaml
# analytics_api.yaml
database_url: "postgresql://readonly:${DB_PASSWORD}@analytics-db:5432/data"
swagger_title: "Analytics Data API"
swagger_version: "1.0.0"
swagger_description: |
  Read-only analytics API for business intelligence
  
  ## Data Sources
  - Website analytics
  - Sales performance
  - User behavior metrics
  - Monthly reports
enable_swagger: true

tables:
  # All tables are read-only for security
  - name: page_views
    crud: [get]
  
  - name: user_sessions
    crud: [get]
  
  - name: sales_data
    crud: [get]
  
  - name: monthly_reports
    crud: [get]
```

### 4. Multi-Database Configuration

```yaml
# multi_db_api.yaml
database_url: "${PRIMARY_DATABASE_URL}"
swagger_title: "Multi-Database API"
swagger_version: "3.0.0"
swagger_description: |
  Flexible API supporting multiple database backends
  
  Supported databases:
  - SQLite: sqlite:///database.db
  - PostgreSQL: postgresql://user:pass@host:port/db
  - MySQL: mysql+pymysql://user:pass@host:port/db
enable_swagger: true

tables:
  - name: companies
    crud: [get, post, put, patch, delete]
  
  - name: employees
    crud: [get, post, put, patch, delete]
  
  - name: projects
    crud: [get, post, put, patch, delete]
```

## Running Your API

Once you have a YAML configuration file, running your API is simple:

```python
from lightapi import LightApi

# Create API from YAML configuration
app = LightApi.from_config('your_config.yaml')

# Run the server
app.run(host='0.0.0.0', port=8000)
```

Your API will be available at:
- **API Endpoints**: http://localhost:8000/
- **Swagger Documentation**: http://localhost:8000/docs
- **OpenAPI Spec**: http://localhost:8000/openapi.json

## Testing Your API

### Using curl

```bash
# Get all users
curl http://localhost:8000/users/

# Create a new user
curl -X POST http://localhost:8000/users/ \
  -H 'Content-Type: application/json' \
  -d '{"name": "John Doe", "email": "john@example.com"}'

# Get specific user
curl http://localhost:8000/users/1

# Update user
curl -X PUT http://localhost:8000/users/1 \
  -H 'Content-Type: application/json' \
  -d '{"name": "John Updated", "email": "john.updated@example.com"}'

# Delete user
curl -X DELETE http://localhost:8000/users/1
```

### Using the Swagger UI

Visit http://localhost:8000/docs in your browser for an interactive API documentation interface where you can:
- Browse all available endpoints
- Test API calls directly from the browser
- View request/response schemas
- Download the OpenAPI specification

## Configuration Patterns

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

### Create + Read (Blog Posts)
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

## Best Practices

### Security
- Use environment variables for database credentials
- Disable Swagger documentation in production (`enable_swagger: false`)
- Limit CRUD operations based on user roles
- Use read-only configurations for public APIs

### Performance
- Use connection pooling for production databases
- Consider read replicas for read-heavy workloads
- Implement caching for frequently accessed data

### Deployment
- Use different YAML files for different environments
- Set up proper database migrations
- Monitor API performance and usage
- Implement proper logging and error tracking

## Troubleshooting

### Common Issues

**Table not found error:**
```
Table 'users' not found: Could not reflect: requested table(s) not available
```
- Ensure the table exists in your database
- Check the database connection string
- Verify table name spelling

**Connection refused:**
```
Connection refused: could not connect to server
```
- Check database server is running
- Verify connection string format
- Ensure network connectivity

**Permission denied:**
```
Permission denied for table users
```
- Check database user permissions
- Ensure user has SELECT/INSERT/UPDATE/DELETE privileges as needed

### Getting Help

- Check the [Troubleshooting Guide](../troubleshooting.md)
- Review the [Examples Directory](../../examples/) for working configurations
- Open an issue on GitHub for bugs or feature requests

## Next Steps

- Explore [Advanced Features](../advanced/) for authentication, caching, and middleware
- Check out [Deployment Guides](../deployment/) for production setup
- Browse [Real-World Examples](../../examples/) for inspiration
- Read the [API Reference](../api-reference/) for detailed documentation

The YAML configuration system makes LightAPI incredibly powerful for rapid API development. With just a few lines of YAML, you can expose your entire database as a modern REST API with full documentation and validation.