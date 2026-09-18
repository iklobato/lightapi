"""Pydantic models of the declarative YAML document (see yaml_loader for the format)."""

from __future__ import annotations

import datetime
import os
from decimal import Decimal
from typing import Union

from pydantic import BaseModel, field_validator, model_validator

from lightapi.exceptions import ConfigurationError

YAML_FIELD_TYPES: dict[str, type] = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "datetime": datetime.datetime,
    "Decimal": Decimal,
    "decimal": Decimal,
}


def _substitute_env(value: str) -> str:
    """Replace ${VAR} with the environment variable value."""
    if value.startswith("${") and value.endswith("}"):
        var = value[2:-1]
        resolved = os.environ.get(var)
        if not resolved:
            raise ConfigurationError(
                f"Environment variable '{var}' is not set (required by lightapi.yaml)."
            )
        return resolved
    return value


class DatabaseConfig(BaseModel):
    """Nested database block: database: { url: ... }"""

    url: str

    @field_validator("url", mode="before")
    @classmethod
    def substitute_env(cls, v: str) -> str:
        return _substitute_env(v)


class AuthLoginConfig(BaseModel):
    """Login/auth block: auth: { auth_path: ..., login_validator: ... }.

    When using JWTAuthentication or BasicAuthentication, login_validator is required.
    It can be specified as a dotted path (e.g. myapp.validators.validate_login)
    or passed as an override to from_config(login_validator=...).
    """

    auth_path: str = "/auth"
    login_validator: str | None = None


class AuthConfig(BaseModel):
    """Authentication block used in defaults and per-endpoint meta."""

    backend: str | None = None
    permission: Union[str, dict[str, str], None] = None
    jwt_expiration: int | None = None
    jwt_extra_claims: list[str] | None = None
    jwt_algorithm: str | None = None

    def merged_over(self, defaults: AuthConfig | None) -> AuthConfig:
        """These settings, with every one left unset taken from ``defaults``."""
        if defaults is None:
            return self
        return defaults.model_copy(update=self.model_dump(exclude_none=True))


class FilteringConfig(BaseModel):
    """Filtering block inside meta."""

    backends: list[str] = []
    fields: list[str] = []
    search: list[str] = []
    ordering: list[str] = []


class PaginationConfig(BaseModel):
    """Pagination block used in defaults and per-endpoint meta."""

    style: str = "page_number"
    page_size: int = 20


class DefaultsConfig(BaseModel):
    """Global defaults applied to all endpoints unless overridden."""

    authentication: AuthConfig | None = None
    pagination: PaginationConfig | None = None


class MethodAuthConfig(BaseModel):
    """Per-method authentication override inside meta.methods dict."""

    authentication: AuthConfig | None = None


class CacheConfig(BaseModel):
    """Cache block inside meta: cache: { ttl: 60 }"""

    ttl: int = 60


class SerializerConfig(BaseModel):
    """Serializer block inside meta.

    Use ``fields`` for a unified list, or ``read``/``write`` for per-verb lists.
    """

    fields: list[str] | None = None
    read: list[str] | None = None
    write: list[str] | None = None


class MetaConfig(BaseModel):
    """meta: block inside a declarative endpoint entry."""

    # methods can be a list ["GET", "POST"] or a dict {GET: {...}, DELETE: {...}}
    methods: Union[list[str], dict[str, MethodAuthConfig | None]] = []
    authentication: AuthConfig | None = None
    filtering: FilteringConfig | None = None
    pagination: PaginationConfig | None = None
    cache: CacheConfig | None = None
    serializer: SerializerConfig | None = None
    table: str | None = None  # custom table name (required when reflect: true)


class FieldSpec(BaseModel):
    """Single field definition inside fields:."""

    type: str
    optional: bool = False
    # All remaining keys forwarded to Field() as pydantic constraints
    model_config = {"extra": "allow"}

    @field_validator("type")
    @classmethod
    def type_must_be_known(cls, v: str) -> str:
        if v not in YAML_FIELD_TYPES:
            raise ValueError(
                f"Unknown field type '{v}'. Valid types: {sorted(YAML_FIELD_TYPES)}"
            )
        return v


class EndpointConfig(BaseModel):
    """A single endpoint entry."""

    route: str
    fields: dict[str, FieldSpec] = {}
    reflect: bool = False
    meta: MetaConfig = MetaConfig()

    @model_validator(mode="after")
    def require_route(self) -> "EndpointConfig":
        if not self.route:
            raise ValueError("Each endpoint must have a 'route'.")
        return self

    @property
    def effective_route(self) -> str:
        return self.route.strip()


class LightAPIConfig(BaseModel):
    """Root YAML document schema."""

    database: DatabaseConfig | None = None
    cors_origins: list[str] = []
    defaults: DefaultsConfig = DefaultsConfig()
    endpoints: list[EndpointConfig] = []
    middleware: list[str] = []
    auth: AuthLoginConfig | None = None
    mode: str | None = None  # "sync" | "async" — auto-detected when omitted

    @property
    def effective_database_url(self) -> str | None:
        return self.database.url if self.database else None
