"""LightApi — application entry point."""

from __future__ import annotations

import asyncio
import importlib
import json
import logging
import os
import warnings
from typing import Any, Callable, Dict, Optional

import uvicorn
from sqlalchemy import create_engine
from starlette.applications import Starlette
from starlette.background import BackgroundTasks
from starlette.middleware.cors import CORSMiddleware as StarletteCORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from lightapi._registry import (
    get_registry_and_metadata,
    set_engine,
    set_login_validator,
)
from lightapi.auth import AllowAny, BasicAuthentication, JWTAuthentication
from lightapi.cache import get_cached, invalidate_cache_prefix, set_cached
from lightapi.exceptions import ConfigurationError
from lightapi.rest import RestEndpoint
from lightapi.yaml_loader import load_config

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
        cors_origins: list[str] | None = None,
        middlewares: list[type] | None = None,
        login_validator: Any = None,
        auth_path: str = "/auth",
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

        self._engine = engine
        set_engine(engine)

        # Detect async engine — drives session strategy and startup validation
        try:
            importlib.import_module("sqlalchemy.ext.asyncio")
            from sqlalchemy.ext.asyncio import AsyncEngine

            self._async: bool = isinstance(engine, AsyncEngine)
        except ImportError:
            self._async = False

        self._routes: list[Route] = []
        self._endpoint_map: dict[str, type] = {}
        self._middlewares: list[type] = middlewares or []
        self._cors_origins: list[str] = cors_origins or []
        self._login_validator = login_validator
        self._auth_path = auth_path
        self._auth_rate_limiter = None
        if login_validator is not None:
            set_login_validator(login_validator)

    # ─────────────────────────────────────────────────────────────────────────
    # Registration
    # ─────────────────────────────────────────────────────────────────────────

    def register(self, mapping: dict[str, type]) -> None:
        """Register endpoint classes against URL patterns.

        Args:
            mapping: ``{"/path": EndpointClass}`` dictionary.
                Each class must be a ``RestEndpoint`` subclass.
        """

        for path, cls in mapping.items():
            if not (isinstance(cls, type) and issubclass(cls, RestEndpoint)):
                raise ConfigurationError(
                    f"register() value for '{path}' must be a RestEndpoint subclass, "
                    f"got {cls!r}."
                )
            # Warn if endpoint defines async queryset but engine is sync
            if not self._async:
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
                from lightapi.rest import _map_reflected

                meta_obj = getattr(cls, "Meta", None) or type("Meta", (), {})
                partial = cls._meta.get("reflect") == "partial"
                extra_cols = getattr(cls, "_reflect_partial_columns", [])
                _map_reflected(
                    cls,
                    cls.__name__,
                    meta_obj=meta_obj,
                    partial=partial,
                    extra_columns=extra_cols,
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
            collection_route = Route(
                path,
                endpoint=self._make_collection_handler(cls),
                methods=[m for m in allowed if m in {"GET", "POST"}],
            )
            detail_route = Route(
                path.rstrip("/") + "/{id:int}",
                endpoint=self._make_detail_handler(cls),
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

        if auth_backends & {JWTAuthentication, BasicAuthentication}:
            # Initialize rate limiter if not already created
            if self._auth_rate_limiter is None:
                from lightapi.rate_limiter import RateLimiter

                self._auth_rate_limiter = RateLimiter()

            if self._login_validator is None:
                raise ConfigurationError(
                    "login_validator is required when using JWTAuthentication "
                    "or BasicAuthentication. Pass it to LightApi(login_validator=...)."
                )
            has_jwt = JWTAuthentication in auth_backends
            auth_path = self._auth_path.rstrip("/")

            # Check if auth routes already exist
            login_path = f"{auth_path}/login"
            token_path = f"{auth_path}/token"

            # Remove existing auth routes if any
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
    ) -> Any:
        """Create the login/token handler with captured config."""
        from lightapi._login import login_handler

        login_validator = self._login_validator

        async def handler(request: Request) -> Response:
            return await login_handler(
                request,
                login_validator=login_validator,
                has_jwt=has_jwt,
                jwt_expiration=jwt_expiration,
                jwt_extra_claims=jwt_extra_claims,
                jwt_algorithm=jwt_algorithm,
                rate_limiter=self._auth_rate_limiter,
            )

        return handler

    def _make_collection_handler(self, cls: type) -> Any:
        app_middlewares = self._middlewares
        is_async = self._async

        async def handler(request: Request) -> Response:
            endpoint = cls()
            endpoint._background = BackgroundTasks()
            endpoint._current_request = request

            pre_result = await _run_pre_middlewares(app_middlewares, request)
            if pre_result is not None:
                return pre_result

            auth_result = _check_auth(
                cls, request, login_validator=self._login_validator
            )
            if auth_result is not None:
                return auth_result

            if request.method == "GET":
                get_override = getattr(cls, "get", None)
                if get_override and asyncio.iscoroutinefunction(get_override):
                    response = await get_override(endpoint, request)
                elif is_async:
                    response = await endpoint._list_async(request)
                else:
                    response = _maybe_cached(
                        cls, request, lambda: endpoint.list(request)
                    )
            elif request.method == "POST":
                data = await _read_body(request)
                post_override = getattr(cls, "post", None)
                if post_override and asyncio.iscoroutinefunction(post_override):
                    response = await post_override(endpoint, request)
                elif is_async:
                    response = await endpoint._create_async(data)
                else:
                    response = endpoint.create(data)
            else:
                allowed = ", ".join(sorted(cls._allowed_methods & {"GET", "POST"}))
                response = JSONResponse(
                    {"detail": f"Method Not Allowed. Allowed: {allowed}"},
                    status_code=405,
                    headers={"Allow": allowed},
                )

            if not is_async:
                _maybe_invalidate_cache(cls, request)

            if endpoint._background.tasks:
                response.background = endpoint._background

            return await _run_post_middlewares(app_middlewares, request, response)

        handler.__name__ = f"{cls.__name__}_collection"
        handler.__endpoint_cls__ = cls
        return handler

    def _make_detail_handler(self, cls: type) -> Any:
        app_middlewares = self._middlewares
        is_async = self._async

        async def handler(request: Request) -> Response:
            pk: int = request.path_params["id"]
            endpoint = cls()
            endpoint._background = BackgroundTasks()
            endpoint._current_request = request

            pre_result = await _run_pre_middlewares(app_middlewares, request)
            if pre_result is not None:
                return pre_result

            auth_result = _check_auth(
                cls, request, login_validator=self._login_validator
            )
            if auth_result is not None:
                return auth_result

            if request.method == "GET":
                get_override = getattr(cls, "get", None)
                if get_override and asyncio.iscoroutinefunction(get_override):
                    response = await get_override(endpoint, request)
                elif is_async:
                    response = await endpoint._retrieve_async(request, pk)
                else:
                    response = _maybe_cached(
                        cls, request, lambda: endpoint.retrieve(request, pk)
                    )
            elif request.method in {"PUT", "PATCH"}:
                data = await _read_body(request)
                partial = request.method == "PATCH"
                put_override = getattr(cls, "put" if not partial else "patch", None)
                if put_override and asyncio.iscoroutinefunction(put_override):
                    response = await put_override(endpoint, request)
                elif is_async:
                    response = await endpoint._update_async(data, pk, partial=partial)
                else:
                    response = endpoint.update(data, pk, partial=partial)
            elif request.method == "DELETE":
                delete_override = getattr(cls, "delete", None)
                if delete_override and asyncio.iscoroutinefunction(delete_override):
                    response = await delete_override(endpoint, request)
                elif is_async:
                    response = await endpoint._destroy_async(request, pk)
                else:
                    response = endpoint.destroy(request, pk)
            else:
                allowed = ", ".join(
                    sorted(cls._allowed_methods & {"GET", "PUT", "PATCH", "DELETE"})
                )
                response = JSONResponse(
                    {"detail": f"Method Not Allowed. Allowed: {allowed}"},
                    status_code=405,
                    headers={"Allow": allowed},
                )

            if not is_async:
                _maybe_invalidate_cache(cls, request)

            if endpoint._background.tasks:
                response.background = endpoint._background

            return await _run_post_middlewares(app_middlewares, request, response)

        handler.__name__ = f"{cls.__name__}_detail"
        handler.__endpoint_cls__ = cls
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
        if self._async:
            _validate_async_dependencies(self._engine)
        self._create_tables()
        self._check_cache_connections()

        on_startup = [self._async_create_tables] if self._async else []
        app = Starlette(debug=debug, routes=self._routes, on_startup=on_startup)

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
        on_startup = [self._async_create_tables] if self._async else []
        return Starlette(routes=self._routes, on_startup=on_startup)

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

    # ─────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _create_tables(self) -> None:
        _, metadata = get_registry_and_metadata()
        try:
            if self._async:
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
                metadata.create_all(bind=self._engine)
                logger.info("Tables created/verified against %s", self._engine.url)
        except Exception as exc:
            logger.warning("Table creation warning: %s", exc)

    async def _async_create_tables(self) -> None:
        """Called on server startup; creates tables inside the running event loop."""
        _, metadata = get_registry_and_metadata()
        try:
            async with self._engine.begin() as conn:
                await conn.run_sync(metadata.create_all)
            logger.info("Tables created/verified against %s", self._engine.url)
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


# ─────────────────────────────────────────────────────────────────────────────
# Handler utilities
# ─────────────────────────────────────────────────────────────────────────────


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


async def _read_body(request: Request) -> dict[str, Any]:
    """Read and parse JSON body; return {} on failure."""

    try:
        body = await request.body()
        return json.loads(body) if body else {}
    except Exception:
        return {}


def _check_auth(
    cls: type,
    request: Request,
    login_validator: Optional[Callable[[str, str], Dict[str, Any] | None]] = None,
) -> Response | None:
    """Run authentication + permission checks; return 401/403 response or None."""

    auth_cfg = cls._meta.get("authentication")
    if auth_cfg is None:
        return None

    backend = auth_cfg.backend
    permission_cls = auth_cfg.permission

    # Resolve permission for this method
    if permission_cls is not None:
        if isinstance(permission_cls, dict):
            perm_cls = permission_cls.get(request.method)
            if perm_cls is None:
                perm_cls = AllowAny
            # Per-method AllowAny: method is public, skip backend
            if perm_cls is AllowAny:
                return None
        else:
            perm_cls = permission_cls
    else:
        perm_cls = AllowAny

    if backend is not None:
        # Pass JWT configuration if backend is JWTAuthentication
        if backend.__name__ == "JWTAuthentication":
            authenticator = backend(
                expiration=getattr(auth_cfg, "jwt_expiration", None),
                algorithm=getattr(auth_cfg, "jwt_algorithm", None),
            )
        elif backend.__name__ == "BasicAuthentication":
            authenticator = backend(login_validator=login_validator)
        else:
            authenticator = backend()

        if not authenticator.authenticate(request):
            return JSONResponse(
                {"detail": "Authentication credentials invalid."}, status_code=401
            )

    if perm_cls is not None:
        perm = perm_cls()
        if not perm.has_permission(request):
            return JSONResponse(
                {"detail": "You do not have permission to perform this action."},
                status_code=403,
            )

    return None


async def _run_pre_middlewares(
    middlewares: list[type], request: Request
) -> Response | None:
    """Run pre-request middleware; supports both sync and async process() methods."""
    for mw_cls in middlewares:
        mw = mw_cls()
        if asyncio.iscoroutinefunction(mw.process):
            result = await mw.process(request, None)
        else:
            result = mw.process(request, None)
        if result is not None:
            return result
    return None


async def _run_post_middlewares(
    middlewares: list[type], request: Request, response: Response
) -> Response:
    """Run post-response middleware in reverse order; supports sync and async process()."""
    for mw_cls in reversed(middlewares):
        mw = mw_cls()
        if asyncio.iscoroutinefunction(mw.process):
            result = await mw.process(request, response)
        else:
            result = mw.process(request, response)
        if result is not None:
            response = result
    return response


def _maybe_cached(cls: type, request: Request, fn: Any) -> Response:
    """Serve from Redis cache (GET only) or call fn() and populate cache."""

    cache_cfg = cls._meta.get("cache")
    if cache_cfg is None:
        return fn()

    key = _cache_key(cls, request)
    try:
        cached = get_cached(key)
    except Exception:
        cached = None
    if cached is not None:
        return JSONResponse(cached)
    response = fn()
    if isinstance(response, JSONResponse) and response.status_code == 200:
        import json

        try:
            set_cached(key, json.loads(response.body), cache_cfg.ttl)
        except Exception:
            pass
    return response


def _maybe_invalidate_cache(cls: type, request: Request) -> None:
    """Invalidate cache entries after mutating requests."""
    if request.method == "GET":
        return
    cache_cfg = cls._meta.get("cache")
    if cache_cfg is None:
        return

    invalidate_cache_prefix(_cache_key_prefix(cls))


def _cache_key(cls: type, request: Request) -> str:
    query = str(request.query_params)
    return f"lightapi:{cls.__name__}:{request.url.path}:{query}"


def _cache_key_prefix(cls: type) -> str:
    return f"lightapi:{cls.__name__}:"
