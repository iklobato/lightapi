import logging
from typing import Callable, Dict, Type
import os
import yaml
from sqlalchemy import create_engine, MetaData, Table, event
from sqlalchemy.pool import NullPool

from aiohttp import web
from sqlalchemy.exc import SQLAlchemyError, InvalidRequestError, ArgumentError
import base64
from sqlalchemy.sql.sqltypes import LargeBinary

from lightapi.database import Base, engine
from lightapi.handlers import (
    CreateHandler, ReadHandler, UpdateHandler, PatchHandler, DeleteHandler,
    RetrieveAllHandler, OptionsHandler, HeadHandler
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
        self, initialize_callback: Callable = None, initialize_arguments: Dict = None
    ) -> None:
        """
        Initializes the LightApi, sets up the aiohttp application, and creates tables in the database.

        Creates an empty list of routes and attempts to create database tables using SQLAlchemy. Logs the status of
        table creation.

        Raises:
            SQLAlchemyError: If there is an error during the creation of tables.
        """
        self.initialize(
            callback=initialize_callback, callback_arguments=initialize_arguments
        )
        self.app = web.Application()
        self.routes = []
        try:
            Base.metadata.create_all(bind=engine)
            logging.info(f"Tables successfully created and connected to {engine.url}")
        except SQLAlchemyError as e:
            logging.error(f"Error creating tables: {e}")

    def initialize(
        self, callback: Callable = None, callback_arguments: Dict = ()
    ) -> None:
        """
        Initializes the LightApi according to a callable
        """
        if not callback:
            return
        if not callable(callback):
            raise TypeError("Callback must be a callable object")
        logging.debug(f"Initializing LightApi with {callback_arguments}")
        callback(**callback_arguments)

    def register(self, handlers: Dict[str, Type]) -> None:
        """
        Registers routes for SQLAlchemy models or custom RestEndpoint classes.

        Args:
            handlers (Dict[str, Type]): A dictionary where keys are route paths and values are either:
                - SQLAlchemy model classes: Routes are created based on the model.
                - Custom RestEndpoint subclasses: Routes are generated from the RestEndpoint instance.

        Raises:
            TypeError: If a handler in the dictionary is neither a SQLAlchemy model nor a RestEndpoint subclass.
        """
        for path, handler in handlers.items():
            if issubclass(handler, Base):
                self.routes.extend(create_handler(handler))
            elif issubclass(handler, RestEndpoint):
                endpoint_instance = handler()
                self.routes.extend(endpoint_instance.routes)
            else:
                raise TypeError(
                    f"Handler for path {path} must be either a SQLAlchemy model or a RestEndpoint subclass."
                )
        for r in self.routes:
            logging.info(f"{r.method} {r.path}")

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
        # Load YAML config
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        # Resolve environment variables in database_url
        db_url = config["database_url"]
        if db_url.startswith("${") and db_url.endswith("}"):
            env_var = db_url[2:-1]
            db_url = os.environ.get(env_var)
            if not db_url:
                raise ValueError(f"Environment variable {env_var} not set for database_url")

        # Extract table names from config['tables']
        table_names = [t['name'] if isinstance(t, dict) else t for t in config['tables']]
        if engine is None:
            engine = create_engine(db_url, poolclass=NullPool)
            if db_url.startswith('sqlite'):
                @event.listens_for(engine, "connect")
                def set_sqlite_pragma(dbapi_connection, connection_record):
                    cursor = dbapi_connection.cursor()
                    cursor.execute("PRAGMA foreign_keys=ON")
                    cursor.close()
        metadata = MetaData()
        try:
            metadata.reflect(bind=engine, only=table_names)
        except (InvalidRequestError, ArgumentError) as e:
            raise ValueError(str(e))

        from sqlalchemy.orm import sessionmaker
        session_factory = sessionmaker(bind=engine)

        # Map HTTP verbs to handler classes and route patterns
        HANDLER_MAP = {
            "post": (CreateHandler, lambda t: (f"/{t}/", "post")),
            "get": (RetrieveAllHandler, lambda t: (f"/{t}/", "get")),
            "get_id": (ReadHandler, lambda t: (f"/{t}/{{id}}", "get")),
            "put": (UpdateHandler, lambda t: (f"/{t}/{{id}}", "put")),
            "patch": (PatchHandler, lambda t: (f"/{t}/{{id}}", "patch")),
            "delete": (DeleteHandler, lambda t: (f"/{t}/{{id}}", "delete")),
            "options": (OptionsHandler, lambda t: (f"/{t}/", "options")),
            "head": (HeadHandler, lambda t: (f"/{t}/", "head")),
        }

        # Prepare routes
        routes = []
        for table_cfg in config["tables"]:
            table_name = table_cfg["name"] if isinstance(table_cfg, dict) else table_cfg
            verbs = [v.lower() for v in table_cfg.get("crud", [])]
            if table_name not in metadata.tables:
                raise ValueError(f"Table '{table_name}' not found in database.")
            table = metadata.tables[table_name]

            # Dynamically create a model class for this table
            def serialize(self):
                import base64, datetime
                result = {}
                for col in self.__table__.columns:
                    val = getattr(self, col.name)
                    # If the column is a Date and val is a string, convert to datetime.date
                    if hasattr(col.type, 'python_type') and col.type.python_type is datetime.date and isinstance(val, str):
                        try:
                            val = datetime.date.fromisoformat(val)
                        except Exception:
                            pass
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
                    {"__table__": table, "__tablename__": table_name, "serialize": serialize}
                )
                # Set .pk attribute for primary key lookup (required by handlers)
                pk_cols = [col.name for col in table.primary_key.columns]
                if not pk_cols:
                    raise ValueError("no primary key")
                if len(pk_cols) == 1:
                    model.pk = table.c[pk_cols[0]]
                else:
                    model.pk = tuple(table.c[pk] for pk in pk_cols)
            except (ArgumentError, InvalidRequestError) as e:
                if isinstance(e, ArgumentError) and 'could not assemble any primary key' in str(e):
                    raise ValueError('no primary key')
                raise ValueError(str(e))

            # Dynamically create a custom CreateHandler if BLOB columns are present
            has_blob = any(isinstance(col.type, LargeBinary) for col in table.columns)
            if has_blob:
                class CustomCreateHandler(CreateHandler):
                    async def handle(self, db, request):
                        import datetime
                        data = await request.json()
                        for col in table.columns:
                            if isinstance(col.type, LargeBinary) and col.name in data and isinstance(data[col.name], str):
                                try:
                                    data[col.name] = base64.b64decode(data[col.name])
                                except Exception:
                                    pass  # Let DB raise error if not valid base64
                            # Convert string date/datetime fields to Python objects
                            if col.name in data:
                                val = data[col.name]
                                if hasattr(col.type, 'python_type'):
                                    if col.type.python_type is datetime.datetime:
                                        if isinstance(val, datetime.datetime):
                                            val = val.isoformat()
                                        if isinstance(val, str):
                                            try:
                                                data[col.name] = datetime.datetime.fromisoformat(val)
                                            except Exception:
                                                pass
                                    elif col.type.python_type is datetime.date:
                                        if isinstance(val, str):
                                            try:
                                                data[col.name] = datetime.date.fromisoformat(val)
                                            except Exception:
                                                pass
                                        # If already a datetime.date, leave as is
                            # Convert string date/datetime fields to Python objects
                            if col.name in data:
                                val = data[col.name]
                                if hasattr(col.type, 'python_type'):
                                    if col.type.python_type is datetime.datetime:
                                        if isinstance(val, datetime.datetime):
                                            val = val.isoformat()
                                        if isinstance(val, str):
                                            try:
                                                data[col.name] = datetime.datetime.fromisoformat(val)
                                            except Exception:
                                                pass
                                    elif col.type.python_type is datetime.date:
                                        if isinstance(val, datetime.date):
                                            val = val.isoformat()
                                        if isinstance(val, str):
                                            try:
                                                data[col.name] = datetime.date.fromisoformat(val)
                                            except Exception:
                                                pass
                        # Ensure Date columns are set to None if not present, so DB default is used
                        for col in table.columns:
                            if hasattr(col.type, 'python_type') and col.type.python_type is datetime.date:
                                if col.name not in data:
                                    data[col.name] = None
                            # Set Python-side defaults for all missing or None fields before model creation
                            if col.default is not None and col.default.is_scalar:
                                if col.name not in data or data[col.name] is None:
                                    data[col.name] = col.default.arg
                        item = self.model(**data)
                        # After model creation, set Python-side defaults for any None fields (redundant, but safe)
                        for col in table.columns:
                            if col.default is not None and col.default.is_scalar:
                                if getattr(item, col.name) is None:
                                    setattr(item, col.name, col.default.arg)
                        item = self.add_and_commit_item(db, item)
                        # Re-fetch the item from the DB using PK(s) to ensure all DB defaults are loaded
                        if hasattr(self.model, 'pk'):
                            if isinstance(self.model.pk, tuple):
                                filters = [col == getattr(item, col.name) for col in self.model.pk]
                                item = db.query(self.model).filter(*filters).first()
                            else:
                                item = db.query(self.model).filter(self.model.pk == getattr(item, self.model.pk.name)).first()
                        # Set Python-side defaults if still None
                        from sqlalchemy import inspect as _inspect
                        for col in self.model.__table__.columns:
                            if getattr(item, col.name) is None and col.default is not None and col.default.is_scalar:
                                setattr(item, col.name, col.default.arg)
                        if isinstance(item, __import__('aiohttp').web.Response):
                            return item
                        return self.json_response(item, status=201)
            else:
                CustomCreateHandler = CreateHandler

            # Register only the specified CRUD routes for this table
            for verb in verbs:
                if verb == "get":
                    # GET all
                    handler_cls, route_fn = HANDLER_MAP["get"]
                    path, method = route_fn(table_name)
                    routes.append(getattr(web, method)(path, handler_cls(model, session_factory)))
                    # GET by id
                    handler_cls, route_fn = HANDLER_MAP["get_id"]
                    if isinstance(model.pk, tuple):
                        pk_path = ",".join([f"{{{col.name}}}" for col in model.pk])
                        path = f"/{table_name}/{{id}}"
                    else:
                        path, method = route_fn(table_name)
                    routes.append(getattr(web, method)(path, handler_cls(model, session_factory)))
                elif verb == "post":
                    handler_cls, route_fn = HANDLER_MAP["post"]
                    path, method = route_fn(table_name)
                    routes.append(getattr(web, method)(path, CustomCreateHandler(model, session_factory)))
                elif verb in HANDLER_MAP:
                    handler_cls, route_fn = HANDLER_MAP[verb]
                    path, method = route_fn(table_name)
                    routes.append(getattr(web, method)(path, handler_cls(model, session_factory)))

        # Create the LightApi instance and set its routes
        instance = cls()
        instance.routes = routes
        instance.app.add_routes(routes)
        instance.engine = engine
        instance.session_factory = session_factory
        return instance
