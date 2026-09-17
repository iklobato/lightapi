from __future__ import annotations

import datetime
from collections.abc import Iterable
from operator import ge, le
from typing import Any

from sqlalchemy import Date, DateTime, Integer, Numeric, asc, desc
from starlette.requests import Request

_RESERVED_PARAMS = frozenset({"page", "page_size", "cursor", "ordering"})
_LIKE_ESCAPE_CHAR = "\\"

# Column types whose values are ordered, and therefore accept range bounds.
# Float is covered by Numeric, which it subclasses.
_RANGEABLE_TYPES = (Integer, Numeric, Date, DateTime)


def _escape_like(value: str) -> str:
    """Escape LIKE special characters so user input is treated as a literal string."""
    return (
        value.replace(_LIKE_ESCAPE_CHAR, _LIKE_ESCAPE_CHAR * 2)
        .replace("%", _LIKE_ESCAPE_CHAR + "%")
        .replace("_", _LIKE_ESCAPE_CHAR + "_")
    )


class BaseFilter:
    """Base class for SQLAlchemy 2.0-style filter backends.

    Subclasses implement ``filter_queryset(request, queryset, view)``
    which receives a Select statement and should return a Select statement.
    """

    def filter_queryset(self, request: Request, queryset: Any, view: Any) -> Any:
        return queryset


def _column_type(col: Any) -> Any:
    """Return the SQLAlchemy type of a mapped column, or None when unavailable."""
    col_type = col.property.columns[0].type if hasattr(col, "property") else None
    if col_type is None:
        # InstrumentedAttribute from mapped class
        col_type = getattr(col, "type", None)
    return col_type


def _coerce_filter_value(col: Any, value: str) -> Any:
    """Coerce a query-string value to match the column's Python type."""
    try:
        from sqlalchemy import Boolean, Float, Integer, Numeric

        col_type = _column_type(col)
        if isinstance(col_type, Boolean):
            return value.lower() in ("1", "true", "yes", "on")
        if isinstance(col_type, Integer):
            return int(value)
        if isinstance(col_type, (Numeric, Float)):
            return float(value)
    except Exception:
        pass
    return value


def _coerce_range_value(col: Any, value: str) -> Any:
    """Coerce a range bound to the column's Python type.

    Returns ``None`` when the value cannot be compared against the column —
    an unparseable number/date, or a column type that has no ordering. The
    caller then skips that bound, matching how the other backends ignore
    query parameters they cannot honour.
    """
    try:
        col_type = _column_type(col)
        if isinstance(col_type, Integer):
            return int(value)
        if isinstance(col_type, Numeric):
            return float(value)
        if isinstance(col_type, DateTime):
            return datetime.datetime.fromisoformat(value)
        if isinstance(col_type, Date):
            return datetime.date.fromisoformat(value)
    except (AttributeError, IndexError, TypeError, ValueError):
        return None
    return None


class FieldFilter(BaseFilter):
    """Exact-match filter on whitelisted fields declared in Meta.filtering.fields."""

    def filter_queryset(self, request: Request, queryset: Any, view: Any) -> Any:
        filtering_cfg = getattr(view, "_meta", {}).get("filtering")
        allowed_fields: list[str] = (
            (filtering_cfg.fields or []) if filtering_cfg else []
        )
        if not allowed_fields:
            return queryset

        cls = type(view)
        for param, value in request.query_params.items():
            if param in _RESERVED_PARAMS or param not in allowed_fields:
                continue
            col = getattr(cls._model_class, param, None)
            if col is not None:
                coerced = _coerce_filter_value(col, value)
                queryset = queryset.where(col == coerced)
        return queryset


class RangeFilter(BaseFilter):
    """Inclusive range filter on fields declared in Meta.filtering.ranges.

    For every whitelisted field, ``?<field>_min=`` adds ``col >= value`` and
    ``?<field>_max=`` adds ``col <= value``. The two bounds are independent:
    either one, both, or neither may be supplied.
    """

    def filter_queryset(self, request: Request, queryset: Any, view: Any) -> Any:
        filtering_cfg = getattr(view, "_meta", {}).get("filtering")
        allowed_fields: list[str] = (
            (filtering_cfg.ranges or []) if filtering_cfg else []
        )
        if not allowed_fields:
            return queryset

        cls = type(view)
        for field in allowed_fields:
            col = getattr(cls._model_class, field, None)
            if col is None:
                continue
            for suffix, comparison in (("_min", ge), ("_max", le)):
                raw = request.query_params.get(f"{field}{suffix}")
                if raw is None:
                    continue
                bound = _coerce_range_value(col, raw)
                if bound is None:
                    continue
                queryset = queryset.where(comparison(col, bound))
        return queryset


class SearchFilter(BaseFilter):
    """Case-insensitive LIKE search across Meta.filtering.search fields."""

    def filter_queryset(self, request: Request, queryset: Any, view: Any) -> Any:
        query = request.query_params.get("search")
        if not query:
            return queryset

        filtering_cfg = getattr(view, "_meta", {}).get("filtering")
        search_fields: list[str] = (filtering_cfg.search or []) if filtering_cfg else []
        if not search_fields:
            return queryset

        from sqlalchemy import or_

        cls = type(view)
        clauses = []
        for field in search_fields:
            col = getattr(cls._model_class, field, None)
            if col is not None:
                clauses.append(
                    col.ilike(f"%{_escape_like(query)}%", escape=_LIKE_ESCAPE_CHAR)
                )
        if clauses:
            queryset = queryset.where(or_(*clauses))
        return queryset


class OrderingFilter(BaseFilter):
    """Ordering via ``?ordering=field`` or ``?ordering=-field`` (descending)."""

    def filter_queryset(self, request: Request, queryset: Any, view: Any) -> Any:
        ordering_param = request.query_params.get("ordering")
        if not ordering_param:
            return queryset

        filtering_cfg = getattr(view, "_meta", {}).get("filtering")
        allowed: list[str] = (filtering_cfg.ordering or []) if filtering_cfg else []

        # No whitelist configured → ordering is disabled entirely.
        if not allowed:
            return queryset

        cls = type(view)
        for field in ordering_param.split(","):
            field = field.strip()
            direction = desc if field.startswith("-") else asc
            field_name = field.lstrip("-")
            if field_name not in allowed:
                continue
            col = getattr(cls._model_class, field_name, None)
            if col is not None:
                queryset = queryset.order_by(direction(col))
        return queryset


def validate_range_fields(
    endpoint_name: str, filtering: Any, columns: Iterable[Any]
) -> None:
    """Validate Meta.filtering.ranges against the endpoint's own columns.

    A range bound only makes sense on an ordered column, so a name that is not
    a field of the endpoint — or one mapped to a type without an ordering, such
    as str or bool — is a configuration mistake and is rejected at class
    definition time rather than silently ignored on every request.
    """
    ranges = getattr(filtering, "ranges", None) or ()
    if not ranges:
        return

    from lightapi.exceptions import ConfigurationError

    columns_by_name = {col.name: col for col in columns}
    for field in ranges:
        col = columns_by_name.get(field)
        if col is None:
            raise ConfigurationError(
                f"RestEndpoint '{endpoint_name}': Meta.filtering.ranges lists "
                f"'{field}', which is not a field on this endpoint."
            )
        if not isinstance(col.type, _RANGEABLE_TYPES):
            raise ConfigurationError(
                f"RestEndpoint '{endpoint_name}': Meta.filtering.ranges lists "
                f"'{field}', whose type {type(col.type).__name__} has no "
                "ordering. Use a numeric, date, or datetime field."
            )
