---
title: Quickstart Guide
description: Create your first LightAPI application in 5 minutes
---

# Quickstart Guide

Get your first LightAPI application running in just 5 minutes! This guide shows you two approaches: the new **YAML configuration** method (zero Python code) and the traditional **Python code** method.

## Prerequisites

```bash
# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install LightAPI
pip install lightapi
```

## Method 1: YAML Configuration (Recommended)

**Perfect for beginners and rapid prototyping!**

### Step 1: Create a sample database

```bash
# Create a simple SQLite database
sqlite3 blog.db << EOF
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(200) NOT NULL,
    content TEXT,
    user_id INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

INSERT INTO users (name, email) VALUES ('John Doe', 'john@example.com');
INSERT INTO users (name, email) VALUES ('Jane Smith', 'jane@example.com');
INSERT INTO posts (title, content, user_id) VALUES ('First Post', 'Hello World!', 1);
EOF
```

### Step 2: Create YAML configuration

```yaml
# config.yaml
database_url: "sqlite:///blog.db"
swagger_title: "My Blog API"
swagger_version: "1.0.0"
swagger_description: "A simple blog API created with YAML configuration"
enable_swagger: true

tables:
  - name: users
    crud: [get, post, put, delete]
  - name: posts
    crud: [get, post, put, delete]
```

### Step 3: Run your API

```python
# app.py
from lightapi import LightApi

# Create API from YAML configuration
app = LightApi.from_config('config.yaml')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
```

**That's it!** Your API is now running with full CRUD operations.

## Method 2: Python Code (Traditional)

### Step 1: Define SQLAlchemy Models

```python
# models.py
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from lightapi import RestEndpoint, register_model_class

class User(Base, RestEndpoint):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), nullable=False, unique=True)
    created_at = Column(DateTime, server_default=func.now())

class Post(Base, RestEndpoint):
    __tablename__ = 'posts'
    
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    content = Column(String)
    user_id = Column(Integer, ForeignKey('users.id'))
    created_at = Column(DateTime, server_default=func.now())
```

### Step 2: Create and Run Your App

```python
# app.py
from lightapi import LightApi
from models import User, Post

app = LightApi(database_url="sqlite:///blog.db")
app.register({
    '/users': User,
    '/posts': Post
})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
```

## Testing Your API

Once your API is running, you can test it in several ways:

### 1. Interactive Swagger Documentation

Visit **http://localhost:8000/docs** in your browser for an interactive API documentation interface where you can:
- Browse all available endpoints
- Test API calls directly from the browser
- View request/response schemas
- Download the OpenAPI specification

### 2. Using curl

```bash
# Get all users
curl http://localhost:8000/users/

# Create a new user
curl -X POST http://localhost:8000/users/ \
  -H 'Content-Type: application/json' \
  -d '{"name": "Alice", "email": "alice@example.com"}'

# Get specific user
curl http://localhost:8000/users/1

# Update user
curl -X PUT http://localhost:8000/users/1 \
  -H 'Content-Type: application/json' \
  -d '{"name": "Alice Updated", "email": "alice.updated@example.com"}'

# Delete user
curl -X DELETE http://localhost:8000/users/1

# Get all posts
curl http://localhost:8000/posts/

# Create a new post
curl -X POST http://localhost:8000/posts/ \
  -H 'Content-Type: application/json' \
  -d '{"title": "My First Post", "content": "Hello World!", "user_id": 1}'
```

### 3. Using Python requests

```python
import requests

# Get all users
response = requests.get('http://localhost:8000/users/')
print(response.json())

# Create a new user
user_data = {"name": "Bob", "email": "bob@example.com"}
response = requests.post('http://localhost:8000/users/', json=user_data)
print(response.json())
```

## What You Get Out of the Box

Both methods automatically provide:

### 🔗 **REST Endpoints**
- `GET /users/` - List all users with pagination
- `GET /users/{id}` - Get specific user by ID
- `POST /users/` - Create new user
- `PUT /users/{id}` - Update entire user record
- `PATCH /users/{id}` - Partially update user
- `DELETE /users/{id}` - Delete user

### ✅ **Automatic Validation**
- Required field validation based on database schema
- Data type validation (integers, strings, etc.)
- Unique constraint validation
- Foreign key constraint validation
- Custom error messages with HTTP status codes

### 📚 **API Documentation**
- Interactive Swagger UI at `/docs`
- OpenAPI 3.0 specification at `/openapi.json`
- Automatic schema generation from database tables
- Request/response examples

### 🛡️ **Error Handling**
- Proper HTTP status codes (200, 201, 400, 404, 409, 500)
- Detailed error messages for validation failures
- Constraint violation handling (unique, foreign key, not null)

## Next Steps

Now that you have a working API, explore these advanced features:

### 🔐 **Add Authentication**
```yaml
# Add JWT authentication to your YAML config
enable_jwt: true
jwt_secret: "your-secret-key"
```

### 🚀 **Add Caching**
```yaml
# Add Redis caching
cache_backend: "redis"
cache_url: "redis://localhost:6379"
```

### 🔍 **Add Filtering and Pagination**
Your API automatically supports:
- `GET /users/?page=1&page_size=10` - Pagination
- `GET /users/?name=John` - Field filtering
- `GET /users/?sort=created_at` - Sorting

### 🌍 **Environment Variables**
```yaml
# Use environment variables for production
database_url: "${DATABASE_URL}"
swagger_title: "${API_TITLE}"
```

## Learn More

- **[YAML Configuration Guide](../examples/yaml-configuration.md)** - Complete YAML reference
- **[Authentication](../examples/auth.md)** - Secure your APIs
- **[Caching](../examples/caching.md)** - Improve performance
- **[Deployment](../deployment/production.md)** - Production setup
- **[Examples](../../examples/)** - Real-world examples

## Troubleshooting

### Common Issues

**"Table not found" error:**
- Ensure your database file exists and contains the specified tables
- Check the database URL path is correct

**"Connection refused" error:**
- Make sure your database server is running (for PostgreSQL/MySQL)
- Verify the connection string format

**"Permission denied" error:**
- Check database user permissions
- Ensure the database user has the necessary privileges

For more help, see the [Troubleshooting Guide](../troubleshooting.md).

---

**Congratulations!** You now have a fully functional REST API. The YAML configuration approach is perfect for rapid prototyping and exposing existing databases, while the Python code approach gives you more control and customization options.
