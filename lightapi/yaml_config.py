"""Declarative YAML configuration: the document's models and how they become an app.

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
import inspect
import os
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    ValidationError,
    field_validator,
    model_validator,
)

from lightapi.authentication import (
    AllowAny,
    BasePermission,
    BasicAuthentication,
    IsAdminUser,
    IsAuthenticated,
    JWTAuthentication,
)
from lightapi.config import Authentication, Cache, Filtering, Pagination, Serializer
from lightapi.constants import DEFAULT_CACHE_TTL, DEFAULT_PAGE_SIZE, HTTP_METHOD_MIXINS
from lightapi.core import AuthenticationMiddleware, CORSMiddleware, Middleware
from lightapi.exceptions import ConfigurationError
from lightapi.fields import Field
from lightapi.filters import FieldFilter, OrderingFilter, SearchFilter
from lightapi.pagination import PaginationStyle
from lightapi.rest import RestEndpoint

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

    from lightapi.lightapi import LightApi

YAML_FIELD_TYPES: Final[dict[str, type]] = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "datetime": datetime.datetime,
    "Decimal": Decimal,
    "decimal": Decimal,
}

# Built-ins a YAML document may name without a dotted path.
NAME_REGISTRY: Final[dict[str, type]] = {
    "JWTAuthentication": JWTAuthentication,
    "BasicAuthentication": BasicAuthentication,
    "AllowAny": AllowAny,
    "IsAuthenticated": IsAuthenticated,
    "IsAdminUser": IsAdminUser,
    "FieldFilter": FieldFilter,
    "SearchFilter": SearchFilter,
    "OrderingFilter": OrderingFilter,
    "Middleware": Middleware,
    "CORSMiddleware": CORSMiddleware,
    "AuthenticationMiddleware": AuthenticationMiddleware,
    **HTTP_METHOD_MIXINS,
}

# Keys of a field spec that are forwarded to Field() as they are.
FIELD_CONSTRAINT_KEYS: Final = frozenset(
    {
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
)


class _Document(BaseModel):
    """A block of the YAML document: a key the format does not know is an error.

    The docs promise that a typo fails at load time; pydantic's default would
    drop it and serve an app without the feature the user thought they configured.
    """

    model_config = ConfigDict(extra="forbid")


class DatabaseConfig(_Document):
    """Nested database block: database: { url: ... }"""

    url: str

    @field_validator("url", mode="before")
    @classmethod
    def substitute_env(cls, value: str) -> str:
        """Replace ${VAR} with the environment variable value."""
        if value.startswith("${") and value.endswith("}"):
            var = value[2:-1]
            resolved = os.environ.get(var)
            if not resolved:
                raise ConfigurationError(
                    f"Environment variable '{var}' is not set "
                    "(required by lightapi.yaml)."
                )
            return resolved
        return value


class AuthLoginConfig(_Document):
    """Login/auth block: auth: { auth_path: ..., login_validator: ... }.

    When using JWTAuthentication or BasicAuthentication, login_validator is required.
    It can be specified as a dotted path (e.g. myapp.validators.validate_login)
    or passed as an override to from_config(login_validator=...).
    """

    auth_path: str = "/auth"
    login_validator: str | None = None


class AuthConfig(_Document):
    """Authentication block used in defaults and per-endpoint meta."""

    backend: str | None = None
    permission: str | dict[str, str] | None = None
    jwt_expiration: int | None = None
    jwt_extra_claims: list[str] | None = None
    jwt_algorithm: str | None = None

    def merged_over(self, defaults: AuthConfig | None) -> AuthConfig:
        """These settings, with every one left unset taken from ``defaults``."""
        if defaults is None:
            return self
        return defaults.model_copy(update=self.model_dump(exclude_none=True))

    def resolved_permission(
        self,
    ) -> type[BasePermission] | dict[str, type[BasePermission]] | None:
        """The permission class, or {method: class} for a per-method dict."""
        if isinstance(self.permission, dict):
            return {
                method: LightAPIConfig.resolve_name(name)
                for method, name in self.permission.items()
            }
        if isinstance(self.permission, str):
            permission: type[BasePermission] = LightAPIConfig.resolve_name(
                self.permission
            )
            return permission
        return None

    def to_authentication(
        self, permission: type[BasePermission] | dict[str, type[BasePermission]] | None
    ) -> Authentication:
        return Authentication(
            backend=LightAPIConfig.resolve_name(self.backend) if self.backend else None,
            permission=permission,
            jwt_expiration=self.jwt_expiration,
            jwt_extra_claims=self.jwt_extra_claims,
            jwt_algorithm=self.jwt_algorithm,
        )


class FilteringConfig(_Document):
    """Filtering block inside meta."""

    backends: list[str] = []
    fields: list[str] = []
    search: list[str] = []
    ordering: list[str] = []

    def to_filtering(self) -> Filtering:
        """Named backends, or the ones the populated lists call for."""
        backends: list[type] = [LightAPIConfig.resolve_name(b) for b in self.backends]
        if not backends:
            if self.fields:
                backends.append(FieldFilter)
            if self.search:
                backends.append(SearchFilter)
            if self.ordering:
                backends.append(OrderingFilter)

        return Filtering(
            backends=backends or None,
            fields=self.fields or None,
            search=self.search or None,
            ordering=self.ordering or None,
        )


class PaginationConfig(_Document):
    """Pagination block used in defaults and per-endpoint meta."""

    style: str = PaginationStyle.PAGE_NUMBER.value
    page_size: int = DEFAULT_PAGE_SIZE

    def to_pagination(self) -> Pagination:
        return Pagination(style=self.style, page_size=self.page_size)


class DefaultsConfig(_Document):
    """Global defaults applied to all endpoints unless overridden."""

    authentication: AuthConfig | None = None
    pagination: PaginationConfig | None = None


class MethodAuthConfig(_Document):
    """Per-method authentication override inside meta.methods dict."""

    authentication: AuthConfig | None = None


class CacheConfig(_Document):
    """Cache block inside meta: cache: { ttl: 60 }"""

    ttl: int = DEFAULT_CACHE_TTL


class SerializerConfig(_Document):
    """Serializer block inside meta.

    Use ``fields`` for a unified list, or ``read``/``write`` for per-verb lists.
    """

    fields: list[str] | None = None
    read: list[str] | None = None
    write: list[str] | None = None


class MetaConfig(_Document):
    """meta: block inside a declarative endpoint entry."""

    # methods can be a list ["GET", "POST"] or a dict {GET: {...}, DELETE: {...}}
    methods: list[str] | dict[str, MethodAuthConfig | None] = []
    authentication: AuthConfig | None = None
    filtering: FilteringConfig | None = None
    pagination: PaginationConfig | None = None
    cache: CacheConfig | None = None
    serializer: SerializerConfig | None = None
    table: str | None = None  # custom table name (required when reflect: true)

    def build_meta_class(self, defaults: DefaultsConfig, *, reflect: bool) -> type:
        """The ``Meta`` inner class of the endpoint this block describes."""
        attrs: dict[str, Any] = {}

        if reflect:
            attrs["reflect"] = True
            if self.table:
                attrs["table"] = self.table
            return type("Meta", (), attrs)

        if isinstance(self.methods, dict):
            auth = self._per_method_authentication(self.methods, defaults)
        else:
            auth = self._endpoint_authentication(defaults)
        if auth is not None:
            attrs["authentication"] = auth

        if self.filtering is not None:
            attrs["filtering"] = self.filtering.to_filtering()

        # Pagination: endpoint meta overrides defaults
        pagination = self.pagination or defaults.pagination
        if pagination is not None:
            attrs["pagination"] = pagination.to_pagination()

        if self.cache is not None:
            attrs["cache"] = Cache(ttl=self.cache.ttl)

        if self.serializer is not None:
            attrs["serializer"] = Serializer(
                fields=self.serializer.fields,
                read=self.serializer.read,
                write=self.serializer.write,
            )

        if self.table:
            attrs["table"] = self.table

        return type("Meta", (), attrs)

    def endpoint_bases(self) -> tuple[type, ...]:
        """RestEndpoint plus the HttpMethod mixins named by ``methods``."""
        method_names = (
            list(self.methods.keys())
            if isinstance(self.methods, dict)
            else self.methods
        )
        bases: list[type] = [RestEndpoint]
        for name in method_names:
            mixin = HTTP_METHOD_MIXINS.get(name)
            if mixin is None:
                raise ConfigurationError(
                    f"Unknown HTTP method '{name}' in methods list."
                )
            bases.append(mixin)
        return tuple(bases)

    def _endpoint_authentication(
        self, defaults: DefaultsConfig
    ) -> Authentication | None:
        """Endpoint settings win; the defaults fill whatever the endpoint left unset."""
        settings = (self.authentication or AuthConfig()).merged_over(
            defaults.authentication
        )
        if settings.backend is None and settings.permission is None:
            return None
        return settings.to_authentication(settings.resolved_permission())

    def _per_method_authentication(
        self, methods: dict[str, MethodAuthConfig | None], defaults: DefaultsConfig
    ) -> Authentication | None:
        """Authentication for ``methods: {GET: {...}, DELETE: {...}}``.

        Each method takes its own permission, else the endpoint's, else the default.
        """
        default_auth = defaults.authentication
        default_permission = default_auth.permission if default_auth else None

        permissions: dict[str, type] = {}
        for method, method_cfg in methods.items():
            method_auth = (method_cfg.authentication if method_cfg else None) or (
                self.authentication
            )
            name = self._permission_name(method, method_auth, default_permission)
            if name:
                permissions[method] = LightAPIConfig.resolve_name(name)

        if not permissions:
            return None
        settings = (self.authentication or AuthConfig()).merged_over(default_auth)
        return settings.to_authentication(permissions)

    @staticmethod
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

    @model_validator(mode="after")
    def extra_keys_must_be_constraints(self) -> FieldSpec:
        """A key that is not a constraint (`min_lenght`) would be dropped silently."""
        unknown = sorted(
            set(self.model_extra or ()) - FIELD_CONSTRAINT_KEYS - {"default"}
        )
        if unknown:
            raise ValueError(
                f"Unknown field option(s) {unknown}. "
                f"Valid: {sorted(FIELD_CONSTRAINT_KEYS | {'default'})}"
            )
        return self

    @property
    def annotation(self) -> object:
        """The field's type, or ``type | None`` for an optional one."""
        py_type = YAML_FIELD_TYPES[self.type]
        return py_type | None if self.optional else py_type

    def field_info(self) -> FieldInfo | None:
        """The Field() for this spec; None for a constraint-less, default-less field.

        Such a field stays annotation-only on purpose: an Ellipsis placeholder
        would survive the FieldInfo stripping and stop SQLAlchemy from mapping the
        column, so its value would silently never be inserted.
        """
        extra = self.model_extra or {}
        kwargs = {k: v for k, v in extra.items() if k in FIELD_CONSTRAINT_KEYS}
        if "default" in extra:
            kwargs["default"] = extra["default"]
        elif self.optional:
            kwargs["default"] = None
        return Field(**kwargs) if kwargs else None


class EndpointConfig(_Document):
    """A single endpoint entry."""

    route: str
    fields: dict[str, FieldSpec] = {}
    reflect: bool = False
    meta: MetaConfig = MetaConfig()

    @model_validator(mode="after")
    def require_route(self) -> EndpointConfig:
        if not self.route:
            raise ValueError("Each endpoint must have a 'route'.")
        return self

    @property
    def effective_route(self) -> str:
        return self.route.strip()

    @property
    def class_name(self) -> str:
        """/announcements -> AnnouncementsEndpoint, /api/v1/items -> ItemsEndpoint."""
        slug = self.effective_route.strip("/").split("/")[-1].replace("-", "_")
        return slug.title().replace("_", "") + "Endpoint"

    def build_endpoint_class(self, defaults: DefaultsConfig) -> type:
        """The RestEndpoint subclass this entry declares."""
        annotations: dict[str, Any] = {}
        class_attrs: dict[str, Any] = {"__annotations__": annotations}
        for field_name, spec in self.fields.items():
            annotations[field_name] = spec.annotation
            field_info = spec.field_info()
            if field_info is not None:
                class_attrs[field_name] = field_info

        class_attrs["Meta"] = self.meta.build_meta_class(defaults, reflect=self.reflect)
        # type() runs RestEndpointMeta.__new__, which maps fields and Meta.
        return type(self.class_name, self.meta.endpoint_bases(), class_attrs)


class LightAPIConfig(_Document):
    """Root YAML document schema."""

    database: DatabaseConfig | None = None
    cors_origins: list[str] = []
    defaults: DefaultsConfig = DefaultsConfig()
    endpoints: list[EndpointConfig] = []
    middleware: list[str] = []
    auth: AuthLoginConfig | None = None
    mode: str | None = None  # "sync" or "async"; auto-detected when omitted

    @property
    def effective_database_url(self) -> str | None:
        return self.database.url if self.database else None

    @classmethod
    def from_file(cls, config_path: str) -> LightAPIConfig:
        """The validated document at ``config_path``."""
        with Path(config_path).open() as fh:
            raw: dict[str, Any] = yaml.safe_load(fh) or {}
        try:
            return cls.model_validate(raw)
        except ValidationError as exc:
            # Location and message only: pydantic's own text prints the input,
            # and under a typo like `databse:` that input is the database URL.
            problems = "\n".join(
                f"  {'.'.join(str(part) for part in error['loc']) or '<root>'}: "
                f"{error['msg']}"
                for error in exc.errors(include_input=False, include_url=False)
            )
            raise ConfigurationError(
                f"Invalid lightapi.yaml — {exc.error_count()} error(s):\n{problems}"
            ) from exc

    def build_app(
        self,
        app_cls: type[LightApi],
        **overrides: Any,  # noqa: ANN401  LightApi constructor kwargs, forwarded
    ) -> LightApi:
        """A configured ``app_cls`` instance with every endpoint registered.

        Kwargs override YAML-derived values (e.g. engine=..., database_url=...).
        """
        middlewares = [self.resolve_name(name) for name in self.middleware]
        constructor_kwargs: dict[str, Any] = {
            "database_url": self.effective_database_url or None,
            "cors_origins": self.cors_origins or None,
            "middlewares": middlewares or None,
        }
        if self.mode is not None:
            constructor_kwargs["mode"] = self.mode
        if self.auth:
            constructor_kwargs["auth_path"] = self.auth.auth_path
            if self.auth.login_validator:
                constructor_kwargs["login_validator"] = self.resolve_callable(
                    self.auth.login_validator
                )
        constructor_kwargs.update(overrides)

        instance = app_cls(**constructor_kwargs)
        mapping = {
            entry.effective_route: entry.build_endpoint_class(self.defaults)
            for entry in self.endpoints
        }
        if mapping:
            instance.register(mapping)
        return instance

    @staticmethod
    def resolve_name(
        name: str,
    ) -> Any:  # noqa: ANN401  whatever class the dotted path names
        """The class a document names: a built-in by short name, else a dotted path."""
        if name in NAME_REGISTRY:
            return NAME_REGISTRY[name]
        if "." in name:
            module_path, class_name = name.rsplit(".", 1)
            try:
                mod = importlib.import_module(module_path)
                return getattr(mod, class_name)
            except (ImportError, AttributeError) as exc:
                raise ConfigurationError(f"Cannot resolve '{name}': {exc}") from exc
        raise ConfigurationError(
            f"Unknown class name '{name}'. "
            "Use a fully dotted import path for custom classes."
        )

    @staticmethod
    def resolve_callable(dotted_path: str) -> Callable[..., Any]:
        """The login validator at a dotted path: sync, takes (username, password)."""
        if "." not in dotted_path:
            raise ConfigurationError(
                f"login_validator must be a dotted path (e.g. myapp.validators.check), "
                f"got '{dotted_path}'"
            )
        module_path, attr_name = dotted_path.rsplit(".", 1)
        try:
            mod = importlib.import_module(module_path)
            fn = getattr(mod, attr_name)
        except (ImportError, AttributeError) as exc:
            raise ConfigurationError(
                f"Cannot resolve login_validator '{dotted_path}': {exc}"
            ) from exc
        if not callable(fn):
            raise ConfigurationError(
                f"login_validator '{dotted_path}' is not callable."
            )

        if inspect.iscoroutinefunction(fn):
            raise ConfigurationError(
                f"login_validator '{dotted_path}' is async, "
                "but sync function required. "
                "Login validation must be a synchronous function."
            )
        validator: Callable[..., Any] = fn

        try:
            sig = inspect.signature(fn)
        except ValueError:
            # Some callables (e.g., builtins) don't have inspectable signatures
            return validator

        required_params = sum(
            1
            for param in sig.parameters.values()
            if param.kind
            in (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
            )
            and param.default is inspect.Parameter.empty
        )
        if required_params != 2:
            raise ConfigurationError(
                f"login_validator '{dotted_path}' must accept exactly 2 required "
                f"positional parameters (username, password), got {required_params}"
            )
        return validator
