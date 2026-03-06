"""Declarative YAML configuration loader for LightAPI v2.

Uses Pydantic v2 models to validate the YAML structure, then translates
the validated model into RestEndpoint subclasses and LightApi configuration.

Declarative format::

    database:
      url: postgresql://user:pass@localhost/shop

    defaults:
      authentication: { backend: JWTAuthentication, permission: IsAuthenticated }
      pagination:     { style: page_number, page_size: 20 }

    endpoints:
      - route: /announcements
        fields:
          title:  { type: str, min_length: 1, max_length: 200 }
          pinned: { type: bool, default: false }
        meta:
          methods: [GET, POST]
          authentication: { permission: AllowAny }
          filtering: { fields: [pinned], ordering: [created_at] }

    middleware: [CORSMiddleware, RequestIdMiddleware]
"""
from __future__ import annotations

import datetime
import importlib
import os
from decimal import Decimal
from typing import Any, Union

from pydantic import BaseModel, field_validator, model_validator

from lightapi.exceptions import ConfigurationError

# ─────────────────────────────────────────────────────────────────────────────
# String → class registry (everything a YAML author would reference by name)
# ─────────────────────────────────────────────────────────────────────────────

def _build_name_registry() -> dict[str, type]:
    from lightapi.auth import AllowAny, IsAdminUser, IsAuthenticated, JWTAuthentication
    from lightapi.core import AuthenticationMiddleware, CORSMiddleware, Middleware
    from lightapi.filters import (
        FieldFilter,
        OrderingFilter,
        ParameterFilter,
        SearchFilter,
    )
    from lightapi.methods import HttpMethod

    return {
        # Auth backends
        "JWTAuthentication": JWTAuthentication,
        # Permissions
        "AllowAny": AllowAny,
        "IsAuthenticated": IsAuthenticated,
        "IsAdminUser": IsAdminUser,
        # Filter backends
        "FieldFilter": FieldFilter,
        "SearchFilter": SearchFilter,
        "OrderingFilter": OrderingFilter,
        "ParameterFilter": ParameterFilter,
        # Middleware
        "Middleware": Middleware,
        "CORSMiddleware": CORSMiddleware,
        "AuthenticationMiddleware": AuthenticationMiddleware,
        # HttpMethod mixins (for bases resolution)
        "GET": HttpMethod.GET,
        "POST": HttpMethod.POST,
        "PUT": HttpMethod.PUT,
        "PATCH": HttpMethod.PATCH,
        "DELETE": HttpMethod.DELETE,
    }


def _resolve_name(name: str) -> type:
    """Resolve a class name string to a class.

    Tries the built-in registry first, then falls back to dotted import path
    (e.g. 'myapp.middleware.RequestIdMiddleware').
    """
    registry = _build_name_registry()
    if name in registry:
        return registry[name]
    # Dotted path fallback
    if "." in name:
        module_path, class_name = name.rsplit(".", 1)
        try:
            mod = importlib.import_module(module_path)
            return getattr(mod, class_name)
        except (ImportError, AttributeError) as exc:
            raise ConfigurationError(
                f"Cannot resolve '{name}': {exc}"
            ) from exc
    raise ConfigurationError(
        f"Unknown class name '{name}'. "
        "Use a fully dotted import path for custom classes."
    )


# ─────────────────────────────────────────────────────────────────────────────
# Type map for declarative field definitions
# ─────────────────────────────────────────────────────────────────────────────

_YAML_TYPE_MAP: dict[str, type] = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "datetime": datetime.datetime,
    "Decimal": Decimal,
    "decimal": Decimal,
}

# ─────────────────────────────────────────────────────────────────────────────
# Pydantic v2 models — the YAML schema
# ─────────────────────────────────────────────────────────────────────────────

class DatabaseConfig(BaseModel):
    """Nested database block: database: { url: ... }"""
    url: str

    @field_validator("url", mode="before")
    @classmethod
    def substitute_env(cls, v: str) -> str:
        return _substitute_env(v)


class AuthConfig(BaseModel):
    """Authentication block used in defaults and per-endpoint meta."""
    backend: str | None = None
    permission: Union[str, dict[str, str], None] = None


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


class MetaConfig(BaseModel):
    """meta: block inside a declarative endpoint entry."""
    # methods can be a list ["GET", "POST"] or a dict {GET: {...}, DELETE: {...}}
    methods: Union[list[str], dict[str, MethodAuthConfig | None]] = []
    authentication: AuthConfig | None = None
    filtering: FilteringConfig | None = None
    pagination: PaginationConfig | None = None


class FieldSpec(BaseModel):
    """Single field definition inside fields:."""
    type: str
    optional: bool = False
    # All remaining keys forwarded to Field() as pydantic constraints
    model_config = {"extra": "allow"}

    @field_validator("type")
    @classmethod
    def type_must_be_known(cls, v: str) -> str:
        if v not in _YAML_TYPE_MAP:
            raise ValueError(
                f"Unknown field type '{v}'. Valid types: {sorted(_YAML_TYPE_MAP)}"
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

    @property
    def effective_database_url(self) -> str | None:
        return self.database.url if self.database else None


# ─────────────────────────────────────────────────────────────────────────────
# Translation: validated Pydantic model → LightAPI objects
# ─────────────────────────────────────────────────────────────────────────────

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


def _make_authentication(
    auth_cfg: AuthConfig | None, defaults_auth: AuthConfig | None
) -> Any:
    """Build an Authentication instance from an AuthConfig, merged with defaults."""
    from lightapi.config import Authentication

    # Merge: explicit cfg wins over defaults, defaults fill gaps
    merged_backend = None
    merged_permission = None

    for source in (defaults_auth, auth_cfg):
        if source is None:
            continue
        if source.backend is not None:
            merged_backend = source.backend
        if source.permission is not None:
            merged_permission = source.permission

    if merged_backend is None and merged_permission is None:
        return None

    backend_cls = _resolve_name(merged_backend) if merged_backend else None

    if isinstance(merged_permission, dict):
        # Per-method permission dict: {GET: IsAuthenticated, DELETE: IsAdminUser}
        permission = {
            method: _resolve_name(perm)
            for method, perm in merged_permission.items()
        }
    elif isinstance(merged_permission, str):
        permission = _resolve_name(merged_permission)
    else:
        permission = None

    return Authentication(backend=backend_cls, permission=permission)


def _make_filtering(filtering_cfg: FilteringConfig | None) -> Any:
    """Build a Filtering instance from a FilteringConfig."""
    if filtering_cfg is None:
        return None
    from lightapi.config import Filtering
    from lightapi.filters import FieldFilter, OrderingFilter, SearchFilter

    # Auto-select backends based on which lists are populated
    backends: list[type] = list(
        [_resolve_name(b) for b in filtering_cfg.backends]
        if filtering_cfg.backends
        else []
    )
    if not backends:
        if filtering_cfg.fields:
            backends.append(FieldFilter)
        if filtering_cfg.search:
            backends.append(SearchFilter)
        if filtering_cfg.ordering:
            backends.append(OrderingFilter)

    return Filtering(
        backends=backends or None,
        fields=filtering_cfg.fields or None,
        search=filtering_cfg.search or None,
        ordering=filtering_cfg.ordering or None,
    )


def _make_pagination(pag_cfg: PaginationConfig | None) -> Any:
    """Build a Pagination instance from a PaginationConfig."""
    if pag_cfg is None:
        return None
    from lightapi.config import Pagination
    return Pagination(style=pag_cfg.style, page_size=pag_cfg.page_size)


def _build_meta_class(
    meta: MetaConfig,
    defaults: DefaultsConfig,
    reflect: bool,
) -> type:
    """Construct a Meta inner class for dynamic RestEndpoint subclasses."""
    attrs: dict[str, Any] = {}

    if reflect:
        attrs["reflect"] = True
        return type("Meta", (), attrs)

    # Authentication — handle per-method dict (methods as dict form)
    if isinstance(meta.methods, dict):
        # Build per-method permission dict from the methods dict
        permission_map: dict[str, type] = {}
        method_auth_default = meta.authentication  # endpoint-level auth override
        for method, method_cfg in meta.methods.items():
            cfg_auth = method_cfg.authentication if method_cfg else None
            src_auth = cfg_auth or method_auth_default
            if src_auth and src_auth.permission:
                perm = src_auth.permission
                if isinstance(perm, str):
                    permission_map[method] = _resolve_name(perm)
        if permission_map:
            # Determine shared backend (from endpoint auth or defaults)
            backend_name = (
                (meta.authentication and meta.authentication.backend)
                or (defaults.authentication and defaults.authentication.backend)
            )
            from lightapi.config import Authentication
            attrs["authentication"] = Authentication(
                backend=_resolve_name(backend_name) if backend_name else None,
                permission=permission_map,
            )
    else:
        # Simple auth: endpoint overrides defaults
        auth = _make_authentication(meta.authentication, defaults.authentication)
        if auth is not None:
            attrs["authentication"] = auth

    filtering = _make_filtering(meta.filtering)
    if filtering is not None:
        attrs["filtering"] = filtering

    # Pagination: endpoint meta overrides defaults
    pag_cfg = meta.pagination or defaults.pagination
    pagination = _make_pagination(pag_cfg)
    if pagination is not None:
        attrs["pagination"] = pagination

    return type("Meta", (), attrs)


def _resolve_methods_bases(meta: MetaConfig) -> tuple[type, ...]:
    """Return HttpMethod mixin bases from a methods list (ignored for dict form)."""
    from lightapi.rest import RestEndpoint

    if not isinstance(meta.methods, list) or not meta.methods:
        return (RestEndpoint,)

    registry = _build_name_registry()
    bases: list[type] = [RestEndpoint]
    for m in meta.methods:
        mixin = registry.get(m)
        if mixin is None:
            raise ConfigurationError(f"Unknown HTTP method '{m}' in methods list.")
        bases.append(mixin)
    return tuple(bases)


def _build_endpoint_class(entry: EndpointConfig, defaults: DefaultsConfig) -> type:
    """Dynamically build a RestEndpoint subclass from a declarative endpoint entry."""
    from typing import Optional

    from lightapi.fields import Field

    route = entry.effective_route
    # /announcements → AnnouncementsEndpoint, /api/v1/items → ItemsEndpoint
    slug = route.strip("/").split("/")[-1].replace("-", "_")
    class_name = slug.title().replace("_", "") + "Endpoint"

    annotations: dict[str, Any] = {}
    class_attrs: dict[str, Any] = {"__annotations__": annotations}

    for field_name, spec in entry.fields.items():
        py_type = _YAML_TYPE_MAP[spec.type]
        if spec.optional:
            py_type = Optional[py_type]  # type: ignore[assignment]

        # Forward all extra keys (min_length, max_length, gt, default, …) to Field()
        extra = spec.model_extra or {}
        constraint_keys = {
            "min_length", "max_length", "gt", "ge", "lt", "le",
            "pattern", "unique", "index", "foreign_key", "decimal_places", "exclude",
        }
        pydantic_kwargs = {k: v for k, v in extra.items() if k in constraint_keys}
        default = pydantic_kwargs.pop("default", ... if not spec.optional else None)

        annotations[field_name] = py_type
        if pydantic_kwargs or default is not ...:
            if default is not ...:
                pydantic_kwargs["default"] = default
            class_attrs[field_name] = Field(**pydantic_kwargs)
        else:
            class_attrs[field_name] = ...

    # Build Meta inner class
    Meta = _build_meta_class(entry.meta, defaults, reflect=entry.reflect)
    class_attrs["Meta"] = Meta

    # Resolve bases — HttpMethod mixins from methods list
    bases = _resolve_methods_bases(entry.meta)

    # type() call triggers RestEndpointMeta.__new__ automatically
    return type(class_name, bases, class_attrs)


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def load_config(app_cls: type, config_path: str, **overrides: Any) -> Any:
    """Parse a lightapi.yaml file and return a configured LightApi instance.

    Uses the declarative format: database.url + endpoints[].route +
    endpoints[].fields + defaults + middleware.

    Kwargs override YAML-derived values (e.g. engine=..., database_url=...).
    """
    import yaml
    from pydantic import ValidationError

    with open(config_path) as fh:
        raw: dict[str, Any] = yaml.safe_load(fh) or {}

    try:
        cfg = LightAPIConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigurationError(
            f"Invalid lightapi.yaml — {exc.error_count()} error(s):\n{exc}"
        ) from exc

    db_url = cfg.effective_database_url
    middlewares: list[type] = [_resolve_name(name) for name in cfg.middleware]

    constructor_kwargs: dict[str, Any] = {
        "database_url": db_url or None,
        "cors_origins": cfg.cors_origins or None,
        "middlewares": middlewares or None,
    }
    constructor_kwargs.update(overrides)

    instance = app_cls(**constructor_kwargs)

    mapping: dict[str, type] = {}
    for entry in cfg.endpoints:
        route = entry.effective_route
        endpoint_cls = _build_endpoint_class(entry, cfg.defaults)
        mapping[route] = endpoint_cls

    if mapping:
        instance.register(mapping)

    return instance
