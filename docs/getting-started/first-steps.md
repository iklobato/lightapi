---
title: First Steps
---

Build your first real LightAPI v2 application step by step.

## 1. Project Layout

```
myapp/
├── app/
│   ├── __init__.py
│   ├── endpoints.py   # RestEndpoint subclasses
│   └── main.py        # LightApi wiring
├── pyproject.toml
└── .env
```

## 2. Defining Your First Endpoint

In v2, one class serves as the ORM model, the Pydantic schema, **and** the HTTP endpoint.

```python
# app/endpoints.py
from typing import Optional
from lightapi import RestEndpoint
from lightapi.fields import Field

class UserEndpoint(RestEndpoint):
    username: str = Field(min_length=3, max_length=50, unique=True, index=True)
    email: str = Field(min_length=5, unique=True)
    bio: Optional[str] = None
```

LightAPI auto-generates:
- A `users` table (derived from the class name) with columns `id`, `username`, `email`, `bio`, `created_at`, `updated_at`, `version`
- A Pydantic create schema (excludes `id`, `created_at`, `updated_at`, `version`)
- A Pydantic read schema (includes all columns including auto-injected ones)
- `GET /users`, `POST /users`, `GET /users/{id}`, `PUT /users/{id}`, `PATCH /users/{id}`, `DELETE /users/{id}`

## 3. Wiring Up the Application

```python
# app/main.py
import os
from sqlalchemy import create_engine
from lightapi import LightApi
from app.endpoints import UserEndpoint

engine = create_engine(os.environ.get("DATABASE_URL", "sqlite:///app.db"))

app = LightApi(engine=engine)
app.register({"/users": UserEndpoint})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
```

## 4. Running the Application

```bash
python -m app.main
```

## 5. Exploring the API

```bash
# Create a user
curl -X POST http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "email": "alice@example.com"}'
# → 201 {"id": 1, "username": "alice", "email": "alice@example.com", "bio": null, "version": 1, ...}

# List users
curl http://localhost:8000/users
# → {"results": [{"id": 1, "username": "alice", ...}]}

# Update (optimistic locking — version required)
curl -X PUT http://localhost:8000/users/1 \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "email": "alice@example.com", "bio": "Hello!", "version": 1}'
# → 200 {"id": 1, ..., "version": 2}

# Validation error
curl -X POST http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{"username": "ab", "email": "alice@example.com"}'
# → 422 {"detail": [{"loc": ["username"], "msg": "String should have at least 3 characters", ...}]}
```

## 6. Restricting HTTP Methods

Use `HttpMethod` mixins to expose only the verbs you need:

```python
from lightapi import RestEndpoint, HttpMethod
from lightapi.fields import Field

class ReadOnlyUserEndpoint(RestEndpoint, HttpMethod.GET):
    username: str = Field(min_length=3)
    email: str = Field(min_length=5)
```

A `POST /users` to this endpoint will return `405 Method Not Allowed`.

## Next Steps

- [Authentication](../advanced/authentication.md) — protect endpoints with JWT
- [Filtering & Pagination](../advanced/filtering.md) — add query filters and pagination
- [Serializer](../advanced/serializer.md) — control which fields are exposed
