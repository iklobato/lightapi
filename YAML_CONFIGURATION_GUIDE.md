# LightAPI YAML Configuration Guide

## 🎯 Overview

LightAPI's YAML configuration system allows you to create complete REST APIs from existing database tables without writing Python code. Simply define your database connection and specify which tables should have API endpoints.

## 🚀 Quick Start

### 1. Basic YAML Configuration

```yaml
# config.yaml
database_url: "sqlite:///my_database.db"
swagger_title: "My API"
swagger_version: "1.0.0"
swagger_description: "API generated from database tables"
enable_swagger: true

tables:
  - name: users
    crud: [get, post, put, delete]
  - name: products
    crud: [get, post, put, patch, delete]
  - name: categories
    crud: [get, post]
```

### 2. Run Your API

```python
from lightapi import LightApi

# Create API from YAML configuration
app = LightApi.from_config('config.yaml')

# Start the server
app.run()
```

That's it! Your API is now running with:
- Full CRUD endpoints for your tables
- Automatic OpenAPI/Swagger documentation
- Database reflection and validation

## 📋 Configuration Reference

### Core Configuration

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `database_url` | string | ✅ | Database connection URL |
| `swagger_title` | string | ❌ | API title in documentation |
| `swagger_version` | string | ❌ | API version |
| `swagger_description` | string | ❌ | API description |
| `enable_swagger` | boolean | ❌ | Enable Swagger UI (default: true) |
| `tables` | array | ✅ | List of tables to expose as API |

### Database URL Formats

```yaml
# SQLite
database_url: "sqlite:///path/to/database.db"
database_url: "sqlite:///./relative/path.db"

# PostgreSQL
database_url: "postgresql://username:password@localhost:5432/database_name"
database_url: "postgresql+psycopg2://user:pass@localhost/db"

# MySQL
database_url: "mysql+pymysql://username:password@localhost:3306/database_name"
database_url: "mysql://user:pass@localhost/db"

# Environment Variables
database_url: "${DATABASE_URL}"  # Reads from environment variable
```

### Table Configuration

#### Simple Format
```yaml
tables:
  - name: users
    crud: [get, post, put, delete]
```

#### Detailed Format
```yaml
tables:
  - name: users
    crud: 
      - get     # GET /users/ and GET /users/{id}
      - post    # POST /users/
      - put     # PUT /users/{id}
      - patch   # PATCH /users/{id}
      - delete  # DELETE /users/{id}
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

## 🎨 Configuration Examples

### 1. Basic E-commerce API

```yaml
# ecommerce_basic.yaml
database_url: "sqlite:///ecommerce.db"
swagger_title: "E-commerce API"
swagger_version: "1.0.0"
swagger_description: "Simple e-commerce REST API"
enable_swagger: true

tables:
  - name: products
    crud: [get, post, put, delete]
  - name: categories
    crud: [get, post, put, delete]
  - name: customers
    crud: [get, post, put, delete]
  - name: orders
    crud: [get, post, put, delete]
```

**Generated Endpoints:**
- `GET/POST /products/` - List/Create products
- `GET/PUT/DELETE /products/{id}` - Get/Update/Delete product
- `GET/POST /categories/` - List/Create categories
- `GET/PUT/DELETE /categories/{id}` - Get/Update/Delete category
- Similar patterns for customers and orders

### 2. Role-Based Access API

```yaml
# role_based.yaml
database_url: "postgresql://user:pass@localhost/mydb"
swagger_title: "Role-Based Store API"
swagger_version: "2.0.0"
enable_swagger: true

tables:
  # Full access for admins
  - name: users
    crud: [get, post, put, patch, delete]
  
  # Products - full CRUD
  - name: products
    crud: [get, post, put, patch, delete]
  
  # Categories - no delete (preserve data integrity)
  - name: categories
    crud: [get, post, put]
  
  # Orders - create and update status only
  - name: orders
    crud: [get, post, patch]
  
  # Order items - read only (managed through orders)
  - name: order_items
    crud: [get]
  
  # Settings - read only
  - name: settings
    crud: [get]
```

### 3. Read-Only Data API

```yaml
# readonly_api.yaml
database_url: "mysql://user:pass@localhost/analytics_db"
swagger_title: "Analytics Data API"
swagger_version: "1.0.0"
swagger_description: "Read-only access to analytics data"
enable_swagger: true

tables:
  - name: sales_data
    crud: [get]
  - name: customer_metrics
    crud: [get]
  - name: product_performance
    crud: [get]
  - name: monthly_reports
    crud: [get]
```

### 4. Minimal API

```yaml
# minimal.yaml
database_url: "sqlite:///minimal.db"
swagger_title: "Minimal API"
enable_swagger: true

tables:
  - name: posts
    crud: [get, post]  # Browse and create only
  - name: comments
    crud: [get]        # Read-only
```

### 5. Environment-Based Configuration

```yaml
# production.yaml
database_url: "${DATABASE_URL}"
swagger_title: "${API_TITLE}"
swagger_version: "${API_VERSION}"
swagger_description: "${API_DESCRIPTION}"
enable_swagger: true

tables:
  - name: users
    crud: [get, post, put, delete]
  - name: products
    crud: [get, post, put, delete]
```

**Environment Variables:**
```bash
export DATABASE_URL="postgresql://user:pass@prod-db:5432/myapp"
export API_TITLE="Production API"
export API_VERSION="2.1.0"
export API_DESCRIPTION="Production REST API for MyApp"
```

## 🔧 Advanced Features

### Database Reflection

LightAPI automatically reflects your database schema:

```python
# Your existing database tables are automatically discovered
# Primary keys, foreign keys, and constraints are respected
# Data types are automatically mapped to JSON schema
```

### Automatic Validation

Based on your database schema:
- **Required fields**: NOT NULL columns are required
- **Unique constraints**: Enforced automatically
- **Foreign keys**: Validated automatically
- **Data types**: Automatic type conversion and validation

### Error Handling

Standard HTTP status codes:
- `200` - Success
- `201` - Created
- `400` - Bad Request (validation errors)
- `404` - Not Found
- `409` - Conflict (unique constraint violations)
- `500` - Internal Server Error

## 🚀 Running Your API

### Method 1: Python Script

```python
# run_api.py
from lightapi import LightApi

app = LightApi.from_config('config.yaml')
app.run(host='0.0.0.0', port=8000)
```

```bash
python run_api.py
```

### Method 2: Command Line

```python
# One-liner
python -c "from lightapi import LightApi; LightApi.from_config('config.yaml').run()"
```

### Method 3: Production Deployment

```python
# app.py
from lightapi import LightApi

app = LightApi.from_config('config.yaml')

# For ASGI servers like uvicorn, gunicorn
if __name__ == "__main__":
    app.run()
```

```bash
# Development
python app.py

# Production with uvicorn
uvicorn app:app --host 0.0.0.0 --port 8000

# Production with gunicorn
gunicorn app:app -w 4 -k uvicorn.workers.UvicornWorker
```

## 📖 API Documentation

### Swagger UI

Visit `http://localhost:8000/docs` for interactive API documentation.

### OpenAPI Specification

Get the OpenAPI JSON at `http://localhost:8000/openapi.json`.

### Custom Documentation

```yaml
swagger_title: "My Custom API"
swagger_version: "2.1.0"
swagger_description: |
  This is a comprehensive API for managing our application data.
  
  ## Authentication
  Some endpoints may require authentication.
  
  ## Rate Limiting
  API calls are limited to 1000 requests per hour.
  
  ## Support
  Contact support@mycompany.com for help.
```

## 🧪 Testing Your API

### Using curl

```bash
# Get all users
curl http://localhost:8000/users/

# Create a user
curl -X POST http://localhost:8000/users/ \
  -H "Content-Type: application/json" \
  -d '{"name": "John Doe", "email": "john@example.com"}'

# Get specific user
curl http://localhost:8000/users/1

# Update user
curl -X PUT http://localhost:8000/users/1 \
  -H "Content-Type: application/json" \
  -d '{"name": "John Smith", "email": "john.smith@example.com"}'

# Delete user
curl -X DELETE http://localhost:8000/users/1
```

### Using Python requests

```python
import requests

base_url = "http://localhost:8000"

# Get all products
response = requests.get(f"{base_url}/products/")
products = response.json()

# Create a product
new_product = {
    "name": "New Product",
    "price": 29.99,
    "category_id": 1
}
response = requests.post(f"{base_url}/products/", json=new_product)
created_product = response.json()

# Update product
updated_data = {"price": 24.99}
response = requests.patch(f"{base_url}/products/{created_product['id']}", json=updated_data)
```

## 🔍 Database Requirements

### Supported Databases

- **SQLite** - File-based database (great for development)
- **PostgreSQL** - Production-ready relational database
- **MySQL** - Popular relational database
- **Any SQLAlchemy-supported database**

### Table Requirements

1. **Primary Key**: Each table must have a primary key
2. **Existing Tables**: Tables must exist in the database
3. **Proper Schema**: Well-defined column types and constraints

### Sample Database Schema

```sql
-- Users table
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    full_name VARCHAR(100),
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Products table
CREATE TABLE products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    price DECIMAL(10,2) NOT NULL,
    category_id INTEGER,
    sku VARCHAR(50) UNIQUE,
    stock_quantity INTEGER DEFAULT 0,
    FOREIGN KEY (category_id) REFERENCES categories(id)
);

-- Categories table
CREATE TABLE categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    parent_id INTEGER,
    FOREIGN KEY (parent_id) REFERENCES categories(id)
);
```

## ⚠️ Limitations and Considerations

### Current Limitations

1. **Authentication**: YAML config doesn't include authentication setup
2. **Custom Validation**: No custom validation rules in YAML
3. **Middleware**: No custom middleware configuration
4. **Relationships**: No automatic relationship handling in responses
5. **Filtering**: No built-in filtering/pagination configuration

### Security Considerations

1. **Database Access**: Ensure proper database permissions
2. **Network Security**: Use HTTPS in production
3. **Input Validation**: Database constraints provide basic validation
4. **Rate Limiting**: Consider adding rate limiting middleware
5. **Authentication**: Add authentication for sensitive endpoints

### Performance Considerations

1. **Database Indexes**: Ensure proper indexing for performance
2. **Connection Pooling**: Configure appropriate connection pools
3. **Caching**: Consider adding caching for frequently accessed data
4. **Pagination**: Large datasets may need pagination

## 🎯 Best Practices

### 1. Configuration Organization

```yaml
# Use clear, descriptive names
swagger_title: "Company Product API"
swagger_description: "Internal API for product management"

# Group related tables
tables:
  # Core entities
  - name: users
    crud: [get, post, put, delete]
  - name: products
    crud: [get, post, put, delete]
  
  # Reference data (limited operations)
  - name: categories
    crud: [get, post, put]
  - name: settings
    crud: [get]
```

### 2. Environment Management

```yaml
# development.yaml
database_url: "sqlite:///dev.db"
enable_swagger: true

# production.yaml
database_url: "${DATABASE_URL}"
enable_swagger: false  # Disable in production
```

### 3. Incremental Development

Start minimal and expand:

```yaml
# Phase 1: Read-only
tables:
  - name: products
    crud: [get]

# Phase 2: Add creation
tables:
  - name: products
    crud: [get, post]

# Phase 3: Full CRUD
tables:
  - name: products
    crud: [get, post, put, delete]
```

### 4. Documentation

```yaml
swagger_description: |
  # Product Management API
  
  This API provides access to our product catalog.
  
  ## Endpoints
  - `/products/` - Product management
  - `/categories/` - Category management
  
  ## Data Format
  All dates are in ISO 8601 format.
  All prices are in USD cents.
```

## 🚀 Next Steps

1. **Create your YAML config** based on your database
2. **Test with a simple configuration** first
3. **Add more tables and operations** incrementally
4. **Deploy to production** with environment variables
5. **Add authentication and middleware** as needed
6. **Monitor and optimize** performance

## 📚 Examples Repository

Check the `examples/` directory for:
- `yaml_comprehensive_example.py` - Complete demonstration
- `config_basic.yaml` - Basic configuration
- `config_advanced.yaml` - Advanced configuration
- `config_readonly.yaml` - Read-only API
- `config_minimal.yaml` - Minimal setup

---

**Ready to create your database-driven API? Start with a simple YAML file and watch your API come to life!** 🎉