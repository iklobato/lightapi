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

- 🚀 **Automatic CRUD endpoints** from SQLAlchemy models or YAML config
- 🔄 **Database reflection**: Expose existing tables instantly
- 🔐 **JWT authentication** with CORS support
- ⚡ **Async performance** (aiohttp)
- 💾 **Redis caching** with auto-invalidation
- 🧪 **Request validation** and error handling
- 🔍 **Filtering, pagination, and sorting**
- 📖 **OpenAPI/Swagger documentation** auto-generated
- 🔧 **Custom middleware** support
- 🗄️ **Works with SQLite, PostgreSQL, MySQL, and more**
- 📝 **Environment-based configuration**

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
