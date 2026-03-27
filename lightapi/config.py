from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from lightapi.exceptions import ConfigurationError
from lightapi.constants import (
    DEFAULT_JWT_ALGORITHM,
    DEFAULT_JWT_EXPIRATION,
    DEFAULT_PAGE_SIZE,
    DEFAULT_CACHE_TTL,
    VALID_JWT_ALGORITHMS,
    VALID_PAGINATION_STYLES,
    RESERVED_JWT_CLAIMS,
)


@dataclass
class Config:
    """Configuration for LightAPI.

    Can be instantiated with custom values or loaded from environment.
    """

    jwt_secret: str | None = None
    jwt_algorithm: str = DEFAULT_JWT_ALGORITHM
    jwt_expiration: int = DEFAULT_JWT_EXPIRATION

    @property
    def jwt_secret_value(self) -> str | None:
        if self.jwt_secret is not None:
            return self.jwt_secret
        return os.environ.get("LIGHTAPI_JWT_SECRET")

    @property
    def jwt_algorithm_value(self) -> str:
        algorithm = self.jwt_algorithm or os.environ.get(
            "LIGHTAPI_JWT_ALGORITHM", DEFAULT_JWT_ALGORITHM
        )
        if algorithm not in VALID_JWT_ALGORITHMS:
            raise ConfigurationError(
                f"Invalid JWT algorithm '{algorithm}'. "
                f"Valid algorithms are: {sorted(VALID_JWT_ALGORITHMS)}"
            )
        return algorithm

    def update(self, **kwargs: Any) -> None:
        """Update configuration values."""
        if "jwt_secret" in kwargs:
            self.jwt_secret = kwargs["jwt_secret"]
        if "jwt_algorithm" in kwargs:
            self.jwt_algorithm = kwargs["jwt_algorithm"]
        if "jwt_expiration" in kwargs:
            self.jwt_expiration = kwargs["jwt_expiration"]


# Default global config instance for backward compatibility
config = Config()


@dataclass(frozen=True)
class Authentication:
    """Authentication configuration for a RestEndpoint."""

    backend: type | None = None
    permission: type | None = None
    jwt_expiration: int | None = None
    jwt_extra_claims: tuple[str, ...] = field(default_factory=tuple)
    jwt_algorithm: str | None = None

    @property
    def permission_value(self) -> type:
        from lightapi.auth import AllowAny

        return self.permission or AllowAny


@dataclass(frozen=True)
class Filtering:
    """Filtering configuration for a RestEndpoint."""

    backends: tuple[type, ...] = field(default_factory=tuple)
    fields: tuple[str, ...] = field(default_factory=tuple)
    search: tuple[str, ...] = field(default_factory=tuple)
    ordering: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class Pagination:
    """Pagination configuration for a RestEndpoint."""

    style: str = "page_number"
    page_size: int = DEFAULT_PAGE_SIZE

    def __post_init__(self):
        if self.style not in VALID_PAGINATION_STYLES:
            raise ConfigurationError(
                f"Pagination style '{self.style}' is invalid. "
                f"Choose from: {VALID_PAGINATION_STYLES}"
            )
        if self.page_size < 1:
            raise ConfigurationError("Pagination page_size must be a positive integer.")


@dataclass(frozen=True)
class Cache:
    """Response caching configuration for a RestEndpoint."""

    ttl: int = DEFAULT_CACHE_TTL
    vary_on: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self):
        if self.ttl < 1:
            raise ConfigurationError("Cache ttl must be a positive integer (seconds).")


# Serializer has complex __init_subclass__ logic, keep as is
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
