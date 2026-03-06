from __future__ import annotations

import os
from typing import Any

from lightapi.exceptions import ConfigurationError


class _LegacyConfig:
    """Backward-compatibility shim for legacy modules and JWTAuthentication."""

    def __init__(self) -> None:
        self._overrides: dict[str, Any] = {}

    def update(self, **kwargs: Any) -> None:
        self._overrides.update(kwargs)

    def _get(self, key: str, env_key: str, default: Any = None) -> Any:
        if key in self._overrides:
            return self._overrides[key]
        val = os.environ.get(env_key)
        return val if val is not None else default

    @property
    def jwt_secret(self) -> str | None:
        return self._get("jwt_secret", "LIGHTAPI_JWT_SECRET")

    @property
    def database_url(self) -> str:
        return self._get("database_url", "LIGHTAPI_DATABASE_URL", "sqlite:///app.db")

    @property
    def host(self) -> str:
        return self._get("host", "LIGHTAPI_HOST", "0.0.0.0")

    @property
    def port(self) -> int:
        return int(self._get("port", "LIGHTAPI_PORT", 8000))

    @property
    def debug(self) -> bool:
        v = self._get("debug", "LIGHTAPI_DEBUG", False)
        return v if isinstance(v, bool) else v.lower() == "true"

    @property
    def reload(self) -> bool:
        v = self._get("reload", "LIGHTAPI_RELOAD", False)
        return v if isinstance(v, bool) else v.lower() == "true"

    @property
    def enable_swagger(self) -> bool:
        v = self._get("enable_swagger", "LIGHTAPI_ENABLE_SWAGGER", False)
        return v if isinstance(v, bool) else v.lower() == "true"

    @property
    def swagger_title(self) -> str:
        return self._get("swagger_title", "LIGHTAPI_SWAGGER_TITLE", "LightAPI")

    @property
    def swagger_version(self) -> str:
        return self._get("swagger_version", "LIGHTAPI_SWAGGER_VERSION", "1.0.0")

    @property
    def swagger_description(self) -> str:
        return self._get("swagger_description", "LIGHTAPI_SWAGGER_DESCRIPTION", "")

    @property
    def cors_origins(self) -> list[str]:
        return self._get("cors_origins", "LIGHTAPI_CORS_ORIGINS", [])


config = _LegacyConfig()


class Authentication:
    """Authentication configuration for a RestEndpoint."""

    def __init__(
        self,
        backend: type | None = None,
        permission: type | dict[str, type] | None = None,
    ) -> None:
        from lightapi.auth import AllowAny

        self.backend = backend
        self.permission: type | dict[str, type] = (
            permission if permission is not None else AllowAny
        )


class Filtering:
    """Filtering configuration for a RestEndpoint."""

    def __init__(
        self,
        backends: list[type] | None = None,
        fields: list[str] | None = None,
        search: list[str] | None = None,
        ordering: list[str] | None = None,
    ) -> None:
        self.backends: list[type] = backends or []
        self.fields: list[str] = fields or []
        self.search: list[str] = search or []
        self.ordering: list[str] = ordering or []


class Pagination:
    """Pagination configuration for a RestEndpoint."""

    VALID_STYLES = ("page_number", "cursor")

    def __init__(self, style: str = "page_number", page_size: int = 20) -> None:
        if style not in self.VALID_STYLES:
            raise ConfigurationError(
                f"Pagination style '{style}' is invalid. "
                f"Choose from: {self.VALID_STYLES}"
            )
        if page_size < 1:
            raise ConfigurationError("Pagination page_size must be a positive integer.")
        self.style = style
        self.page_size = page_size


class Serializer:
    """Field-projection configuration for a RestEndpoint.

    Four forms:
    1. Serializer()                          → all fields, all verbs
    2. Serializer(fields=[...])              → unified subset, all verbs
    3. Serializer(read=[...], write=[...])   → per-verb subsets
    4. Subclass with class-level attributes  → reusable across endpoints
    """

    fields: list[str] | None = None
    read: list[str] | None = None
    write: list[str] | None = None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        has_fields = cls.__dict__.get("fields") is not None
        has_read = cls.__dict__.get("read") is not None
        has_write = cls.__dict__.get("write") is not None
        if has_fields and (has_read or has_write):
            raise ConfigurationError(
                f"Serializer subclass '{cls.__name__}' defines both 'fields' and "
                "'read'/'write'. These are mutually exclusive."
            )

    def __init__(
        self,
        fields: list[str] | None = None,
        read: list[str] | None = None,
        write: list[str] | None = None,
    ) -> None:
        # When instantiated as a subclass, class-level attributes take precedence
        # over None defaults so that form-4 (subclass) serializers work correctly.
        cls_dict = type(self).__dict__
        resolved_fields = fields if fields is not None else cls_dict.get("fields")
        resolved_read = read if read is not None else cls_dict.get("read")
        resolved_write = write if write is not None else cls_dict.get("write")

        if resolved_fields is not None and (
            resolved_read is not None or resolved_write is not None
        ):
            raise ConfigurationError(
                "Serializer 'fields' and 'read'/'write' are mutually exclusive."
            )
        self.fields = resolved_fields
        self.read = resolved_read
        self.write = resolved_write


class Cache:
    """Response caching configuration for a RestEndpoint."""

    def __init__(self, ttl: int, vary_on: list[str] | None = None) -> None:
        if ttl < 1:
            raise ConfigurationError("Cache ttl must be a positive integer (seconds).")
        self.ttl = ttl
        self.vary_on: list[str] = vary_on or []
