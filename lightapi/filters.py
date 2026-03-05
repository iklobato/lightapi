from __future__ import annotations

from typing import Any

from sqlalchemy import asc, desc
from starlette.requests import Request


_RESERVED_PARAMS = frozenset({"page", "page_size", "cursor", "ordering"})


class BaseFilter:
    """Base class for SQLAlchemy 2.0-style filter backends.

    Subclasses implement ``filter_queryset(request, queryset, view)``
    which receives a Select statement and should return a Select statement.
    """

    def filter_queryset(self, request: Request, queryset: Any, view: Any) -> Any:
        return queryset


class FieldFilter(BaseFilter):
    """Exact-match filter on whitelisted fields declared in Meta.filtering.fields."""

    def filter_queryset(self, request: Request, queryset: Any, view: Any) -> Any:
        filtering_cfg = getattr(view, "_meta", {}).get("filtering")
        allowed_fields: list[str] = (filtering_cfg.fields or []) if filtering_cfg else []
        if not allowed_fields:
            return queryset

        cls = type(view)
        for param, value in request.query_params.items():
            if param in _RESERVED_PARAMS or param not in allowed_fields:
                continue
            col = getattr(cls._model_class, param, None)
            if col is not None:
                queryset = queryset.where(col == value)
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
                clauses.append(col.ilike(f"%{query}%"))
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

        cls = type(view)
        for field in ordering_param.split(","):
            field = field.strip()
            direction = desc if field.startswith("-") else asc
            field_name = field.lstrip("-")
            if allowed and field_name not in allowed:
                continue
            col = getattr(cls._model_class, field_name, None)
            if col is not None:
                queryset = queryset.order_by(direction(col))
        return queryset


class ParameterFilter(BaseFilter):
    """
    Base class for query filters.

    Provides a common interface for all filtering methods.
    By default, returns the queryset unchanged.
    """

    def filter_queryset(self, queryset: Query, request) -> Query:
        """
        Filter a database queryset based on the request.

        Args:
            queryset: The SQLAlchemy query to filter.
            request: The HTTP request containing filter parameters.

        Returns:
            Query: The filtered query.
        """
        return queryset


class ParameterFilter(BaseFilter):
    """
    Filter queryset based on request query parameters.

    Automatically filters the queryset using query parameters that
    match model field names, performing exact matching.
    """

    def filter_queryset(self, queryset: Query, request) -> Query:
        """
        Filter a database queryset based on request query parameters.

        For each query parameter that matches a model field name,
        the queryset is filtered to records where that field equals
        the parameter value.

        Args:
            queryset: The SQLAlchemy query to filter.
            request: The HTTP request containing filter parameters.

        Returns:
            Query: The filtered query.
        """
        query_params = dict(request.query_params)
        if not query_params:
            return queryset

        entity = queryset.column_descriptions[0]["entity"]
        result = None
        for param, value in query_params.items():
            if hasattr(entity, param):
                result = queryset.filter(getattr(entity, param) == value)
        return result if result is not None else queryset
