"""LightApi — application entry point."""
from __future__ import annotations

import logging
import os
from typing import Any

import uvicorn
import yaml
from sqlalchemy import create_engine
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware as StarletteCORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from lightapi._registry import get_registry_and_metadata, set_engine
from lightapi.exceptions import ConfigurationError

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
    ) -> None:
        if engine is None and database_url:
            engine = create_engine(database_url)
        elif engine is None:
            from lightapi.config import config
            engine = create_engine(config.database_url)

        self._engine = engine
        set_engine(engine)

        self._routes: list[Route] = []
        self._middlewares: list[type] = middlewares or []
        self._cors_origins: list[str] = cors_origins or []

    # ─────────────────────────────────────────────────────────────────────────
    # Registration
    # ─────────────────────────────────────────────────────────────────────────

    def register(self, mapping: dict[str, type]) -> None:
        """Register endpoint classes against URL patterns.

        Args:
            mapping: ``{"/path": EndpointClass}`` dictionary.
                Each class must be a ``RestEndpoint`` subclass.
        """
        from lightapi.rest import RestEndpoint

        for path, cls in mapping.items():
            if not (isinstance(cls, type) and issubclass(cls, RestEndpoint)):
                raise ConfigurationError(
                    f"register() value for '{path}' must be a RestEndpoint subclass, "
                    f"got {cls!r}."
                )
            # Perform deferred reflection now that an engine is available
            if getattr(cls, "_reflect_deferred", False):
                from lightapi.rest import _map_reflected
                partial = cls._meta.get("reflect") == "partial"
                extra_cols = getattr(cls, "_reflect_partial_columns", [])
                _map_reflected(
                    cls,
                    cls.__name__,
                    meta_obj=cls.__dict__.get("Meta") or type("Meta", (), {}),
                    partial=partial,
                    extra_columns=extra_cols,
                )
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

    def _make_collection_handler(self, cls: type) -> Any:
        app_middlewares = self._middlewares

        async def handler(request: Request) -> Response:
            endpoint = cls()
            pre_result = _run_pre_middlewares(app_middlewares, request)
            if pre_result is not None:
                return pre_result

            auth_result = _check_auth(cls, request)
            if auth_result is not None:
                return auth_result

            if request.method == "GET":
                response = _maybe_cached(cls, request, lambda: endpoint.list(request))
            elif request.method == "POST":
                data = await _read_body(request)
                response = endpoint.create(data)
            else:
                allowed = ", ".join(sorted(cls._allowed_methods & {"GET", "POST"}))
                response = JSONResponse(
                    {"detail": f"Method Not Allowed. Allowed: {allowed}"},
                    status_code=405,
                    headers={"Allow": allowed},
                )
            _maybe_invalidate_cache(cls, request)
            return _run_post_middlewares(app_middlewares, request, response)

        handler.__name__ = f"{cls.__name__}_collection"
        return handler

    def _make_detail_handler(self, cls: type) -> Any:
        app_middlewares = self._middlewares

        async def handler(request: Request) -> Response:
            pk: int = request.path_params["id"]
            endpoint = cls()
            pre_result = _run_pre_middlewares(app_middlewares, request)
            if pre_result is not None:
                return pre_result

            auth_result = _check_auth(cls, request)
            if auth_result is not None:
                return auth_result

            if request.method == "GET":
                response = _maybe_cached(cls, request, lambda: endpoint.retrieve(request, pk))
            elif request.method in {"PUT", "PATCH"}:
                data = await _read_body(request)
                response = endpoint.update(data, pk, partial=request.method == "PATCH")
            elif request.method == "DELETE":
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
            _maybe_invalidate_cache(cls, request)
            return _run_post_middlewares(app_middlewares, request, response)

        handler.__name__ = f"{cls.__name__}_detail"
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
        self._create_tables()
        self._check_cache_connections()

        app = Starlette(debug=debug, routes=self._routes)

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
        """
        self._create_tables()
        return Starlette(routes=self._routes)

    # ─────────────────────────────────────────────────────────────────────────
    # YAML factory
    # ─────────────────────────────────────────────────────────────────────────

    @classmethod
    def from_config(cls, config_path: str) -> "LightApi":
        """Create a LightApi instance from a ``lightapi.yaml`` file."""
        with open(config_path) as fh:
            raw = yaml.safe_load(fh)

        db_url: str = raw.get("database_url", "")
        if db_url.startswith("${") and db_url.endswith("}"):
            env_var = db_url[2:-1]
            db_url = os.environ.get(env_var, "")
            if not db_url:
                raise ConfigurationError(
                    f"Environment variable '{env_var}' is not set (required by lightapi.yaml)."
                )

        cors = raw.get("cors_origins", [])
        instance = cls(database_url=db_url, cors_origins=cors)

        endpoints_cfg: list[dict[str, Any]] = raw.get("endpoints", [])
        mapping: dict[str, type] = {}
        for entry in endpoints_cfg:
            path = entry["path"]
            module_path, class_name = entry["class"].rsplit(".", 1)
            import importlib
            mod = importlib.import_module(module_path)
            endpoint_cls = getattr(mod, class_name)
            mapping[path] = endpoint_cls

        if mapping:
            instance.register(mapping)

        return instance

    # ─────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _create_tables(self) -> None:
        _, metadata = get_registry_and_metadata()
        try:
            metadata.create_all(bind=self._engine)
            logger.info("Tables created/verified against %s", self._engine.url)
        except Exception as exc:
            logger.warning("Table creation warning: %s", exc)

    def _check_cache_connections(self) -> None:
        """Emit RuntimeWarning if any endpoint has cache configured but Redis is unreachable."""
        import warnings
        from lightapi.rest import RestEndpoint

        checked = False
        for route in self._routes:
            handler = route.endpoint
            cls = getattr(handler, "__endpoint_cls__", None)
            if cls is None:
                continue
            cache_cfg = getattr(cls, "_meta", {}).get("cache")
            if cache_cfg and not checked:
                from lightapi.cache import _ping_redis
                if not _ping_redis():
                    warnings.warn(
                        "Redis is configured for caching but is not reachable at startup. "
                        "Cache will be skipped for all requests.",
                        RuntimeWarning,
                        stacklevel=3,
                    )
                checked = True


# ─────────────────────────────────────────────────────────────────────────────
# Handler utilities
# ─────────────────────────────────────────────────────────────────────────────


async def _read_body(request: Request) -> dict[str, Any]:
    """Read and parse JSON body; return {} on failure."""
    import json
    try:
        body = await request.body()
        return json.loads(body) if body else {}
    except Exception:
        return {}


def _check_auth(cls: type, request: Request) -> Response | None:
    """Run authentication + permission checks; return 401/403 response or None."""
    auth_cfg = cls._meta.get("authentication")
    if auth_cfg is None:
        return None

    backend = auth_cfg.backend
    permission_cls = auth_cfg.permission

    if backend is not None:
        authenticator = backend()
        if not authenticator.authenticate(request):
            return JSONResponse({"detail": "Authentication credentials invalid."}, status_code=401)

    if permission_cls is not None:
        perm = permission_cls()
        if not perm.has_permission(request):
            return JSONResponse({"detail": "You do not have permission to perform this action."}, status_code=403)

    return None


def _run_pre_middlewares(
    middlewares: list[type], request: Request
) -> Response | None:
    for mw_cls in middlewares:
        result = mw_cls().process(request, None)
        if result is not None:
            return result
    return None


def _run_post_middlewares(
    middlewares: list[type], request: Request, response: Response
) -> Response:
    for mw_cls in reversed(middlewares):
        result = mw_cls().process(request, response)
        if result is not None:
            response = result
    return response


def _maybe_cached(cls: type, request: Request, fn: Any) -> Response:
    """Serve from Redis cache (GET only) or call fn() and populate cache."""
    from lightapi.cache import get_cached, set_cached

    cache_cfg = cls._meta.get("cache")
    if cache_cfg is None:
        return fn()

    key = _cache_key(cls, request)
    cached = get_cached(key)
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
    from lightapi.cache import invalidate_cache_prefix
    invalidate_cache_prefix(_cache_key_prefix(cls))


def _cache_key(cls: type, request: Request) -> str:
    query = str(request.query_params)
    return f"lightapi:{cls.__name__}:{request.url.path}:{query}"


def _cache_key_prefix(cls: type) -> str:
    return f"lightapi:{cls.__name__}:"
