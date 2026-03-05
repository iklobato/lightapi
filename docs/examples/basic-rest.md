---
title: Basic REST API Example
---

# Basic REST API

A complete REST API with multiple resources, covering the most common setup patterns.

## Installation

```bash
uv add lightapi
```

## Defining endpoints

```python
# app/endpoints.py
from typing import Optional
from decimal import Decimal
from lightapi import RestEndpoint, Field, HttpMethod

class UserEndpoint(RestEndpoint):
    username: str = Field(min_length=3, max_length=50, unique=True, index=True)
    email:    str = Field(unique=True)
    bio:      Optional[str] = None


class PostEndpoint(RestEndpoint, HttpMethod.GET, HttpMethod.POST):
    """Read-only + create. No PUT/PATCH/DELETE."""
    title:  str = Field(min_length=1, max_length=255)
    body:   str
    author: str


class ProductEndpoint(RestEndpoint):
    name:     str     = Field(min_length=1, max_length=200)
    price:    Decimal = Field(ge=0, decimal_places=2)
    sku:      str     = Field(unique=True, index=True)
    active:   bool    = Field(default=True)
```

## Application entry point

```python
# app/main.py
import os
from sqlalchemy import create_engine
from lightapi import LightApi

from app.endpoints import UserEndpoint, PostEndpoint, ProductEndpoint

engine = create_engine(os.environ.get("DATABASE_URL", "sqlite:///app.db"))

app = LightApi(
    engine=engine,
    cors_origins=["http://localhost:3000"],
)

app.register({
    "/users":    UserEndpoint,
    "/posts":    PostEndpoint,
    "/products": ProductEndpoint,
})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, reload=True)
```

## Exploring the API

```bash
# Users
curl -X POST http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "email": "alice@example.com"}'

curl http://localhost:8000/users
curl http://localhost:8000/users/1

# Posts (GET + POST only — no PUT/PATCH/DELETE)
curl -X POST http://localhost:8000/posts \
  -H "Content-Type: application/json" \
  -d '{"title": "Hello World", "body": "...", "author": "alice"}'

# Products
curl -X POST http://localhost:8000/products \
  -H "Content-Type: application/json" \
  -d '{"name": "Widget", "price": "9.99", "sku": "WGT-001"}'
```

## Adding authentication

```python
from lightapi import (
    RestEndpoint, Field,
    Authentication, JWTAuthentication, IsAuthenticated, AllowAny,
)

class SecurePostEndpoint(RestEndpoint, HttpMethod.GET, HttpMethod.POST):
    title: str
    body:  str

    class Meta:
        authentication = Authentication(
            backend=JWTAuthentication,
            # GET is public; POST requires a valid JWT
            permission={
                "GET":  AllowAny,
                "POST": IsAuthenticated,
            },
        )
```

```bash
export LIGHTAPI_JWT_SECRET="my-secret"
```

## Using PostgreSQL

```python
from sqlalchemy import create_engine

engine = create_engine("postgresql+psycopg2://user:pass@localhost:5432/mydb")
app = LightApi(engine=engine)
```

Install the driver: `uv add psycopg2-binary`
