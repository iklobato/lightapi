import asyncio
import base64
import datetime
import inspect
import logging
import os
from types import SimpleNamespace
from typing import Any, Callable, Dict, Type, Union

import uvicorn
import yaml
from aiohttp import web
from sqlalchemy import MetaData, create_engine, event
from sqlalchemy.exc import ArgumentError, InvalidRequestError, SQLAlchemyError
from sqlalchemy.orm import declarative_base as dynamic_declarative_base
from sqlalchemy.orm.session import sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy.sql.sqltypes import LargeBinary
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.responses import Response as StarletteResponse
from starlette.routing import Route as StarletteRoute

from lightapi.database import Base, SessionLocal, engine
from lightapi.handlers import (
    CreateHandler,
    DeleteHandler,
    PatchHandler,
    ReadHandler,
    RetrieveAllHandler,
    UpdateHandler,
    create_handler,
)
from lightapi.rest import RestEndpoint

from .config import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)


class LightApi:
    """
    The main application class for managing routes and running the server.

    This class registers routes for both SQLAlchemy models and custom `RestEndpoint` subclasses. It initializes
    the application, creates database tables, and provides methods to register routes and start the server.

    Attributes:
        app (web.Application): The aiohttp application instance.
        aiohttp_routes (List[web.RouteDef]): A list of route definitions to be added to the application.
        starlette_routes (List[StarletteRoute]): A list of Starlette routes to be added to the application.

    Methods:
        __init__() -> None:
            Initializes the LightApi, creates database tables, and prepares an empty list of routes.

        register(handlers: Dict[str, Type]) -> None:
            Registers routes for SQLAlchemy models or custom RestEndpoint subclasses.

        run(host: str = '0.0.0.0', port: int = 8000) -> None:
            Starts the web application and runs the server.

        from_config(config_path: str) -> "LightApi":
            Create a LightApi instance from a YAML configuration file.
    """

    def __init__(
        self,
        database_url: str = None,
        swagger_title: str = None,
        swagger_version: str = None,
        swagger_description: str = None,
        enable_swagger: bool = None,
        cors_origins: list = None,
        initialize_callback: Callable = None,
        initialize_arguments: Dict = None,
    ) -> None:
        """
        Initializes the LightApi, sets up the aiohttp application, and creates tables in the database.

        Creates an empty list of routes and attempts to create database tables using SQLAlchemy. Logs the status of
        table creation.

        Raises:
            SQLAlchemyError: If there is an error during the creation of tables.
        """

        update_values = {}
        if database_url is not None:
            update_values["database_url"] = database_url
        if swagger_title is not None:
            update_values["swagger_title"] = swagger_title
        if swagger_version is not None:
            update_values["swagger_version"] = swagger_version
        if swagger_description is not None:
            update_values["swagger_description"] = swagger_description
        if enable_swagger is not None:
            update_values["enable_swagger"] = enable_swagger
        if cors_origins is not None:
            update_values["cors_origins"] = cors_origins
        config.update(**update_values)
        self.enable_swagger = config.enable_swagger
        if self.enable_swagger:
            from lightapi.swagger import (
                SwaggerGenerator,
            )

            self.swagger_generator = SwaggerGenerator(
                title=config.swagger_title,
                version=config.swagger_version,
                description=config.swagger_description,
            )
        self.initialize(callback=initialize_callback, callback_arguments=initialize_arguments)
        self.app = web.Application()
        self.aiohttp_routes = []
        self.starlette_routes = []
        Base.metadata.create_all(bind=engine)
        logging.info(f"Tables successfully created and connected to {engine.url}")
        self.middleware = []

        if database_url is not None:
            self.engine = create_engine(database_url)
            self.Session = sessionmaker(bind=self.engine)

    def initialize(self, callback: Callable = None, callback_arguments: Dict = ()) -> None:
        """
        Initializes the LightApi according to a callable
        """
        if not callback:
            return
        if not callable(callback):
            raise TypeError("Callback must be a callable object")
        logging.debug(f"Initializing LightApi with {callback_arguments}")
        callback(**callback_arguments)

    def register(self, handler):
        if inspect.isclass(handler) and issubclass(handler, RestEndpoint):
            # Use __tablename__ if available, else fallback to class name
            route_patterns = getattr(handler, "route_patterns", None)
            if route_patterns:
                # Use custom route patterns for registration (custom endpoints, not models)
                patterns = route_patterns
            elif hasattr(handler, "__tablename__") and getattr(handler, "__tablename__", None):
                # Use __tablename__ for RESTful paths (SQLAlchemy models only)
                tablename = getattr(handler, "__tablename__")
                patterns = [f"/{tablename.lower()}", f"/{tablename.lower()}/{{id}}"]
            else:
                raise ValueError(f"Handler {handler.__name__} must define either route_patterns or __tablename__.")
            endpoint_instance = handler()
            allowed_methods = getattr(getattr(endpoint_instance, "Configuration", None), "http_method_names", None)
            if not allowed_methods:
                allowed_methods = [m.upper() for m in ["get", "post", "put", "patch", "delete"]]
            else:
                allowed_methods = [m.upper() for m in allowed_methods]
            all_methods = ["GET", "POST", "PUT", "PATCH", "DELETE"]
            for pattern in patterns:
                for method in all_methods:
                    if method in allowed_methods:
                        if pattern and not any(r.path == pattern and method in r.methods for r in self.starlette_routes):

                            def make_starlette_handler(handler, method):
                                async def starlette_handler(request):
                                    class RequestAdapter:
                                        def __init__(self, aiohttp_request):
                                            self.aiohttp_request = aiohttp_request
                                            if hasattr(aiohttp_request, "path_params"):
                                                self.path_params = aiohttp_request.path_params
                                                self.query_params = aiohttp_request.query_params
                                            else:
                                                self.path_params = aiohttp_request.match_info
                                                self.query_params = aiohttp_request.query

                                        @property
                                        def method(self):
                                            if hasattr(self.aiohttp_request, "method"):
                                                return self.aiohttp_request.method
                                            return getattr(self.aiohttp_request, "_method", None)

                                        async def get_data(self):
                                            if hasattr(self, "_data"):
                                                return self._data
                                            try:
                                                self._data = await self.aiohttp_request.json()
                                            except Exception:
                                                self._data = {}
                                            return self._data

                                        @property
                                        def data(self):
                                            try:
                                                loop = asyncio.get_event_loop()
                                                if loop.is_running():
                                                    raise RuntimeError(
                                                        "RequestAdapter.data cannot be used in an async context. Use 'await get_data()' instead."
                                                    )
                                                return loop.run_until_complete(self.get_data())
                                            except RuntimeError as e:
                                                if "no current event loop" in str(e):
                                                    return asyncio.run(self.get_data())
                                                raise

                                        @property
                                        def headers(self):
                                            if hasattr(self.aiohttp_request, "headers"):
                                                return self.aiohttp_request.headers
                                            return {}

                                        @property
                                        def state(self):
                                            if hasattr(self.aiohttp_request, "state"):
                                                return self.aiohttp_request.state
                                            if not hasattr(self, "_state"):
                                                self._state = SimpleNamespace()
                                            return self._state

                                    adapted_request = RequestAdapter(request)
                                    composed_handler = handler
                                    if hasattr(endpoint_instance, "middleware") and endpoint_instance.middleware:

                                        async def wrapped_with_middleware(req):
                                            pre_middleware = getattr(endpoint_instance, "middleware", [])
                                            called_middleware = []
                                            for mw_class in pre_middleware:
                                                mw = mw_class()
                                                if mw in called_middleware:
                                                    continue
                                                result = mw.process(req, None)
                                                if result is not None:
                                                    return result
                                                called_middleware.append(mw)
                                            response = await handler(req)
                                            if hasattr(response, "__table__"):
                                                response = {c.name: getattr(response, c.name) for c in response.__table__.columns}
                                            if isinstance(response, tuple):
                                                data, status = response
                                                response = JSONResponse(data, status_code=status)
                                            for mw in reversed(called_middleware):
                                                response = mw.process(req, response)
                                            return response

                                        composed_handler = wrapped_with_middleware
                                    if hasattr(endpoint_instance, "cache_decorator"):
                                        composed_handler = endpoint_instance.cache_decorator(composed_handler)
                                    result = composed_handler(adapted_request)
                                    if inspect.isawaitable(result):
                                        result = await result
                                    if hasattr(result, "__table__"):
                                        result = {c.name: getattr(result, c.name) for c in result.__table__.columns}
                                    if isinstance(result, tuple):
                                        data, status = result
                                        result = JSONResponse(data, status_code=status)
                                    if isinstance(result, web.Response):
                                        body = None
                                        if hasattr(result, "text") and isinstance(result.text, str):
                                            body = result.text
                                            return PlainTextResponse(body, status_code=result.status)
                                        if hasattr(result, "json") and callable(result.json):
                                            body = result.json()
                                            return JSONResponse(body, status_code=result.status)
                                        if hasattr(result, "body"):
                                            body = result.body
                                            return PlainTextResponse(body, status_code=result.status)
                                        return PlainTextResponse("Internal error: could not adapt aiohttp response", status_code=500)
                                    return result

                                return starlette_handler

                            self.starlette_routes.append(
                                StarletteRoute(
                                    pattern,
                                    make_starlette_handler(
                                        getattr(endpoint_instance, method.lower(), lambda req: web.Response(status=405)), method
                                    ),
                                    methods=[method, "OPTIONS"],
                                )
                            )
        elif inspect.isclass(handler) and hasattr(handler, "__tablename__") and getattr(handler, "__tablename__") is not None:
            aiohttp_new_routes = create_handler(handler)
            self.aiohttp_routes.extend(aiohttp_new_routes)

        else:
            handler_name = f"class {handler.__name__}" if inspect.isclass(handler) else type(handler).__name__
            raise TypeError(f"Handler must be a SQLAlchemy model class or RestEndpoint class. Got: {handler_name}")

    def _create_rest_endpoint_routes(self, endpoint_instance, base_path=None):
        """Create aiohttp route handlers for a RestEndpoint instance at a given base path."""

        if base_path is None:
            if hasattr(endpoint_instance, "__tablename__") and endpoint_instance.__tablename__:
                base_path = f"/{endpoint_instance.__tablename__.lower()}"
            else:
                base_path = f"/{endpoint_instance.__class__.__name__.lower()}"

        if not base_path.startswith("/"):
            base_path = f"/{base_path}"

        base_path = base_path.rstrip("/")

        async def endpoint_handler(request):
            session = SessionLocal()

            class RequestAdapter:
                def __init__(self, aiohttp_request):
                    self.aiohttp_request = aiohttp_request
                    if hasattr(aiohttp_request, "path_params"):
                        self.path_params = aiohttp_request.path_params
                        self.query_params = aiohttp_request.query_params
                    else:
                        self.path_params = aiohttp_request.match_info
                        self.query_params = aiohttp_request.query

                @property
                def method(self):
                    if hasattr(self.aiohttp_request, "method"):
                        return self.aiohttp_request.method
                    return getattr(self.aiohttp_request, "_method", None)

                async def get_data(self):
                    if hasattr(self, "_data"):
                        return self._data
                    try:
                        self._data = await self.aiohttp_request.json()
                    except Exception:
                        self._data = {}
                    return self._data

                @property
                def data(self):
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            raise RuntimeError("RequestAdapter.data cannot be used in an async context. Use 'await get_data()' instead.")
                        return loop.run_until_complete(self.get_data())
                    except RuntimeError as e:
                        if "no current event loop" in str(e):
                            return asyncio.run(self.get_data())
                        raise

                @property
                def headers(self):
                    if hasattr(self.aiohttp_request, "headers"):
                        return self.aiohttp_request.headers
                    return {}

                @property
                def state(self):
                    if hasattr(self.aiohttp_request, "state"):
                        return self.aiohttp_request.state
                    if not hasattr(self, "_state"):
                        self._state = SimpleNamespace()
                    return self._state

            adapted_request = RequestAdapter(request)
            setup_result = endpoint_instance._setup(adapted_request, session)
            if setup_result:
                session.close()
                return setup_result
            method = request.method.lower()
            if hasattr(endpoint_instance, method):
                handler_result = getattr(endpoint_instance, method)(adapted_request)
                if inspect.isawaitable(handler_result):
                    handler_result = await handler_result
                if isinstance(handler_result, (web.Response, Response)):
                    session.close()
                    return handler_result

                if hasattr(handler_result, "__table__"):
                    handler_result = {c.name: getattr(handler_result, c.name) for c in handler_result.__table__.columns}
                    session.close()
                    return web.json_response(handler_result, status=200)
                if isinstance(handler_result, tuple):
                    result_data, status_code = handler_result
                    if hasattr(result_data, "__table__"):
                        result_data = {c.name: getattr(result_data, c.name) for c in result_data.__table__.columns}
                    session.close()
                    return web.json_response(result_data, status=status_code)

                if hasattr(handler_result, "__table__"):
                    handler_result = {c.name: getattr(handler_result, c.name) for c in handler_result.__table__.columns}

                if isinstance(handler_result, list) and handler_result and hasattr(handler_result[0], "__table__"):
                    handler_result = [{c.name: getattr(item, c.name) for c in item.__table__.columns} for item in handler_result]
                session.close()
                return web.json_response(handler_result, status=200)
            session.close()
            return web.Response(status=405)

        return [
            web.get(base_path, endpoint_handler),
            web.get(base_path + "/", endpoint_handler),
            web.post(base_path, endpoint_handler),
            web.post(base_path + "/", endpoint_handler),
            web.get(f"{base_path}/{{id}}", endpoint_handler),
            web.put(f"{base_path}/{{id}}", endpoint_handler),
            web.delete(f"{base_path}/{{id}}", endpoint_handler),
            web.patch(f"{base_path}/{{id}}", endpoint_handler),
        ]

    def _wrap_with_middleware(self, handler):
        """
        Wrap a handler with the middleware chain (pre and post processing).
        """

        async def wrapped(request):
            pre_middleware = getattr(self, "middleware", [])
            called_middleware = []

            for mw_class in pre_middleware:
                mw = mw_class()
                if mw in called_middleware:
                    continue
                result = mw.process(request, None)
                if result is not None:
                    return result
                called_middleware.append(mw)

            response = await handler(request)

            if isinstance(response, tuple):
                try:
                    data, status = response
                    response = JSONResponse(data, status_code=status)
                except ImportError:
                    response = web.json_response(response[0], status=response[1])

            for mw in reversed(called_middleware):
                response = mw.process(request, response)
            return response

        return wrapped

    def add_middleware(self, middleware_classes):
        self.middleware = middleware_classes

        new_starlette_routes = []
        for route in self.starlette_routes:

            def make_starlette_handler(handler):
                async def starlette_handler(request):
                    result = await handler(request)

                    if isinstance(result, web.Response):
                        body = None

                        if hasattr(result, "text") and isinstance(result.text, str):
                            body = result.text
                            return PlainTextResponse(body, status_code=result.status)

                        if hasattr(result, "json") and callable(result.json):
                            body = result.json()
                            return JSONResponse(body, status_code=result.status)

                        if hasattr(result, "body"):
                            body = result.body
                            return PlainTextResponse(body, status_code=result.status)
                        return PlainTextResponse("Internal error: could not adapt aiohttp response", status_code=500)

                    try:
                        if hasattr(result, "__table__"):
                            result = {c.name: getattr(result, c.name) for c in result.__table__.columns}
                    except Exception:
                        pass
                    return result

                return starlette_handler

            endpoint = self._wrap_with_middleware(route.endpoint)
            endpoint = make_starlette_handler(endpoint)
            new_starlette_routes.append(StarletteRoute(route.path, endpoint, methods=route.methods))
        self.starlette_routes = new_starlette_routes

    def run(self, host: str = "0.0.0.0", port: int = 8000, debug: bool = False, reload: bool = False) -> None:
        """
        Starts the web application and begins listening for incoming requests.

        Args:
            host (str): The hostname or IP address to bind the server to. Defaults to '0.0.0.0'.
            port (int): The port number on which the server will listen. Defaults to 8000.
            debug (bool): Whether to enable debug mode. Defaults to False.
            reload (bool): Whether to enable auto-reload. Defaults to False.
        """
        import uvicorn
        from starlette.applications import Starlette

        if hasattr(self, "starlette_routes") and self.starlette_routes:
            print("\nRegistered Starlette routes:")
            for r in self.starlette_routes:
                print(f"  {r.path} -> {r.endpoint.__name__} [{','.join(r.methods)}]")
            app = Starlette(routes=self.starlette_routes)
            uvicorn.run(app, host=host, port=port, reload=reload, log_level="debug" if debug else "info")
        elif hasattr(self, "app"):
            # Assume self.app is an aiohttp app
            import asyncio

            from aiohttp import web

            web.run_app(self.app, host=host, port=port)
        else:
            raise RuntimeError("No application instance found to run.")

    @classmethod
    def from_config(cls, config_path: str, engine=None) -> "LightApi":
        """
        Create a LightApi instance from a YAML configuration file.
        The config must specify the database_url and tables with allowed CRUD verbs.
        Optionally accepts an existing SQLAlchemy engine (for testing).
        """

        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        db_url = config["database_url"]
        if db_url.startswith("${") and db_url.endswith("}"):
            env_var = db_url[2:-1]
            db_url = os.environ.get(env_var)
            if not db_url:
                raise ValueError(f"Environment variable {env_var} not set for database_url")

        table_names = [t["name"] if isinstance(t, dict) else t for t in config["tables"]]
        if engine is None:
            engine = create_engine(db_url, poolclass=NullPool)
            if db_url.startswith("sqlite"):

                @event.listens_for(engine, "connect")
                def set_sqlite_pragma(dbapi_connection, connection_record):
                    cursor = dbapi_connection.cursor()
                    cursor.execute("PRAGMA foreign_keys=ON")
                    cursor.close()

        metadata = MetaData()
        try:
            metadata.reflect(bind=engine, only=table_names)
        except InvalidRequestError as e:
            raise ValueError(f"Table not found: {e}")

        session_factory = sessionmaker(bind=engine)

        DynamicBase = dynamic_declarative_base()

        HANDLER_MAP = {
            "post": (CreateHandler, lambda t: (f"/{t}/", "post")),
            "get": (RetrieveAllHandler, lambda t: (f"/{t}/", "get")),
            "get_id": (ReadHandler, lambda t: (f"/{t}/{{id}}", "get")),
            "put": (UpdateHandler, lambda t: (f"/{t}/{{id}}", "put")),
            "patch": (PatchHandler, lambda t: (f"/{t}/{{id}}", "patch")),
            "delete": (DeleteHandler, lambda t: (f"/{t}/{{id}}", "delete")),
        }

        routes = []
        for table_cfg in config["tables"]:
            table_name = table_cfg["name"] if isinstance(table_cfg, dict) else table_cfg
            verbs = [v.lower() for v in table_cfg.get("crud", [])]

            verbs = [v for v in verbs if v not in ("options", "head")]
            print(f"[DEBUG] Registering table: {table_name}, verbs: {verbs}")
            if table_name not in metadata.tables:
                raise ValueError(f"Table '{table_name}' not found in database.")
            table = metadata.tables[table_name]

            def serialize(self):
                result = {}
                for col in self.__table__.columns:
                    val = getattr(self, col.name)

                    if hasattr(col.type, "python_type") and col.type.python_type is datetime.date and isinstance(val, str):
                        val = datetime.date.fromisoformat(val)
                    if isinstance(val, bytes):
                        result[col.name] = base64.b64encode(val).decode()
                    elif isinstance(val, (datetime.datetime, datetime.date)):
                        result[col.name] = val.isoformat()
                    else:
                        result[col.name] = val
                return result

            try:
                model_attrs = {
                    "__table__": table,
                    "__tablename__": table_name,
                    "serialize": serialize,
                }
                pk_cols = [col.name for col in table.primary_key.columns]
                if not pk_cols:
                    raise ValueError("no primary key")
                if len(pk_cols) == 1 and pk_cols[0] == "id":
                    model_attrs["id"] = table.c["id"]
                model = type(
                    table_name.capitalize(),
                    (DynamicBase,),
                    model_attrs,
                )
                if len(pk_cols) == 1:
                    model.pk = table.c[pk_cols[0]]
                else:
                    model.pk = tuple(table.c[pk] for pk in pk_cols)
            except (ArgumentError, InvalidRequestError) as e:
                if isinstance(e, ArgumentError) and "could not assemble any primary key" in str(e):
                    raise ValueError("no primary key")
                raise ValueError(str(e))

            has_blob = any(isinstance(col.type, LargeBinary) for col in table.columns)
            if has_blob:

                class CustomCreateHandler(CreateHandler):
                    async def handle(self, db, request):
                        data = await request.json()
                        for col in table.columns:
                            if isinstance(col.type, LargeBinary) and col.name in data and isinstance(data[col.name], str):
                                try:
                                    data[col.name] = base64.b64decode(data[col.name])
                                except (base64.binascii.Error, ValueError):
                                    return web.json_response({"error": f"Invalid base64 encoding for field '{col.name}'"}, status=400)

                            if col.name in data:
                                val = data[col.name]
                                if hasattr(col.type, "python_type"):
                                    if col.type.python_type is datetime.datetime:
                                        if isinstance(val, datetime.datetime):
                                            val = val.isoformat()
                                        if isinstance(val, str):
                                            data[col.name] = datetime.datetime.fromisoformat(val)
                                    elif col.type.python_type is datetime.date:
                                        if isinstance(val, str):
                                            data[col.name] = datetime.date.fromisoformat(val)

                            if col.name in data:
                                val = data[col.name]
                                if hasattr(col.type, "python_type"):
                                    if col.type.python_type is datetime.datetime:
                                        if isinstance(val, datetime.datetime):
                                            val = val.isoformat()
                                        if isinstance(val, str):
                                            data[col.name] = datetime.datetime.fromisoformat(val)
                                    elif col.type.python_type is datetime.date:
                                        if isinstance(val, datetime.date):
                                            val = val.isoformat()
                                        if isinstance(val, str):
                                            data[col.name] = datetime.date.fromisoformat(val)

                        for col in table.columns:
                            if hasattr(col.type, "python_type") and col.type.python_type is datetime.date:
                                if col.name not in data:
                                    data[col.name] = None

                            if col.default is not None and col.default.is_scalar:
                                if col.name not in data or data[col.name] is None:
                                    data[col.name] = col.default.arg
                        item = self.model(**data)

                        for col in table.columns:
                            if col.default is not None and col.default.is_scalar:
                                if getattr(item, col.name) is None:
                                    setattr(item, col.name, col.default.arg)
                        item = self.add_and_commit_item(db, item)

                        if hasattr(self.model, "pk"):
                            if isinstance(self.model.pk, tuple):
                                filters = [col == getattr(item, col.name) for col in self.model.pk]
                                item = db.query(self.model).filter(*filters).first()
                            else:
                                item = db.query(self.model).filter(self.model.pk == getattr(item, self.model.pk.name)).first()

                        for col in self.model.__table__.columns:
                            if getattr(item, col.name) is None and col.default is not None and col.default.is_scalar:
                                setattr(item, col.name, col.default.arg)
                        if isinstance(item, JSONResponse):
                            return item
                        return web.json_response(item, status=201)

            else:
                CustomCreateHandler = CreateHandler

            for verb in verbs:
                if verb == "get":
                    handler_cls, route_fn = HANDLER_MAP["get"]
                    path, method = route_fn(table_name)
                    print(f"[DEBUG] Registering route: {method.upper()} {path}")
                    routes.append(getattr(web, method)(path, handler_cls(model, session_factory)))

                    pk_cols = [col.name for col in table.primary_key.columns]
                    if len(pk_cols) == 1:
                        pk_path = f"/{{{pk_cols[0]}}}"
                    else:
                        pk_path = "/" + "/".join([f"{{{col}}}" for col in pk_cols])
                    path = f"/{table_name}{pk_path}"
                    method = "get"
                    print(f"[DEBUG] Registering route: {method.upper()} {path}")

                    handler_cls, _ = HANDLER_MAP["get_id"]
                    routes.append(getattr(web, method)(path, handler_cls(model, session_factory, pk_cols=pk_cols)))
                elif verb == "post":
                    handler_cls, route_fn = HANDLER_MAP["post"]
                    path, method = route_fn(table_name)
                    print(f"[DEBUG] Registering route: {method.upper()} {path}")
                    routes.append(getattr(web, method)(path, CustomCreateHandler(model, session_factory)))
                elif verb in HANDLER_MAP:
                    handler_cls, route_fn = HANDLER_MAP[verb]
                    pk_cols = [col.name for col in table.primary_key.columns]
                    if len(pk_cols) == 1:
                        pk_path = f"/{{{pk_cols[0]}}}"
                    else:
                        pk_path = "/" + "/".join([f"{{{col}}}" for col in pk_cols])
                    path = f"/{table_name}{pk_path}"
                    method = verb
                    print(f"[DEBUG] Registering route: {method.upper()} {path}")

                    if verb in ("put", "patch", "delete"):
                        routes.append(getattr(web, method)(path, handler_cls(model, session_factory, pk_cols=pk_cols)))
                    else:
                        routes.append(getattr(web, method)(path, handler_cls(model, session_factory)))

        instance = cls()
        instance.aiohttp_routes = routes
        instance.app.add_routes(routes)
        instance.engine = engine
        instance.session_factory = session_factory
        return instance
