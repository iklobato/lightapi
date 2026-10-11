from __future__ import annotations

import base64
import json
import math
from typing import TYPE_CHECKING, Any, Callable, Protocol

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.requests import Request

from lightapi.constants import CURSOR_PARAM, DEFAULT_PAGE_SIZE, PAGE_PARAM, ResponseKey

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def encode_cursor(last_id: int) -> str:
    return base64.urlsafe_b64encode(json.dumps({"id": last_id}).encode()).decode()


def decode_cursor(cursor: str) -> int:
    return json.loads(base64.urlsafe_b64decode(cursor.encode()))["id"]


RowSerializer = Callable[[Any], dict[str, Any]]


class Paginator(Protocol):
    """Turns a query into the body of a list response."""

    def render(
        self, request: Request, qs: Any, session: Session, serialize: RowSerializer
    ) -> dict[str, Any]: ...


class NoPagination:
    """Every row in a single response."""

    def render(
        self, request: Request, qs: Any, session: Session, serialize: RowSerializer
    ) -> dict[str, Any]:
        rows = session.execute(qs).scalars().all()
        return {ResponseKey.RESULTS: [serialize(row) for row in rows]}


class PageNumberPaginator:
    """Page-number based paginator that returns count/next/previous/results."""

    def __init__(self, page_size: int = DEFAULT_PAGE_SIZE) -> None:
        self.page_size = page_size

    def render(
        self, request: Request, qs: Any, session: Session, serialize: RowSerializer
    ) -> dict[str, Any]:
        rows, total = self.paginate(request, qs, session, self.page_size)
        page = int(request.query_params.get(PAGE_PARAM, 1))
        results = [serialize(row) for row in rows]
        return self.wrap(request, results, total, page, self.page_size)

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
        """paginate() for an AsyncSession."""
        return await session.run_sync(
            lambda sync_session: self.paginate(request, qs, sync_session, page_size)
        )

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
            ResponseKey.COUNT: total,
            ResponseKey.PAGES: pages,
            ResponseKey.NEXT: next_url,
            ResponseKey.PREVIOUS: prev_url,
            ResponseKey.RESULTS: results,
        }


class CursorPaginator:
    """Keyset cursor-based paginator using base64(json({"id": last_id}))."""

    def __init__(self, page_size: int = DEFAULT_PAGE_SIZE) -> None:
        self.page_size = page_size

    def render(
        self, request: Request, qs: Any, session: Session, serialize: RowSerializer
    ) -> dict[str, Any]:
        rows, next_cursor = self.paginate(request, qs, session, self.page_size)
        return self.wrap([serialize(row) for row in rows], next_cursor, None)

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
        """paginate() for an AsyncSession."""
        return await session.run_sync(
            lambda sync_session: self.paginate(request, qs, sync_session, page_size)
        )

    def wrap(
        self,
        results: list[Any],
        next_cursor: str | None,
        prev_cursor: str | None,
    ) -> dict[str, Any]:
        return {
            ResponseKey.NEXT: next_cursor,
            ResponseKey.PREVIOUS: prev_cursor,
            ResponseKey.RESULTS: results,
        }


PAGINATORS: dict[str, type[PageNumberPaginator] | type[CursorPaginator]] = {
    "page_number": PageNumberPaginator,
    "cursor": CursorPaginator,
}
