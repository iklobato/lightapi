import logging
from typing import Callable, Dict, Type

from aiohttp import web
from sqlalchemy.exc import SQLAlchemyError

from lightapi.database import Base, engine
from lightapi.handlers import create_handler
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
