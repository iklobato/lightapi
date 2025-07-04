import asyncio
import base64
import datetime
import inspect
import logging
import os
from typing import Any, Callable, Dict, Type, Union

import yaml
from aiohttp import web
from sqlalchemy import MetaData, create_engine, event
from sqlalchemy.exc import ArgumentError, InvalidRequestError, SQLAlchemyError
from sqlalchemy.orm.session import sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy.sql.sqltypes import LargeBinary

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
        routes (List[web.RouteDef]): A list of route definitions to be added to the application.

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
        initialize_callback: Callable = None,
        initialize_arguments: Dict = None,
        swagger_title: str = "LightAPI Documentation",
        swagger_version: str = "1.0.0",
        swagger_description: str = "API documentation",
        enable_swagger: bool = False,
    ) -> None:
        """
        Initializes the LightApi, sets up the aiohttp application, and creates tables in the database.

        Creates an empty list of routes and attempts to create database tables using SQLAlchemy. Logs the status of
        table creation.

        Raises:
            SQLAlchemyError: If there is an error during the creation of tables.
        """
        self.enable_swagger = enable_swagger
        if self.enable_swagger:
            from lightapi.swagger import (
                SwaggerGenerator,  # Lazy import to avoid circular dependency
            )

            self.swagger_generator = SwaggerGenerator(
                title=swagger_title,
                version=swagger_version,
                description=swagger_description,
            )
        self.initialize(callback=initialize_callback, callback_arguments=initialize_arguments)
        self.app = web.Application()
        self.routes = []
        Base.metadata.create_all(bind=engine)
        logging.info(f"Tables successfully created and connected to {engine.url}")

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
        """
        Register a model or endpoint class/instance. For RestEndpoint classes, use __tablename__ if present, otherwise the class name as the endpoint path.
        """
        initial_route_count = len(self.routes)

        if inspect.isclass(handler) and issubclass(handler, RestEndpoint):
            tablename = getattr(handler, "__tablename__", None)
            if tablename:
                path = f"/{tablename.lower()}"
            else:
                path = f"/{handler.__name__.lower()}"
            endpoint_instance = handler()
            self.routes.extend(self._create_rest_endpoint_routes(endpoint_instance, path))
        elif inspect.isclass(handler) and hasattr(handler, "__tablename__") and getattr(handler, "__tablename__") is not None:
            self.routes.extend(create_handler(handler))
        else:
            handler_name = f"class {handler.__name__}" if inspect.isclass(handler) else type(handler).__name__
            raise TypeError(f"Handler must be a SQLAlchemy model class or RestEndpoint class. Got: {handler_name}")

        new_routes = self.routes[initial_route_count:]
        max_method_length = max(len(route.method) for route in new_routes if hasattr(route, "method")) if new_routes else 0
        grouped_routes = {}
        for route in new_routes:
            if hasattr(route, "method") and hasattr(route, "path"):
                base_path = route.path.split("/")[1]
                if base_path not in grouped_routes:
                    grouped_routes[base_path] = []

                if route.path.endswith("/") and route.path[:-1] in [r[1] for r in grouped_routes[base_path]]:
                    continue
                grouped_routes[base_path].append((route.method, route.path))
        for base_path, routes in grouped_routes.items():
            logging.info(f"Routes for /{base_path}:")
            for method, path in routes:
                logging.info(f"  {method.ljust(max_method_length)} {path}")

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
                    self.path_params = aiohttp_request.match_info
                    self.query_params = aiohttp_request.query

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
                    loop = asyncio.get_event_loop()
                    return loop.run_until_complete(self.get_data())

            adapted_request = RequestAdapter(request)
            setup_result = endpoint_instance._setup(adapted_request, session)
            if setup_result:
                session.close()
                return setup_result
            method = request.method.lower()
            if hasattr(endpoint_instance, method):
                result_data, status_code = getattr(endpoint_instance, method)(adapted_request)
                session.close()
                return web.json_response(result_data, status=status_code)
            session.close()
            return web.json_response({"error": "Method not allowed"}, status=405)

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

    def run(self, host: str = "0.0.0.0", port: int = 8000) -> None:
        """
        Starts the web application and begins listening for incoming requests.

        Args:
            host (str): The hostname or IP address to bind the server to. Defaults to '0.0.0.0'.
            port (int): The port number on which the server will listen. Defaults to 8000.
        """
        self.app.add_routes(self.routes)

        web.run_app(self.app, host=host, port=port)

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
        metadata.reflect(bind=engine, only=table_names)

        session_factory = sessionmaker(bind=engine)

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
                model = type(
                    table_name.capitalize(),
                    (Base,),
                    {
                        "__table__": table,
                        "__tablename__": table_name,
                        "serialize": serialize,
                    },
                )

                pk_cols = [col.name for col in table.primary_key.columns]
                if not pk_cols:
                    raise ValueError("no primary key")
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
                        if isinstance(item, __import__("aiohttp").web.Response):
                            return item
                        return self.json_response(item, status=201)

            else:
                CustomCreateHandler = CreateHandler

            for verb in verbs:
                if verb == "get":
                    handler_cls, route_fn = HANDLER_MAP["get"]
                    path, method = route_fn(table_name)
                    print(f"[DEBUG] Registering route: {method.upper()} {path}")
                    routes.append(getattr(web, method)(path, handler_cls(model, session_factory)))
                    handler_cls, route_fn = HANDLER_MAP["get_id"]
                    if isinstance(model.id, tuple):
                        path = f"/{table_name}/{{id}}"
                    else:
                        path, method = route_fn(table_name)
                    print(f"[DEBUG] Registering route: {method.upper()} {path}")
                    routes.append(getattr(web, method)(path, handler_cls(model, session_factory)))
                elif verb == "post":
                    handler_cls, route_fn = HANDLER_MAP["post"]
                    path, method = route_fn(table_name)
                    print(f"[DEBUG] Registering route: {method.upper()} {path}")
                    routes.append(getattr(web, method)(path, CustomCreateHandler(model, session_factory)))
                elif verb in HANDLER_MAP:
                    handler_cls, route_fn = HANDLER_MAP[verb]
                    path, method = route_fn(table_name)
                    print(f"[DEBUG] Registering route: {method.upper()} {path}")
                    routes.append(getattr(web, method)(path, handler_cls(model, session_factory)))

        instance = cls()
        instance.routes = routes
        instance.app.add_routes(routes)
        instance.engine = engine
        instance.session_factory = session_factory
        return instance
