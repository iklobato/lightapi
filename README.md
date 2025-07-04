# LightAPI: Fast Python REST API Framework with Async, CRUD, OpenAPI, JWT, and YAML

[![PyPI version](https://badge.fury.io/py/lightapi.svg)](https://pypi.org/project/lightapi/)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**LightAPI** is a fast, async-ready Python REST API framework that lets you instantly generate CRUD endpoints from SQLAlchemy models or your existing database schema. With built-in OpenAPI documentation, JWT authentication, Redis caching, and YAML-driven configuration, LightAPI is the best choice for building scalable, production-ready APIs in Python.

---

## Table of Contents
- [Why LightAPI?](#why-lightapi)
- [Who is LightAPI for?](#who-is-lightapi-for)
- [Features: Python REST API, Async, CRUD, OpenAPI, JWT, Caching](#features-python-rest-api-async-crud-openapi-jwt-caching)
- [Feature Details & Usage](#feature-details--usage)
  - [Automatic CRUD Endpoints with SQLAlchemy](#automatic-crud-endpoints-with-sqlalchemy)
  - [YAML-Driven API Generation (Database Reflection)](#yaml-driven-api-generation-database-reflection)
  - [OpenAPI/Swagger Documentation](#openapiswapper-documentation)
  - [Works with All Major Databases](#works-with-all-major-databases)
  - [Environment-based Configuration](#environment-based-configuration)
  - [JWT Authentication and Security](#jwt-authentication-and-security)
  - [CORS Support for Python APIs](#cors-support-for-python-apis)
  - [Custom Middleware for Python APIs](#custom-middleware-for-python-apis)
  - [Async/Await Support for High-Performance Python APIs](#asyncawait-support-for-high-performance-python-apis)
  - [Redis Caching for Python APIs](#redis-caching-for-python-apis)
  - [Filtering, Pagination, and Sorting](#filtering-pagination-and-sorting)
  - [Request Validation](#request-validation)
  - [Type Hints & Modern Python](#type-hints--modern-python)
  - [Comprehensive Error Handling](#comprehensive-error-handling)
- [Quick Start: Build a Python REST API in Minutes](#quick-start-build-a-python-rest-api-in-minutes)
- [Example Endpoints](#example-endpoints)
- [Documentation](#documentation)
- [FAQ](#faq)
- [Comparison](#comparison)
- [License](#license)
- [Troubleshooting](#troubleshooting)

---

## Why LightAPI?

LightAPI is a modern, async-ready Python REST API framework designed for rapid development and production use. Instantly generate CRUD endpoints from your SQLAlchemy models or YAML config, with full support for OpenAPI docs, JWT authentication, Redis caching, request validation, and more. LightAPI is ideal for anyone who wants to build scalable, maintainable, and high-performance APIs in Python.

---

## Who is LightAPI for?

- **Backend developers** who want to ship APIs fast, with minimal code.
- **Data engineers** needing to expose existing databases as RESTful services.
- **Prototypers** and **startups** who want to iterate quickly and scale later.
- **Anyone** who wants a clean, maintainable, and extensible Python API stack.

---

# Features: Python REST API, Async, CRUD, OpenAPI, JWT, Caching

LightAPI is designed to cover all the essentials for modern API development. Features are grouped for clarity:

## Core Features
- **Automatic CRUD Endpoints with SQLAlchemy**
- **YAML-Driven API Generation (Database Reflection)**
- **OpenAPI/Swagger Documentation**
- **Works with All Major Databases**
- **Environment-based Configuration**

## Security & Access Control
- **JWT Authentication and Security**
- **CORS Support for Python APIs**
- **Custom Middleware for Python APIs**

## Performance & Scalability
- **Async/Await Support for High-Performance Python APIs**
- **Redis Caching for Python APIs**
- **Filtering, Pagination, and Sorting**

## Developer Experience
- **Request Validation**
- **Type Hints & Modern Python**
- **Comprehensive Error Handling**

---

# Feature Details & Usage

## Automatic CRUD Endpoints with SQLAlchemy
Instantly generate RESTful endpoints for your models or tables, so you can create, read, update, and delete records with no manual wiring.
```python
from lightapi import LightApi
from sqlalchemy import Column, Integer, String
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String(50))
app = LightApi()
app.register(User)
```
*How to use:* Define your SQLAlchemy model, register it with `app.register()`, and LightAPI will expose full CRUD endpoints automatically. 
*Use cases:* Quickly build admin panels, internal tools, or MVPs where you need instant API access to your data.

## YAML-Driven API Generation (Database Reflection)
Point LightAPI at your existing database and expose tables as REST endpoints without writing model code. [Learn more about SQLAlchemy](https://www.sqlalchemy.org/).
```yaml
# config.yaml
database_url: sqlite:///mydata.db
tables:
  - name: users
    crud: [get, post, put, patch, delete]
```
```python
from lightapi import LightApi
api = LightApi.from_config('config.yaml')
api.run()
```
*How to use:* Create a YAML config describing your database and tables, then use `LightApi.from_config()` to generate endpoints instantly.
*Use cases:* Expose legacy or third-party databases as REST APIs for integration, analytics, or migration.

## OpenAPI/Swagger Documentation
Get interactive API docs and OpenAPI JSON automatically, always in sync with your endpoints. [Learn more about OpenAPI](https://swagger.io/specification/).
```python
app = LightApi(swagger_title="My API", swagger_version="1.0.0")
# Visit http://localhost:8000/docs
```
*How to use:* Set Swagger options when creating your app. Docs are auto-generated and always up to date.
*Use cases:* Share your API with frontend teams, generate client SDKs, or provide public API documentation.

## Works with All Major Databases
Use SQLite, PostgreSQL, MySQL, or any SQLAlchemy-supported backend. [SQLAlchemy Docs](https://docs.sqlalchemy.org/)
```python
app = LightApi(database_url="postgresql://user:pass@localhost/db")
# or
app = LightApi(database_url="mysql://user:pass@localhost/db")
```
*How to use:* Set the `database_url` parameter to match your database backend.
*Use cases:* Migrate between databases, support multiple environments, or connect to cloud-hosted DBs.

## Environment-based Configuration
Configure your app for development, testing, or production using environment variables or YAML.
```yaml
# config.yaml
database_url: sqlite:///dev.db
debug: true
```
```python
api = LightApi.from_config('config.yaml')
```
*How to use:* Store your settings in a YAML file or environment variables, then load them with `from_config()` or `os.environ`.
*Use cases:* Seamlessly switch between dev, staging, and production setups, or deploy with Docker and CI/CD.

## JWT Authentication and Security
Secure your API with industry-standard JSON Web Tokens, including login endpoints and protected resources. [Learn more about JWT](https://jwt.io/)
```python
from lightapi.auth import JWTAuthentication
class UserEndpoint(RestEndpoint):
    class Configuration:
        authentication_class = JWTAuthentication
# Set secret
export LIGHTAPI_JWT_SECRET="supersecret"
```
*How to use:* Add `authentication_class = JWTAuthentication` to your endpoint's Configuration. Set the secret key as an environment variable. 
*Use cases:* Protect sensitive endpoints, implement login/logout, and control access for different user roles.

## CORS Support for Python APIs
Easily enable Cross-Origin Resource Sharing for frontend/backend integration. [Learn more about CORS](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS)
```python
from lightapi.core import CORSMiddleware
app.add_middleware([CORSMiddleware])
```
*How to use:* Add `CORSMiddleware` to your app's middleware list to allow cross-origin requests from browsers.
*Use cases:* Enable frontend apps (React, Vue, etc.) to call your API from a different domain during development or production.

## Custom Middleware for Python APIs
Add logging, rate limiting, authentication, or any cross-cutting logic with a simple middleware interface.
```python
from lightapi.core import Middleware
class LoggingMiddleware(Middleware):
    def process(self, request, response=None):
        print(f"{request.method} {request.url}")
        return response
app.add_middleware([LoggingMiddleware])
```
*How to use:* Subclass `Middleware` and implement the `process` method. Add your middleware to the app.
*Use cases:* Add request logging, enforce rate limits, or inject custom headers for all responses.

## Async/Await Support for High-Performance Python APIs
Built on aiohttp for high concurrency and fast response times. All endpoints are async-ready; just use `async def` in your handlers. [Learn more about aiohttp](https://docs.aiohttp.org/)
```python
class MyEndpoint(RestEndpoint):
    async def get(self, request):
        return {"message": "Async ready!"}
```
*How to use:* Write your endpoint methods as `async def` to take full advantage of Python's async capabilities.
*Use cases:* Handle thousands of concurrent API requests, real-time dashboards, or chat/messaging backends.

## Redis Caching for Python APIs
Speed up your API with automatic or custom caching of responses, including cache invalidation. [Learn more about Redis](https://redis.io/)
```python
from lightapi.cache import RedisCache
class Product(RestEndpoint):
    class Configuration:
        caching_class = RedisCache
        caching_method_names = ['GET']
```
*How to use:* Set `caching_class = RedisCache` and specify which HTTP methods to cache. LightAPI will cache responses transparently.
*Use cases:* Reduce database load for expensive queries, speed up product catalogs, or cache public data.

## Filtering, Pagination, and Sorting
Query your data efficiently with flexible filters, paginated results, and sort options.
```python
from lightapi.filters import ParameterFilter
from lightapi.pagination import Paginator
class ProductFilter(ParameterFilter): ...
class ProductPaginator(Paginator): ...
class Product(RestEndpoint):
    class Configuration:
        filter_class = ProductFilter
        pagination_class = ProductPaginator
```
*How to use:* Implement custom filter and paginator classes, then assign them in your endpoint's Configuration.
*Use cases:* Build APIs for large datasets, searchable product listings, or analytics dashboards.

## Request Validation
Validate incoming data with custom or automatic validators, returning clear error messages.
```python
from lightapi.rest import Validator
class UserValidator(Validator):
    def validate_name(self, value):
        if not value:
            raise ValueError('Name required')
        return value
class User(RestEndpoint):
    class Configuration:
        validator_class = UserValidator
```
*How to use:* Create a Validator class and assign it in your endpoint's Configuration. Validation errors are returned as 400 responses.
*Use cases:* Enforce business rules, prevent bad data, and provide user-friendly error messages in your API.

## Type Hints & Modern Python
All code is type-annotated and follows modern Python best practices for maintainability and IDE support.

## Comprehensive Error Handling
Detailed error messages and robust error handling are built in, making debugging and production support easier.

---

# Quick Start: Build a Python REST API in Minutes

## 1. Install LightAPI

```bash
pip install lightapi
```

## 2. Define your model (SQLAlchemy)

```python
from lightapi import LightApi
from lightapi.database import Base
from sqlalchemy import Column, Integer, String

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(50))
    email = Column(String(100))

app = LightApi()
app.register(User)

if __name__ == "__main__":
    app.run()
```

## 3. Or use YAML for instant API from your database

```yaml
# config.yaml
database_url: sqlite:///mydata.db
tables:
  - name: users
    crud: [get, post, put, patch, delete]
  - name: orders
    crud: [get, post]
```

```python
from lightapi import LightApi
api = LightApi.from_config('config.yaml')
api.run(host="0.0.0.0", port=8081)
```

---

# Example Endpoints

- `GET    /users/`         - List users
- `POST   /users/`         - Create user
- `GET    /users/{id}`     - Get user by ID
- `PUT    /users/{id}`     - Replace user
- `PATCH  /users/{id}`     - Update user
- `DELETE /users/{id}`     - Delete user
- `GET    /orders/`        - List orders
- `POST   /orders/`        - Create order
- `GET    /orders/{id}`    - Get order by ID

---

# Documentation

- [Full Documentation](https://iklobato.github.io/lightapi/)
- [Getting Started](https://iklobato.github.io/lightapi/getting-started/installation/)
- [API Reference](https://iklobato.github.io/lightapi/api-reference/core/)
- [Examples](https://iklobato.github.io/lightapi/examples/basic-rest/)
- [SQLAlchemy](https://www.sqlalchemy.org/)
- [aiohttp](https://docs.aiohttp.org/)
- [OpenAPI](https://swagger.io/specification/)
- [JWT](https://jwt.io/)
- [Redis](https://redis.io/)

---

# FAQ

**Q: Can I use LightAPI with my existing database?**  
A: Yes! Use the YAML config to reflect your schema and instantly expose REST endpoints.

**Q: What databases are supported?**  
A: Any database supported by SQLAlchemy (PostgreSQL, MySQL, SQLite, etc.).

**Q: How do I secure my API?**  
A: Enable JWT authentication and CORS with a single line.

**Q: Can I customize endpoints or add business logic?**  
A: Yes, you can extend or override any handler, add middleware, and use validators.

**Q: Is this production-ready?**  
A: Yes. LightAPI is designed for both rapid prototyping and production deployment.

---

# Comparison

| Feature                                 | LightAPI | FastAPI | Flask | Django REST |
|------------------------------------------|----------|---------|-------|-------------|
| Zero-boilerplate CRUD generation         | ✅       | ❌      | ❌    | ❌          |
| YAML-driven API/config                   | ✅       | ❌      | ❌    | ❌          |
| Async/await support                      | ✅       | ✅      | ❌    | ❌          |
| Automatic OpenAPI/Swagger docs           | ✅       | ✅      | ❌    | ✅          |
| JWT authentication (built-in)            | ✅       | ❌      | ❌    | ✅          |
| CORS support (built-in)                  | ✅       | ✅      | ❌    | ✅          |
| Redis caching (built-in)                 | ✅       | ❌      | ❌    | ✅          |
| Request validation (customizable)        | ✅       | ✅      | ❌    | ✅          |
| Filtering, pagination, sorting           | ✅       | ✅      | ❌    | ✅          |
| Database reflection                      | ✅       | ❌      | ❌    | ❌          |
| Type hints & modern Python               | ✅       | ✅      | ❌    | ✅          |
| Custom middleware                        | ✅       | ✅      | ✅    | ✅          |
| Environment-based configuration          | ✅       | ✅      | ❌    | ✅          |
| Production-ready out of the box          | ✅       | ✅      | ❌    | ✅          |

---

# License

MIT License. See [LICENSE](LICENSE).

---

> **Note:** Only GET, POST, PUT, PATCH, DELETE HTTP verbs are supported. Required fields must be NOT NULL in the schema. Constraint violations (NOT NULL, UNIQUE, FK) return 409.  
> To start your API, always use `api.run(host, port)`. Do not use external libraries or `app = api.app` to start the server directly.

---

**LightAPI** - The fastest way to build Python REST APIs from your database.

---

# Troubleshooting

### ModuleNotFoundError: No module named 'lightapi'

If you see this error when running example scripts:

```
Traceback (most recent call last):
  File "examples/mega_example.py", line 22, in <module>
    from lightapi.auth import JWTAuthentication
ModuleNotFoundError: No module named 'lightapi'
```

**Solution:**
- Make sure you run the script from the project root directory, not from inside the `examples/` folder.
- Or, set the `PYTHONPATH` to include the project root:

```bash
PYTHONPATH=. python3 examples/mega_example.py
```

This ensures Python can find the `lightapi` package in your local project.
