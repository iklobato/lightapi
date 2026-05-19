"""LightAPI Example 03 - JWT Authentication.

Demonstrates:
- JWT token-based authentication
- Protected endpoints requiring valid JWT
- Token generation via /auth/login endpoint
- JWT payload with custom claims

Notes:
    Uses SQLite by default (swap DATABASE_URL for PostgreSQL).
    JWT secret may be overridden via LIGHTAPI_JWT_SECRET env var.

Run with:
    python examples/03_auth_jwt.py

Then try:
    # Login to get token (returns JWT)
    curl -X POST http://localhost:8000/auth/login \
        -H 'Content-Type: application/json' \
        -d '{"username":"admin","password":"secret"}'

    # Use token to access protected endpoint
    curl -H 'Authorization: Bearer <TOKEN>' http://localhost:8000/books

    # Without token returns 401
    curl http://localhost:8000/books
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from lightapi import (
    Authentication,
    HttpMethod,
    JWTAuthentication,
    LightApi,
    RestEndpoint,
)
from lightapi.fields import Field

DATABASE_URL = "sqlite:///:memory:"

# Set JWT secret
os.environ.setdefault("LIGHTAPI_JWT_SECRET", "my-secret")


def login_validator(username: str, password: str):
    """Validate credentials and return user payload."""
    if username == "admin" and password == "secret":
        return {"sub": "1", "username": "admin", "is_admin": True}
    if username == "user" and password == "password":
        return {"sub": "2", "username": "user", "is_admin": False}
    return None


class BookEndpoint(RestEndpoint, HttpMethod.GET, HttpMethod.POST):
    """Book endpoint protected by JWT authentication."""

    title: str = Field(min_length=1)
    author: str = Field(min_length=1)
    price: float = Field(ge=0.0)

    class Meta:
        authentication = Authentication(
            backend=JWTAuthentication,
        )


if __name__ == "__main__":
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    app = LightApi(
        engine=engine,
        login_validator=login_validator,
    )
    app.register({"/books": BookEndpoint})
    app.run(host="0.0.0.0", port=8000, debug=True)
