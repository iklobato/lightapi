# LightAPI

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Starlette](https://img.shields.io/badge/built%20with-Starlette-FF6B35.svg)](https://www.starlette.io/)
[![SQLAlchemy](https://img.shields.io/badge/ORM-SQLAlchemy-red.svg)](https://www.sqlalchemy.org/)

**A production-ready, lightweight API framework that combines the power of Starlette and SQLAlchemy to deliver enterprise-grade REST APIs with minimal configuration.**

## Overview

LightAPI is an enterprise-ready framework engineered for rapid development of high-performance REST APIs. By unifying SQLAlchemy ORM models with API endpoints in a single class definition, LightAPI eliminates boilerplate code while maintaining flexibility and scalability. Built on top of Starlette's proven asynchronous foundation, it delivers exceptional performance for both small applications and large-scale enterprise systems.

### Why Choose LightAPI?

- **🚀 Rapid Development**: Deploy production-ready APIs in minutes, not hours
- **⚡ High Performance**: Built on Starlette's async foundation for maximum throughput
- **🏗️ Enterprise Ready**: Comprehensive middleware, authentication, and caching systems
- **🎯 Developer Focused**: Intuitive API design that reduces cognitive overhead
- **🔧 Highly Configurable**: Extensive customization options for complex business requirements
- **📚 Well Documented**: Comprehensive documentation with real-world examples

## 🎯 Core Features

### **Model-Endpoint Unification**
- **Single Class Definition**: Combine SQLAlchemy models and REST endpoints in one cohesive class
- **Automatic CRUD Generation**: Intelligent REST operations generated from your model structure
- **Selective HTTP Methods**: Granular control over allowed HTTP methods per endpoint
- **Zero Boilerplate**: Focus on business logic, not infrastructure code

### **Enterprise Authentication & Security**
- **JWT Authentication**: Production-ready JWT with automatic token validation
- **CORS Integration**: Seamless CORS handling with preflight request support
- **Authentication Middleware**: Global and per-endpoint authentication strategies
- **Security Headers**: Automatic security header injection for production environments

### **Advanced Data Management**
- **Smart Filtering**: Sophisticated query parameter filtering with type coercion
- **Pagination System**: Configurable, high-performance pagination with metadata
- **Request Validation**: Comprehensive input validation with custom validator support
- **Data Serialization**: Automatic JSON serialization with custom encoder support

### **Performance & Scalability**
- **Redis Caching**: Enterprise-grade Redis integration with automatic cache invalidation
- **Async Foundation**: Built on Starlette's proven async architecture
- **Connection Pooling**: Optimized database connection management
- **Response Compression**: Automatic gzip compression for improved bandwidth efficiency

### **Developer Experience**
- **Hot Reloading**: Instant server restart during development with change detection
- **Automatic Documentation**: OpenAPI 3.0 specification with Swagger UI integration
- **Comprehensive Logging**: Structured logging with request tracing capabilities
- **Error Handling**: Intelligent error responses with detailed development feedback
- **Endpoint Listing**: Automatic display of all available endpoints on startup

### **Extensibility**
- **Middleware Architecture**: Comprehensive middleware system for cross-cutting concerns
- **Custom Validators**: Extensible validation framework for complex business rules
- **Plugin System**: Modular architecture supporting custom extensions
- **Database Agnostic**: Support for PostgreSQL, MySQL, SQLite, and other SQLAlchemy-compatible databases

## 📦 Installation

### Prerequisites

- **Python**: 3.8 or higher
- **Database**: PostgreSQL, MySQL, SQLite, or any SQLAlchemy-compatible database
- **Redis** (optional): For caching functionality

### Quick Installation

#### Using uv (Recommended)

```bash
# Install uv (modern Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create and activate virtual environment
uv venv lightapi-env
source lightapi-env/bin/activate  # On Windows: lightapi-env\Scripts\activate

# Install LightAPI with all dependencies
uv add lightapi[all]
```

#### Using pip

```bash
# Create virtual environment
python -m venv lightapi-env
source lightapi-env/bin/activate  # On Windows: lightapi-env\Scripts\activate

# Install LightAPI
pip install lightapi

# For additional features
pip install lightapi[redis,jwt,cors]  # Redis caching, JWT auth, CORS support
```

### Development Installation

```bash
# Clone the repository
git clone https://github.com/your-org/lightapi.git
cd lightapi

# Install in development mode with all dependencies
uv pip install -e ".[dev,test,docs]"

# Run tests to verify installation
uv run pytest
```

## 🚀 Quick Start

### Minimal Example (30 Seconds to API)

Create a fully functional REST API in just a few lines:

```python
from lightapi.rest import RestEndpoint
from lightapi.core import LightApi
from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime

class User(RestEndpoint):
    """User model with automatic REST endpoints"""
    __tablename__ = 'users'
    
    # SQLAlchemy model definition
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    class Configuration:
        # Enable full CRUD operations
        http_method_names = ['GET', 'POST', 'PUT', 'DELETE']
        # Enable automatic pagination for GET requests
        pagination_class = None  # Uses default pagination

# Initialize application
app = LightApi(
    database_url="sqlite:///users.db",
    title="User Management API",
    version="1.0.0"
)

# Register endpoints
app.register({
    '/users': User,          # Full CRUD: /users, /users/{id}
    '/api/v1/users': User    # Alternative path
})

if __name__ == "__main__":
    # Development server with hot reload
    app.run(host="0.0.0.0", port=8000, debug=True, reload=True)
    # Visit http://localhost:8000/api/docs for interactive documentation
```

### Test Your API

```bash
# Start the server
python app.py

# Test endpoints
curl -X POST http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{"name": "John Doe", "email": "john@example.com"}'

curl http://localhost:8000/users  # List all users
curl http://localhost:8000/users/1  # Get specific user
```

Your API automatically provides:
- ✅ **GET** `/users` - List all users with pagination
- ✅ **GET** `/users/{id}` - Get specific user
- ✅ **POST** `/users` - Create new user
- ✅ **PUT** `/users/{id}` - Update user
- ✅ **DELETE** `/users/{id}` - Delete user
- ✅ **Interactive Documentation** at `/api/docs`
- ✅ **Endpoint Listing** displayed on startup

## 🔧 Advanced Usage

### Enterprise-Grade API with Validation

```python
from lightapi.rest import RestEndpoint, Response, Validator
from lightapi.core import LightApi
from lightapi.auth import JWTAuthentication
from lightapi.cache import RedisCache
from lightapi.pagination import Paginator
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from datetime import datetime
import re

class UserValidator(Validator):
    """Comprehensive user input validation"""
    
    def validate_name(self, value):
        if not value or len(value.strip()) < 2:
            raise ValueError("Name must be at least 2 characters")
        if len(value) > 100:
            raise ValueError("Name cannot exceed 100 characters")
        return value.strip().title()
    
    def validate_email(self, value):
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, value):
            raise ValueError("Invalid email format")
        return value.lower()
    
    def validate_age(self, value):
        if value is not None and (value < 0 or value > 150):
            raise ValueError("Age must be between 0 and 150")
        return value

class UserPaginator(Paginator):
    """Custom pagination with metadata"""
    limit = 25
    max_limit = 100
    sort = True
    include_count = True

class User(RestEndpoint):
    """Enterprise user model with full feature set"""
    __tablename__ = 'users'
    
    # Enhanced model schema
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    age = Column(Integer, nullable=True)
    bio = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    class Configuration:
        # HTTP methods configuration
        http_method_names = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']
        
        # Security and validation
        authentication_class = JWTAuthentication
        validator_class = UserValidator
        
        # Performance optimizations
        caching_class = RedisCache
        caching_method_names = ['GET']
        caching_ttl = 300  # 5 minutes
        
        # Data presentation
        pagination_class = UserPaginator
        filterable_fields = ['name', 'email', 'is_active', 'created_at']
        searchable_fields = ['name', 'email', 'bio']
    
    def post(self, request):
        """Custom user creation with business logic"""
        data = request.json()
        
        # Business logic
        user = self.create_from_dict(data)
        
        # Custom response
        return Response({
            'message': 'User created successfully',
            'user': self.to_dict(user),
            'links': {
                'self': f'/users/{user.id}',
                'update': f'/users/{user.id}',
                'delete': f'/users/{user.id}'
            }
        }, status_code=201)
    
    def get(self, request, pk=None):
        """Enhanced GET with custom logic"""
        if pk:
            # Single user with additional data
            user = self.get_object(pk)
            return Response({
                'user': self.to_dict(user),
                'metadata': {
                    'retrieved_at': datetime.utcnow().isoformat(),
                    'is_cached': hasattr(request, '_from_cache')
                }
            })
        
        # List users with enhanced filtering
        return super().get(request)
```

### Production-Ready Application Architecture

```python
from lightapi.core import LightApi, CORSMiddleware, AuthenticationMiddleware
from lightapi.rest import RestEndpoint
from lightapi.auth import JWTAuthentication
from lightapi.cache import RedisCache
from lightapi.pagination import Paginator
from sqlalchemy import Column, Integer, String, Decimal, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
import os

# Application configuration
class Config:
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://user:pass@localhost/myapp')
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    JWT_SECRET = os.getenv('JWT_SECRET', 'your-secret-key')
    CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*').split(',')

class ProductPaginator(Paginator):
    """High-performance pagination for product listings"""
    limit = 20
    max_limit = 100
    sort = True
    include_count = True

class Product(RestEndpoint):
    """Enterprise product management endpoint"""
    __tablename__ = 'products'
    
    # Comprehensive model schema
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text)
    price = Column(Decimal(10, 2), nullable=False)
    category_id = Column(Integer, ForeignKey('categories.id'))
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    
    # Relationships
    category = relationship("Category", back_populates="products")
    
    class Configuration:
        # API Configuration
        http_method_names = ['GET', 'POST', 'PUT', 'DELETE']
        
        # Security
        authentication_class = JWTAuthentication
        require_auth_methods = ['POST', 'PUT', 'DELETE']  # Public read access
        
        # Performance
        caching_class = RedisCache
        caching_method_names = ['GET']
        caching_ttl = 600  # 10 minutes
        
        # Data handling
        pagination_class = ProductPaginator
        filterable_fields = ['name', 'category_id', 'price']
        searchable_fields = ['name', 'description']
        sortable_fields = ['name', 'price', 'created_at']

class Category(RestEndpoint):
    """Product category management"""
    __tablename__ = 'categories'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    
    # Relationships
    products = relationship("Product", back_populates="category")
    
    class Configuration:
        http_method_names = ['GET', 'POST', 'PUT', 'DELETE']
        authentication_class = JWTAuthentication
        require_auth_methods = ['POST', 'PUT', 'DELETE']

# Application setup
app = LightApi(
    database_url=Config.DATABASE_URL,
    redis_url=Config.REDIS_URL,
    title="E-Commerce API",
    version="2.0.0",
    description="Professional e-commerce API with advanced features"
)

# Global middleware configuration
app.add_middleware([
    CORSMiddleware(
        allow_origins=Config.CORS_ORIGINS,
        allow_methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
        allow_headers=['*'],
        allow_credentials=True
    ),
    AuthenticationMiddleware(JWTAuthentication)
])

# Register API endpoints
app.register({
    '/api/v1/products': Product,
    '/api/v1/categories': Category,
})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=False)
```

### Enterprise Middleware System

LightAPI features a comprehensive middleware architecture for handling cross-cutting concerns:

#### Built-in Middleware Classes

```python
from lightapi.core import LightApi, CORSMiddleware, AuthenticationMiddleware
from lightapi.auth import JWTAuthentication
from lightapi.rest import RestEndpoint
import logging

# Configure structured logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class APIEndpoint(RestEndpoint):
    __tablename__ = 'api_data'
    
    class Configuration:
        http_method_names = ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']

app = LightApi(
    title="Enterprise API",
    version="1.0.0",
    description="Production-ready API with comprehensive middleware"
)

# Professional middleware stack
app.add_middleware([
    # Security Layer
    CORSMiddleware(
        allow_origins=['https://app.domain.com', 'https://admin.domain.com'],
        allow_methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS', 'HEAD'],
        allow_headers=['Authorization', 'Content-Type', 'X-API-Key', 'X-Request-ID'],
        allow_credentials=True,
        expose_headers=['X-Process-Time', 'X-Cache-Status']
    ),
    
    # Authentication Layer
    AuthenticationMiddleware(JWTAuthentication)
])

app.register({'/api/v1/data': APIEndpoint})
```

#### Advanced Custom Middleware

```python
from lightapi.core import Middleware
from starlette.requests import Request
from starlette.responses import Response
import time
import uuid
import logging
from datetime import datetime

class RequestTrackingMiddleware(Middleware):
    """Comprehensive request tracking and logging middleware"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def process(self, request: Request, response: Response = None):
        if response is None:
            # Pre-processing: Setup request tracking
            request.state.request_id = str(uuid.uuid4())
            request.state.start_time = time.time()
            request.state.timestamp = datetime.utcnow()
            
            self.logger.info(
                f"REQUEST_START",
                extra={
                    'request_id': request.state.request_id,
                    'method': request.method,
                    'url': str(request.url),
                    'user_agent': request.headers.get('user-agent'),
                    'client_ip': request.client.host if request.client else None
                }
            )
            return None
        
        # Post-processing: Add tracking headers and log completion
        if hasattr(request.state, 'request_id'):
            response.headers['X-Request-ID'] = request.state.request_id
            
            if hasattr(request.state, 'start_time'):
                duration = time.time() - request.state.start_time
                response.headers['X-Process-Time'] = f"{duration:.3f}s"
                
                self.logger.info(
                    f"REQUEST_COMPLETE",
                    extra={
                        'request_id': request.state.request_id,
                        'status_code': response.status_code,
                        'duration_ms': round(duration * 1000, 2),
                        'response_size': len(response.body) if hasattr(response, 'body') else None
                    }
                )
        
        return response

class SecurityHeadersMiddleware(Middleware):
    """Add security headers for production environments"""
    
    def process(self, request: Request, response: Response = None):
        if response is None:
            return None
        
        # Add comprehensive security headers
        security_headers = {
            'X-Content-Type-Options': 'nosniff',
            'X-Frame-Options': 'DENY',
            'X-XSS-Protection': '1; mode=block',
            'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
            'Content-Security-Policy': "default-src 'self'",
            'Referrer-Policy': 'strict-origin-when-cross-origin',
            'X-Permitted-Cross-Domain-Policies': 'none'
        }
        
        for header, value in security_headers.items():
            response.headers[header] = value
        
        return response

# Apply enterprise middleware stack
app.add_middleware([
    SecurityHeadersMiddleware(),
    RequestTrackingMiddleware(),
    CORSMiddleware(),
    AuthenticationMiddleware(JWTAuthentication)
])
```

## 🌐 Cross-Origin Resource Sharing (CORS)

LightAPI provides enterprise-grade CORS support with intelligent defaults and extensive customization options:

### Automatic CORS Integration

```python
from lightapi.core import LightApi, CORSMiddleware
from lightapi.auth import JWTAuthentication
from lightapi.rest import RestEndpoint

class APIEndpoint(RestEndpoint):
    class Configuration:
        http_method_names = ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
        authentication_class = JWTAuthentication  # Automatically handles preflight

# Simple CORS setup
app = LightApi()
app.add_middleware([CORSMiddleware()])  # Permissive defaults for development
app.register({'/api': APIEndpoint})
```

### Production CORS Configuration

```python
# Production-ready CORS configuration
cors_config = CORSMiddleware(
    allow_origins=[
        'https://app.mycompany.com',
        'https://admin.mycompany.com',
        'https://mobile.mycompany.com'
    ],
    allow_methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS', 'HEAD'],
    allow_headers=[
        'Authorization',
        'Content-Type',
        'X-API-Key',
        'X-Request-ID',
        'X-Client-Version'
    ],
    expose_headers=[
        'X-Process-Time',
        'X-Cache-Status',
        'X-Rate-Limit-Remaining'
    ],
    allow_credentials=True,
    max_age=86400  # 24 hours preflight cache
)

app.add_middleware([cors_config])
```

## 🗄️ Database Integration

LightAPI supports the full spectrum of databases through SQLAlchemy's robust ecosystem:

### Supported Databases

| Database    | Driver Examples              | Use Case                    |
|-------------|-----------------------------|-----------------------------|
| PostgreSQL  | `psycopg2`, `asyncpg`       | Production, scalability     |
| MySQL       | `PyMySQL`, `mysqlclient`    | Traditional web apps        |
| SQLite      | Built-in                    | Development, testing        |
| Oracle      | `cx_Oracle`                 | Enterprise systems          |
| SQL Server  | `pyodbc`, `pymssql`         | Microsoft environments      |
| MariaDB     | `PyMySQL`                   | Open-source alternative     |

### Database Configuration Examples

```python
# PostgreSQL (Recommended for production)
app = LightApi(
    database_url="postgresql+psycopg2://user:password@localhost:5432/myapp_prod",
    pool_size=20,
    max_overflow=0,
    pool_pre_ping=True
)

# MySQL with connection pooling
app = LightApi(
    database_url="mysql+pymysql://user:password@localhost:3306/myapp",
    pool_size=10,
    pool_recycle=3600
)

# SQLite for development
app = LightApi(database_url="sqlite:///./development.db")

# Environment-based configuration
import os
app = LightApi(
    database_url=os.getenv('DATABASE_URL', 'sqlite:///./default.db'),
    echo=os.getenv('SQL_ECHO', 'False').lower() == 'true'
)
```

## ⚡ High-Performance Caching

LightAPI's caching system provides enterprise-level performance optimization:

### Redis Caching Configuration

```python
from lightapi.cache import RedisCache
from lightapi.rest import RestEndpoint

class ProductCache(RedisCache):
    """Custom cache configuration for products"""
    default_timeout = 3600  # 1 hour
    key_prefix = "product_api"
    
    def get_cache_key(self, request, endpoint_name, method):
        """Custom cache key generation"""
        base_key = super().get_cache_key(request, endpoint_name, method)
        user_tier = getattr(request.state, 'user_tier', 'default')
        return f"{base_key}:tier:{user_tier}"

class Product(RestEndpoint):
    __tablename__ = 'products'
    
    class Configuration:
        caching_class = ProductCache
        caching_method_names = ['GET']
        cache_vary_headers = ['Authorization', 'Accept-Language']
        cache_control_max_age = 600  # 10 minutes browser cache

# Redis cluster configuration
app = LightApi(
    redis_url="redis://localhost:6379/0",
    redis_config={
        'socket_timeout': 5,
        'socket_connect_timeout': 5,
        'connection_pool_kwargs': {
            'max_connections': 100,
            'retry_on_timeout': True
        }
    }
)
```

### Cache Strategies

```python
class SmartCachingEndpoint(RestEndpoint):
    __tablename__ = 'data'
    
    class Configuration:
        caching_class = RedisCache
        caching_method_names = ['GET']
    
    def get(self, request, pk=None):
        """Custom caching logic with conditional invalidation"""
        if pk:
            # Check if data is fresh enough
            cache_key = f"item:{pk}:version"
            version = self.cache.get(cache_key)
            
            if version and self.is_data_stale(pk, version):
                self.cache.delete_pattern(f"item:{pk}:*")
        
        return super().get(request, pk)
    
    def post(self, request):
        """Invalidate related cache on creation"""
        result = super().post(request)
        # Invalidate list cache
        self.cache.delete_pattern("list:*")
        return result
```

## 🔐 Enterprise Authentication & Security

### JWT Authentication with Advanced Features

```python
from lightapi.auth import JWTAuthentication
from datetime import timedelta
import os

class EnterpriseJWTAuth(JWTAuthentication):
    """Enhanced JWT authentication for enterprise use"""
    
    def __init__(self):
        super().__init__(
            secret_key=os.getenv('JWT_SECRET'),
            algorithm='HS256',
            token_expiry=timedelta(hours=8),  # 8-hour sessions
            refresh_threshold=timedelta(hours=1)  # Refresh when < 1 hour left
        )
    
    def get_user_from_token(self, token_data):
        """Enhanced user loading with permissions"""
        user_data = super().get_user_from_token(token_data)
        
        # Load user permissions
        user_data['permissions'] = self.load_user_permissions(user_data['user_id'])
        user_data['roles'] = self.load_user_roles(user_data['user_id'])
        
        return user_data
    
    def authorize_endpoint(self, request, endpoint_config):
        """Role-based access control"""
        required_permissions = getattr(endpoint_config, 'required_permissions', [])
        
        if required_permissions:
            user_permissions = request.state.user.get('permissions', [])
            if not any(perm in user_permissions for perm in required_permissions):
                raise PermissionError("Insufficient permissions")

# Usage with role-based access
class AdminEndpoint(RestEndpoint):
    __tablename__ = 'admin_data'
    
    class Configuration:
        authentication_class = EnterpriseJWTAuth
        required_permissions = ['admin.read', 'admin.write']
        http_method_names = ['GET', 'POST', 'PUT', 'DELETE']
```

### Multi-Factor Authentication Integration

```python
class MFAAuthentication(JWTAuthentication):
    """JWT Authentication with MFA support"""
    
    def validate_token(self, token):
        """Validate token and check MFA requirements"""
        user_data = super().validate_token(token)
        
        # Check if MFA is required for this user
        if user_data.get('mfa_required') and not user_data.get('mfa_verified'):
            raise AuthenticationError("MFA verification required")
        
        return user_data
    
    def require_mfa_verification(self, request):
        """Endpoint decorator for MFA-required actions"""
        if not request.state.user.get('mfa_verified'):
            return JSONResponse(
                {"error": "MFA verification required", "mfa_required": True},
                status_code=403
            )
        return None
```

## 📚 Automatic API Documentation

LightAPI generates comprehensive OpenAPI 3.0 documentation with advanced features:

### Enhanced Documentation Configuration

```python
from lightapi.swagger import SwaggerConfig

swagger_config = SwaggerConfig(
    title="Enterprise API Documentation",
    version="2.1.0",
    description="""
    # Enterprise API
    
    Comprehensive REST API for enterprise operations with:
    - JWT Authentication
    - Role-based access control
    - Advanced caching
    - Rate limiting
    - Comprehensive error handling
    
    ## Authentication
    Use Bearer token authentication with JWT tokens.
    
    ## Rate Limiting
    Standard rate limits apply: 1000 requests per hour for authenticated users.
    """,
    contact={
        "name": "API Support",
        "url": "https://company.com/support",
        "email": "api-support@company.com"
    },
    license={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT"
    },
    servers=[
        {"url": "https://api.company.com/v1", "description": "Production"},
        {"url": "https://api-staging.company.com/v1", "description": "Staging"},
        {"url": "http://localhost:8000", "description": "Development"}
    ]
)

app = LightApi(swagger_config=swagger_config)
```

### Rich Endpoint Documentation

```python
class DocumentedEndpoint(RestEndpoint):
    """
    User Management Endpoint
    
    Comprehensive user management with full CRUD operations,
    advanced filtering, and role-based access control.
    """
    __tablename__ = 'users'
    
    # Model with documentation
    id = Column(Integer, primary_key=True, doc="Unique user identifier")
    email = Column(String(255), unique=True, nullable=False, 
                  doc="User email address (unique)")
    name = Column(String(100), nullable=False, 
                 doc="Full name of the user")
    
    class Configuration:
        http_method_names = ['GET', 'POST', 'PUT', 'DELETE']
        # OpenAPI tags for grouping
        tags = ['Users', 'Authentication']
        # Response examples
        response_examples = {
            200: {
                "description": "Success",
                "content": {
                    "application/json": {
                        "example": {
                            "id": 1,
                            "email": "user@example.com",
                            "name": "John Doe"
                        }
                    }
                }
            }
        }
    
    def get(self, request, pk=None):
        """
        Retrieve Users
        
        Retrieve a list of users or a specific user by ID.
        
        **Query Parameters:**
        - `limit`: Number of results to return (max 100)
        - `offset`: Number of results to skip
        - `search`: Search term for name or email
        - `active`: Filter by active status (true/false)
        
        **Examples:**
        - `GET /users?limit=10&search=john`
        - `GET /users?active=true&limit=50`
        """
        return super().get(request, pk)
```

## 🚀 Development & Production Features

### Development Server with Hot Reload

```python
# Development configuration
if __name__ == "__main__":
    import os
    
    # Development settings
    development_config = {
        'host': '0.0.0.0',
        'port': 8000,
        'debug': True,
        'reload': True,
        'reload_dirs': ['./src', './templates'],
        'log_level': 'debug'
    }
    
    # Enable debug toolbar
    if os.getenv('DEBUG_TOOLBAR', 'false').lower() == 'true':
        from debug_toolbar import DebugToolbarExtension
        development_config['extensions'] = [DebugToolbarExtension()]
    
    app.run(**development_config)
```

### Production Deployment

```python
# Production server configuration
import uvicorn
from lightapi.core import LightApi

def create_production_app():
    """Factory function for production deployment"""
    
    app = LightApi(
        database_url=os.getenv('DATABASE_URL'),
        redis_url=os.getenv('REDIS_URL'),
        debug=False,
        title="Production API",
        version="1.0.0"
    )
    
    # Production middleware stack
    app.add_middleware([
        SecurityHeadersMiddleware(),
        RequestTrackingMiddleware(),
        RateLimitingMiddleware(requests_per_minute=1000),
        CORSMiddleware(allow_origins=os.getenv('CORS_ORIGINS', '').split(',')),
        AuthenticationMiddleware(JWTAuthentication)
    ])
    
    # Register endpoints
    register_api_endpoints(app)
    
    return app

# ASGI application for deployment
app = create_production_app()

# For running with gunicorn: gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker
```

## 📊 API Endpoint Reference

LightAPI automatically generates comprehensive REST endpoints with automatic startup listing:

### Startup Endpoint Display

When your LightAPI server starts, it automatically displays all available endpoints:

```
============================================================
🚀 LightAPI - Available Endpoints
============================================================
Path                    Methods                    Endpoint
------------------------------------------------------------
/api/v1/users           GET, HEAD, OPTIONS, POST   User
/api/v1/users/{id}      GET, PUT, DELETE          User
/api/v1/products        GET, HEAD, OPTIONS, POST   Product
/api/v1/products/{id}   GET, PUT, DELETE          Product
📚 API Documentation: http://127.0.0.1:8000/api/docs
🌐 Server will start on http://127.0.0.1:8000
============================================================
```

### Generated Endpoint Patterns

| Method | Endpoint Pattern | Description | Query Parameters |
|--------|-----------------|-------------|------------------|
| `GET` | `/resource/` | List resources | `limit`, `offset`, `search`, filters |
| `POST` | `/resource/` | Create resource | - |
| `GET` | `/resource/{id}` | Get resource | - |
| `PUT` | `/resource/{id}` | Replace resource | - |
| `PATCH` | `/resource/{id}` | Update resource | - |
| `DELETE` | `/resource/{id}` | Delete resource | - |
| `OPTIONS` | `/resource/` | CORS preflight | - |
| `HEAD` | `/resource/` | Check existence | Same as GET |

### Advanced Query Parameters

```bash
# Pagination
GET /users?limit=20&offset=40

# Filtering
GET /users?name__contains=john&age__gte=18&active=true

# Sorting
GET /users?sort=name&sort=-created_at  # name asc, created_at desc

# Field selection
GET /users?fields=id,name,email

# Including relationships
GET /users?include=profile,permissions

# Search across multiple fields
GET /users?search=john%20doe
```

## 🌍 Environment Configuration

### Complete Environment Variables Reference

```bash
# Server Configuration
LIGHTAPI_HOST=0.0.0.0
LIGHTAPI_PORT=8000
LIGHTAPI_DEBUG=false
LIGHTAPI_RELOAD=false
LIGHTAPI_LOG_LEVEL=info

# Database Configuration
DATABASE_URL=postgresql://user:password@host:5432/database
LIGHTAPI_DB_POOL_SIZE=20
LIGHTAPI_DB_MAX_OVERFLOW=0
LIGHTAPI_DB_POOL_RECYCLE=3600
LIGHTAPI_DB_ECHO=false

# Redis Configuration
REDIS_URL=redis://localhost:6379/0
LIGHTAPI_REDIS_SOCKET_TIMEOUT=5
LIGHTAPI_REDIS_MAX_CONNECTIONS=100

# Authentication
JWT_SECRET=your-256-bit-secret-key-here
LIGHTAPI_JWT_ALGORITHM=HS256
LIGHTAPI_JWT_EXPIRY_HOURS=8
LIGHTAPI_JWT_REFRESH_THRESHOLD_HOURS=1

# CORS Configuration
CORS_ORIGINS=https://app.com,https://admin.app.com
CORS_ALLOW_CREDENTIALS=true
CORS_MAX_AGE=86400

# Security
LIGHTAPI_RATE_LIMIT_REQUESTS_PER_MINUTE=100
LIGHTAPI_ENABLE_SECURITY_HEADERS=true
LIGHTAPI_ALLOWED_HOSTS=api.company.com,localhost

# Documentation
LIGHTAPI_ENABLE_SWAGGER=true
LIGHTAPI_SWAGGER_URL=/api/docs
LIGHTAPI_OPENAPI_URL=/api/openapi.json

# Caching
LIGHTAPI_CACHE_DEFAULT_TTL=3600
LIGHTAPI_CACHE_KEY_PREFIX=lightapi
LIGHTAPI_ENABLE_CACHE_VARY_HEADERS=true

# Monitoring & Logging
LIGHTAPI_ENABLE_REQUEST_LOGGING=true
LIGHTAPI_LOG_FORMAT=json
LIGHTAPI_METRICS_ENABLED=true
```

### Docker Configuration

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Set environment variables
ENV PYTHONPATH=/app
ENV LIGHTAPI_HOST=0.0.0.0
ENV LIGHTAPI_PORT=8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:password@db:5432/myapp
      - REDIS_URL=redis://redis:6379/0
      - JWT_SECRET=your-secret-key
    depends_on:
      - db
      - redis
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=myapp
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

## 🤝 Contributing & Support

### Contributing Guidelines

We welcome contributions! Please follow these guidelines:

1. **Fork the repository** and create a feature branch
2. **Write tests** for new functionality
3. **Follow code style** guidelines (black, isort, flake8)
4. **Update documentation** for any API changes
5. **Submit a pull request** with a clear description

### Development Setup

```bash
# Clone and setup
git clone https://github.com/your-org/lightapi.git
cd lightapi

# Install development dependencies
uv venv
source .venv/bin/activate
uv pip install -e ".[dev,test,docs]"

# Run tests
pytest tests/ -v --cov=lightapi

# Code formatting
black lightapi/ tests/
isort lightapi/ tests/
flake8 lightapi/ tests/

# Generate documentation
mkdocs serve
```

### Support & Community

- **📖 Documentation**: [https://lightapi.readthedocs.io](https://lightapi.readthedocs.io)
- **🐛 Bug Reports**: [GitHub Issues](https://github.com/your-org/lightapi/issues)
- **💬 Discussions**: [GitHub Discussions](https://github.com/your-org/lightapi/discussions)
- **📧 Email**: support@lightapi.dev

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**Built with ❤️ for the Python community**
