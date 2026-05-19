"""Queryset resolver and filtering for endpoints."""

from typing import Any

from sqlalchemy import select as sa_select
from starlette.requests import Request


class QuerysetResolver:
    def get_sync(self, endpoint: Any, request: Request) -> Any:
        """Resolve queryset for sync endpoints."""
        cls = type(endpoint)
        qs_attr = cls.__dict__.get("queryset")
        if qs_attr is None:
            qs_attr = getattr(cls, "queryset", None)
        if qs_attr is None:
            return sa_select(cls._model_class)
        if callable(qs_attr):
            return qs_attr(endpoint, request)
        return qs_attr

    async def get_async(self, endpoint: Any, request: Request) -> Any:
        """Resolve queryset for async endpoints."""
        import asyncio

        cls = type(endpoint)
        qs_attr = cls.__dict__.get("queryset")
        if qs_attr is None:
            qs_attr = getattr(cls, "queryset", None)
        if qs_attr is None:
            return sa_select(cls._model_class)
        if asyncio.iscoroutinefunction(qs_attr):
            result = await qs_attr(endpoint, request)
            return result
        if callable(qs_attr):
            return qs_attr(endpoint, request)
        return qs_attr


class FilterRunner:
    def run(self, endpoint: Any, request: Request, qs: Any) -> Any:
        """Run filter backends on queryset."""
        filtering = endpoint._meta.get("filtering")
        if not filtering or not filtering.backends:
            return qs
        for backend_cls in filtering.backends:
            qs = backend_cls().filter_queryset(request, qs, endpoint)
        return qs


class RowSerializer:
    def serialize(self, endpoint: Any, row: Any, method: str) -> dict[str, Any]:
        """Serialize a database row to response dict."""
        from lightapi.schema import _apply_fields, _row_to_dict, resolve_fields

        cls = type(endpoint)
        d = _row_to_dict(row)
        fields = resolve_fields(cls, method)
        d = _apply_fields(d, fields)
        schema = cls.__schema_read__
        validated = schema.model_validate(d)
        result = validated.model_dump(mode="json")
        if fields is not None:
            result = {k: v for k, v in result.items() if k in fields}
        return result
