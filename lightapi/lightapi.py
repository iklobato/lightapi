"""LightApi — application entry point."""

from __future__ import annotations

import asyncio
import importlib
import logging
import os
import warnings
from typing import Any, Callable

import uvicorn
from sqlalchemy import create_engine
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware as StarletteCORSMiddleware
from starlette.routing import Route

from lightapi._login import LoginEndpoint
from lightapi.authentication import (
    BaseAuthentication,
    BasicAuthentication,
    JWTAuthentication,
)
from lightapi.endpoint_handler import AppContext, EndpointHandler
from lightapi.exceptions import ConfigurationError
from lightapi.health import HEALTH_PATH, HealthCheckEndpoint
from lightapi.rate_limiter import RateLimiter
from lightapi.rest import RestEndpoint
from lightapi.session_manager import SessionManager
from lightapi.yaml_loader import load_config

logger = logging.getLogger(__name__)

# Limits of the login routes when the app sets none.
_LOGIN_RATE_LIMITS = {
    "requests_per_minute": 1000,
    "requests_per_hour": 10000,
    "requests_per_day": 100000,
}


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
            if isinstance(rate_limiter, RateLimiter):
                self._rate_limiter_global = rate_limiter
            elif isinstance(rate_limiter, dict):
                self._rate_limiter_global = RateLimiter(
                    **{
                        limit: rate_limiter.get(limit, default)
                        for limit, default in _LOGIN_RATE_LIMITS.items()
                    }
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

            cls._table_source.map(cls, self._session_manager)

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
            app_context = AppContext(
                self._middlewares, self._mode == "async", self._login_validator
            )
            collection = EndpointHandler.for_collection(cls, app_context)
            detail = EndpointHandler.for_detail(cls, app_context)
            self._routes.append(
                Route(
                    path,
                    endpoint=collection.handle,
                    methods=collection.methods,
                    name=f"{cls.__name__}_collection",
                )
            )
            self._routes.append(
                Route(
                    path.rstrip("/") + "/{id:int}",
                    endpoint=detail.handle,
                    methods=detail.methods,
                    name=f"{cls.__name__}_detail",
                )
            )
            self._endpoint_map[path] = cls

        self._register_login_routes()

    def _register_login_routes(self) -> None:
        """(Re)build /auth/login and /auth/token when an endpoint uses JWT or Basic."""
        backend = self._login_backend()
        if backend is None:
            return

        rate_limiter = self._rate_limiter_global or RateLimiter(**_LOGIN_RATE_LIMITS)
        login = LoginEndpoint(backend, self._login_validator, rate_limiter)
        auth_path = self._auth_path.rstrip("/")
        login_paths = (f"{auth_path}/login", f"{auth_path}/token")

        self._routes = [
            route
            for route in self._routes
            if not (isinstance(route, Route) and route.path in login_paths)
        ]
        for position, path in enumerate(login_paths):
            self._routes.insert(position, Route(path, login.handle, methods=["POST"]))

    def _login_backend(self) -> BaseAuthentication | None:
        """The backend that answers the login routes: a JWT one if any, else Basic."""
        configured = [
            authentication
            for cls in self._endpoint_map.values()
            if (authentication := cls._meta.get("authentication"))
            and authentication.backend
        ]
        for kind in (JWTAuthentication, BasicAuthentication):
            for authentication in configured:
                if issubclass(authentication.backend, kind):
                    return authentication.build_backend(self._login_validator)
        return None

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
