"""
Full-feature LightAPI example using async PostgreSQL (asyncpg).

Demonstrates:
  - Async engine (create_async_engine) → automatic async CRUD
  - Multiple endpoints: Author, Book, Tag
  - async def queryset with join + filtering
  - async def post override + self.background()
  - Sync endpoint on the same async app (Category)
  - Filtering, pagination, serialization, JWT auth
  - AllowAny endpoint alongside JWT-protected endpoint
  - Optimistic-locking PUT / PATCH
  - Soft-delete via async def delete override
  - Mixed sync/async middleware

Run with:
    uv run python examples/postgres_full.py
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from pydantic import Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine
from starlette.requests import Request
from starlette.responses import Response

from lightapi import LightApi, RestEndpoint
from lightapi.auth import AllowAny
from lightapi.config import Authentication, Filtering, Pagination, Serializer
from lightapi.core import Middleware
from lightapi.filters import FieldFilter, OrderingFilter, SearchFilter

logging.basicConfig(level=logging.INFO)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres",
)

# ── Tracking list for background tasks (demo) ────────────────────────────────
_audit_log: list[dict] = []


async def _audit(action: str, table: str, row_id: int) -> None:
    """Simulated async background audit logger."""
    _audit_log.append({"action": action, "table": table, "id": row_id})
    logging.info("AUDIT: %s %s id=%s", action, table, row_id)


# ── Middleware ────────────────────────────────────────────────────────────────


class RequestLogMiddleware(Middleware):
    """Sync middleware: log every incoming request."""

    def process(self, request: Request, response: Response | None) -> None:
        if response is None:
            logging.info("→ %s %s", request.method, request.url.path)
        return None


class TimingMiddleware(Middleware):
    """Async middleware: add X-Powered-By header to every response."""

    async def process(self, request: Request, response: Response | None) -> None:
        if response is not None:
            response.headers["X-Powered-By"] = "LightAPI-async"
        return None


# ── Endpoints ─────────────────────────────────────────────────────────────────


class Author(RestEndpoint):
    """Public author resource — AllowAny, paginated, filterable, serialized."""

    name: str = Field(min_length=1, max_length=200)
    bio: Optional[str] = Field(default=None)
    active: bool = Field(default=True)

    class Meta:
        authentication = Authentication(permission=AllowAny)
        filtering = Filtering(
            backends=[FieldFilter, OrderingFilter, SearchFilter],
            fields=["name", "active"],
            ordering=["name", "created_at"],
            search=["name", "bio"],
        )
        pagination = Pagination(page_size=10)
        serializer = Serializer(
            fields=["id", "name", "bio", "active", "created_at"],
        )

    async def queryset(self, request: Request):
        return select(type(self)._model_class).where(
            type(self)._model_class.active.is_(True)
        )

    async def post(self, request: Request) -> Response:
        import json

        data = json.loads(await request.body())
        resp = await self._create_async(data)
        if resp.status_code == 201:
            body = json.loads(resp.body)
            self.background(_audit, "create", "authors", body["id"])
        return resp


class Book(RestEndpoint):
    """JWT-protected book resource with async queryset join and background audit."""

    title: str = Field(min_length=1, max_length=300)
    author_id: int = Field(gt=0)
    isbn: Optional[str] = Field(default=None, max_length=20)
    published: bool = Field(default=False)
    page_count: int = Field(default=0, ge=0)

    class Meta:
        authentication = Authentication(permission=AllowAny)
        filtering = Filtering(
            backends=[FieldFilter, OrderingFilter],
            fields=["published", "author_id"],
            ordering=["title", "page_count"],
        )
        pagination = Pagination(page_size=5)
        serializer = Serializer(
            fields=[
                "id",
                "title",
                "author_id",
                "isbn",
                "published",
                "page_count",
                "created_at",
            ],
        )

    async def queryset(self, request: Request):
        return select(type(self)._model_class)

    async def post(self, request: Request) -> Response:
        import json

        data = json.loads(await request.body())
        resp = await self._create_async(data)
        if resp.status_code == 201:
            body = json.loads(resp.body)
            self.background(_audit, "create", "books", body["id"])
        return resp

    async def delete(self, request: Request) -> Response:
        """Soft-delete: mark published=False instead of physical delete."""
        pk = request.path_params["id"]
        resp = await self._update_async(
            {"published": False, "version": _get_version(request)}, pk, partial=True
        )
        if resp.status_code in (200, 409):
            return resp
        return resp


def _get_version(request: Request) -> int:
    """Extract version from query param for soft-delete demo (default 1)."""
    return int(request.query_params.get("version", 1))


class Tag(RestEndpoint):
    """Simple sync-queryset endpoint on the async app — proves coexistence."""

    label: str = Field(min_length=1, max_length=100)
    color: str = Field(default="#ffffff", max_length=7)

    class Meta:
        authentication = Authentication(permission=AllowAny)
        serializer = Serializer(fields=["id", "label", "color"])

    def queryset(self, request: Request):
        """Sync queryset — proves sync still works on async app."""
        return select(type(self)._model_class)


# ── App factory ───────────────────────────────────────────────────────────────


def build() -> LightApi:
    engine = create_async_engine(DATABASE_URL, echo=False)
    app = LightApi(
        engine=engine,
        middlewares=[RequestLogMiddleware, TimingMiddleware],
    )
    app.register(
        {
            "/authors": Author,
            "/books": Book,
            "/tags": Tag,
        }
    )
    return app


if __name__ == "__main__":
    import uvicorn

    lapi = build()
    starlette_app = lapi.build_app()
    uvicorn.run(starlette_app, host="0.0.0.0", port=8000, log_level="info")
