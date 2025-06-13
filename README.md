# LightAPI

[![PyPI version](https://badge.fury.io/py/lightapi.svg)](https://badge.fury.io/py/lightapi)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A lightweight, fast, and easy-to-use web API framework for Python with automatic REST endpoint generation, built-in authentication, caching, and more.

## Features

- 🚀 **Zero-boilerplate REST APIs** - Automatically generate CRUD operations from SQLAlchemy models
- 🔐 **Built-in Authentication** - JWT authentication with automatic CORS handling
- ⚡ **High Performance** - Built on Starlette for async support and speed
- 💾 **Smart Caching** - Redis-based caching with automatic invalidation
- 📊 **Request Validation** - Automatic request validation and error handling
- 🔍 **Advanced Filtering** - Query filtering, pagination, and sorting out of the box
- 📖 **Auto Documentation** - Automatic OpenAPI/Swagger documentation generation
- 🔧 **Flexible Middleware** - Easy middleware system for custom logic
- 🗄️ **Database Integration** - Seamless SQLAlchemy integration with automatic table creation
- ⚙️ **Environment Configuration** - Easy configuration management

## Quick Start

### Installation

```bash
pip install lightapi
```

### Basic Usage

```python
from lightapi import LightApi
from lightapi.database import Base
from sqlalchemy import Column, Integer, String

# Define your model
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(50))
    email = Column(String(100))

# Create API instance
app = LightApi()

# Register your model - automatically creates CRUD endpoints
app.register(User)

# Run the server
if __name__ == "__main__":
    app.run()
```

That's it! You now have a fully functional REST API with:
- `GET /users` - List all users with filtering and pagination
- `GET /users/{id}` - Get user by ID
- `POST /users` - Create new user
- `PUT /users/{id}` - Update user
- `DELETE /users/{id}` - Delete user
- `OPTIONS /users` - CORS preflight support

## Dynamic API from YAML Config (SQLAlchemy Reflection)

LightAPI can instantly generate a REST API from a YAML configuration file, reflecting your database schema at runtime using SQLAlchemy. This is ideal for exposing existing databases with zero model code.

### How It Works
- **Reflects** the schema of specified tables from your database (PostgreSQL, MySQL, SQLite, etc.)
- **Dynamically generates** SQLAlchemy models and CRUD endpoints for each table
- **Configurable**: You control which tables and which CRUD operations (GET, POST, PUT, PATCH, DELETE) are exposed
- **Composite primary keys, unique constraints, foreign keys, BLOBs, JSON, and more** are supported
- **Advanced edge cases** (triggers, generated columns, partial unique constraints, etc.) are handled

### End-to-End Example

#### 1. Create a YAML Config
```yaml
database_url: sqlite:///mydata.db

tables:
  - name: users
    crud: [get, post, put, patch, delete]
  - name: orders
    crud: [get, post]
```

#### 2. Create Your Database (SQLite example)
```bash
sqlite3 mydata.db "CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE); CREATE TABLE orders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, amount REAL NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id));"
```

#### 3. Start the API
```python
from lightapi import LightApi
import aiohttp.web

api = LightApi.from_config('my_api_config.yaml')
app = api.app

aiohttp.web.run_app(app, port=8080)
```

#### 4. Use the API (with curl)
```bash
# Create a user
curl -X POST http://localhost:8080/users/ -H 'Content-Type: application/json' -d '{"name": "Alice", "email": "alice@example.com"}'

# List users
curl http://localhost:8080/users/

# Create an order for Alice (id=1)
curl -X POST http://localhost:8080/orders/ -H 'Content-Type: application/json' -d '{"user_id": 1, "amount": 42.5}'

# List orders
curl http://localhost:8080/orders/
```

### FAQ & Tips
- **Server-side defaults**: Only `server_default` (e.g., `server_default=text('...')`) are available after reflection. Python-side defaults are not reflected.
- **Composite PKs**: Supported transparently in routes and handlers.
- **Error handling**: Unique, check, not null, and foreign key constraints are enforced. Violations return 409 Conflict with details.
- **Partial CRUD**: You can expose only the operations you want per table.
- **Supported DBs**: Any DB supported by SQLAlchemy reflection (PostgreSQL, MySQL, SQLite, etc.)

See the [docs](./docs/getting-started/quickstart.md#dynamic-api-from-yaml-config-sqlalchemy-reflection) for more advanced examples and details.

## Documentation

Visit our comprehensive documentation at: https://iklobato.github.io/lightapi/

- [Getting Started Guide](https://iklobato.github.io/lightapi/getting-started/installation/)
- [API Reference](https://iklobato.github.io/lightapi/api-reference/core/)
- [Examples](https://iklobato.github.io/lightapi/examples/basic-rest/)

## Advanced Features

### Authentication

```python
from lightapi.auth import JWTAuthentication

# Add JWT authentication
auth = JWTAuthentication(secret_key="your-secret-key")
app.add_middleware(auth)

# Protected endpoints automatically require valid JWT tokens
```

### Caching

```python
from lightapi.cache import RedisCache

# Add Redis caching
cache = RedisCache(host="localhost", port=6379)
app.register(User, cache=cache, cache_ttl=300)  # 5 minutes TTL
```

### Validation

```python
from lightapi.rest import Validator

class UserValidator(Validator):
    def validate_post(self, data):
        if not data.get("email"):
            raise ValueError("Email is required")
        return data

app.register(User, validator=UserValidator())
```

- All required fields must be defined as NOT NULL in your database schema for correct enforcement.
- The API will return 409 Conflict if you attempt to create or update a record missing a NOT NULL field, or violating a UNIQUE or FOREIGN KEY constraint.

### Middleware

```python
from lightapi.core import Middleware

class LoggingMiddleware(Middleware):
    async def process(self, request, call_next):
        print(f"Request: {request.method} {request.url}")
        response = await call_next(request)
        print(f"Response: {response.status_code}")
        return response

app.add_middleware(LoggingMiddleware())
```

## Why LightAPI?

- **Rapid Development**: Get REST APIs running in minutes, not hours
- **Production Ready**: Built-in security, caching, and error handling
- **Flexible**: Customize every aspect while keeping defaults simple
- **Modern**: Async support, type hints, and contemporary Python practices
- **Well Documented**: Comprehensive docs with real-world examples

## Examples

Check out the [examples directory](./examples/) for complete applications:

- [Basic REST API](./examples/basic_rest_api.py) - Simple CRUD operations
- [Authentication](./examples/auth_example.py) - JWT authentication
- [Caching](./examples/caching_example.py) - Redis caching implementation
- [Validation](./examples/validation_example.py) - Request validation
- [Middleware](./examples/middleware_example.py) - Custom middleware
- [Filtering & Pagination](./examples/filtering_pagination_example.py) - Advanced queries

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**LightAPI** - *Making web APIs light and fast* ⚡

<!-- Testing development pipeline -->

> **Note:** Only GET, POST, PUT, PATCH, DELETE HTTP verbs are supported. OPTIONS and HEAD are not available. Required fields must be NOT NULL in the schema. Constraint violations (NOT NULL, UNIQUE, FK) return 409.
