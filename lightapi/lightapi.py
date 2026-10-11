"""LightApi — application entry point."""

from __future__ import annotations

import asyncio
import concurrent.futures
import contextlib
import importlib
import logging
import os
import warnings
from collections.abc import AsyncIterator, Callable
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, Final

import uvicorn
from sqlalchemy import Engine, MetaData, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError
from starlette.applications import Starlette
from starlette.exceptions import HTTPException
from starlette.middleware.cors import CORSMiddleware as StarletteCORSMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from lightapi._dict_config_loader import DictConfig
from lightapi._login import LoginEndpoint
from lightapi.authentication import (
    BaseAuthentication,
    BasicAuthentication,
    JWTAuthentication,
)
from lightapi.cache import RedisCacheBackend
from lightapi.constants import CRUD_VERBS, ExecutionMode, HttpVerb
from lightapi.endpoint_handler import AppContext, EndpointHandler, MiddlewareChain
from lightapi.exceptions import ConfigurationError
from lightapi.health import HEALTH_PATH, HealthCheckEndpoint
from lightapi.rate_limiter import RateLimiter
from lightapi.rest import RestEndpoint
from lightapi.session_manager import SessionManager
from lightapi.yaml_config import LightAPIConfig

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

    from lightapi.config import Authentication
    from lightapi.core import Middleware

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

    # Limits of the login routes when the app sets none.
    _LOGIN_RATE_LIMITS: Final[dict[str, int]] = {
        "requests_per_minute": 1000,
        "requests_per_hour": 10000,
        "requests_per_day": 100000,
    }
    # An `async def` of any of these on an endpoint switches the app to async mode.
    _ASYNC_HANDLER_NAMES: Final = (
        "queryset",
        *(verb.value.lower() for verb in CRUD_VERBS),
    )

    def __init__(
        self,
        engine: Engine | AsyncEngine | None = None,
        database_url: str | None = None,
        mode: str | None = None,  # Auto-detected if not provided
        cors_origins: list[str] | None = None,
        middlewares: list[type[Middleware]] | None = None,
        auth_path: str = "/auth",
        session_manager: SessionManager | None = None,
        rate_limiter: RateLimiter | dict[str, int] | None = None,
        login_validator: Callable[[str, str], dict[str, Any] | None] | None = None,
        use_test_isolation: bool = False,
    ) -> None:
        self._mode = ExecutionMode.from_user(mode)
        # Sync or async is a runtime fact (ExecutionMode), so the attribute is loose.
        self._engine: Any = (
            engine
            if engine is not None
            else self._engine_from_url(database_url, self._mode)
        )
        if self._engine_is_async(self._engine):
            # The README promises the mode is detected when omitted: an AsyncEngine,
            # or an async driver in the URL (sqlite+aiosqlite, postgresql+asyncpg).
            if mode is not None and self._mode is ExecutionMode.SYNC:
                raise ConfigurationError(
                    "mode='sync' with an async engine or driver: drop mode, or use "
                    "a sync engine."
                )
            self._mode = ExecutionMode.ASYNC
        self._session_manager = session_manager or SessionManager(
            self._engine, use_test_isolation=use_test_isolation
        )
        self._login_validator = login_validator
        self._rate_limiter_global = self._as_rate_limiter(rate_limiter)

        self._routes: list[Route] = []
        self._endpoint_map: dict[str, type[RestEndpoint]] = {}
        self._middlewares: list[type[Middleware]] = middlewares or []
        self._cors_origins: list[str] = cors_origins or []
        self._auth_path = auth_path

    # ─────────────────────────────────────────────────────────────────────────
    # Registration
    # ─────────────────────────────────────────────────────────────────────────

    def register(self, mapping: dict[str, type[RestEndpoint]]) -> None:
        """Register endpoint classes against URL patterns.

        Args:
            mapping: ``{"/path": EndpointClass}`` dictionary.
                Each class must be a ``RestEndpoint`` subclass.
        """
        for path, cls in mapping.items():
            self._require_rest_endpoint(path, cls)
            self._require_sync_basic_validator(path, cls)

        # An `async def` verb or queryset on any endpoint switches the app to async.
        if self._mode is ExecutionMode.SYNC and any(
            map(self._has_async_handlers, mapping.values())
        ):
            self._mode = ExecutionMode.ASYNC
        if self._mode is ExecutionMode.ASYNC:
            self._require_async_engine(self._engine)

        app_context = AppContext(
            MiddlewareChain(self._middlewares), self._mode, self._login_validator
        )
        for path, cls in mapping.items():
            self._register_endpoint(path, cls, app_context)

    def _register_endpoint(
        self, path: str, cls: type[RestEndpoint], app_context: AppContext
    ) -> None:
        cls._session_manager = self._session_manager
        cls._table_source.map(cls, self._session_manager)
        logger.info("Registering endpoint %s -> %s", path, cls.__name__)
        logger.debug("  SQLAlchemy metadata: %s", cls._meta)

        collection = EndpointHandler.for_collection(cls, app_context)
        detail = EndpointHandler.for_detail(cls, app_context)
        # Only the allowed verbs, so Starlette keeps routing by method (two classes
        # may share a path) and a disallowed verb never reaches the guard or the
        # middlewares: its JSON 405 comes from the app's handler in build_app().
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

    def _login_routes(self) -> list[Route]:
        """/auth/login and /auth/token, when an endpoint uses JWT or Basic auth."""
        backend = self._login_backend()
        if backend is None:
            return []

        rate_limiter = self._rate_limiter_global or RateLimiter(
            **self._LOGIN_RATE_LIMITS
        )
        login = LoginEndpoint(backend, self._login_validator, rate_limiter)
        auth_path = self._auth_path.rstrip("/")
        return [
            Route(f"{auth_path}/{name}", login.handle, methods=[HttpVerb.POST.value])
            for name in ("login", "token")
        ]

    def _login_backend(self) -> BaseAuthentication | None:
        """The backend that answers the login routes: a JWT one if any, else Basic."""
        configured: list[Authentication] = [
            authentication
            for cls in self._endpoint_map.values()
            if (authentication := cls._meta.get("authentication"))
            and authentication.backend
        ]
        for kind in (JWTAuthentication, BasicAuthentication):
            for authentication in configured:
                backend = authentication.backend
                if backend is not None and issubclass(backend, kind):
                    return authentication.build_backend(self._login_validator)
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # Run
    # ─────────────────────────────────────────────────────────────────────────

    def run(
        self,
        host: str = "0.0.0.0",  # noqa: S104  the documented default; pass host= to narrow it
        port: int = 8000,
        debug: bool = False,
        reload: bool = False,
    ) -> None:
        """Create tables, build the Starlette ASGI app and start uvicorn."""
        if self._mode is ExecutionMode.ASYNC:
            self._validate_async_dependencies(self._engine)
        uvicorn.run(
            self.build_app(debug=debug),
            host=host,
            port=port,
            log_level="debug" if debug else "info",
            reload=reload,
        )

    def build_app(self, *, debug: bool = False) -> Starlette:
        """Build and return the Starlette ASGI app without starting the server.

        Useful for testing with ``httpx.AsyncClient`` or
        ``starlette.testclient.TestClient``.
        For async engines, table creation is deferred to the app's lifespan startup
        so it runs inside the correct event loop (not a throwaway thread loop).
        """
        self._create_tables()
        self._check_cache_connections()
        lifespan = self._lifespan if self._mode is ExecutionMode.ASYNC else None
        app = Starlette(
            debug=debug,
            routes=self._asgi_routes(),
            lifespan=lifespan,
            # Starlette's own 405 is text/plain; the README documents a JSON one.
            exception_handlers={HTTPStatus.METHOD_NOT_ALLOWED: self._json_405},
        )
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
        """Login routes first, then the endpoints, then the always-on ``/healthz``."""
        return [
            *self._login_routes(),
            *self._routes,
            Route(HEALTH_PATH, HealthCheckEndpoint),
        ]

    # ─────────────────────────────────────────────────────────────────────────
    # YAML factory
    # ─────────────────────────────────────────────────────────────────────────

    @classmethod
    def from_config(
        cls,
        config_path: str,
        **kwargs: Any,  # noqa: ANN401  constructor kwargs, forwarded
    ) -> LightApi:
        """Create a LightApi instance from a ``lightapi.yaml`` file.

        Uses the declarative format: ``database.url``, ``endpoints[].route``,
        inline ``fields``, ``defaults``, ``middleware``. Parsing and validation
        is handled by :mod:`lightapi.yaml_loader` using Pydantic v2 models.

        Kwargs override YAML values (e.g. engine=..., database_url=...).
        """
        return LightAPIConfig.from_file(config_path).build_app(cls, **kwargs)

    @classmethod
    def from_dict(
        cls,
        config: dict[str, Any],
        **kwargs: Any,  # noqa: ANN401  constructor kwargs, forwarded
    ) -> LightApi:
        """Create a LightApi instance from a Python dictionary.

        Deprecated: removed in 0.2.0. Declare RestEndpoint subclasses and call
        register(), or use from_config() with a YAML file.

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
        warnings.warn(
            "LightApi.from_dict is deprecated and will be removed in 0.2.0. "
            "Declare RestEndpoint subclasses and call register(), or use "
            "from_config() with a YAML file.",
            DeprecationWarning,
            stacklevel=2,
        )
        return DictConfig(config).build(cls, **kwargs)

    # ─────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _create_tables(self) -> None:
        """Create/verify database tables for all registered endpoints."""
        metadata = self._session_manager.metadata
        logger.debug("_create_tables called with metadata: %s", metadata)
        logger.debug("Available tables in metadata: %s", list(metadata.tables.keys()))
        try:
            if self._mode is ExecutionMode.ASYNC:
                self._create_tables_inside_running_loop(metadata)
            elif self._session_manager.is_async:
                # create_all() needs a sync engine, and register() only switches to
                # async mode for an endpoint that needs it. Before, this was an
                # AttributeError swallowed into the same warning.
                logger.warning(
                    "Table creation skipped: an AsyncEngine without mode='async'. "
                    "Pass mode='async' or create the tables yourself."
                )
            else:
                metadata.create_all(bind=self._engine)
                logger.info("Tables created/verified against %s", self._engine.url)
        except SQLAlchemyError:
            logger.warning("Table creation warning", exc_info=True)

    @contextlib.asynccontextmanager
    async def _lifespan(self, _: Starlette) -> AsyncIterator[None]:
        """Startup of an async app: create the tables on the loop that serves it.

        The DDL must run on this loop: a connection opened on another loop (a
        worker thread running asyncio.run) goes back to the pool and fails the next
        request with "attached to a different loop" (asyncpg).
        """
        metadata = self._session_manager.metadata
        try:
            async with self._engine.begin() as conn:
                await conn.run_sync(metadata.create_all)
            logger.info("Tables created/verified against %s", self._engine.url)
        except SQLAlchemyError:
            logger.warning("Table creation warning", exc_info=True)
        yield

    def _create_tables_inside_running_loop(self, metadata: MetaData) -> None:
        """build_app() called inside a loop that is already running (pytest-asyncio)
        creates the tables on a loop of its own, in a worker thread; a served app
        gets them from the lifespan instead."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return

        async def create_all() -> None:
            async with self._engine.begin() as conn:
                await conn.run_sync(metadata.create_all)

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(asyncio.run, create_all()).result()

    def _check_cache_connections(self) -> None:
        """RuntimeWarning when an endpoint has a cache but Redis is unreachable."""
        for cls in self._endpoint_map.values():
            if cls._meta.get("cache"):
                if not RedisCacheBackend.shared().ping():
                    warnings.warn(
                        "Redis is configured for caching but is not reachable at "
                        "startup. Cache will be skipped for all requests.",
                        RuntimeWarning,
                        stacklevel=3,
                    )
                break

    # ─────────────────────────────────────────────────────────────────────────
    # Constructor and register() checks
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _engine_from_url(
        database_url: str | None, mode: ExecutionMode
    ) -> Engine | AsyncEngine:
        url = database_url or os.environ.get("LIGHTAPI_DATABASE_URL")
        if url is None:
            raise ConfigurationError(
                "No database configured. Provide engine=..., database_url=..., or set "
                "LIGHTAPI_DATABASE_URL environment variable."
            )
        if make_url(url).get_dialect().is_async:
            # sqlalchemy[asyncio] is the optional `async` extra.
            from sqlalchemy.ext.asyncio import create_async_engine

            return create_async_engine(url)
        if mode is ExecutionMode.ASYNC:
            shown = make_url(url).render_as_string(hide_password=True)
            raise ConfigurationError(
                "mode='async' needs an async driver in the database URL "
                f"(sqlite+aiosqlite://, postgresql+asyncpg://), got '{shown}'."
            )
        return create_engine(url)

    @staticmethod
    def _engine_is_async(engine: object) -> bool:
        try:
            from sqlalchemy.ext.asyncio import AsyncEngine
        except ImportError:
            return False
        return isinstance(engine, AsyncEngine)

    @staticmethod
    async def _json_405(_request: Request, exc: Exception) -> Response:
        """Starlette raised its 405 for a verb the route does not list."""
        headers = exc.headers if isinstance(exc, HTTPException) else None
        allowed = (headers or {}).get("Allow", "")
        return EndpointHandler.method_not_allowed(
            allowed.split(", ") if allowed else ()
        )

    @classmethod
    def _as_rate_limiter(
        cls, value: RateLimiter | dict[str, int] | None
    ) -> RateLimiter | None:
        if isinstance(value, dict):
            return RateLimiter.from_limits(value, cls._LOGIN_RATE_LIMITS)
        return value if isinstance(value, RateLimiter) else None

    @staticmethod
    def _require_rest_endpoint(path: str, cls: object) -> None:
        if not (isinstance(cls, type) and issubclass(cls, RestEndpoint)):
            raise ConfigurationError(
                f"register() value for '{path}' must be a RestEndpoint subclass, "
                f"got {cls!r}."
            )

    @staticmethod
    def _require_sync_basic_validator(path: str, cls: type[RestEndpoint]) -> None:
        """The guard calls a Basic backend's validate_credentials without awaiting.

        An ``async def`` there returns a coroutine, which is truthy, so every Basic
        credential would pass (B6-005). The login route awaits it, the guard cannot.
        """
        authentication = cls._meta.get("authentication")
        backend = getattr(authentication, "backend", None)
        if (
            isinstance(backend, type)
            and issubclass(backend, BasicAuthentication)
            and asyncio.iscoroutinefunction(backend.validate_credentials)
        ):
            raise ConfigurationError(
                f"'{path}': {backend.__name__}.validate_credentials is async, but a "
                "BasicAuthentication backend checks every request synchronously; "
                "make it a plain def (JWTAuthentication may keep an async one)."
            )

    @classmethod
    def _has_async_handlers(cls, endpoint_cls: type[RestEndpoint]) -> bool:
        # A queryset may be a Select, which is not callable, so check before asking.
        return any(
            callable(handler) and asyncio.iscoroutinefunction(handler)
            for handler in (
                getattr(endpoint_cls, name, None) for name in cls._ASYNC_HANDLER_NAMES
            )
        )

    @staticmethod
    def _require_async_engine(engine: object) -> None:
        try:
            # sqlalchemy[asyncio] is the optional `async` extra.
            from sqlalchemy.ext.asyncio import AsyncEngine
        except ImportError:
            raise ConfigurationError(
                "mode='async' requires async dependencies. "
                "Install: uv add 'lightapi[async]'"
            ) from None
        if not isinstance(engine, AsyncEngine):
            raise ConfigurationError(
                f"mode='async' requires AsyncEngine, got {type(engine).__name__}"
            )

    @staticmethod
    def _validate_async_dependencies(engine: Engine | AsyncEngine) -> None:
        """ConfigurationError if the async SQLAlchemy extra or the driver is missing."""
        try:
            importlib.import_module("sqlalchemy.ext.asyncio")
        except ImportError:
            raise ConfigurationError(
                "AsyncEngine supplied but 'sqlalchemy[asyncio]' is not installed. "
                "Install with: uv add 'sqlalchemy[asyncio]'"
            ) from None
        dialect = engine.url.get_dialect().name
        driver = _ASYNC_DRIVERS.get(dialect)
        if driver:
            try:
                importlib.import_module(driver)
            except ImportError:
                raise ConfigurationError(
                    f"Async driver for '{dialect}' is not installed. "
                    f"Install with: uv add {driver}"
                ) from None


# The async driver each dialect needs; a dialect missing here is not checked.
_ASYNC_DRIVERS: Final[dict[str, str]] = {
    "postgresql": "asyncpg",
    "sqlite": "aiosqlite",
    "mysql": "aiomysql",
}
