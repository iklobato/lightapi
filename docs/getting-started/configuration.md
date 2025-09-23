---
title: Configuration Guide
description: Complete guide to configuring LightAPI applications
---

# Configuration Guide

LightAPI offers flexible configuration options to suit different development and deployment scenarios. This guide covers both YAML-based configuration (recommended for most use cases) and Python-based configuration for advanced customization.

## Configuration Methods

LightAPI supports two primary configuration approaches:

1. **YAML Configuration** (Recommended) - Zero-code API generation
2. **Python Configuration** - Full programmatic control

## YAML Configuration (Recommended)

YAML configuration allows you to create fully functional REST APIs without writing Python code. This approach uses database reflection to automatically discover your schema and generate endpoints.

### Basic YAML Structure

```yaml
# config.yaml
database_url: "sqlite:///my_app.db"
swagger_title: "My API"
swagger_version: "1.0.0"
swagger_description: "API generated from YAML configuration"
enable_swagger: true

tables:
  - name: users
    crud: [get, post, put, delete]
  - name: posts
    crud: [get, post, put]
  - name: comments
    crud: [get]  # Read-only
```

### YAML Configuration Options

#### Database Configuration

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

#### API Documentation

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

#### Table Configuration

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

### CRUD Operations Mapping

| CRUD Operation | HTTP Method | Endpoint | Description |
|----------------|-------------|----------|-------------|
| `get` | GET | `/table/` | List all records |
| `get` | GET | `/table/{id}` | Get specific record |
| `post` | POST | `/table/` | Create new record |
| `put` | PUT | `/table/{id}` | Update entire record |
| `patch` | PATCH | `/table/{id}` | Partially update record |
| `delete` | DELETE | `/table/{id}` | Delete record |

### Environment Variables in YAML

Use environment variables for flexible deployment:

```yaml
# config.yaml
database_url: "${DATABASE_URL}"
swagger_title: "${API_TITLE}"
enable_swagger: ${ENABLE_SWAGGER:true}  # Default to true

tables:
  - name: users
    crud: [get, post, put, patch, delete]
```

Set environment variables:

```bash
export DATABASE_URL="postgresql://user:pass@localhost:5432/mydb"
export API_TITLE="Production API"
export ENABLE_SWAGGER="false"
```

### Loading YAML Configuration

```python
from lightapi import LightApi

# Create API from YAML configuration
app = LightApi.from_config('config.yaml')
app.run()
```

## Python Configuration

For advanced use cases requiring custom logic, use Python-based configuration:

### Basic Python Configuration

```python
from lightapi import LightApi

app = LightApi(
    database_url="sqlite:///my_app.db",
    swagger_title="My API",
    swagger_version="1.0.0",
    enable_swagger=True,
    cors_origins=["http://localhost:3000"],
    debug=True
)
```

### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `database_url` | str | Required | Database connection string |
| `swagger_title` | str | "LightAPI" | API title in documentation |
| `swagger_version` | str | "1.0.0" | API version |
| `swagger_description` | str | None | API description |
| `enable_swagger` | bool | True | Enable Swagger UI |
| `cors_origins` | List[str] | [] | CORS allowed origins |
| `debug` | bool | False | Enable debug mode |
| `host` | str | "127.0.0.1" | Server host |
| `port` | int | 8000 | Server port |

### Advanced Python Configuration

```python
from lightapi import LightApi
from lightapi.auth import JWTAuth
from lightapi.cache import RedisCache

# Advanced configuration
app = LightApi(
    database_url="postgresql://user:pass@localhost:5432/mydb",
    swagger_title="Advanced API",
    swagger_version="2.0.0",
    enable_swagger=True,
    cors_origins=["https://myapp.com", "https://admin.myapp.com"],
    debug=False
)

# Add authentication
jwt_auth = JWTAuth(secret_key="your-secret-key")
app.add_middleware(jwt_auth)

# Add caching
redis_cache = RedisCache(url="redis://localhost:6379")
app.add_cache(redis_cache)
```

## Environment Variables

LightAPI supports environment variables for configuration:

### Standard Environment Variables

```bash
# Database
DATABASE_URL=sqlite:///app.db

# Server
HOST=0.0.0.0
PORT=8000
DEBUG=false

# API Documentation
SWAGGER_TITLE="My API"
SWAGGER_VERSION="1.0.0"
ENABLE_SWAGGER=true

# Security
CORS_ORIGINS=["https://myapp.com"]
JWT_SECRET=your-secret-key

# Caching
REDIS_URL=redis://localhost:6379
CACHE_TTL=300
```

### Loading Environment Variables

```python
import os
from dotenv import load_dotenv
from lightapi import LightApi

# Load environment variables from .env file
load_dotenv()

app = LightApi(
    database_url=os.getenv("DATABASE_URL"),
    swagger_title=os.getenv("SWAGGER_TITLE", "My API"),
    enable_swagger=os.getenv("ENABLE_SWAGGER", "true").lower() == "true",
    cors_origins=os.getenv("CORS_ORIGINS", "").split(",") if os.getenv("CORS_ORIGINS") else [],
    debug=os.getenv("DEBUG", "false").lower() == "true"
)
```

## Multi-Environment Configuration

### Development Configuration

```yaml
# development.yaml
database_url: "sqlite:///dev.db"
swagger_title: "Development API"
enable_swagger: true
debug: true

tables:
  - name: users
    crud: [get, post, put, patch, delete]  # Full access in dev
  - name: posts
    crud: [get, post, put, patch, delete]
```

### Staging Configuration

```yaml
# staging.yaml
database_url: "${STAGING_DATABASE_URL}"
swagger_title: "Staging API"
enable_swagger: true
debug: false

tables:
  - name: users
    crud: [get, post, put, patch]  # No delete in staging
  - name: posts
    crud: [get, post, put, patch]
```

### Production Configuration

```yaml
# production.yaml
database_url: "${PROD_DATABASE_URL}"
swagger_title: "Production API"
enable_swagger: false  # Disabled for security
debug: false

tables:
  - name: users
    crud: [get, patch]  # Limited access in production
  - name: posts
    crud: [get, post, patch]
```

### Environment-Specific Deployment

```python
import os
from lightapi import LightApi

# Determine environment
env = os.getenv("ENVIRONMENT", "development")
config_file = f"{env}.yaml"

# Load appropriate configuration
app = LightApi.from_config(config_file)
app.run()
```

```bash
# Development
export ENVIRONMENT=development
python app.py

# Production
export ENVIRONMENT=production
export PROD_DATABASE_URL="postgresql://user:pass@prod-db:5432/app"
python app.py
```

## Configuration Validation

LightAPI automatically validates configuration:

### YAML Validation

```yaml
# Invalid configuration will raise errors
database_url: "invalid-url"  # ❌ Invalid database URL
tables:
  - name: users
    crud: [invalid_operation]  # ❌ Invalid CRUD operation
```

### Python Validation

```python
from lightapi import LightApi

# This will raise a validation error
app = LightApi(
    database_url="invalid-url",  # ❌ Invalid database URL
    cors_origins="not-a-list"    # ❌ Should be a list
)
```

## Configuration Best Practices

### Security

1. **Never commit secrets** to version control
2. **Use environment variables** for sensitive data
3. **Disable Swagger** in production
4. **Limit CORS origins** to specific domains

```yaml
# ✅ Good
database_url: "${DATABASE_URL}"
enable_swagger: false
cors_origins: ["https://myapp.com"]

# ❌ Bad
database_url: "postgresql://user:password@host/db"
enable_swagger: true
cors_origins: ["*"]
```

### Performance

1. **Use connection pooling** for production databases
2. **Enable caching** for frequently accessed data
3. **Limit CRUD operations** based on use case

```yaml
# ✅ Optimized for read-heavy workload
tables:
  - name: analytics
    crud: [get]  # Read-only for performance
  - name: cache_table
    crud: [get, post]  # Limited operations
```

### Maintainability

1. **Use descriptive names** for configurations
2. **Document your YAML** with comments
3. **Separate environments** with different files
4. **Version your configurations**

```yaml
# ✅ Well-documented configuration
# E-commerce API Configuration
# Version: 2.0.0
# Environment: Production

database_url: "${PROD_DATABASE_URL}"
swagger_title: "E-commerce API"
swagger_description: |
  Production API for e-commerce platform
  
  ## Security
  - JWT authentication required
  - Rate limiting enabled
  - CORS restricted to app domains

# User management (admin only)
tables:
  - name: users
    crud: [get, patch]  # Limited for security
```

## Troubleshooting Configuration

### Common Issues

**YAML syntax errors:**
```bash
# Error: Invalid YAML syntax
yaml.scanner.ScannerError: mapping values are not allowed here
```
Solution: Check YAML indentation and syntax

**Database connection errors:**
```bash
# Error: Could not connect to database
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) unable to open database file
```
Solution: Verify database URL and file permissions

**Table not found errors:**
```bash
# Error: Table not found
Table 'users' not found: Could not reflect: requested table(s) not available
```
Solution: Ensure table exists in database

### Debugging Configuration

Enable debug mode to see detailed configuration information:

```python
from lightapi import LightApi

app = LightApi.from_config('config.yaml', debug=True)
```

Or set environment variable:
```bash
export DEBUG=true
python app.py
```

## Next Steps

Now that you understand LightAPI configuration:

1. **[Quickstart Guide](quickstart.md)** - Build your first API
2. **[YAML Configuration Examples](../examples/yaml-configuration.md)** - Real-world examples
3. **[Tutorial](../tutorial/basic-api.md)** - Step-by-step development
4. **[Advanced Features](../advanced/)** - Authentication, caching, and more

---

**Configuration is the foundation of great APIs.** Choose the approach that best fits your project needs and deployment requirements.
