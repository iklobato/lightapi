from __future__ import annotations

import base64
import json
import math
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.requests import Request


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
        page = max(1, int(request.query_params.get("page", 1)))
        offset = (page - 1) * page_size
        count_stmt = select(func.count()).select_from(qs.subquery())
        total: int = session.execute(count_stmt).scalar_one()
        rows = session.execute(qs.limit(page_size).offset(offset)).scalars().all()
        return rows, total

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
            params["page"] = str(page + 1)
            next_url = base + "?" + "&".join(f"{k}={v}" for k, v in params.items())
        if page > 1:
            params["page"] = str(page - 1)
            prev_url = base + "?" + "&".join(f"{k}={v}" for k, v in params.items())
        return {
            "count": total,
            "pages": pages,
            "next": next_url,
            "previous": prev_url,
            "results": results,
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
        cursor_str = request.query_params.get("cursor")
        if cursor_str:
            try:
                last_id = decode_cursor(cursor_str)
                # Extract entity from the select and filter on its id column
                entity = qs.columns_clause_froms[0] if hasattr(qs, "columns_clause_froms") else None
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
        return rows, next_cursor

    def wrap(
        self,
        results: list[Any],
        next_cursor: str | None,
        prev_cursor: str | None,
    ) -> dict[str, Any]:
        return {
            "next": next_cursor,
            "previous": prev_cursor,
            "results": results,
        }


class Paginator:
    """
    Base class for pagination.

    Provides methods for limiting, offsetting, and sorting database queries.
    Can be subclassed to implement custom pagination behavior.

    Attributes:
        limit: Maximum number of records to return.
        offset: Number of records to skip.
        sort: Whether to apply sorting.
    """

    limit = 10
    offset = 0
    sort = False

    def paginate(self, queryset: Query) -> List[Any]:
        """
        Apply pagination to a database query.

        Limits the number of results, applies offset, and
        optionally sorts the queryset.

        Args:
            queryset: The SQLAlchemy query to paginate.

        Returns:
            List[Any]: The paginated list of results.
        """
        request_limit = self.get_limit()
        request_offset = self.get_offset()

        if self.sort:
            queryset = self.apply_sorting(queryset)

        return queryset.limit(request_limit).offset(request_offset).all()

    def get_limit(self) -> int:
        """
        Get the limit for pagination.

        Override this method to implement dynamic limits based on the request.

        Returns:
            int: The maximum number of records to return.
        """
        return self.limit

    def get_offset(self) -> int:
        """
        Get the offset for pagination.

        Override this method to implement dynamic offsets based on the request.

        Returns:
            int: The number of records to skip.
        """
        return self.offset

    def apply_sorting(self, queryset: Query) -> Query:
        """
        Apply sorting to the queryset.

        Override this method to implement custom sorting logic.

        Args:
            queryset: The SQLAlchemy query to sort.

        Returns:
            Query: The sorted query.
        """
        return queryset
