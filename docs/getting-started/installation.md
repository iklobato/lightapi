---
title: Installation Guide
description: Install LightAPI and set up your development environment
---

# Installation Guide

Get LightAPI up and running in your development environment. This guide covers installation, dependencies, and environment setup.

## Requirements

LightAPI requires Python 3.10 or higher and supports the following platforms:

- **Python**: 3.10, 3.11, 3.12, 3.13
- **Operating Systems**: Linux, macOS, Windows
- **Databases**: SQLite, PostgreSQL, MySQL (via SQLAlchemy)

## Installation Methods

### Method 1: uv (Recommended)

```bash
uv add lightapi
```

### Method 2: pip

```bash
pip install lightapi
```

### Method 3: Development Installation

```bash
git clone https://github.com/iklobato/lightapi.git
cd lightapi
uv sync --extra dev
```

### Method 3: Virtual Environment (Recommended)

Create an isolated environment for your project:

```bash
# Create virtual environment
python -m venv lightapi-env

# Activate virtual environment
# On Linux/macOS:
source lightapi-env/bin/activate
# On Windows:
lightapi-env\Scripts\activate

# Install LightAPI
pip install lightapi
```

## Core Dependencies

LightAPI v2 ships with these pinned core dependencies:

| Package | Version | Purpose |
|---|---|---|
| `sqlalchemy` | `>=2.0` | ORM and imperative mapping |
| `pydantic` | `>=2.0` | Schema validation |
| `starlette` | `>=0.37` | ASGI framework |
| `uvicorn` | `>=0.30` | ASGI server |
| `pyjwt` | `>=2.8` | JWT authentication |
| `redis` | `>=5.0` | Response caching |
| `pyyaml` | `>=6.0` | YAML configuration |

## Optional Extras

### Async I/O (`lightapi[async]`)

Activate fully async database I/O by installing the async extra:

```bash
uv add "lightapi[async]"
# or: pip install "lightapi[async]"
```

This installs:

| Package | Purpose |
|---|---|
| `sqlalchemy[asyncio]` | Async SQLAlchemy core |
| `asyncpg` | PostgreSQL async driver |
| `aiosqlite` | SQLite async driver |
| `greenlet` | Required by SQLAlchemy async |

Then swap `create_engine` for `create_async_engine`:

```python
# Before (sync)
from sqlalchemy import create_engine
engine = create_engine("postgresql://user:pass@localhost/db")

# After (async — one-line change)
from sqlalchemy.ext.asyncio import create_async_engine
engine = create_async_engine("postgresql+asyncpg://user:pass@localhost/db")
```

See [Async Support](../advanced/async.md) for the full guide.

### Development Tools (`lightapi[dev]`)

```bash
uv add "lightapi[dev]"
```

Includes: `pytest`, `pytest-asyncio`, `pytest-cov`, `httpx`, `aiosqlite`, `ruff`, `mypy`.

## Verify Installation

```python
# verify.py
from sqlalchemy import create_engine
from lightapi import LightApi, RestEndpoint, Field

class PingEndpoint(RestEndpoint):
    message: str = Field(default="pong")

engine = create_engine("sqlite:///:memory:")
app = LightApi(engine=engine)
app.register({"/ping": PingEndpoint})
print("LightAPI installed successfully.")
```

```bash
python verify.py
# LightAPI installed successfully.
```

**Verify async support:**

```python
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from lightapi import get_async_session
from sqlalchemy import text

async def check():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with get_async_session(engine) as s:
        result = await s.execute(text("SELECT 1"))
        assert result.scalar() == 1
    print("Async support working.")

asyncio.run(check())
```

## Database Setup

### SQLite (Default)

SQLite works out of the box with no additional setup:

```python
from lightapi import LightApi

app = LightApi(database_url="sqlite:///my_app.db")
```

### PostgreSQL

1. Install PostgreSQL server
2. Install Python driver:
   ```bash
   pip install psycopg2-binary
   ```
3. Configure connection:
   ```python
   app = LightApi(database_url="postgresql://user:password@localhost:5432/mydb")
   ```

### MySQL

1. Install MySQL server
2. Install Python driver:
   ```bash
   pip install pymysql
   ```
3. Configure connection:
   ```python
   app = LightApi(database_url="mysql+pymysql://user:password@localhost:3306/mydb")
   ```

## Environment Configuration

### Environment Variables

Create a `.env` file for environment-specific settings:

```bash
# .env
DATABASE_URL=sqlite:///development.db
REDIS_URL=redis://localhost:6379
JWT_SECRET=your-secret-key-here
DEBUG=true
```

Load environment variables in your application:

```python
import os
from dotenv import load_dotenv
from lightapi import LightApi

# Load environment variables
load_dotenv()

app = LightApi(
    database_url=os.getenv("LIGHTAPI_DATABASE_URL"),
    redis_url=os.getenv("REDIS_URL"),
    jwt_secret=os.getenv("JWT_SECRET"),
    debug=os.getenv("DEBUG", "false").lower() == "true"
)
```

### Docker Setup

Create a `Dockerfile` for containerized deployment:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Run application
CMD ["python", "app.py"]
```

Create `requirements.txt`:

```
lightapi
psycopg2-binary  # for PostgreSQL
redis           # for caching
python-dotenv   # for environment variables
```

Build and run:

```bash
docker build -t my-lightapi-app .
docker run -p 8000:8000 my-lightapi-app
```

## IDE Setup

### VS Code

Install recommended extensions:

```json
{
  "recommendations": [
    "ms-python.python",
    "ms-python.black-formatter",
    "ms-python.isort",
    "ms-python.mypy-type-checker",
    "redhat.vscode-yaml"
  ]
}
```

### PyCharm

1. Create new Python project
2. Configure Python interpreter to use your virtual environment
3. Install LightAPI plugin (if available)
4. Configure code style for Black formatting

## Troubleshooting

### Common Installation Issues

**Issue**: `pip install lightapi` fails with permission error
```bash
# Solution: Use user installation
pip install --user lightapi
```

**Issue**: SQLAlchemy version conflicts
```bash
# Solution: Upgrade SQLAlchemy
pip install --upgrade sqlalchemy
```

**Issue**: asyncpg installation fails on Windows
```bash
# Solution: Install Visual C++ Build Tools or use the pre-built wheel
pip install asyncpg --only-binary asyncpg
```

**Issue**: PostgreSQL driver installation fails
```bash
# Solution: Install binary version
pip install psycopg2-binary
```

### Verification Commands

Check installed packages:
```bash
pip list | grep lightapi
pip show lightapi
```

Check Python version:
```bash
python --version
```

Test database connectivity:
```python
from sqlalchemy import create_engine
engine = create_engine("sqlite:///test.db")
print("✅ Database connection successful")
```

## Next Steps

Now that LightAPI is installed, you're ready to:

1. **[Quickstart Guide](quickstart.md)** - Build your first API in 5 minutes
2. **[Configuration Guide](configuration.md)** - Learn about YAML and Python configuration
3. **[Tutorial](../tutorial/basic-api.md)** - Step-by-step API development
4. **[Examples](../examples/basic-rest.md)** - Explore real-world examples

## Getting Help

If you encounter issues during installation:

- **Documentation**: Check our comprehensive guides
- **GitHub Issues**: [Report bugs or ask questions](https://github.com/iklobato/lightapi/issues)
- **Community**: Join discussions and get help from other users

---

**Installation complete!** 🎉 You're now ready to build amazing APIs with LightAPI.
