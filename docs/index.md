---
title: LightAPI Documentation
description: Enterprise-grade REST API framework for Python
---

# LightAPI Documentation

**LightAPI** is a production-ready, enterprise-grade REST API framework that combines the power of **Starlette** and **SQLAlchemy** to deliver high-performance APIs with minimal configuration. Built for both rapid prototyping and large-scale enterprise applications.

## What is LightAPI?

LightAPI revolutionizes API development by unifying SQLAlchemy ORM models with REST endpoints in a single class definition. This innovative approach eliminates boilerplate code while maintaining the flexibility and scalability needed for enterprise applications.

### Design Philosophy

- **🎯 Developer-First**: Intuitive API design that reduces cognitive overhead
- **⚡ Performance-Oriented**: Built on Starlette's async foundation for maximum throughput
- **🏗️ Enterprise-Ready**: Comprehensive middleware system for production environments
- **🔧 Highly Configurable**: Extensive customization without sacrificing simplicity
- **📖 Documentation-First**: Auto-generated OpenAPI documentation with rich examples

## Core Architecture

LightAPI integrates proven technologies into a cohesive framework:

- **🔥 Starlette**: High-performance ASGI framework for async HTTP handling
- **🗄️ SQLAlchemy**: Powerful ORM with support for all major databases
- **🚀 Redis**: Enterprise-grade caching and session management
- **🔐 JWT**: Industry-standard authentication with CORS integration
- **📚 OpenAPI**: Automatic documentation generation with Swagger UI

## Quick Start

Get a production-ready API running in under 60 seconds:

```python
from lightapi.rest import RestEndpoint
from lightapi.core import LightApi
from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime

class User(RestEndpoint):
    """User management endpoint with automatic CRUD operations"""
    __tablename__ = 'users'
    
    # SQLAlchemy model definition
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    class Configuration:
        # Enable full CRUD operations
        http_method_names = ['GET', 'POST', 'PUT', 'DELETE']

# Initialize and run
app = LightApi(database_url="sqlite:///app.db")
app.register({'/users': User})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True, reload=True)
```

**Result**: A fully functional API with 8 endpoints, automatic documentation, and startup endpoint listing.

## Enterprise Features

### 🔐 Authentication & Security

**JWT Authentication with CORS Integration**
- Automatic CORS preflight handling
- Role-based access control
- Multi-factor authentication support
- Token refresh mechanisms

```python
from lightapi.auth import JWTAuthentication
from lightapi.core import AuthenticationMiddleware

class SecureEndpoint(RestEndpoint):
    class Configuration:
        authentication_class = JWTAuthentication
        require_auth_methods = ['POST', 'PUT', 'DELETE']  # Public read access

# Global authentication
app.add_middleware([
    AuthenticationMiddleware(JWTAuthentication)
])
```

### ⚡ High-Performance Caching

**Redis-Based Caching System**
- Automatic cache key generation
- Selective method caching
- Cache invalidation strategies
- Custom cache backends

```python
from lightapi.cache import RedisCache

class CachedEndpoint(RestEndpoint):
    class Configuration:
        caching_class = RedisCache
        caching_method_names = ['GET']
        caching_ttl = 3600  # 1 hour cache
        cache_vary_headers = ['Authorization']
```

### 🌐 CORS & Middleware

**Production-Ready Middleware Stack**
- Built-in CORS handling
- Security headers injection
- Request/response logging
- Rate limiting
- Custom middleware support

```python
from lightapi.core import CORSMiddleware, AuthenticationMiddleware

app.add_middleware([
    CORSMiddleware(
        allow_origins=['https://app.company.com'],
        allow_credentials=True,
        expose_headers=['X-Process-Time']
    ),
    AuthenticationMiddleware(JWTAuthentication)
])
```

### 📊 Advanced Data Management

**Intelligent Query Processing**
- Advanced filtering with operators
- High-performance pagination
- Full-text search capabilities
- Field selection and expansion

```python
# Advanced query examples
GET /users?name__contains=john&age__gte=18&is_active=true
GET /users?limit=50&offset=100&sort=-created_at
GET /users?search=john%20doe&fields=id,name,email
GET /users?include=profile,permissions
```

### 📚 Automatic Documentation

**OpenAPI 3.0 with Swagger UI**
- Rich endpoint documentation
- Interactive API testing
- Request/response examples
- Authentication integration

```python
from lightapi.swagger import SwaggerConfig

swagger_config = SwaggerConfig(
    title="Enterprise API",
    version="2.0.0",
    description="Comprehensive REST API with advanced features",
    contact={"email": "api-support@company.com"},
    servers=[
        {"url": "https://api.company.com", "description": "Production"},
        {"url": "http://localhost:8000", "description": "Development"}
    ]
)

app = LightApi(swagger_config=swagger_config)
```

## Getting Started

Ready to build your first LightAPI application? Check out our comprehensive guides:

- **[User Goal Example](../examples/user_goal_example.py)**: See the exact usage pattern LightAPI was designed for
- **[Troubleshooting Guide](troubleshooting.md)**: Solutions for common issues and best practices
- **[API Reference](api-reference/)**: Complete documentation of all classes and methods

## Real-World Example

### User Goal Example

The `examples/user_goal_example.py` demonstrates the exact usage pattern envisioned for LightAPI, showcasing:

- **Custom Validators**: Field-specific validation with custom logic
- **JWT Authentication**: Secure endpoints with environment-based configuration  
- **Multiple Endpoint Types**: Different authentication requirements per endpoint
- **Built-in Middleware**: CORS support with proper integration
- **Flexible Response Formats**: Both tuple and Response object patterns

```bash
# Run the comprehensive example
LIGHTAPI_JWT_SECRET="test-secret-key-123" python examples/user_goal_example.py
```

### Enterprise Features Example

Here's a comprehensive example showing LightAPI's enterprise capabilities:

```python
from lightapi.rest import RestEndpoint, Validator
from lightapi.core import LightApi, CORSMiddleware, AuthenticationMiddleware
from lightapi.auth import JWTAuthentication
from lightapi.cache import RedisCache
from lightapi.pagination import Paginator
from sqlalchemy import Column, Integer, String, Decimal, DateTime, Text, Boolean
from datetime import datetime
import re

class ProductValidator(Validator):
    """Enterprise-grade input validation"""
    
    def validate_name(self, value):
        if not value or len(value.strip()) < 3:
            raise ValueError("Product name must be at least 3 characters")
        return value.strip()
    
    def validate_price(self, value):
        if value <= 0:
            raise ValueError("Price must be positive")
        return round(value, 2)

class ProductPaginator(Paginator):
    """Custom pagination for product listings"""
    limit = 20
    max_limit = 100
    sort = True
    include_count = True

class Product(RestEndpoint):
    """Enterprise product management API"""
    __tablename__ = 'products'
    
    # Comprehensive model schema
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text)
    price = Column(Decimal(10, 2), nullable=False)
    category = Column(String(100), index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    class Configuration:
        # HTTP methods
        http_method_names = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']
        
        # Security
        authentication_class = JWTAuthentication
        require_auth_methods = ['POST', 'PUT', 'DELETE']
        
        # Validation
        validator_class = ProductValidator
        
        # Performance
        caching_class = RedisCache
        caching_method_names = ['GET']
        caching_ttl = 600  # 10 minutes
        
        # Data handling
        pagination_class = ProductPaginator
        filterable_fields = ['name', 'category', 'price', 'is_active']
        searchable_fields = ['name', 'description']
        sortable_fields = ['name', 'price', 'created_at']
        
        # Documentation
        tags = ['Products', 'E-commerce']
    
    def get(self, request, pk=None):
        """
        Retrieve Products
        
        Advanced product retrieval with filtering, pagination, and search.
        
        **Query Parameters:**
        - `category`: Filter by product category
        - `price__gte`: Minimum price filter
        - `price__lte`: Maximum price filter
        - `is_active`: Filter by active status
        - `search`: Search in name and description
        - `limit`: Results per page (max 100)
        - `offset`: Results to skip
        - `sort`: Sort fields (prefix with '-' for descending)
        
        **Examples:**
        ```
        GET /products?category=electronics&price__gte=100
        GET /products?search=laptop&limit=20&sort=-price
        GET /products?is_active=true&sort=name
        ```
        """
        return super().get(request, pk)
    
    def post(self, request):
        """
        Create Product
        
        Create a new product with comprehensive validation.
        
        **Required Fields:**
        - `name`: Product name (3-200 characters)
        - `price`: Product price (must be positive)
        
        **Optional Fields:**
        - `description`: Product description
        - `category`: Product category
        - `is_active`: Active status (default: true)
        """
        return super().post(request)

# Enterprise application setup
app = LightApi(
    database_url="postgresql://user:pass@localhost/ecommerce",
    redis_url="redis://localhost:6379/0",
    title="E-commerce API",
    version="2.0.0",
    description="Professional e-commerce API with enterprise features"
)

# Production middleware stack
app.add_middleware([
    CORSMiddleware(
        allow_origins=['https://app.ecommerce.com', 'https://admin.ecommerce.com'],
        allow_methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
        allow_headers=['Authorization', 'Content-Type', 'X-API-Key'],
        allow_credentials=True,
        expose_headers=['X-Process-Time', 'X-Cache-Status']
    ),
    AuthenticationMiddleware(
        JWTAuthentication,
        exclude_paths=['/health', '/metrics', '/api/docs']
    )
])

# Register API endpoints
app.register({
    '/api/v1/products': Product
})

if __name__ == "__main__":
    # Production configuration
    app.run(
        host="0.0.0.0",
        port=8000,
        debug=False,
        workers=4
    )
```

## Development Experience

### 🔄 Hot Reloading

LightAPI provides instant feedback during development:

```python
# Development server with hot reload
app.run(
    host="0.0.0.0",
    port=8000,
    debug=True,
    reload=True,
    reload_dirs=['./src', './templates']
)
```

### 📊 Startup Endpoint Display

When your server starts, LightAPI automatically displays all available endpoints:

```
============================================================
🚀 LightAPI - Available Endpoints
============================================================
Path                         Methods                    Endpoint
------------------------------------------------------------
/api/v1/products            GET, HEAD, OPTIONS, POST   Product
/api/v1/products/{id}       GET, PUT, PATCH, DELETE    Product
/api/v1/categories          GET, HEAD, OPTIONS, POST   Category
/api/v1/categories/{id}     GET, PUT, PATCH, DELETE    Category
📚 API Documentation: http://127.0.0.1:8000/api/docs
🌐 Server will start on http://127.0.0.1:8000
============================================================
```

### 🐛 Rich Error Handling

LightAPI provides detailed error information in development mode while maintaining security in production:

```python
# Development mode: Detailed error traces
app.run(debug=True)

# Production mode: Secure error responses
app.run(debug=False)
```

## Database Support

LightAPI supports all databases compatible with SQLAlchemy:

| Database    | Production Use | Performance | Scalability |
|-------------|---------------|-------------|-------------|
| PostgreSQL  | ✅ Recommended | Excellent   | Horizontal  |
| MySQL       | ✅ Production  | Very Good   | Vertical    |
| SQLite      | 🔨 Development | Good        | Limited     |
| Oracle      | ✅ Enterprise  | Excellent   | Enterprise  |
| SQL Server  | ✅ Microsoft   | Very Good   | Vertical    |

```python
# Production PostgreSQL
app = LightApi(
    database_url="postgresql+psycopg2://user:pass@host:5432/db",
    pool_size=20,
    max_overflow=0,
    pool_pre_ping=True
)

# Development SQLite
app = LightApi(database_url="sqlite:///./development.db")
```

## Environment Configuration

LightAPI supports comprehensive environment-based configuration:

```bash
# Server Configuration
LIGHTAPI_HOST=0.0.0.0
LIGHTAPI_PORT=8000
LIGHTAPI_DEBUG=false
LIGHTAPI_RELOAD=false

# Database
DATABASE_URL=postgresql://user:password@host:5432/database

# Authentication
JWT_SECRET=your-256-bit-secret-key
LIGHTAPI_JWT_ALGORITHM=HS256
LIGHTAPI_JWT_EXPIRY_HOURS=8

# Redis Caching
REDIS_URL=redis://localhost:6379/0

# CORS
CORS_ORIGINS=https://app.com,https://admin.app.com
CORS_ALLOW_CREDENTIALS=true

# Documentation
LIGHTAPI_ENABLE_SWAGGER=true
LIGHTAPI_SWAGGER_URL=/api/docs
```

## Next Steps

Ready to dive deeper? Explore our comprehensive guides:

### **Getting Started**
- [Installation Guide](getting-started/installation.md) - Set up your development environment
- [First API](getting-started/first-api.md) - Build your first LightAPI application
- [Configuration](getting-started/configuration.md) - Environment and application configuration

### **Core Concepts**
- [RestEndpoint](tutorial/rest-endpoints.md) - Understanding endpoint classes
- [Authentication](tutorial/authentication.md) - Implementing JWT and custom auth
- [Middleware](tutorial/middleware.md) - Built-in and custom middleware
- [Caching](tutorial/caching.md) - Redis integration and strategies

### **Advanced Topics**
- [Production Deployment](deployment/production.md) - Docker, monitoring, and scaling
- [Performance Optimization](advanced/performance.md) - Caching, database optimization
- [Security Best Practices](advanced/security.md) - Enterprise security patterns

### **API Reference**
- [Core API](api-reference/core.md) - Complete API documentation
- [Authentication](api-reference/auth.md) - Authentication classes and methods
- [Caching](api-reference/cache.md) - Caching system reference

### **Examples**
- [Real-World Examples](examples/) - Production-ready code examples
- [Integration Patterns](examples/integrations/) - Third-party service integration

---

**Ready to build amazing APIs?** Start with our [Quick Start Guide](getting-started/installation.md) or explore the [API Reference](api-reference/) for detailed documentation.

