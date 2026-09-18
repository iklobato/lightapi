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

from typing import Any

from lightapi.exceptions import ConfigurationError
from lightapi.yaml_names import name_registry, resolve_callable, resolve_name
from lightapi.yaml_schema import (
    YAML_FIELD_TYPES,
    AuthConfig,
    DefaultsConfig,
    EndpointConfig,
    FilteringConfig,
    LightAPIConfig,
    MetaConfig,
    PaginationConfig,
)


def _make_authentication(
    auth_cfg: AuthConfig | None,
    defaults_auth: AuthConfig | None,
) -> Any:
    """Endpoint settings win; the defaults fill whatever the endpoint left unset."""
    settings = (auth_cfg or AuthConfig()).merged_over(defaults_auth)
    if settings.backend is None and settings.permission is None:
        return None
    return _authentication_from(settings, _resolved_permission(settings.permission))


def _per_method_authentication(meta: MetaConfig, defaults: DefaultsConfig) -> Any:
    """Authentication for ``methods: {GET: {...}, DELETE: {...}}``.

    Each method takes its own permission, else the endpoint's, else the default.
    """
    default_auth = defaults.authentication
    default_permission = default_auth.permission if default_auth else None

    permissions: dict[str, type] = {}
    for method, method_cfg in meta.methods.items():
        method_auth = (method_cfg.authentication if method_cfg else None) or (
            meta.authentication
        )
        name = _permission_name(method, method_auth, default_permission)
        if name:
            permissions[method] = resolve_name(name)

    if not permissions:
        return None
    settings = (meta.authentication or AuthConfig()).merged_over(default_auth)
    return _authentication_from(settings, permissions)


def _permission_name(
    method: str,
    method_auth: AuthConfig | None,
    default_permission: str | dict[str, str] | None,
) -> str | None:
    own = method_auth.permission if method_auth else None
    if isinstance(own, str):
        return own
    if isinstance(default_permission, dict):
        return default_permission.get(method)
    return default_permission


def _resolved_permission(permission: str | dict[str, str] | None) -> Any:
    if isinstance(permission, dict):
        # Per-method permission dict: {GET: IsAuthenticated, DELETE: IsAdminUser}
        return {method: resolve_name(name) for method, name in permission.items()}
    if isinstance(permission, str):
        return resolve_name(permission)
    return None


def _authentication_from(settings: AuthConfig, permission: Any) -> Any:
    from lightapi.config import Authentication

    return Authentication(
        backend=resolve_name(settings.backend) if settings.backend else None,
        permission=permission,
        jwt_expiration=settings.jwt_expiration,
        jwt_extra_claims=settings.jwt_extra_claims,
        jwt_algorithm=settings.jwt_algorithm,
    )


def _make_filtering(filtering_cfg: FilteringConfig | None) -> Any:
    """Build a Filtering instance from a FilteringConfig."""
    if filtering_cfg is None:
        return None
    from lightapi.config import Filtering
    from lightapi.filters import FieldFilter, OrderingFilter, SearchFilter

    # Auto-select backends based on which lists are populated
    backends: list[type] = list(
        [resolve_name(b) for b in filtering_cfg.backends]
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
        if meta.table:
            attrs["table"] = meta.table
        return type("Meta", (), attrs)

    if isinstance(meta.methods, dict):
        auth = _per_method_authentication(meta, defaults)
    else:
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

    # Cache
    if meta.cache is not None:
        from lightapi.config import Cache

        attrs["cache"] = Cache(ttl=meta.cache.ttl)

    # Serializer
    if meta.serializer is not None:
        from lightapi.config import Serializer

        ser_cfg = meta.serializer
        attrs["serializer"] = Serializer(
            fields=ser_cfg.fields,
            read=ser_cfg.read,
            write=ser_cfg.write,
        )

    if meta.table:
        attrs["table"] = meta.table

    return type("Meta", (), attrs)


def _resolve_methods_bases(meta: MetaConfig) -> tuple[type, ...]:
    """Return HttpMethod mixin bases for both list and dict forms of ``methods``."""
    from lightapi.rest import RestEndpoint

    if isinstance(meta.methods, dict):
        # Dict form: {GET: {auth: ...}, POST: {auth: ...}} — keys are the allowed verbs.
        method_list = list(meta.methods.keys())
    elif isinstance(meta.methods, list):
        method_list = meta.methods
    else:
        return (RestEndpoint,)

    if not method_list:
        return (RestEndpoint,)

    registry = name_registry()
    bases: list[type] = [RestEndpoint]
    for m in method_list:
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
        py_type = YAML_FIELD_TYPES[spec.type]
        if spec.optional:
            py_type = Optional[py_type]  # type: ignore[assignment]

        # Forward all extra keys (min_length, max_length, gt, default, …) to Field()
        extra = spec.model_extra or {}
        constraint_keys = {
            "min_length",
            "max_length",
            "gt",
            "ge",
            "lt",
            "le",
            "pattern",
            "unique",
            "index",
            "foreign_key",
            "decimal_places",
            "exclude",
        }
        pydantic_kwargs = {k: v for k, v in extra.items() if k in constraint_keys}
        # Extract 'default' from the raw extra dict, not from pydantic_kwargs.
        # 'default' is not in constraint_keys, so filtering would silently drop it.
        _UNSET = object()
        raw_default = extra.get("default", _UNSET)
        if raw_default is not _UNSET:
            default = raw_default
        elif spec.optional:
            default = None
        else:
            default = ...  # sentinel: no default provided

        annotations[field_name] = py_type
        if pydantic_kwargs or default is not ...:
            if default is not ...:
                pydantic_kwargs["default"] = default
            class_attrs[field_name] = Field(**pydantic_kwargs)
        # A constraint-less, default-less field is annotation-only. Do NOT set a
        # class attribute: an Ellipsis placeholder would survive _strip_field_infos
        # (which only removes FieldInfo) and stop SQLAlchemy from mapping the
        # column, so the value would silently never be inserted.

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
    middlewares: list[type] = [resolve_name(name) for name in cfg.middleware]

    constructor_kwargs: dict[str, Any] = {
        "database_url": db_url or None,
        "cors_origins": cfg.cors_origins or None,
        "middlewares": middlewares or None,
    }

    if cfg.mode is not None:
        constructor_kwargs["mode"] = cfg.mode

    # Auth/login config from YAML auth: block
    if cfg.auth:
        constructor_kwargs["auth_path"] = cfg.auth.auth_path
        if cfg.auth.login_validator:
            constructor_kwargs["login_validator"] = resolve_callable(
                cfg.auth.login_validator
            )

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
