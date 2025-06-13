---
title: Quickstart
---

This quickstart guide shows you how to create your first LightAPI application in just a few simple steps.

## 1. Create a Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 2. Install LightAPI

```bash
pip install lightapi
```

## 3. Define a SQLAlchemy Model

```python
# models.py
from sqlalchemy import Column, Integer, String
from lightapi.database import Base

class Item(Base):
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    description = Column(String, nullable=True)
```

## 4. Create and Run Your App

```python
# main.py
from lightapi import LightApi
from models import Item

app = LightApi()
app.register({'/items': Item})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
```

Now navigate to `http://localhost:8000/items` in your browser or use CURL to interact with the automatically generated CRUD endpoints.

## Dynamic API from YAML Config (SQLAlchemy Reflection)

LightAPI can generate a REST API from a YAML configuration file, reflecting your database schema at runtime. This is ideal for exposing existing databases without writing models.

### End-to-End Example

**1. Create a YAML config:**
```yaml
database_url: sqlite:///mydata.db
tables:
  - name: users
    crud: [get, post, put, patch, delete]
  - name: orders
    crud: [get, post]
```

**2. Create your database (SQLite example):**
```bash
sqlite3 mydata.db "CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT UNIQUE); CREATE TABLE orders (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, amount REAL, FOREIGN KEY(user_id) REFERENCES users(id));"
```

**3. Start the API:**
```python
from lightapi import LightApi
api = LightApi.from_config('my_api_config.yaml')
api.run(host="0.0.0.0", port=8080)
```

**4. Use the API (with curl):**
```bash
curl -X POST http://localhost:8080/users/ -H 'Content-Type: application/json' -d '{"name": "Alice", "email": "alice@example.com"}'
curl http://localhost:8080/users/
curl -X POST http://localhost:8080/orders/ -H 'Content-Type: application/json' -d '{"user_id": 1, "amount": 42.5}'
curl http://localhost:8080/orders/
```

### FAQ
- Only server-side defaults (e.g., `server_default`) are available after reflection.
- Composite PKs, foreign keys, and constraints are supported.
- Violations (e.g., unique, FK) return 409 Conflict with details.
- You can expose only the operations you want per table.

See the [README](../../README.md) for more details and advanced usage.
