from __future__ import annotations

import base64
import json
import math
from typing import TYPE_CHECKING, Any, Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.requests import Request

from lightapi.constants import (
    PAGE_PARAM,
    RESPONSE_KEY_COUNT,
    RESPONSE_KEY_PAGES,
    RESPONSE_KEY_NEXT,
    RESPONSE_KEY_PREVIOUS,
    RESPONSE_KEY_RESULTS,
    CURSOR_PARAM,
    VALID_PAGINATION_STYLES,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class PaginatorProtocol(Protocol):
    """Protocol for pagination strategies."""

    def paginate(
        self,
        request: Request,
        qs: Any,
        session: Session,
        page_size: int,
    ) -> tuple[list[Any], int] | tuple[list[Any], str | None]:
        """Paginate a queryset."""
        ...

    def wrap(
        self,
        request: Request,
        results: list[Any],
        total: int = ...,
        page: int = ...,
        page_size: int = ...,
        next_cursor: str | None = ...,
        prev_cursor: str | None = ...,
    ) -> dict[str, Any]:
        """Wrap results in pagination response."""
        ...


class PaginatorFactory:
    """Factory to create paginator instances based on configuration."""

    @staticmethod
    def create(style: str = "page_number") -> PaginatorProtocol:
        """Create a paginator instance based on the style.

        Args:
            style: Pagination style ("page_number" or "cursor")

        Returns:
            A paginator instance implementing PaginatorProtocol

        Raises:
            ValueError: If style is not recognized
        """
        if style not in VALID_PAGINATION_STYLES:
            raise ValueError(
                f"Unknown pagination style: {style}. "
                f"Valid styles: {VALID_PAGINATION_STYLES}"
            )

        if style == "cursor":
            return CursorPaginator()
        return PageNumberPaginator()


def encode_cursor(last_id: int) -> str:
    return base64.urlsafe_b64encode(json.dumps({"id": last_id}).encode()).decode()


def decode_cursor(cursor: str) -> int:
    return json.loads(base64.urlsafe_b64decode(cursor.encode()))["id"]


class PageNumberPaginator:
    """Page-number based paginator that returns count/next/previous/results."""

    def paginate(
        self,
        request: Request,
        qs: Any,
        session: Session,
        page_size: int,
    ) -> tuple[list[Any], int]:
        page = max(1, int(request.query_params.get(PAGE_PARAM, 1)))
        offset = (page - 1) * page_size
        count_stmt = select(func.count()).select_from(qs.subquery())
        total: int = session.execute(count_stmt).scalar_one()
        rows = session.execute(qs.limit(page_size).offset(offset)).scalars().all()
        return list(rows), total

    async def paginate_async(
        self,
        request: Request,
        qs: Any,
        session: AsyncSession,
        page_size: int,
    ) -> tuple[list[Any], int]:
        """Async mirror of paginate(); uses await session.execute()."""
        page = max(1, int(request.query_params.get(PAGE_PARAM, 1)))
        offset = (page - 1) * page_size
        count_stmt = select(func.count()).select_from(qs.subquery())
        total: int = (await session.execute(count_stmt)).scalar_one()
        rows = (
            (await session.execute(qs.limit(page_size).offset(offset))).scalars().all()
        )
        return list(rows), total

    def wrap(
        self,
        request: Request,
        results: list[Any],
        total: int,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        pages = math.ceil(total / page_size) if page_size else 0
        base = str(request.url).split("?")[0]
        params = dict(request.query_params)
        next_url = None
        prev_url = None
        if page < pages:
            params[PAGE_PARAM] = str(page + 1)
            next_url = base + "?" + "&".join(f"{k}={v}" for k, v in params.items())
        if page > 1:
            params[PAGE_PARAM] = str(page - 1)
            prev_url = base + "?" + "&".join(f"{k}={v}" for k, v in params.items())
        return {
            RESPONSE_KEY_COUNT: total,
            RESPONSE_KEY_PAGES: pages,
            RESPONSE_KEY_NEXT: next_url,
            RESPONSE_KEY_PREVIOUS: prev_url,
            RESPONSE_KEY_RESULTS: results,
        }


class CursorPaginator:
    """Keyset cursor-based paginator using base64(json({"id": last_id}))."""

    def paginate(
        self,
        request: Request,
        qs: Any,
        session: Session,
        page_size: int,
    ) -> tuple[list[Any], str | None]:
        cursor_str = request.query_params.get(CURSOR_PARAM)
        if cursor_str:
            try:
                last_id = decode_cursor(cursor_str)
                # Extract entity from the select and filter on its id column
                entity = (
                    qs.columns_clause_froms[0]
                    if hasattr(qs, "columns_clause_froms")
                    else None
                )
                id_col = None
                if entity is not None:
                    id_col = entity.c.get("id")
                if id_col is not None:
                    qs = qs.where(id_col > last_id)
            except Exception:
                pass
        rows = session.execute(qs.order_by("id").limit(page_size)).scalars().all()
        next_cursor = None
        if len(rows) == page_size:
            last_obj = rows[-1]
            last_row_id = getattr(last_obj, "id", None)
            if last_row_id is not None:
                next_cursor = encode_cursor(last_row_id)
        return list(rows), next_cursor

    async def paginate_async(
        self,
        request: Request,
        qs: Any,
        session: AsyncSession,
        page_size: int,
    ) -> tuple[list[Any], str | None]:
        """Async mirror of paginate(); uses await session.execute()."""
        cursor_str = request.query_params.get(CURSOR_PARAM)
        if cursor_str:
            try:
                last_id = decode_cursor(cursor_str)
                entity = (
                    qs.columns_clause_froms[0]
                    if hasattr(qs, "columns_clause_froms")
                    else None
                )
                id_col = None
                if entity is not None:
                    id_col = entity.c.get("id")
                if id_col is not None:
                    qs = qs.where(id_col > last_id)
            except Exception:
                pass
        rows = (
            (await session.execute(qs.order_by("id").limit(page_size))).scalars().all()
        )
        next_cursor = None
        if len(rows) == page_size:
            last_obj = rows[-1]
            last_row_id = getattr(last_obj, "id", None)
            if last_row_id is not None:
                next_cursor = encode_cursor(last_row_id)
        return list(rows), next_cursor

    def wrap(
        self,
        results: list[Any],
        next_cursor: str | None,
        prev_cursor: str | None,
    ) -> dict[str, Any]:
        return {
            RESPONSE_KEY_NEXT: next_cursor,
            RESPONSE_KEY_PREVIOUS: prev_cursor,
            RESPONSE_KEY_RESULTS: results,
        }
