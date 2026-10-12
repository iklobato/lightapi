from __future__ import annotations

import base64
import binascii
import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any, ClassVar, Protocol

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session
from starlette.requests import Request

from lightapi.constants import CURSOR_PARAM, DEFAULT_PAGE_SIZE, PAGE_PARAM, ResponseKey

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True, slots=True)
class Cursor:
    """Position of a keyset page: the id of the last row the client saw."""

    last_id: int

    # What a client-supplied cursor can fail with; the paginator ignores such a cursor.
    INVALID: ClassVar[tuple[type[Exception], ...]] = (
        binascii.Error,
        UnicodeDecodeError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
    )

    def __post_init__(self) -> None:
        if not isinstance(self.last_id, int):
            raise TypeError(f"cursor id must be an int, got {self.last_id!r}")

    def encode(self) -> str:
        return base64.urlsafe_b64encode(
            json.dumps({"id": self.last_id}).encode()
        ).decode()

    @classmethod
    def decode(cls, text: str) -> Cursor:
        return cls(json.loads(base64.urlsafe_b64decode(text.encode()))["id"])


RowSerializer = Callable[[Any], dict[str, Any]]


class Paginator(Protocol):
    """Turns a query into the body of a list response."""

    def render(
        self,
        request: Request,
        qs: Select[Any],
        session: Session,
        serialize: RowSerializer,
    ) -> dict[str, Any]: ...


class PaginationStyle(str, Enum):
    """How a list response is split; the value is what `Pagination(style=...)` takes."""

    PAGE_NUMBER = "page_number"
    CURSOR = "cursor"

    def build(self, page_size: int) -> Paginator:
        if self is PaginationStyle.CURSOR:
            return CursorPaginator(page_size)
        return PageNumberPaginator(page_size)


class NoPagination:
    """Every row in a single response."""

    def render(
        self,
        request: Request,  # noqa: ARG002  Paginator protocol
        qs: Select[Any],
        session: Session,
        serialize: RowSerializer,
    ) -> dict[str, Any]:
        rows = session.execute(qs).scalars().all()
        return {ResponseKey.RESULTS: [serialize(row) for row in rows]}


class PageNumberPaginator:
    """Page-number based paginator that returns count/next/previous/results."""

    def __init__(self, page_size: int = DEFAULT_PAGE_SIZE) -> None:
        self.page_size = page_size

    def render(
        self,
        request: Request,
        qs: Select[Any],
        session: Session,
        serialize: RowSerializer,
    ) -> dict[str, Any]:
        rows, total = self.paginate(request, qs, session, self.page_size)
        page = self._current_page(request)
        results = [serialize(row) for row in rows]
        return self.wrap(request, results, total, page, self.page_size)

    def paginate(
        self,
        request: Request,
        qs: Select[Any],
        session: Session,
        page_size: int,
    ) -> tuple[list[Any], int]:
        page = self._current_page(request)
        offset = (page - 1) * page_size
        count_stmt = select(func.count()).select_from(qs.subquery())
        total: int = session.execute(count_stmt).scalar_one()
        rows = session.execute(qs.limit(page_size).offset(offset)).scalars().all()
        return list(rows), total

    async def paginate_async(
        self,
        request: Request,
        qs: Select[Any],
        session: AsyncSession,
        page_size: int,
    ) -> tuple[list[Any], int]:
        """paginate() for an AsyncSession."""
        return await session.run_sync(
            lambda sync_session: self.paginate(request, qs, sync_session, page_size)
        )

    @staticmethod
    def _current_page(request: Request) -> int:
        """The requested page, clamped to at least 1; a non-numeric value is page 1."""
        try:
            page = int(request.query_params.get(PAGE_PARAM, 1))
        except ValueError:
            return 1
        return max(1, page)

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
        self,
        request: Request,
        qs: Select[Any],
        session: Session,
        serialize: RowSerializer,
    ) -> dict[str, Any]:
        rows, next_cursor = self.paginate(request, qs, session, self.page_size)
        return self.wrap([serialize(row) for row in rows], next_cursor, None)

    def paginate(
        self,
        request: Request,
        qs: Select[Any],
        session: Session,
        page_size: int,
    ) -> tuple[list[Any], str | None]:
        cursor_text = request.query_params.get(CURSOR_PARAM)
        if cursor_text:
            try:
                cursor: Cursor | None = Cursor.decode(cursor_text)
            except Cursor.INVALID:
                cursor = None
            # The id column of the entity being selected, when the query has one.
            froms = getattr(qs, "columns_clause_froms", ())
            id_col = froms[0].c.get("id") if froms else None
            if cursor is not None and id_col is not None:
                qs = qs.where(id_col > cursor.last_id)
        rows = session.execute(qs.order_by("id").limit(page_size)).scalars().all()
        next_cursor = None
        if len(rows) == page_size:
            last_row_id = getattr(rows[-1], "id", None)
            if last_row_id is not None:
                next_cursor = Cursor(last_row_id).encode()
        return list(rows), next_cursor

    async def paginate_async(
        self,
        request: Request,
        qs: Select[Any],
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
