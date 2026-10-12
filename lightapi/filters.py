from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, Float, Integer, Numeric, Select, asc, desc, or_
from starlette.requests import Request

from lightapi.constants import INT64_MAX, INT64_MIN

if TYPE_CHECKING:
    from lightapi.rest import RestEndpoint


class FilterValueError(ValueError):
    """A query-string value the column type cannot parse (``?pages=lots``)."""

    def __init__(self, param: str, value: str, expected: str) -> None:
        super().__init__(f"{param}={value!r} is not a valid {expected}")
        self.param = param
        self.value = value
        self.expected = expected

    def errors(self) -> list[dict[str, Any]]:
        """The 422 body, shaped like pydantic's error list."""
        return [
            {
                "loc": ["query", self.param],
                "msg": f"Input should be a valid {self.expected}",
                "type": f"{self.expected}_parsing",
                "input": self.value,
            }
        ]


class BaseFilter:
    """Base class for SQLAlchemy 2.0-style filter backends.

    Subclasses implement ``filter_queryset(request, queryset, view)``
    which receives a Select statement and should return a Select statement.
    """

    RESERVED_PARAMS = frozenset({"page", "page_size", "cursor", "ordering"})
    LIKE_ESCAPE_CHAR = "\\"

    def filter_queryset(
        self,
        request: Request,  # noqa: ARG002  interface method
        queryset: Select[Any],
        view: RestEndpoint,  # noqa: ARG002  interface method
    ) -> Select[Any]:
        return queryset

    @classmethod
    def _escape_like(cls, value: str) -> str:
        """Escape LIKE special characters so user input is a literal string."""
        char = cls.LIKE_ESCAPE_CHAR
        return (
            value.replace(char, char * 2)
            .replace("%", char + "%")
            .replace("_", char + "_")
        )

    @staticmethod
    def _coerce_filter_value(
        col: Any,  # noqa: ANN401  a mapped attribute, or whatever a custom backend passes
        value: str,
    ) -> bool | int | float | str:
        """Coerce a query-string value to match the column's Python type.

        An attribute that is not a column passes the value through as the string
        it came in as. A value an int or float column cannot parse raises
        FilterValueError: handed to the database it is a silent empty list on
        SQLite and a DataError (500) on Postgres.
        """
        try:
            col_type = (
                col.property.columns[0].type if hasattr(col, "property") else None
            )
        except (AttributeError, IndexError):
            col_type = None
        if col_type is None:
            # InstrumentedAttribute from mapped class
            col_type = getattr(col, "type", None)
        if isinstance(col_type, Boolean):
            return value.lower() in ("1", "true", "yes", "on")
        expected = "integer" if isinstance(col_type, Integer) else "number"
        try:
            if isinstance(col_type, Integer):
                number = int(value)
            elif isinstance(col_type, (Numeric, Float)):
                return float(value)
            else:
                return value
        except ValueError:
            raise FilterValueError(getattr(col, "key", "?"), value, expected) from None
        # Past 64 bits the driver raises (OverflowError on SQLite) instead of
        # comparing; no column holds such a value.
        if not INT64_MIN <= number <= INT64_MAX:
            raise FilterValueError(getattr(col, "key", "?"), value, expected)
        return number


def _coerce_filter_value(
    col: Any,  # noqa: ANN401  see BaseFilter._coerce_filter_value
    value: str,
) -> bool | int | float | str:
    """Module-level alias of BaseFilter._coerce_filter_value.

    docs/api-reference/filters.md teaches custom backends to import this
    name directly; keep it importing here even though subclasses now get
    it for free via self._coerce_filter_value.
    """
    return BaseFilter._coerce_filter_value(col, value)  # noqa: SLF001  the alias above


class FieldFilter(BaseFilter):
    """Exact-match filter on whitelisted fields declared in Meta.filtering.fields."""

    def filter_queryset(
        self, request: Request, queryset: Select[Any], view: RestEndpoint
    ) -> Select[Any]:
        filtering_cfg = view._meta.get("filtering")  # noqa: SLF001  the endpoint's Meta
        allowed_fields: list[str] = (
            (filtering_cfg.fields or []) if filtering_cfg else []
        )
        if not allowed_fields:
            return queryset

        cls = type(view)
        for param, value in request.query_params.items():
            if param in self.RESERVED_PARAMS or param not in allowed_fields:
                continue
            col = getattr(cls._model_class, param, None)
            if col is not None:
                coerced = self._coerce_filter_value(col, value)
                queryset = queryset.where(col == coerced)
        return queryset


class SearchFilter(BaseFilter):
    """Case-insensitive LIKE search across Meta.filtering.search fields."""

    def filter_queryset(
        self, request: Request, queryset: Select[Any], view: RestEndpoint
    ) -> Select[Any]:
        query = request.query_params.get("search")
        if not query:
            return queryset

        filtering_cfg = view._meta.get("filtering")  # noqa: SLF001  the endpoint's Meta
        search_fields: list[str] = (filtering_cfg.search or []) if filtering_cfg else []
        if not search_fields:
            return queryset

        cls = type(view)
        clauses = []
        for field in search_fields:
            col = getattr(cls._model_class, field, None)
            if col is not None:
                clauses.append(
                    col.ilike(
                        f"%{self._escape_like(query)}%", escape=self.LIKE_ESCAPE_CHAR
                    )
                )
        if clauses:
            queryset = queryset.where(or_(*clauses))
        return queryset


class OrderingFilter(BaseFilter):
    """Ordering via ``?ordering=field`` or ``?ordering=-field`` (descending)."""

    def filter_queryset(
        self, request: Request, queryset: Select[Any], view: RestEndpoint
    ) -> Select[Any]:
        ordering_param = request.query_params.get("ordering")
        if not ordering_param:
            return queryset

        filtering_cfg = view._meta.get("filtering")  # noqa: SLF001  the endpoint's Meta
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
