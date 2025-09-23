---
title: Installation Guide
description: Install LightAPI and set up your development environment
---

# Installation Guide

Get LightAPI up and running in your development environment. This guide covers installation, dependencies, and environment setup.

## Requirements

LightAPI requires Python 3.8 or higher and supports the following platforms:

- **Python**: 3.8, 3.9, 3.10, 3.11, 3.12
- **Operating Systems**: Linux, macOS, Windows
- **Databases**: SQLite, PostgreSQL, MySQL (via SQLAlchemy)

## Installation Methods

### Method 1: pip (Recommended)

Install LightAPI from PyPI using pip:

```bash
pip install lightapi
```

### Method 2: Development Installation

For development or to get the latest features:

```bash
# Clone the repository
git clone https://github.com/iklobato/lightapi.git
cd lightapi

# Install in development mode
pip install -e .
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

LightAPI automatically installs these core dependencies:

```
aiohttp>=3.8.0          # Async HTTP server
sqlalchemy>=1.4.0       # Database ORM
pyyaml>=6.0             # YAML configuration support
pydantic>=1.10.0        # Data validation
```

## Optional Dependencies

Install additional packages for specific features:

### Database Drivers

```bash
# PostgreSQL support
pip install psycopg2-binary

# MySQL support  
pip install pymysql

# SQLite (included with Python)
# No additional installation needed
```

### Caching Support

```bash
# Redis caching
pip install redis

# In-memory caching (built-in)
# No additional installation needed
```

### Authentication

```bash
# JWT authentication
pip install pyjwt

# OAuth support
pip install authlib
```

### Development Tools

```bash
# Testing
pip install pytest pytest-asyncio httpx

# Code formatting
pip install black isort

# Type checking
pip install mypy
```

## Complete Installation

For a full-featured installation with all optional dependencies:

```bash
pip install lightapi[all]
```

Or install specific feature sets:

```bash
# Database support
pip install lightapi[postgres,mysql]

# Caching support
pip install lightapi[redis]

# Authentication support
pip install lightapi[auth]

# Development tools
pip install lightapi[dev]
```

## Verify Installation

Test your installation with a simple script:

```python
# test_installation.py
from lightapi import LightApi

# Create a simple API
app = LightApi(database_url="sqlite:///test.db")

# Add a simple endpoint
@app.get("/health")
def health_check():
    return {"status": "healthy", "version": "1.0.0"}

print("✅ LightAPI installed successfully!")
print("🚀 Ready to build APIs!")

# Optional: Run the server
if __name__ == "__main__":
    print("Starting test server on http://localhost:8000")
    print("Visit http://localhost:8000/health to test")
    app.run(host="0.0.0.0", port=8000)
```

Run the test:

```bash
python test_installation.py
```

You should see:
```
✅ LightAPI installed successfully!
🚀 Ready to build APIs!
Starting test server on http://localhost:8000
```

Visit `http://localhost:8000/health` to confirm everything works.

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
    database_url=os.getenv("DATABASE_URL"),
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

**Issue**: aiohttp installation fails on Windows
```bash
# Solution: Install Visual C++ Build Tools or use conda
conda install aiohttp
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
4. **[Examples](../examples/)** - Explore real-world examples

## Getting Help

If you encounter issues during installation:

- **Documentation**: Check our comprehensive guides
- **GitHub Issues**: [Report bugs or ask questions](https://github.com/iklobato/lightapi/issues)
- **Community**: Join discussions and get help from other users

---

**Installation complete!** 🎉 You're now ready to build amazing APIs with LightAPI.
