"""Programmatic configuration from a plain dict (``LightApi.from_dict``, deprecated).

Removed in 0.2.0 together with ``from_dict``; nothing else imports this module.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from lightapi.authentication import (
    AllowAny,
    BaseAuthentication,
    BasicAuthentication,
    JWTAuthentication,
)
from lightapi.config import Authentication, Filtering, Pagination
from lightapi.constants import HTTP_METHOD_MIXINS
from lightapi.rest import RestEndpoint


class DictAuthKind(str, Enum):
    """The ``auth:`` values a dict config accepts; anything else is ignored."""

    JWT = "jwt"
    BASIC = "basic"

    @property
    def backend(self) -> type[BaseAuthentication]:
        if self is DictAuthKind.BASIC:
            return BasicAuthentication
        return JWTAuthentication


@dataclass(frozen=True)
class DictConfig:
    """A LightApi configuration given as a dict.

    Keys: ``database_url``, ``mode`` ("sync" or "async"), ``cors`` (list of origins),
    ``endpoints`` ({route: {fields, auth, paginate, filters, methods}}) and
    ``login_validator`` (callable).
    """

    config: dict[str, Any]

    def build(self, app_cls: type, **overrides: Any) -> Any:
        """A configured ``app_cls`` instance with every endpoint registered."""
        constructor_kwargs: dict[str, Any] = {
            "database_url": self.config.get("database_url"),
            "mode": self.config.get("mode", "sync"),
            "cors_origins": self.config.get("cors"),
            "login_validator": self.config.get("login_validator"),
        }
        constructor_kwargs.update(overrides)
        instance = app_cls(**constructor_kwargs)

        mapping = {
            route: self._endpoint_class(route, spec)
            for route, spec in self.config.get("endpoints", {}).items()
        }
        if mapping:
            instance.register(mapping)
        return instance

    @classmethod
    def _endpoint_class(cls, route: str, spec: dict[str, Any]) -> type:
        # __annotations__ is what RestEndpointMeta reads for field names; a value
        # that is not a type is replaced by its type.
        annotations = {
            name: value if isinstance(value, type) else type(value)
            for name, value in spec.get("fields", {}).items()
        }
        class_attrs: dict[str, Any] = {
            "__annotations__": annotations,
            "Meta": type("Meta", (), cls._meta_attributes(spec)),
        }
        # HttpMethod mixins must be real bases: RestEndpointMeta scans the MRO.
        bases = (RestEndpoint, *cls._method_mixins(spec.get("methods")))
        return type(cls._class_name(route), bases, class_attrs)

    @staticmethod
    def _meta_attributes(spec: dict[str, Any]) -> dict[str, Any]:
        attrs: dict[str, Any] = {}
        auth = spec.get("auth")
        if auth:
            try:
                kind = DictAuthKind(auth)
            except ValueError:
                kind = None
            if kind is not None:
                attrs["authentication"] = Authentication(
                    backend=kind.backend, permission=AllowAny
                )

        paginate = spec.get("paginate")
        if isinstance(paginate, dict):
            attrs["pagination"] = Pagination(**paginate)
        elif paginate is True:
            attrs["pagination"] = Pagination()

        filters = spec.get("filters")
        if isinstance(filters, dict):
            attrs["filtering"] = Filtering(**filters)
        elif isinstance(filters, list):
            attrs["filtering"] = Filtering(backends=filters)
        return attrs

    @staticmethod
    def _method_mixins(methods: list[str] | None) -> list[type]:
        """The mixins of the named methods; an unknown name is skipped, as always."""
        if not methods:
            return []
        mixins = (HTTP_METHOD_MIXINS.get(method.upper()) for method in methods)
        return [mixin for mixin in mixins if mixin is not None]

    @staticmethod
    def _class_name(route: str) -> str:
        """Convert /books to BooksEndpoint."""
        parts = route.strip("/").split("/")
        return "".join(part.capitalize() for part in parts) + "Endpoint"
