# LightAPI: Instant Python REST APIs from SQL Databases

[![PyPI version](https://badge.fury.io/py/lightapi.svg)](https://pypi.org/project/lightapi/)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**LightAPI** is a modern Python framework for building high-performance REST APIs directly from your SQL database—no boilerplate, no manual endpoint wiring. Instantly expose CRUD endpoints from SQLAlchemy models or a YAML config, with full support for authentication, caching, validation, filtering, and OpenAPI documentation.

---

## Why use LightAPI?

- **Zero-boilerplate Python REST API**: Instantly generate CRUD endpoints from your database schema.
- **YAML-driven API generator**: Reflect your database and expose only the tables and operations you want.
- **Async and Fast**: Built on aiohttp for high concurrency and low latency.
- **Production-ready**: JWT authentication, Redis caching, request validation, and robust error handling.
- **Automatic OpenAPI docs**: Swagger UI and OpenAPI JSON out of the box.
- **Flexible**: Use with SQLite, PostgreSQL, MySQL, or any SQLAlchemy-supported database.
- **Modern Python**: Type hints, async/await, and best practices throughout.

---

## Who is this for?

- **Backend developers** who want to ship APIs fast, with minimal code.
- **Data engineers** needing to expose existing databases as RESTful services.
- **Prototypers** and **startups** who want to iterate quickly and scale later.
- **Anyone** who wants a clean, maintainable, and extensible Python API stack.

---

## Features

Each feature explained:
- **Automatic CRUD endpoints**: Instantly generate RESTful endpoints for your models or tables, so you can create, read, update, and delete records with no manual wiring.
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
- **Database reflection**: Point LightAPI at your existing database and expose tables as REST endpoints without writing model code.
  ```python
  # config.yaml
  database_url: sqlite:///mydata.db
  tables:
    - name: users
      crud: [get, post, put, patch, delete]
  # Python
  from lightapi import LightApi
  api = LightApi.from_config('config.yaml')
  api.run()
  ```
  *How to use:* Create a YAML config describing your database and tables, then use `LightApi.from_config()` to generate endpoints instantly.
  *Use cases:* Expose legacy or third-party databases as REST APIs for integration, analytics, or migration.
- **JWT authentication**: Secure your API with industry-standard JSON Web Tokens, including login endpoints and protected resources.
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
- **CORS support**: Easily enable Cross-Origin Resource Sharing for frontend/backend integration.
  ```python
  from lightapi.core import CORSMiddleware
  app.add_middleware([CORSMiddleware])
  ```
  *How to use:* Add `CORSMiddleware` to your app's middleware list to allow cross-origin requests from browsers.
  *Use cases:* Enable frontend apps (React, Vue, etc.) to call your API from a different domain during development or production.
- **Async performance**: Built on aiohttp for high concurrency and fast response times.
  ```python
  # All endpoints are async-ready; just use async def in your handlers.
  class MyEndpoint(RestEndpoint):
      async def get(self, request):
          return {"message": "Async ready!"}
  ```
  *How to use:* Write your endpoint methods as `async def` to take full advantage of Python's async capabilities.
  *Use cases:* Handle thousands of concurrent API requests, real-time dashboards, or chat/messaging backends.
- **Redis caching**: Speed up your API with automatic or custom caching of responses, including cache invalidation.
  ```python
  from lightapi.cache import RedisCache
  class Product(RestEndpoint):
      class Configuration:
          caching_class = RedisCache
          caching_method_names = ['GET']
  ```
  *How to use:* Set `caching_class = RedisCache` and specify which HTTP methods to cache. LightAPI will cache responses transparently.
  *Use cases:* Reduce database load for expensive queries, speed up product catalogs, or cache public data.
- **Request validation**: Validate incoming data with custom or automatic validators, returning clear error messages.
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
- **Filtering, pagination, and sorting**: Query your data efficiently with flexible filters, paginated results, and sort options.
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
- **OpenAPI/Swagger documentation**: Get interactive API docs and OpenAPI JSON automatically, always in sync with your endpoints.
  ```python
  app = LightApi(swagger_title="My API", swagger_version="1.0.0")
  # Visit http://localhost:8000/docs
  ```
  *How to use:* Set Swagger options when creating your app. Docs are auto-generated and always up to date.
  *Use cases:* Share your API with frontend teams, generate client SDKs, or provide public API documentation.
- **Custom middleware**: Add logging, rate limiting, authentication, or any cross-cutting logic with a simple middleware interface.
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
- **Works with all major databases**: Use SQLite, PostgreSQL, MySQL, or any SQLAlchemy-supported backend.
  ```python
  app = LightApi(database_url="postgresql://user:pass@localhost/db")
  # or
  app = LightApi(database_url="mysql://user:pass@localhost/db")
  ```
  *How to use:* Set the `database_url` parameter to match your database backend.
  *Use cases:* Migrate between databases, support multiple environments, or connect to cloud-hosted DBs.
- **Environment-based configuration**: Configure your app for development, testing, or production using environment variables or YAML.
  ```python
  # config.yaml
  database_url: sqlite:///dev.db
  debug: true
  # Python
  api = LightApi.from_config('config.yaml')
  ```
  *How to use:* Store your settings in a YAML file or environment variables, then load them with `from_config()` or `os.environ`.
  *Use cases:* Seamlessly switch between dev, staging, and production setups, or deploy with Docker and CI/CD.

---

## Quick Start

### 1. Install LightAPI

```bash
pip install lightapi
```

### 2. Define your model (SQLAlchemy)

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

### 3. Or use YAML for instant API from your database

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

## Example Endpoints (from YAML above)

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

## Documentation

- [Full Documentation](https://iklobato.github.io/lightapi/)
- [Getting Started](https://iklobato.github.io/lightapi/getting-started/installation/)
- [API Reference](https://iklobato.github.io/lightapi/api-reference/core/)
- [Examples](https://iklobato.github.io/lightapi/examples/basic-rest/)

---

## FAQ

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

## Comparison

| Feature                | LightAPI | FastAPI | Flask | Django REST |
|------------------------|----------|--------|-------|-------------|
| Zero-boilerplate CRUD  | ✅       | ❌     | ❌    | ❌          |
| YAML-driven API        | ✅       | ❌     | ❌    | ❌          |
| Async support          | ✅       | ✅     | ❌    | ❌          |
| OpenAPI docs           | ✅       | ✅     | ❌    | ✅          |
| Built-in Auth/Caching  | ✅       | ❌     | ❌    | ✅          |
| DB Reflection          | ✅       | ❌     | ❌    | ❌          |

---

## License

MIT License. See [LICENSE](LICENSE).

---

> **Note:** Only GET, POST, PUT, PATCH, DELETE HTTP verbs are supported. Required fields must be NOT NULL in the schema. Constraint violations (NOT NULL, UNIQUE, FK) return 409.  
> To start your API, always use `api.run(host, port)`. Do not use external libraries or `app = api.app` to start the server directly.

---

**LightAPI** - *The fastest way to build Python REST APIs from your database.*
