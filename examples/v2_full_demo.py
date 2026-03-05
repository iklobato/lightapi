"""LightAPI v2 — Full-Feature Demo against PostgreSQL.

Covers every v2 feature in one runnable file:
  - Basic CRUD (BookEndpoint)
  - HttpMethod mixins (AuthorEndpoint: GET + POST only)
  - Serializer  (read vs write field sets)
  - JWT Authentication + IsAuthenticated permission (AuthorEndpoint)
  - JWT Authentication + IsAdminUser permission (AdminBookEndpoint: DELETE only)
  - Filtering: FieldFilter, SearchFilter, OrderingFilter (BookEndpoint)
  - Page-number Pagination (BookEndpoint)
  - Cursor Pagination (TagEndpoint)
  - Custom queryset — published_only filter (BookEndpoint.queryset override)
  - Middleware — AuditMiddleware adds X-Response-Time header
  - Optimistic locking — PUT/PATCH require version; mismatch → 409

Database: postgresql://postgres:postgres@localhost:5432/postgres

Usage
-----
    python examples/v2_full_demo.py

Generate a regular JWT (for IsAuthenticated endpoints):
    python -c "
    import jwt, os
    os.environ['LIGHTAPI_JWT_SECRET'] = 'demo-secret-key'
    token = jwt.encode({'user_id': 1}, 'demo-secret-key', algorithm='HS256')
    print(token)
    "

Generate an admin JWT (for IsAdminUser endpoints):
    python -c "
    import jwt
    token = jwt.encode({'user_id': 1, 'is_admin': True}, 'demo-secret-key', algorithm='HS256')
    print(token)
    "
"""

import json
import os
import time
from typing import Optional

from sqlalchemy import create_engine, select as sa_select
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from lightapi import (
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

DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/postgres"

# Set JWT secret before any endpoint class body is evaluated
os.environ.setdefault("LIGHTAPI_JWT_SECRET", "demo-secret-key")


# ─────────────────────────────────────────────────────────────────────────────
# Middleware
# ─────────────────────────────────────────────────────────────────────────────


class AuditMiddleware(Middleware):
    """Pre/post middleware that adds an X-Response-Time header to every response."""

    def process(self, request: Request, response: Response | None) -> Response | None:
        if response is None:
            # pre-hook: record start time on request state
            request.state._audit_start = time.monotonic()
            return None

        # post-hook: compute elapsed time and attach header
        elapsed = time.monotonic() - getattr(request.state, "_audit_start", time.monotonic())
        try:
            body = json.loads(response.body)
        except Exception:
            # 204 No Content or non-JSON — passthrough
            return response
        return JSONResponse(
            body,
            status_code=response.status_code,
            headers={"X-Response-Time": f"{elapsed:.4f}s"},
        )


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────


class BookEndpoint(
    RestEndpoint,
    HttpMethod.GET,
    HttpMethod.POST,
    HttpMethod.PUT,
    HttpMethod.PATCH,
    HttpMethod.DELETE,
):
    """Full-CRUD endpoint with filtering, pagination, serializer, cache, and a
    custom queryset that restricts results when ?published_only=true."""

    title: str = Field(min_length=1, max_length=200)
    author: str = Field(min_length=1)
    genre: str = Field(min_length=1)
    price: float = Field(ge=0.0)
    published: bool = Field(default=True)

    class Meta:
        filtering = Filtering(
            backends=[FieldFilter, SearchFilter, OrderingFilter],
            fields=["genre"],               # ?genre=fiction
            search=["title", "author"],     # ?search=<term>
            ordering=["title", "price"],    # ?ordering=price or ?ordering=-price
        )
        pagination = Pagination(style="page_number", page_size=5)
        serializer = Serializer(
            read=["id", "title", "author", "genre", "price", "published",
                  "created_at", "updated_at", "version"],
            write=["id", "title", "author", "genre", "price", "published",
                   "created_at", "updated_at", "version"],
        )
        cache = Cache(ttl=30)  # gracefully skipped if Redis is unavailable

    def queryset(self, request: Request):
        """Default queryset; filters to published=True when ?published_only=true."""
        cls = type(self)
        qs = sa_select(cls._model_class)
        if request.query_params.get("published_only") == "true":
            qs = qs.where(cls._model_class.published.is_(True))
        return qs


class AuthorEndpoint(RestEndpoint, HttpMethod.GET, HttpMethod.POST):
    """GET + POST only — PUT/PATCH/DELETE return 405.
    All requests require a valid JWT (IsAuthenticated)."""

    name: str = Field(min_length=1, max_length=150)
    bio: Optional[str] = None

    class Meta:
        authentication = Authentication(
            backend=JWTAuthentication,
            permission=IsAuthenticated,
        )
        serializer = Serializer(
            read=["id", "name", "bio", "created_at", "updated_at", "version"],
            write=["id", "name", "bio", "created_at", "updated_at", "version"],
        )


class AdminBookEndpoint(RestEndpoint, HttpMethod.GET, HttpMethod.POST, HttpMethod.DELETE):
    """Admin-only endpoint (GET, POST, DELETE) — requires is_admin=True in JWT.
    Models its own `adminbookendpoints` table; demonstrates IsAdminUser permission."""

    title: str = Field(min_length=1)
    author: str = Field(min_length=1)
    genre: str = Field(min_length=1)
    price: float = Field(ge=0.0)
    published: bool = Field(default=True)

    class Meta:
        authentication = Authentication(
            backend=JWTAuthentication,
            permission=IsAdminUser,
        )
        serializer = Serializer(
            read=["id", "title", "author", "created_at", "updated_at", "version"],
            write=["id", "title", "author", "created_at", "updated_at", "version"],
        )


class TagEndpoint(RestEndpoint, HttpMethod.GET, HttpMethod.POST):
    """Simple tag endpoint with cursor-based pagination."""

    label: str = Field(min_length=1, max_length=100)

    class Meta:
        pagination = Pagination(style="cursor", page_size=3)
        serializer = Serializer(
            read=["id", "label", "created_at", "updated_at", "version"],
            write=["id", "label", "created_at", "updated_at", "version"],
        )


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    engine = create_engine(DATABASE_URL)

    app = LightApi(
        engine=engine,
        middlewares=[AuditMiddleware],
        cors_origins=["http://localhost:3000"],
    )
    app.register({
        "/books": BookEndpoint,
        "/admin/books": AdminBookEndpoint,
        "/authors": AuthorEndpoint,
        "/tags": TagEndpoint,
    })
    app.run(host="0.0.0.0", port=8000)
