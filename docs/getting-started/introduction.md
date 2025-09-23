---
title: Introduction to LightAPI
description: Learn about LightAPI's core concepts and architecture
---

# Introduction to LightAPI

**LightAPI** is a powerful yet lightweight Python framework for building REST APIs with minimal code. Built on aiohttp and SQLAlchemy, it automatically generates REST APIs from your existing database tables using either Python code or simple YAML configuration files.

## What Makes LightAPI Special?

LightAPI bridges the gap between rapid prototyping and production-ready APIs. Whether you're exposing an existing database as a REST API or building a new application from scratch, LightAPI provides the tools you need with minimal configuration.

### 🚀 **Zero-Code API Generation**

The standout feature of LightAPI is its ability to create fully functional REST APIs from YAML configuration files:

```yaml
# config.yaml
database_url: "sqlite:///my_app.db"
swagger_title: "My API"
enable_swagger: true

tables:
  - name: users
    crud: [get, post, put, delete]
  - name: posts
    crud: [get, post]
```

```python
from lightapi import LightApi

app = LightApi.from_config('config.yaml')
app.run()
```

**That's it!** You now have a fully functional REST API with:
- Full CRUD operations
- Automatic input validation
- Interactive Swagger documentation
- Proper HTTP status codes
- Error handling

## Key Features

### 🔥 **Core Features**
- **Zero-Code APIs**: Create REST APIs from YAML configuration files
- **Database Reflection**: Automatically discovers existing database tables
- **Full CRUD Operations**: GET, POST, PUT, PATCH, DELETE operations
- **Multiple Databases**: SQLite, PostgreSQL, MySQL support via SQLAlchemy
- **Async/Await Support**: Built on aiohttp for high performance

### 🔐 **Security & Authentication**
- **JWT Authentication**: Built-in JSON Web Token support
- **CORS Support**: Cross-Origin Resource Sharing middleware
- **Input Validation**: Automatic validation based on database schema
- **Role-Based Permissions**: Control operations per table/user role

### ⚡ **Performance & Scalability**
- **Redis Caching**: Built-in caching with TTL management
- **Query Optimization**: Automatic filtering, pagination, and sorting
- **Connection Pooling**: Efficient database connection management
- **Async Operations**: Non-blocking request handling

### 🛠️ **Developer Experience**
- **Auto Documentation**: Interactive Swagger/OpenAPI documentation
- **Environment Variables**: Flexible deployment configurations
- **Comprehensive Examples**: Real-world examples for all features
- **Rich Error Handling**: Detailed error messages and debugging

## Core Concepts

### 1. Database Reflection

LightAPI uses **SQLAlchemy reflection** to automatically discover your existing database schema:

- **Table Structure**: Automatically detects columns, data types, and constraints
- **Relationships**: Handles foreign keys and table relationships
- **Validation**: Uses database constraints for automatic input validation
- **Multiple Databases**: Supports SQLite, PostgreSQL, MySQL

### 2. CRUD Operations

Each table can be configured with specific CRUD operations:

| Operation | HTTP Method | Endpoint | Description |
|-----------|-------------|----------|-------------|
| `get` | GET | `/table/` | List all records |
| `get` | GET | `/table/{id}` | Get specific record |
| `post` | POST | `/table/` | Create new record |
| `put` | PUT | `/table/{id}` | Update entire record |
| `patch` | PATCH | `/table/{id}` | Partially update record |
| `delete` | DELETE | `/table/{id}` | Delete record |

### 3. Configuration-Driven Development

LightAPI supports two development approaches:

#### YAML Configuration (Recommended)
- **Zero Python code** required
- **Database reflection** for automatic schema discovery
- **Environment variables** for flexible deployment
- **Role-based permissions** through selective CRUD operations

#### Python Code (Traditional)
- **Full control** over models and endpoints
- **Custom business logic** and validation
- **Advanced features** like custom middleware
- **SQLAlchemy models** with automatic REST endpoints

## Use Cases

### 🚀 **Rapid Prototyping**
```yaml
# prototype.yaml - MVP in minutes
database_url: "sqlite:///prototype.db"
tables:
  - name: users
    crud: [get, post]
  - name: posts
    crud: [get, post]
```

### 🏢 **Enterprise Applications**
```yaml
# enterprise.yaml - Production-ready
database_url: "${DATABASE_URL}"
enable_swagger: false  # Disabled in production

tables:
  - name: users
    crud: [get, post, put, patch, delete]  # Full admin access
  - name: orders
    crud: [get, post, patch]  # Limited operations
  - name: audit_log
    crud: [get]  # Read-only for compliance
```

### 📊 **Analytics APIs**
```yaml
# analytics.yaml - Read-only data access
database_url: "postgresql://readonly@analytics-db/data"
tables:
  - name: page_views
    crud: [get]
  - name: sales_data
    crud: [get]
```

## Framework Philosophy

### Simplicity First
- **Minimal configuration** required to get started
- **Sensible defaults** for common use cases
- **Clear error messages** for debugging
- **Intuitive API design** that follows REST conventions

### Production Ready
- **Async/await support** for high performance
- **Built-in security** features (JWT, CORS, validation)
- **Caching support** with Redis integration
- **Environment-based configuration** for deployment
- **Comprehensive error handling** and logging

### Developer Experience
- **Interactive documentation** with Swagger UI
- **Hot reloading** during development
- **Type hints** for better IDE support
- **Comprehensive examples** and documentation

## Who Should Use LightAPI?

### ✅ **Perfect For:**
- Exposing existing databases as REST APIs
- Rapid prototyping and MVP development
- Microservices with simple CRUD operations
- Analytics and reporting APIs
- Legacy system modernization
- Teams that prefer configuration over code

### ⚠️ **Consider Alternatives For:**
- Complex business logic requiring extensive custom code
- GraphQL APIs (LightAPI focuses on REST)
- Real-time applications requiring WebSockets
- Applications requiring extensive custom authentication flows

## Comparison with Other Frameworks

| Feature | LightAPI | FastAPI | Flask | Django REST |
|---------|----------|---------|-------|-------------|
| **Zero-Code APIs** | ✅ YAML Config | ❌ | ❌ | ❌ |
| **Database Reflection** | ✅ Automatic | ❌ | ❌ | ❌ |
| **Auto CRUD** | ✅ Built-in | ❌ Manual | ❌ Manual | ✅ Complex |
| **Async Support** | ✅ Native | ✅ Native | ❌ | ❌ |
| **Auto Documentation** | ✅ Swagger | ✅ Swagger | ❌ | ✅ Complex |
| **Learning Curve** | 🟢 Easy | 🟡 Medium | 🟢 Easy | 🔴 Hard |
| **Setup Time** | 🟢 Minutes | 🟡 Hours | 🟡 Hours | 🔴 Days |

## Getting Started

Ready to build your first API? Here's your learning path:

### 🚀 **Quick Start (5 minutes)**
1. [Installation](installation.md) - Set up LightAPI
2. [Quickstart](quickstart.md) - Your first API in 5 minutes

### 📚 **Deep Dive**
1. [Configuration Guide](configuration.md) - YAML and Python configuration
2. [Tutorial](../tutorial/basic-api.md) - Step-by-step API building
3. [Examples](../examples/) - Real-world examples and patterns

### 🔧 **Advanced Topics**
1. [Authentication](../advanced/authentication.md) - Secure your APIs
2. [Caching](../advanced/caching.md) - Improve performance
3. [Deployment](../deployment/production.md) - Production setup

---

**Ready to transform your database into a REST API?** Let's start with the [Installation Guide](installation.md)! 