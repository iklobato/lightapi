# LightAPI: Fast Python REST API Framework with Async, CRUD, OpenAPI, JWT, and YAML

[![PyPI version](https://badge.fury.io/py/lightapi.svg)](https://pypi.org/project/lightapi/)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**LightAPI** is a fast, async-ready Python REST API framework that lets you instantly generate CRUD endpoints from SQLAlchemy models or your existing database schema. With built-in OpenAPI documentation, JWT authentication, Redis caching, and YAML-driven configuration, LightAPI is the best choice for building scalable, production-ready APIs in Python.

---

## 🚀 Table of Contents
- [Why LightAPI?](#why-lightapi)
- [Who is LightAPI for?](#who-is-lightapi-for)
- [✨ Features Overview](#-features-overview)
- [🛠️ Installation](#️-installation)
- [⚡ Quick Start](#-quick-start)
- [📚 Feature Documentation](#-feature-documentation)
  - [🔧 Basic CRUD Operations](#-basic-crud-operations)
  - [⚡ Async/Await Support](#-asyncawait-support)
  - [📖 OpenAPI/Swagger Documentation](#-openapiswagger-documentation)
  - [🔐 JWT Authentication](#-jwt-authentication)
  - [🌐 CORS Support](#-cors-support)
  - [💾 Redis Caching](#-redis-caching)
  - [🔍 Advanced Filtering & Pagination](#-advanced-filtering--pagination)
  - [✅ Request Validation](#-request-validation)
  - [📄 YAML Configuration](#-yaml-configuration)
  - [🔧 Custom Middleware](#-custom-middleware)
- [📁 Examples](#-examples)
- [🧪 Testing](#-testing)
- [🔧 Configuration](#-configuration)
- [🚀 Deployment](#-deployment)
- [❓ FAQ](#-faq)
- [📊 Performance](#-performance)
- [🤝 Contributing](#-contributing)
- [📄 License](#-license)

---

## Why LightAPI?

LightAPI is a modern, async-ready Python REST API framework designed for rapid development and production use. It combines the best features of FastAPI, Flask, and Django REST Framework while maintaining simplicity and performance.

### 🎯 Key Benefits
- **⚡ Instant CRUD APIs**: Generate full REST APIs from SQLAlchemy models in seconds
- **🚀 High Performance**: Built on Starlette/Uvicorn with async support
- **📖 Auto Documentation**: OpenAPI/Swagger docs generated automatically
- **🔐 Security First**: Built-in JWT authentication and CORS support
- **💾 Smart Caching**: Redis integration with intelligent cache management
- **🔍 Advanced Queries**: Filtering, pagination, sorting, and search out of the box
- **✅ Data Validation**: Comprehensive request/response validation
- **📄 Configuration Driven**: YAML-based API generation
- **🔧 Extensible**: Custom middleware and endpoint customization

---

## Who is LightAPI for?

- **🏢 Backend developers** who want to ship APIs fast, with minimal code
- **📊 Data engineers** needing to expose existing databases as RESTful services
- **🚀 Prototypers** and **startups** who want to iterate quickly and scale later
- **🏗️ Enterprise teams** building microservices and internal APIs
- **🎓 Educators** teaching REST API development and best practices
- **🔄 Migration projects** moving from other frameworks to modern async Python

---

## ✨ Features Overview

### 🔧 Core Features
- **Automatic CRUD Endpoints**: Generate REST APIs from SQLAlchemy models
- **Async/Await Support**: High-performance async request handling
- **OpenAPI Documentation**: Auto-generated Swagger UI and ReDoc
- **JWT Authentication**: Secure token-based authentication
- **CORS Support**: Cross-origin resource sharing configuration
- **Redis Caching**: Intelligent caching with TTL and invalidation
- **Request Validation**: Comprehensive input validation and error handling
- **Database Agnostic**: Works with PostgreSQL, MySQL, SQLite, and more

### 🚀 Advanced Features
- **Advanced Filtering**: Complex queries with multiple criteria
- **Pagination & Sorting**: Efficient data retrieval with customizable pagination
- **Search Functionality**: Full-text search across multiple fields
- **YAML Configuration**: Define APIs without writing Python code
- **Custom Middleware**: Extensible middleware system
- **Error Handling**: Comprehensive error responses and logging
- **Performance Monitoring**: Built-in performance metrics and caching stats
- **Hot Reloading**: Development server with auto-reload

---

## 🛠️ Installation

### Basic Installation
```bash
pip install lightapi
```

### With Optional Dependencies
```bash
# For Redis caching
pip install lightapi[redis]

# For PostgreSQL support
pip install lightapi[postgresql]

# For MySQL support
pip install lightapi[mysql]

# All features
pip install lightapi[all]
```

### Development Installation
```bash
git clone https://github.com/iklobato/lightapi.git
cd lightapi
pip install -e .
```

---

## ⚡ Quick Start

### 1. Basic CRUD API (30 seconds)

```python
from lightapi import LightApi
from lightapi.rest import RestEndpoint
from lightapi.models import Base
from sqlalchemy import Column, Integer, String, Float

class Product(Base, RestEndpoint):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    price = Column(Float, nullable=False)
    category = Column(String(50))

# Create API
app = LightApi(database_url="sqlite:///./products.db")
app.register(Product)

if __name__ == "__main__":
    app.run()
```

**That's it!** You now have a full REST API with:
- `GET /products` - List all products
- `GET /products/{id}` - Get specific product
- `POST /products` - Create new product
- `PUT /products/{id}` - Update product
- `DELETE /products/{id}` - Delete product
- Auto-generated OpenAPI docs at `/docs`

### 2. Advanced API with Authentication & Caching

```python
from lightapi import LightApi
from lightapi.rest import RestEndpoint
from lightapi.models import Base
from lightapi.cache import cache_manager
from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime

class User(Base, RestEndpoint):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    username = Column(String(50), nullable=False, unique=True)
    email = Column(String(100), nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def get(self, request):
        """Custom GET with caching"""
        user_id = request.path_params.get('id')
        if user_id:
            # Try cache first
            cache_key = f"user:{user_id}"
            cached_user = cache_manager.get(cache_key)
            if cached_user:
                return cached_user
            
            # Get from database and cache
            user = self.get_by_id(int(user_id))
            if user:
                user_data = {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "created_at": user.created_at.isoformat()
                }
                cache_manager.set(cache_key, user_data, ttl=300)  # 5 minutes
                return user_data
            return {"error": "User not found"}, 404
        
        return super().get(request)

# Create API with advanced features
app = LightApi(
    database_url="postgresql://user:pass@localhost/mydb",
    swagger_title="Advanced User API",
    cors_origins=["http://localhost:3000"],
    jwt_secret="your-secret-key"
)

app.register(User)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
```

---

## 📚 Feature Documentation

### 🔧 Basic CRUD Operations

LightAPI automatically generates CRUD endpoints for your SQLAlchemy models:

```python
from lightapi import LightApi
from lightapi.rest import RestEndpoint
from lightapi.models import Base
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime
from datetime import datetime

class Product(Base, RestEndpoint):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    description = Column(String(1000))
    price = Column(Float, nullable=False)
    category = Column(String(50), nullable=False)
    in_stock = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

app = LightApi(database_url="sqlite:///./products.db")
app.register(Product)
```

**Generated Endpoints:**
- `GET /products` - List products with pagination
- `GET /products/{id}` - Get specific product
- `POST /products` - Create new product
- `PUT /products/{id}` - Update existing product
- `DELETE /products/{id}` - Delete product

**Example Usage:**
```bash
# Create a product
curl -X POST http://localhost:8000/products \
  -H "Content-Type: application/json" \
  -d '{"name": "Laptop", "price": 999.99, "category": "electronics"}'

# Get all products
curl http://localhost:8000/products

# Get specific product
curl http://localhost:8000/products/1

# Update product
curl -X PUT http://localhost:8000/products/1 \
  -H "Content-Type: application/json" \
  -d '{"name": "Gaming Laptop", "price": 1299.99}'

# Delete product
curl -X DELETE http://localhost:8000/products/1
```

### ⚡ Async/Await Support

LightAPI supports async endpoints for high-performance applications:

```python
import asyncio
from lightapi.rest import RestEndpoint

class AsyncProduct(Base, RestEndpoint):
    __tablename__ = "async_products"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    
    async def get(self, request):
        """Async GET endpoint"""
        # Simulate async database query
        await asyncio.sleep(0.1)
        
        product_id = request.path_params.get('id')
        if product_id:
            # Async processing
            result = await self.async_get_product(int(product_id))
            return result
        
        # List all products
        products = await self.async_get_all_products()
        return {"products": products}
    
    async def post(self, request):
        """Async POST endpoint"""
        data = await request.json()
        
        # Async validation
        await self.async_validate(data)
        
        # Async save
        new_product = await self.async_create_product(data)
        return new_product, 201
    
    async def async_get_product(self, product_id):
        """Simulate async database lookup"""
        await asyncio.sleep(0.05)
        return {
            "id": product_id,
            "name": f"Async Product {product_id}",
            "processing_time": 0.05
        }
    
    async def async_get_all_products(self):
        """Simulate async list query"""
        await asyncio.sleep(0.1)
        return [
            {"id": i, "name": f"Product {i}"}
            for i in range(1, 11)
        ]
    
    async def async_validate(self, data):
        """Async validation"""
        await asyncio.sleep(0.02)
        if not data.get('name'):
            raise ValueError("Name is required")
    
    async def async_create_product(self, data):
        """Async product creation"""
        await asyncio.sleep(0.05)
        return {
            "id": 999,
            "name": data['name'],
            "created_at": datetime.utcnow().isoformat()
        }
```

**Benefits of Async:**
- Handle thousands of concurrent requests
- Non-blocking I/O operations
- Better resource utilization
- Improved response times under load

### 📖 OpenAPI/Swagger Documentation

LightAPI automatically generates comprehensive API documentation:

```python
app = LightApi(
    database_url="sqlite:///./api.db",
    swagger_title="My Awesome API",
    swagger_version="2.0.0",
    swagger_description="A comprehensive REST API built with LightAPI",
    enable_swagger=True  # Default: True
)
```

**Documentation Features:**
- **Swagger UI**: Interactive API explorer at `/docs`
- **ReDoc**: Alternative documentation at `/redoc`
- **OpenAPI Schema**: JSON schema at `/openapi.json`
- **Auto-generated**: Models, endpoints, and validation rules
- **Customizable**: Add descriptions, examples, and metadata

**Access Documentation:**
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

### 🔐 JWT Authentication

Secure your API with JWT token authentication:

```python
import os
from lightapi import LightApi
from lightapi.auth import AuthEndpoint

# Set JWT secret
os.environ['LIGHTAPI_JWT_SECRET'] = 'your-super-secret-key'

class User(Base, RestEndpoint):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True)
    password_hash = Column(String(255))

class AuthUser(AuthEndpoint):
    """Authentication endpoint"""
    __tablename__ = "auth_users"
    
    id = Column(Integer, primary_key=True)
    username = Column(String(50))
    role = Column(String(20), default="user")

app = LightApi(
    database_url="sqlite:///./secure_api.db",
    jwt_secret="your-super-secret-key"
)

app.register(User)
app.register(AuthUser)
```

**Authentication Flow:**
1. **Login**: `POST /authendpoint` with credentials
2. **Get Token**: Receive JWT token in response
3. **Use Token**: Include in `Authorization: Bearer <token>` header
4. **Access Protected**: Access protected endpoints

**Example Usage:**
```bash
# Login and get token
curl -X POST http://localhost:8000/authendpoint \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "secret"}'

# Response: {"access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."}

# Use token to access protected endpoint
curl -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..." \
  http://localhost:8000/secretresource
```

**JWT Features:**
- Token expiration handling
- Role-based access control
- Automatic token validation
- Secure secret key management
- Custom claims support

### 🌐 CORS Support

Enable Cross-Origin Resource Sharing for web applications:

```python
app = LightApi(
    database_url="sqlite:///./api.db",
    cors_origins=[
        "http://localhost:3000",    # React dev server
        "http://localhost:8080",    # Vue dev server
        "https://myapp.com",        # Production frontend
        "https://*.myapp.com"       # Subdomains
    ]
)
```

**CORS Configuration:**
```python
# Allow all origins (development only)
app = LightApi(cors_origins=["*"])

# Specific origins
app = LightApi(cors_origins=[
    "http://localhost:3000",
    "https://myapp.com"
])

# Environment-based configuration
import os
cors_origins = os.getenv('CORS_ORIGINS', '').split(',')
app = LightApi(cors_origins=cors_origins)
```

### 💾 Redis Caching

Boost performance with intelligent Redis caching:

```python
from lightapi.cache import cache_manager

class CachedProduct(Base, RestEndpoint):
    __tablename__ = "cached_products"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    price = Column(Float)
    
    def get(self, request):
        """GET with caching"""
        product_id = request.path_params.get('id')
        
        if product_id:
            # Try cache first
            cache_key = f"product:{product_id}"
            cached_product = cache_manager.get(cache_key)
            
            if cached_product:
                return {
                    **cached_product,
                    "cache_hit": True,
                    "ttl_remaining": cache_manager.ttl(cache_key)
                }
            
            # Get from database
            product = self.get_by_id(int(product_id))
            if product:
                product_data = {
                    "id": product.id,
                    "name": product.name,
                    "price": product.price
                }
                
                # Cache for 5 minutes
                cache_manager.set(cache_key, product_data, ttl=300)
                
                return {
                    **product_data,
                    "cache_hit": False,
                    "cached_for": 300
                }
            
            return {"error": "Product not found"}, 404
        
        # List with caching
        cache_key = "products:list"
        cached_list = cache_manager.get(cache_key)
        
        if cached_list:
            return {
                **cached_list,
                "cache_hit": True
            }
        
        # Get from database and cache
        products = self.get_all()
        result = {
            "products": [
                {"id": p.id, "name": p.name, "price": p.price}
                for p in products
            ]
        }
        
        cache_manager.set(cache_key, result, ttl=120)  # 2 minutes
        
        return {
            **result,
            "cache_hit": False
        }
    
    def post(self, request):
        """POST with cache invalidation"""
        result = super().post(request)
        
        # Invalidate list cache when creating new product
        cache_manager.delete("products:list")
        
        return result
    
    def put(self, request):
        """PUT with cache update"""
        product_id = request.path_params.get('id')
        result = super().put(request)
        
        # Update cache
        if product_id:
            cache_key = f"product:{product_id}"
            cache_manager.delete(cache_key)  # Or update with new data
            cache_manager.delete("products:list")  # Invalidate list
        
        return result
```

**Caching Features:**
- **TTL Support**: Automatic expiration
- **Cache Invalidation**: Smart cache clearing
- **Pattern Deletion**: Clear multiple keys at once
- **Cache Statistics**: Monitor hit/miss rates
- **JSON Serialization**: Automatic data serialization
- **Key Isolation**: Prevent key conflicts

**Cache Management:**
```python
# Cache statistics
stats = cache_manager.get_info()

# Clear all caches
cache_manager.clear_all()

# Delete by pattern
cache_manager.delete_pattern("products:*")

# Check TTL
remaining = cache_manager.ttl("product:123")
```

### 🔍 Advanced Filtering & Pagination

Powerful querying capabilities out of the box:

```python
class AdvancedProduct(Base, RestEndpoint):
    __tablename__ = "advanced_products"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200))
    price = Column(Float)
    category = Column(String(50))
    brand = Column(String(100))
    rating = Column(Float)
    in_stock = Column(Boolean)
    created_at = Column(DateTime)
    
    def get(self, request):
        """Advanced filtering and pagination"""
        params = request.query_params
        
        # Pagination
        page = int(params.get('page', 1))
        page_size = int(params.get('page_size', 10))
        
        # Filtering
        filters = {}
        if params.get('category'):
            filters['category'] = params.get('category')
        if params.get('brand'):
            filters['brand'] = params.get('brand')
        if params.get('min_price'):
            filters['min_price'] = float(params.get('min_price'))
        if params.get('max_price'):
            filters['max_price'] = float(params.get('max_price'))
        if params.get('min_rating'):
            filters['min_rating'] = float(params.get('min_rating'))
        if params.get('in_stock') is not None:
            filters['in_stock'] = params.get('in_stock').lower() == 'true'
        
        # Text search
        search = params.get('search')
        if search:
            filters['search'] = search
        
        # Sorting
        sort_by = params.get('sort_by', 'id')
        sort_order = params.get('sort_order', 'asc')
        
        # Apply filters and get results
        products = self.filter_products(filters, sort_by, sort_order)
        
        # Pagination
        total_count = len(products)
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        paginated_products = products[start_index:end_index]
        
        return {
            "products": paginated_products,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_count": total_count,
                "total_pages": (total_count + page_size - 1) // page_size,
                "has_next": page * page_size < total_count,
                "has_prev": page > 1
            },
            "filters": filters,
            "sorting": {
                "sort_by": sort_by,
                "sort_order": sort_order
            }
        }
```

**Query Examples:**
```bash
# Basic pagination
GET /products?page=1&page_size=20

# Filter by category
GET /products?category=electronics

# Price range filter
GET /products?min_price=100&max_price=500

# Multiple filters with sorting
GET /products?category=electronics&brand=apple&min_rating=4.0&sort_by=price&sort_order=desc

# Text search
GET /products?search=laptop

# Complex query
GET /products?category=electronics&min_price=200&max_price=1000&in_stock=true&sort_by=rating&sort_order=desc&page=2&page_size=15
```

### ✅ Request Validation

Comprehensive input validation and error handling:

```python
import re
from datetime import datetime

class ValidatedUser(Base, RestEndpoint):
    __tablename__ = "validated_users"
    
    id = Column(Integer, primary_key=True)
    username = Column(String(50), nullable=False)
    email = Column(String(100), nullable=False)
    age = Column(Integer)
    salary = Column(Float)
    
    def validate_data(self, data, method='POST'):
        """Comprehensive validation"""
        errors = []
        
        # Username validation
        username = data.get('username', '').strip()
        if method == 'POST' and not username:
            errors.append("Username is required")
        elif username:
            if len(username) < 3:
                errors.append("Username must be at least 3 characters")
            elif len(username) > 50:
                errors.append("Username must be no more than 50 characters")
            elif not re.match(r'^[a-zA-Z0-9_]+$', username):
                errors.append("Username can only contain letters, numbers, and underscores")
        
        # Email validation
        email = data.get('email', '').strip()
        if method == 'POST' and not email:
            errors.append("Email is required")
        elif email:
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if not re.match(email_pattern, email):
                errors.append("Invalid email format")
        
        # Age validation
        age = data.get('age')
        if age is not None:
            try:
                age = int(age)
                if age < 0:
                    errors.append("Age cannot be negative")
                elif age > 150:
                    errors.append("Age cannot be more than 150")
            except (ValueError, TypeError):
                errors.append("Age must be a valid integer")
        
        # Salary validation
        salary = data.get('salary')
        if salary is not None:
            try:
                salary = float(salary)
                if salary < 0:
                    errors.append("Salary cannot be negative")
            except (ValueError, TypeError):
                errors.append("Salary must be a valid number")
        
        return errors
    
    def post(self, request):
        """Create with validation"""
        try:
            data = request.data
            
            # Validate
            errors = self.validate_data(data, method='POST')
            if errors:
                return {
                    "error": "Validation failed",
                    "details": errors,
                    "received_data": data
                }, 400
            
            # Create user
            new_user = {
                "id": 123,
                "username": data['username'].strip(),
                "email": data['email'].strip(),
                "age": int(data.get('age', 0)) if data.get('age') else None,
                "salary": float(data.get('salary', 0)) if data.get('salary') else None,
                "created_at": datetime.utcnow().isoformat()
            }
            
            return new_user, 201
            
        except Exception as e:
            return {
                "error": "Internal server error",
                "message": str(e)
            }, 500
    
    def put(self, request):
        """Update with validation"""
        user_id = request.path_params.get('id')
        if not user_id:
            return {"error": "User ID is required"}, 400
        
        try:
            user_id = int(user_id)
        except ValueError:
            return {"error": "Invalid user ID format"}, 400
        
        data = request.data
        errors = self.validate_data(data, method='PUT')
        
        if errors:
            return {
                "error": "Validation failed",
                "details": errors
            }, 400
        
        # Update logic here
        return {"message": "User updated successfully"}
```

**Validation Features:**
- **Field Validation**: Required fields, length limits, format checks
- **Type Validation**: Automatic type conversion and validation
- **Custom Rules**: Business logic validation
- **Error Aggregation**: Multiple validation errors in single response
- **Method-Specific**: Different validation for POST/PUT/PATCH
- **Detailed Errors**: Clear error messages with field information

### 📄 YAML Configuration

**Create REST APIs without writing Python code!** LightAPI can automatically generate full CRUD APIs from existing database tables using simple YAML configuration files.

#### Basic YAML Configuration

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

#### Advanced YAML Configuration

```yaml
# advanced_config.yaml
database_url: "${DATABASE_URL}"  # Environment variable
swagger_title: "E-commerce API"
swagger_version: "2.0.0"
swagger_description: |
  E-commerce API with role-based permissions
  
  ## Permission Levels
  - Admin: Full user management
  - Manager: Product and inventory management
  - Customer: Order creation and viewing
enable_swagger: true

tables:
  # ADMIN LEVEL - Full access
  - name: users
    crud: [get, post, put, patch, delete]
  
  # MANAGER LEVEL - Product management
  - name: products
    crud: [get, post, put, patch, delete]
  
  # CUSTOMER LEVEL - Limited operations
  - name: orders
    crud: [get, post, patch]  # Create orders, update status only
  
  # READ-ONLY - Audit trail
  - name: audit_log
    crud: [get]
```

#### Database Support

```yaml
# SQLite
database_url: "sqlite:///app.db"

# PostgreSQL
database_url: "postgresql://user:pass@localhost:5432/db"

# MySQL
database_url: "mysql+pymysql://user:pass@localhost:3306/db"

# Environment variables
database_url: "${DATABASE_URL}"
```

#### Run YAML-Configured API

```python
from lightapi import LightApi

# Create API from YAML configuration
app = LightApi.from_config('config.yaml')
app.run()
```

**That's it!** Your API is now running with:
- Full CRUD operations based on your configuration
- Automatic input validation from database schema
- Interactive Swagger documentation at `/docs`
- Proper HTTP status codes and error handling

#### CRUD Operations

Each CRUD operation maps to HTTP methods:

| CRUD | HTTP Method | Endpoint | Description |
|------|-------------|----------|-------------|
| `get` | GET | `/table/` | List all records |
| `get` | GET | `/table/{id}` | Get specific record |
| `post` | POST | `/table/` | Create new record |
| `put` | PUT | `/table/{id}` | Update entire record |
| `patch` | PATCH | `/table/{id}` | Partially update record |
| `delete` | DELETE | `/table/{id}` | Delete record |

#### Configuration Patterns

```yaml
# Full CRUD
- name: users
  crud: [get, post, put, patch, delete]

# Read-only (analytics, reports)
- name: analytics
  crud: [get]

# Create + Read (blog posts)
- name: posts
  crud: [get, post]

# No delete (data integrity)
- name: categories
  crud: [get, post, put, patch]

# Status updates only
- name: orders
  crud: [get, patch]
```

#### Environment-Based Deployment

```yaml
# development.yaml
database_url: "${DEV_DATABASE_URL}"
enable_swagger: true
tables:
  - name: users
    crud: [get, post, put, patch, delete]  # Full access in dev

# production.yaml  
database_url: "${PROD_DATABASE_URL}"
enable_swagger: false  # Disabled in production
tables:
  - name: users
    crud: [get, patch]  # Limited access in production
```

**Key Benefits:**
- **Zero Python Code**: Define APIs using only YAML
- **Database Reflection**: Automatically discovers existing tables and schemas
- **Environment Variables**: Flexible deployment across dev/staging/production
- **Role-Based Permissions**: Different CRUD operations per table
- **Production Ready**: Proper error handling and validation

### 🔧 Custom Middleware

Extend LightAPI with custom middleware:

```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import time
import logging

class PerformanceMiddleware(BaseHTTPMiddleware):
    """Log request performance"""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Log performance
        logging.info(f"{request.method} {request.url.path} - {duration:.3f}s")
        
        # Add performance header
        response.headers["X-Process-Time"] = str(duration)
        
        return response

class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Custom authentication middleware"""
    
    def __init__(self, app, excluded_paths=None):
        super().__init__(app)
        self.excluded_paths = excluded_paths or ['/docs', '/redoc', '/openapi.json']
    
    async def dispatch(self, request: Request, call_next):
        # Skip authentication for excluded paths
        if request.url.path in self.excluded_paths:
            return await call_next(request)
        
        # Check for API key
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            return Response("API Key required", status_code=401)
        
        # Validate API key (implement your logic)
        if not self.validate_api_key(api_key):
            return Response("Invalid API Key", status_code=401)
        
        # Add user info to request
        request.state.user = self.get_user_from_api_key(api_key)
        
        return await call_next(request)
    
    def validate_api_key(self, api_key):
        # Implement API key validation
        return api_key == "valid-api-key"
    
    def get_user_from_api_key(self, api_key):
        # Get user information from API key
        return {"id": 1, "username": "api_user"}

# Add middleware to app
app = LightApi(database_url="sqlite:///./api.db")

app.add_middleware(PerformanceMiddleware)
app.add_middleware(AuthenticationMiddleware, excluded_paths=['/docs', '/health'])
```

---

## 📁 Examples

LightAPI includes comprehensive examples for all features:

### 📂 Example Files
- **`examples/rest_crud_basic.py`** - Basic CRUD operations
- **`examples/async_performance.py`** - Async/await performance demo
- **`examples/authentication_jwt.py`** - JWT authentication
- **`examples/caching_redis_custom.py`** - Redis caching strategies
- **`examples/advanced_filtering_pagination.py`** - Complex queries
- **`examples/advanced_validation.py`** - Comprehensive validation
- **`examples/yaml_configuration.py`** - YAML-driven API generation
- **`examples/middleware_custom.py`** - Custom middleware
- **`examples/swagger_openapi_docs.py`** - Documentation customization

### 🚀 Running Examples

```bash
# Clone the repository
git clone https://github.com/iklobato/lightapi.git
cd lightapi

# Install dependencies
pip install -e .

# Run basic CRUD example
python examples/rest_crud_basic.py

# Run async performance example
python examples/async_performance.py

# Run JWT authentication example
python examples/authentication_jwt.py

# Run caching example (requires Redis)
redis-server  # Start Redis in another terminal
python examples/caching_redis_custom.py
```

---

## 🧪 Testing

LightAPI includes comprehensive test coverage:

### 🔧 Running Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run all tests
pytest

# Run specific test categories
pytest tests/test_crud.py
pytest tests/test_auth.py
pytest tests/test_caching.py
pytest tests/test_validation.py

# Run with coverage
pytest --cov=lightapi --cov-report=html
```

### 📊 Test Coverage

LightAPI maintains high test coverage across all features:
- ✅ CRUD operations
- ✅ Async functionality
- ✅ JWT authentication
- ✅ Redis caching
- ✅ Request validation
- ✅ Error handling
- ✅ Middleware
- ✅ Configuration

---

## 🔧 Configuration

### 🌍 Environment Variables

```bash
# Database
export LIGHTAPI_DATABASE_URL="postgresql://user:pass@localhost/db"

# Server
export LIGHTAPI_HOST="0.0.0.0"
export LIGHTAPI_PORT="8000"
export LIGHTAPI_DEBUG="true"

# JWT Authentication
export LIGHTAPI_JWT_SECRET="your-super-secret-key"

# CORS
export LIGHTAPI_CORS_ORIGINS='["http://localhost:3000", "https://myapp.com"]'

# Swagger
export LIGHTAPI_SWAGGER_TITLE="My API"
export LIGHTAPI_SWAGGER_VERSION="1.0.0"
export LIGHTAPI_ENABLE_SWAGGER="true"

# Caching
export LIGHTAPI_CACHE_TIMEOUT="3600"
```

### ⚙️ Configuration Class

```python
from lightapi.config import Config

# Custom configuration
config = Config()
config.database_url = "postgresql://localhost/mydb"
config.jwt_secret = "my-secret"
config.cors_origins = ["http://localhost:3000"]

app = LightApi(config=config)
```

---

## 🚀 Deployment

### 🐳 Docker Deployment

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

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
      - LIGHTAPI_DATABASE_URL=postgresql://postgres:password@db:5432/mydb
      - LIGHTAPI_JWT_SECRET=your-secret-key
    depends_on:
      - db
      - redis

  db:
    image: postgres:13
    environment:
      - POSTGRES_DB=mydb
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:6-alpine
    ports:
      - "6379:6379"

volumes:
  postgres_data:
```

### ☁️ Cloud Deployment

**Heroku:**
```bash
# Install Heroku CLI
heroku create my-lightapi-app
heroku addons:create heroku-postgresql:hobby-dev
heroku addons:create heroku-redis:hobby-dev
heroku config:set LIGHTAPI_JWT_SECRET=your-secret-key
git push heroku main
```

**AWS Lambda:**
```python
# lambda_handler.py
from mangum import Mangum
from main import app

handler = Mangum(app)
```

---

## ❓ FAQ

### Q: How does LightAPI compare to FastAPI?
**A:** LightAPI builds on FastAPI's foundation but focuses specifically on rapid CRUD API development. While FastAPI is a general-purpose framework, LightAPI provides:
- Automatic CRUD endpoint generation
- Built-in caching with Redis
- YAML-driven API configuration
- Advanced filtering and pagination out of the box
- Simplified authentication setup

### Q: Can I use LightAPI with existing databases?
**A:** Yes! LightAPI works with any SQLAlchemy-compatible database. You can:
- Use existing SQLAlchemy models
- Generate models from existing database schemas
- Configure database connections via environment variables
- Support PostgreSQL, MySQL, SQLite, and more

### Q: Is LightAPI production-ready?
**A:** Absolutely! LightAPI is built on proven technologies:
- Starlette/Uvicorn for high performance
- SQLAlchemy for robust database operations
- Pydantic for data validation
- Redis for caching
- Comprehensive error handling and logging

### Q: How do I handle database migrations?
**A:** LightAPI integrates with Alembic for database migrations:
```bash
# Initialize migrations
alembic init migrations

# Create migration
alembic revision --autogenerate -m "Add users table"

# Apply migrations
alembic upgrade head
```

### Q: Can I customize the generated endpoints?
**A:** Yes! You have full control:
- Override any HTTP method in your RestEndpoint class
- Add custom validation logic
- Implement custom business logic
- Add middleware for cross-cutting concerns
- Customize response formats

### Q: How do I handle file uploads?
**A:** LightAPI supports file uploads through Starlette:
```python
from starlette.requests import Request

class FileUpload(Base, RestEndpoint):
    def post(self, request: Request):
        form = await request.form()
        file = form["file"]
        
        # Process file
        content = await file.read()
        
        return {"filename": file.filename, "size": len(content)}
```

---

## 📊 Performance

LightAPI is designed for high performance:

### 🚀 Benchmarks
- **Requests/second**: 10,000+ (simple CRUD operations)
- **Async support**: Handle thousands of concurrent connections
- **Memory usage**: Low memory footprint with efficient caching
- **Response times**: Sub-millisecond for cached responses

### ⚡ Performance Tips
1. **Use async endpoints** for I/O-heavy operations
2. **Enable Redis caching** for frequently accessed data
3. **Implement pagination** for large datasets
4. **Use database indexes** for filtered fields
5. **Configure connection pooling** for high-traffic applications

---

## 🤝 Contributing

We welcome contributions! Here's how to get started:

### 🔧 Development Setup
```bash
# Clone repository
git clone https://github.com/iklobato/lightapi.git
cd lightapi

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
flake8 lightapi/
black lightapi/
```

### 📝 Contribution Guidelines
1. **Fork** the repository
2. **Create** a feature branch
3. **Write** tests for new features
4. **Ensure** all tests pass
5. **Submit** a pull request

### 🐛 Bug Reports
Please use GitHub Issues to report bugs. Include:
- Python version
- LightAPI version
- Minimal code example
- Error messages and stack traces

---

## 📄 License

LightAPI is released under the MIT License. See [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

LightAPI is built on the shoulders of giants:
- **FastAPI** - For the excellent foundation and inspiration
- **Starlette** - For the high-performance ASGI framework
- **SQLAlchemy** - For the powerful ORM
- **Pydantic** - For data validation
- **Uvicorn** - For the lightning-fast ASGI server

---

## 📞 Support

- **Documentation**: [https://lightapi.readthedocs.io](https://lightapi.readthedocs.io)
- **GitHub Issues**: [https://github.com/iklobato/lightapi/issues](https://github.com/iklobato/lightapi/issues)
- **Discussions**: [https://github.com/iklobato/lightapi/discussions](https://github.com/iklobato/lightapi/discussions)
- **Email**: support@lightapi.dev

---

**Ready to build lightning-fast APIs? Get started with LightAPI today!** ⚡

```bash
pip install lightapi
```