"""LightApi — application entry point."""

from __future__ import annotations

import asyncio
import importlib
import logging
import os
import warnings
from typing import TYPE_CHECKING, Any, Callable

import uvicorn
from sqlalchemy import create_engine
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware as StarletteCORSMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from lightapi.authentication import BasicAuthentication, JWTAuthentication
from lightapi.exceptions import ConfigurationError
from lightapi.health import HEALTH_PATH, HealthCheckEndpoint
from lightapi.rest import RestEndpoint
from lightapi.session_manager import SessionManager
from lightapi.yaml_loader import load_config

if TYPE_CHECKING:
    from lightapi.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class LightApi:
    """Main application class for building REST APIs with LightAPI v2.

    Usage::

        app = LightApi(engine=create_engine("sqlite:///db.sqlite3"))
        app.register({"/books": BookEndpoint})
        app.run()

    Or using a YAML config::

        app = LightApi.from_config("lightapi.yaml")
    """

    def __init__(
        self,
        engine: Any = None,
        database_url: str | None = None,
        mode: str | None = None,  # Auto-detected if not provided
        cors_origins: list[str] | None = None,
        middlewares: list[type] | None = None,
        auth_path: str = "/auth",
        session_manager: SessionManager | None = None,
        rate_limiter: "RateLimiter | dict[str, int] | None" = None,
        login_validator: Callable[[str, str], dict[str, Any] | None] | None = None,
        use_test_isolation: bool = False,
    ) -> None:
        if engine is None and database_url:
            engine = create_engine(database_url)
        elif engine is None:
            url = os.environ.get("LIGHTAPI_DATABASE_URL")
            if url is None:
                raise ConfigurationError(
                    "No database configured. Provide engine=..., database_url=..., or set "
                    "LIGHTAPI_DATABASE_URL environment variable."
                )
            engine = create_engine(url)

        # Store engine first (we'll detect mode later)
        self._engine = engine

        # Use explicit mode if provided, otherwise will be auto-detected in register()
        if mode is not None:
            if mode not in ("sync", "async"):
                raise ConfigurationError(
                    f"mode must be 'sync' or 'async', got '{mode}'"
                )
            self._mode = mode
        else:
            self._mode = "sync"  # Will be auto-detected in register()

        # Create session manager
        self._session_manager = session_manager or SessionManager(
            engine, use_test_isolation=use_test_isolation
        )

        # Store login_validator for backward compatibility
        self._login_validator = login_validator

        # Rate limiter setup
        self._rate_limiter_global: RateLimiter | None = None
        if rate_limiter is not None:
            from lightapi.rate_limiter import RateLimiter as RL

            if isinstance(rate_limiter, RL):
                self._rate_limiter_global = rate_limiter
            elif isinstance(rate_limiter, dict):
                self._rate_limiter_global = RL(
                    requests_per_minute=rate_limiter.get("requests_per_minute", 1000),
                    requests_per_hour=rate_limiter.get("requests_per_hour", 10000),
                    requests_per_day=rate_limiter.get("requests_per_day", 100000),
                )

        self._routes: list[Route] = []
        self._endpoint_map: dict[str, type] = {}
        self._middlewares: list[type] = middlewares or []
        self._cors_origins: list[str] = cors_origins or []
        self._auth_path = auth_path

    # ─────────────────────────────────────────────────────────────────────────
    # Registration
    # ─────────────────────────────────────────────────────────────────────────

    def register(self, mapping: dict[str, type]) -> None:
        """Register endpoint classes against URL patterns.

        Args:
            mapping: ``{"/path": EndpointClass}`` dictionary.
                Each class must be a ``RestEndpoint`` subclass.
        """

        # First pass: detect if any endpoint has async methods to auto-set mode
        for path, cls in mapping.items():
            if not (isinstance(cls, type) and issubclass(cls, RestEndpoint)):
                raise ConfigurationError(
                    f"register() value for '{path}' must be a RestEndpoint subclass, "
                    f"got {cls!r}."
                )

            # Auto-detect mode from async methods
            if self._mode == "sync":
                for method_name in (
                    "queryset",
                    "get",
                    "post",
                    "put",
                    "patch",
                    "delete",
                ):
                    method = getattr(cls, method_name, None)
                    # Check if it's a coroutine function (skip non-callable like SQLAlchemy Select)
                    if (
                        method is not None
                        and callable(method)
                        and asyncio.iscoroutinefunction(method)
                    ):
                        self._mode = "async"
                        break

        # Validate mode if explicitly set
        if self._mode == "async":
            try:
                importlib.import_module("sqlalchemy.ext.asyncio")
                from sqlalchemy.ext.asyncio import AsyncEngine

                if not isinstance(self._engine, AsyncEngine):
                    raise ConfigurationError(
                        f"mode='async' requires AsyncEngine, got {type(self._engine).__name__}"
                    )
            except ImportError:
                raise ConfigurationError(
                    "mode='async' requires async dependencies. "
                    "Install: uv add 'lightapi[async]'"
                )

        for path, cls in mapping.items():
            # Inject session manager into endpoint class
            cls._session_manager = self._session_manager

            # Always map when test isolation is enabled or when not already mapped
            if not getattr(cls, "_reflect_deferred", False):
                from lightapi.session_manager import get_unique_table_name
                from lightapi.table_mapping import map_imperatively

                # Use test isolation table name if available
                meta_obj = getattr(cls, "Meta", None)
                table_name = (
                    getattr(meta_obj, "table", None) or f"{cls.__name__.lower()}s"
                )

                # Always re-map with test-specific metadata when test isolation is enabled
                if self._session_manager._use_test_isolation:
                    # Generate unique table name for test isolation
                    table_name = get_unique_table_name(table_name)
                    logger.debug(
                        "Mapping %s with test isolation table name: %s",
                        cls.__name__,
                        table_name,
                    )

                    # Create a new meta object with the unique table name
                    class TestIsolationMeta:
                        table = table_name
                        reflect = getattr(meta_obj, "reflect", False)

                    map_imperatively(
                        cls,
                        cls.__name__,
                        columns=getattr(cls, "_all_columns", []),
                        meta_obj=TestIsolationMeta,
                        session_manager=self._session_manager,
                    )
                else:
                    # Always map when not using test isolation
                    map_imperatively(
                        cls,
                        cls.__name__,
                        columns=getattr(cls, "_all_columns", []),
                        meta_obj=meta_obj,
                        session_manager=self._session_manager,
                    )

            # Log registration for transparency
            logger.info(f"Registering endpoint {path} -> {cls.__name__}")
            logger.debug(f"  SQLAlchemy metadata: {cls._meta}")

            # Warn if endpoint defines async queryset but engine is sync
            if self._mode == "sync":
                qs = cls.__dict__.get("queryset")
                if qs is None:
                    qs = getattr(cls, "queryset", None)
                if qs is not None and asyncio.iscoroutinefunction(qs):
                    warnings.warn(
                        f"'{cls.__name__}.queryset' is async but engine is sync; "
                        "sync path will be used.",
                        RuntimeWarning,
                        stacklevel=2,
                    )
            # Perform deferred reflection now that an engine is available
            if getattr(cls, "_reflect_deferred", False):
                from lightapi.table_mapping import map_reflected as _map_reflected

                meta_obj = getattr(cls, "Meta", None) or type("Meta", (), {})
                partial = cls._meta.get("reflect") == "partial"
                extra_cols = getattr(cls, "_reflect_partial_columns", [])
                _map_reflected(
                    cls,
                    cls.__name__,
                    meta_obj,
                    partial,
                    extra_cols,
                    session_manager=self._session_manager,
                )
                if getattr(cls, "_schema_deferred", False):
                    from sqlalchemy import inspect as sa_inspect

                    from lightapi.schema import SchemaFactory

                    table = sa_inspect(cls).persist_selectable
                    cls.__schema_create__, cls.__schema_read__ = (
                        SchemaFactory.build_from_reflected_table(cls, table)
                    )
                    cls._schema_deferred = False
                cls._reflect_deferred = False

            allowed = cls._allowed_methods
            from lightapi.handler_factory import (
                make_collection_handler,
                make_detail_handler,
            )

            collection_route = Route(
                path,
                endpoint=make_collection_handler(
                    cls, self._middlewares, self._mode == "async"
                ),
                methods=[m for m in allowed if m in {"GET", "POST"}],
            )
            detail_route = Route(
                path.rstrip("/") + "/{id:int}",
                endpoint=make_detail_handler(
                    cls, self._middlewares, self._mode == "async"
                ),
                methods=[m for m in allowed if m in {"GET", "PUT", "PATCH", "DELETE"}],
            )
            self._routes.append(collection_route)
            self._routes.append(detail_route)
            self._endpoint_map[path] = cls

        # Auto-register /auth/login and /auth/token when JWT or Basic auth is used

        auth_backends: set[type] = set()
        jwt_config_expiration: int | None = None
        jwt_config_extra_claims: list[str] | None = None
        jwt_config_algorithm: str | None = None
        for cls in self._endpoint_map.values():
            auth_cfg = getattr(cls, "_meta", {}).get("authentication")
            if auth_cfg and auth_cfg.backend:
                auth_backends.add(auth_cfg.backend)
                if (
                    auth_cfg.backend is JWTAuthentication
                    and jwt_config_expiration is None
                ):
                    jwt_config_expiration = getattr(auth_cfg, "jwt_expiration", None)
                    jwt_config_extra_claims = getattr(
                        auth_cfg, "jwt_extra_claims", None
                    )
                    jwt_config_algorithm = getattr(auth_cfg, "jwt_algorithm", None)

        # Check if any endpoint has authentication configured
        auth_backends_list = []
        for cls in self._endpoint_map.values():
            auth_cfg = getattr(cls, "_meta", {}).get("authentication")
            if auth_cfg and auth_cfg.backend:
                # Store login_validator in auth_cfg for use by _check_auth
                # Use object.__setattr__ to bypass frozen dataclass restriction
                object.__setattr__(auth_cfg, "_login_validator", self._login_validator)

                # Store backend instance with its config
                backend = auth_cfg.backend
                # Initialize backend with appropriate parameters based on type
                if backend.__name__ == "JWTAuthentication":
                    backend_instance = backend(
                        expiration=getattr(auth_cfg, "jwt_expiration", None),
                        algorithm=getattr(auth_cfg, "jwt_algorithm", None),
                        rate_limiter=getattr(auth_cfg, "rate_limiter", None),
                    )
                elif backend.__name__ == "BasicAuthentication":
                    backend_instance = backend(
                        rate_limiter=getattr(auth_cfg, "rate_limiter", None),
                        login_validator=self._login_validator,
                    )
                else:
                    backend_instance = backend()
                auth_backends_list.append((cls, auth_cfg, backend_instance))

        # Auto-register /auth/login and /auth/token when JWT or Basic auth is used
        has_auth_backends = any(
            isinstance(auth[2], (JWTAuthentication, BasicAuthentication))
            for auth in auth_backends_list
        )

        if has_auth_backends:
            # Use global rate limiter if set, otherwise create default
            rate_limiter = self._rate_limiter_global
            if rate_limiter is None:
                from lightapi.rate_limiter import RateLimiter

                rate_limiter = RateLimiter(
                    requests_per_minute=1000,
                    requests_per_hour=10000,
                    requests_per_day=100000,
                )

            has_jwt = any(
                isinstance(auth[2], JWTAuthentication) for auth in auth_backends_list
            )
            auth_path = self._auth_path.rstrip("/")

            login_path = f"{auth_path}/login"
            token_path = f"{auth_path}/token"

            self._routes = [
                route
                for route in self._routes
                if not (
                    isinstance(route, Route) and route.path in {login_path, token_path}
                )
            ]

            login_endpoint = self._make_login_endpoint(
                has_jwt=has_jwt,
                jwt_expiration=jwt_config_expiration,
                jwt_extra_claims=jwt_config_extra_claims,
                jwt_algorithm=jwt_config_algorithm,
                rate_limiter=rate_limiter,
            )
            self._routes.insert(
                0,
                Route(
                    login_path,
                    login_endpoint,
                    methods=["POST"],
                ),
            )
            self._routes.insert(
                1,
                Route(
                    token_path,
                    login_endpoint,
                    methods=["POST"],
                ),
            )

    def _make_login_endpoint(
        self,
        *,
        has_jwt: bool,
        jwt_expiration: int | None,
        jwt_extra_claims: list[str] | None,
        jwt_algorithm: str | None,
        rate_limiter: "RateLimiter",
    ) -> Any:
        """Create the login/token handler with captured config."""
        from lightapi._login import login_handler
        from lightapi.authentication import JWTAuthentication

        # Create auth backend that wraps login_validator for validate_credentials
        auth_backend = JWTAuthentication()

        # Override validate_credentials to use login_validator if provided
        original_validate = auth_backend.validate_credentials

        def wrapped_validate(username: str, password: str) -> dict[str, Any] | None:
            # Try login_validator first if provided
            if self._login_validator is not None:
                return self._login_validator(username, password)
            # Otherwise try the original method
            return original_validate(username, password)

        auth_backend.validate_credentials = wrapped_validate

        async def handler(request: Request) -> Response:
            return await login_handler(
                request,
                has_jwt=has_jwt,
                jwt_expiration=jwt_expiration,
                jwt_extra_claims=jwt_extra_claims,
                jwt_algorithm=jwt_algorithm,
                rate_limiter=rate_limiter,
                auth_backend=auth_backend,
            )

        return handler

    # ─────────────────────────────────────────────────────────────────────────
    # Run
    # ─────────────────────────────────────────────────────────────────────────

    def run(
        self,
        host: str = "0.0.0.0",
        port: int = 8000,
        debug: bool = False,
        reload: bool = False,
    ) -> None:
        """Create tables, build the Starlette ASGI app and start uvicorn."""
        if self._mode == "async":
            _validate_async_dependencies(self._engine)
        self._create_tables()
        self._check_cache_connections()

        on_startup = [self._create_tables] if self._mode == "async" else []
        app = Starlette(debug=debug, routes=self._asgi_routes(), on_startup=on_startup)

        if self._cors_origins:
            app.add_middleware(
                StarletteCORSMiddleware,
                allow_origins=self._cors_origins,
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )

        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="debug" if debug else "info",
            reload=reload,
        )

    def build_app(self) -> Starlette:
        """Build and return the Starlette ASGI app without starting the server.

        Useful for testing with ``httpx.AsyncClient`` or ``starlette.testclient.TestClient``.
        For async engines, table creation is deferred to the Starlette on_startup handler
        so it runs inside the correct event loop (not a throwaway thread loop).
        """
        self._create_tables()
        self._check_cache_connections()
        on_startup = [self._create_tables] if self._mode == "async" else []
        app = Starlette(routes=self._asgi_routes(), on_startup=on_startup)
        if self._cors_origins:
            app.add_middleware(
                StarletteCORSMiddleware,
                allow_origins=self._cors_origins,
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )
        return app

    def _asgi_routes(self) -> list[Route]:
        """Registered endpoint routes plus the always-on ``/healthz`` probe."""
        return [
            *self._routes,
            Route(HEALTH_PATH, HealthCheckEndpoint),
        ]

    # ─────────────────────────────────────────────────────────────────────────
    # YAML factory
    # ─────────────────────────────────────────────────────────────────────────

    @classmethod
    def from_config(cls, config_path: str, **kwargs: Any) -> "LightApi":
        """Create a LightApi instance from a ``lightapi.yaml`` file.

        Uses the declarative format: ``database.url``, ``endpoints[].route``,
        inline ``fields``, ``defaults``, ``middleware``. Parsing and validation
        is handled by :mod:`lightapi.yaml_loader` using Pydantic v2 models.

        Kwargs override YAML values (e.g. engine=..., database_url=...).
        """

        return load_config(cls, config_path, **kwargs)

    @classmethod
    def from_dict(cls, config: dict[str, Any], **kwargs: Any) -> "LightApi":
        """Create a LightApi instance from a Python dictionary.

        Simpler alternative to YAML config for programmatic setup.

        Example::

            config = {
                "database_url": "sqlite:///db.sqlite3",
                "endpoints": {
                    "/books": {
                        "fields": {"title": str, "author": str},
                        "auth": "jwt",
                    },
                    "/authors": {
                        "fields": {"name": str},
                    },
                },
                "cors": ["https://myapp.com"],
            }
            app = LightApi.from_dict(config)
        """
        from lightapi._dict_config_loader import load_from_dict

        return load_from_dict(cls, config, **kwargs)

    # ─────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _create_tables(self) -> None:
        """Create/verify database tables for all registered endpoints."""
        metadata = self._session_manager.metadata
        logger.debug("_create_tables called with metadata: %s", metadata)
        logger.debug("Available tables in metadata: %s", list(metadata.tables.keys()))
        try:
            if self._mode == "async":
                # For async engines, table creation must run inside the same event loop
                # that will serve requests (uvicorn's loop), so we defer it to on_startup
                # unless we are already inside a running loop (pytest-asyncio).
                try:
                    asyncio.get_running_loop()

                    # Inside a running loop — create tables directly here (test context).
                    async def _create_inside_loop() -> None:
                        async with self._engine.begin() as conn:
                            await conn.run_sync(metadata.create_all)

                    import concurrent.futures

                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                        pool.submit(asyncio.run, _create_inside_loop()).result()
                except RuntimeError:
                    # No running loop; registration is deferred to the on_startup handler
                    # that build_app() adds. Nothing to do here.
                    pass
            else:
                engine = self._engine
                metadata.create_all(bind=engine)
                logger.info("Tables created/verified against %s", engine.url)
        except Exception as exc:
            logger.warning("Table creation warning: %s", exc)

    def _check_cache_connections(self) -> None:
        """Emit RuntimeWarning if any endpoint has cache configured but Redis is unreachable."""
        import warnings

        for cls in self._endpoint_map.values():
            cache_cfg = getattr(cls, "_meta", {}).get("cache")
            if cache_cfg:
                from lightapi.cache import _ping_redis

                if not _ping_redis():
                    warnings.warn(
                        "Redis is configured for caching but is not reachable at startup. "
                        "Cache will be skipped for all requests.",
                        RuntimeWarning,
                        stacklevel=3,
                    )
                break


def _validate_async_dependencies(engine: Any) -> None:
    """Raise ConfigurationError if async SQLAlchemy extras or dialect driver are missing."""
    try:
        importlib.import_module("sqlalchemy.ext.asyncio")
    except ImportError:
        raise ConfigurationError(
            "AsyncEngine supplied but 'sqlalchemy[asyncio]' is not installed. "
            "Install with: uv add 'sqlalchemy[asyncio]'"
        )
    dialect = engine.url.get_dialect().name
    driver_map = {"postgresql": "asyncpg", "sqlite": "aiosqlite", "mysql": "aiomysql"}
    driver = driver_map.get(dialect)
    if driver:
        try:
            importlib.import_module(driver)
        except ImportError:
            raise ConfigurationError(
                f"Async driver for '{dialect}' is not installed. "
                f"Install with: uv add {driver}"
            )
