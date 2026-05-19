"""LightAPI Example 18 - Full API Demo.

Demonstrates:
- All LightAPI features combined:
  - Multiple endpoints with different permissions
  - JWT auth (Bearer)
  - Pagination (page_number and cursor)
  - Filtering (FieldFilter, SearchFilter, OrderingFilter)
  - Caching (skipped when Redis is unavailable)
  - Middleware
  - Per-verb serializer (read vs write)

Notes:
    Uses SQLite by default (swap DATABASE_URL for PostgreSQL).
    JWT secret defaults to "secret" — override via LIGHTAPI_JWT_SECRET.

Run with:
    python examples/18_full_api.py

This is similar to the existing v2_full_demo.py but organized as a numbered example.
"""

import os
import time
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from starlette.requests import Request
from starlette.responses import Response

from lightapi import (
    AllowAny,
    Authentication,
    Cache,
    Filtering,
    HttpMethod,
    IsAdminUser,
    IsAuthenticated,
    JWTAuthentication,
    LightApi,
    Middleware,
    Pagination,
    RestEndpoint,
    Serializer,
)
from lightapi.fields import Field
from lightapi.filters import FieldFilter, OrderingFilter, SearchFilter

DATABASE_URL = "sqlite:///:memory:"
os.environ.setdefault("LIGHTAPI_JWT_SECRET", "secret")


def login_validator(username: str, password: str):
    if username == "admin" and password == "secret":
        return {"sub": "1", "username": "admin", "is_admin": True}
    if username == "user" and password == "password":
        return {"sub": "2", "username": "user", "is_admin": False}
    return None


class AuditMiddleware(Middleware):
    """Middleware that adds X-Response-Time header to every response."""

    def process(self, request: Request, response: Response | None) -> Response | None:
        if response is None:
            request.state._start = time.monotonic()
            return None
        elapsed = time.monotonic() - getattr(request.state, "_start", time.monotonic())
        response.headers["X-Response-Time"] = f"{elapsed:.4f}s"
        return response


class BookEndpoint(
    RestEndpoint,
    HttpMethod.GET,
    HttpMethod.POST,
    HttpMethod.PUT,
    HttpMethod.PATCH,
    HttpMethod.DELETE,
):
    """Full-CRUD endpoint with all features."""

    title: str = Field(min_length=1, max_length=200)
    author: str = Field(min_length=1)
    genre: str = Field(min_length=1)
    price: float = Field(ge=0.0)
    published: bool = Field(default=True)

    class Meta:
        filtering = Filtering(
            backends=[FieldFilter, SearchFilter, OrderingFilter],
            fields=["genre"],
            search=["title", "author"],
            ordering=["title", "price"],
        )
        pagination = Pagination(style="page_number", page_size=10)
        serializer = Serializer(
            read=[
                "id",
                "title",
                "author",
                "genre",
                "price",
                "published",
                "created_at",
                "version",
            ],
            write=["title", "author", "genre", "price", "published"],
        )
        cache = Cache(ttl=30)


class AuthorEndpoint(RestEndpoint, HttpMethod.GET, HttpMethod.POST):
    """GET + POST only - JWT protected."""

    name: str = Field(min_length=1, max_length=150)
    bio: Optional[str] = None

    class Meta:
        authentication = Authentication(
            backend=JWTAuthentication,
            permission=IsAuthenticated,
        )
        serializer = Serializer(
            read=["id", "name", "bio", "created_at", "version"],
        )


class AdminTagEndpoint(RestEndpoint, HttpMethod.DELETE):
    """DELETE only - Admin only."""

    name: str = Field(min_length=1)

    class Meta:
        authentication = Authentication(
            backend=JWTAuthentication,
            permission=IsAdminUser,
        )


class PublicEndpoint(RestEndpoint, HttpMethod.GET):
    """Public endpoint - no auth required."""

    name: str = Field(min_length=1)

    class Meta:
        authentication = Authentication(permission=AllowAny)
        pagination = Pagination(style="cursor", page_size=20)


if __name__ == "__main__":
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    app = LightApi(
        engine=engine,
        login_validator=login_validator,
        middlewares=[AuditMiddleware],
    )
    app.register(
        {
            "/books": BookEndpoint,
            "/authors": AuthorEndpoint,
            "/tags": AdminTagEndpoint,
            "/public": PublicEndpoint,
        }
    )
    app.run(host="0.0.0.0", port=8000, debug=True)
