---
title: LightAPI Documentation
description: Enterprise-grade REST API framework for Python
---

# LightAPI Documentation

**LightAPI** is a lightweight, powerful API framework built on top of Starlette and SQLAlchemy, designed for rapid development of RESTful APIs in Python. It provides a simple yet flexible way to build production-ready APIs with minimal boilerplate code.

## Key Features

### 🚀 **Rapid Development**
- **Zero-boilerplate REST endpoints** - Create full CRUD APIs with just a few lines of code
- **Automatic OpenAPI/Swagger documentation** - Interactive API docs generated automatically
- **Built-in validation** - Request/response validation with customizable validators
- **Database integration** - Seamless SQLAlchemy integration with automatic table creation

### 🔒 **Security & Authentication**
- **JWT Authentication** - Built-in JSON Web Token support
- **Flexible authentication system** - Easy to extend with custom authentication methods
- **CORS support** - Built-in Cross-Origin Resource Sharing middleware
- **Request/response middleware** - Custom middleware for security, logging, and more

### ⚡ **Performance & Scalability**
- **Redis caching** - Built-in caching system with Redis support
- **Query optimization** - Automatic query filtering and pagination
- **Asynchronous support** - Full async/await support for high performance
- **Middleware system** - Efficient request/response processing pipeline

### 🛠 **Developer Experience**
- **Type hints** - Full type annotation support for better IDE experience
- **Comprehensive testing** - Built-in testing utilities and examples
- **Hot reload** - Development server with automatic code reloading
- **Rich error handling** - Detailed error messages and debugging support

## Quick Start

### Installation

```bash
pip install lightapi
```

### Basic Example

Create a simple REST API in just a few lines:

```python
from sqlalchemy import Column, Integer, String
from lightapi import LightApi, RestEndpoint, Base, register_model_class

@register_model_class
class User(RestEndpoint):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    email = Column(String(100))

# Create and run the API
app = LightApi(database_url="sqlite:///app.db")
app.register({'/users': User})
app.run()
```

This creates a full REST API with:
- `GET /users` - List all users
- `POST /users` - Create a new user  
- `PUT /users` - Update a user
- `DELETE /users` - Delete a user
- Automatic Swagger documentation at `/docs`

## Architecture Overview

LightAPI follows a modular architecture with clear separation of concerns:

```mermaid
graph TB
    A[HTTP Request] --> B[Middleware Pipeline]
    B --> C[Authentication]
    C --> D[Request Validation]
    D --> E[RestEndpoint]
    E --> F[Database/Business Logic]
    F --> G[Response Formatting]
    G --> H[Caching]
    H --> I[HTTP Response]
    
    subgraph "Core Components"
        J[LightApi App]
        K[RestEndpoint]
        L[Authentication]
        M[Validation]
        N[Caching]
        O[Pagination]
        P[Filtering]
    end
```

## Core Concepts

### RestEndpoint
The foundation of LightAPI - combines SQLAlchemy models with REST endpoint logic:
- **Database Model**: Defines table structure and relationships
- **HTTP Methods**: Handles GET, POST, PUT, DELETE, PATCH, OPTIONS
- **Configuration**: Customizes authentication, validation, caching, and more

### Middleware System
Flexible request/response processing pipeline:
- **Built-in middleware**: CORS, Authentication, Error handling
- **Custom middleware**: Easy to create and integrate
- **Order matters**: Middleware processes requests in registration order

### Configuration System
Environment-based configuration with sensible defaults:
- **Database settings**: Connection strings and options
- **Security settings**: JWT secrets, CORS origins
- **API documentation**: Swagger/OpenAPI configuration
- **Cache settings**: Redis connection and timeout options

## What Makes LightAPI Different?

| Feature | LightAPI | FastAPI | Flask-RESTful | Django REST |
|---------|----------|---------|---------------|-------------|
| **Zero Boilerplate** | ✅ | ❌ | ❌ | ❌ |
| **Built-in ORM** | ✅ | ❌ | ❌ | ✅ |
| **Auto CRUD** | ✅ | ❌ | ❌ | ❌ |
| **Auto Swagger** | ✅ | ✅ | ❌ | ✅ |
| **Built-in Auth** | ✅ | ❌ | ❌ | ✅ |
| **Caching** | ✅ | ❌ | ❌ | ✅ |
| **Learning Curve** | Low | Medium | Medium | High |

## Getting Started

Ready to build your first API? Check out our guides:

1. **[Getting Started](getting-started/)** - Basic setup and your first API
2. **[Tutorial](tutorial/)** - Step-by-step walkthrough
3. **[Examples](examples/)** - Real-world examples and patterns
4. **[API Reference](api-reference/)** - Complete API documentation

## Community & Support

- **GitHub**: [LightAPI Repository](https://github.com/henriqueblobato/LightApi)
- **Issues**: [Report bugs or request features](https://github.com/henriqueblobato/LightApi/issues)
- **Discussions**: Share ideas and get help from the community

## License

LightAPI is released under the [MIT License](https://github.com/henriqueblobato/LightApi/blob/main/LICENSE).

---

*Built with ❤️ for Python developers who value simplicity and productivity.*

