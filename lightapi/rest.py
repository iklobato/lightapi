import json
import typing  # noqa: F401
from typing import Any, Dict, List, Optional, Type

from sqlalchemy import inspect as sql_inspect
from starlette.requests import Request

from .core import Response
from .database import Base, SessionLocal


class RestEndpoint:
    """
    Base class for REST API endpoints.

    RestEndpoint provides a complete implementation of a REST resource,
    with built-in support for common HTTP methods, SQLAlchemy integration,
    data validation, filtering, authentication, caching, and pagination.

    Subclasses can customize behavior through the inner Configuration class
    and by overriding HTTP method handlers.

    Attributes:
        __tablename__: SQLAlchemy table name.
        __table__: SQLAlchemy table metadata.
        __abstract__: Whether this class is an abstract base class.
        id: Primary key field (defined by concrete subclasses).
    """

    def __init__(self, **kwargs):
        """
        Initialize an endpoint instance and assign keyword arguments to attributes.

        Args:
            **kwargs: Arbitrary keyword arguments that will be set as instance attributes.
        """
        for key, value in kwargs.items():
            setattr(self, key, value)

    __tablename__ = None
    __table__ = None
    __abstract__ = True

    def __init_subclass__(cls, **kwargs):
        """
        Configure subclasses of RestEndpoint.

        Args:
            **kwargs: Arbitrary keyword arguments.
        """
        super().__init_subclass__(**kwargs)

        # Only mark as abstract if not a SQLAlchemy model class
        if hasattr(cls, "__tablename__") and cls.__tablename__:
            cls.__abstract__ = False
        else:
            cls.__abstract__ = True

    id = None

    @property
    def routes(self):
        """
        Get the routes for this endpoint.

        Returns:
            List of web.RouteDef objects associated with this endpoint.
        """
        from aiohttp import web

        if hasattr(self, "__tablename__") and self.__tablename__:
            base_path = f"/{self.__tablename__}"
        else:
            base_path = f"/{self.__class__.__name__.lower()}"

        async def endpoint_handler(request):
            session = SessionLocal()

            try:

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
                        except:
                            self._data = {}
                        return self._data

                    @property
                    def data(self):
                        import asyncio

                        loop = asyncio.get_event_loop()
                        return loop.run_until_complete(self.get_data())

                adapted_request = RequestAdapter(request)
                setup_result = self._setup(adapted_request, session)
                if setup_result:
                    return setup_result

                method = request.method.lower()
                if hasattr(self, method):
                    result_data, status_code = getattr(self, method)(adapted_request)
                    return web.json_response(result_data, status=status_code)
                else:
                    return web.json_response({"error": "Method not allowed"}, status=405)
            finally:
                session.close()

        return [
            web.get(base_path, endpoint_handler),
            web.post(base_path, endpoint_handler),
            web.get(f"{base_path}/{{id}}", endpoint_handler),
            web.put(f"{base_path}/{{id}}", endpoint_handler),
            web.delete(f"{base_path}/{{id}}", endpoint_handler),
            web.patch(f"{base_path}/{{id}}", endpoint_handler),
            web.options(base_path, endpoint_handler),
        ]

    class Configuration:
        """
        Configuration options for the RestEndpoint.

        Attributes:
            http_method_names: List of allowed HTTP methods.
            validator_class: Class for validating request data.
            filter_class: Class for filtering querysets.
            authentication_class: Class for authenticating requests.
            caching_class: Class for caching responses.
            caching_method_names: List of methods to cache.
            pagination_class: Class for paginating querysets.
        """

        http_method_names = ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
        validator_class = None
        filter_class = None
        authentication_class = None
        caching_class = None
        caching_method_names = []
        pagination_class = None

    def _is_sa_model(self):
        """
        Check if this endpoint is a SQLAlchemy model (extends Base).

        Returns:
            bool: True if the endpoint is a SQLAlchemy model, False otherwise.
        """
        return hasattr(self.__class__, "__tablename__") and self.__class__.__tablename__ is not None

    def _get_columns(self):
        """
        Get column names safely regardless of whether we're a SQLAlchemy model.

        Returns:
            list: List of column/attribute names for this endpoint.
        """
        if self._is_sa_model():
            return [column.name for column in sql_inspect(self.__class__).columns]
        else:
            return [attr for attr in dir(self) if not attr.startswith("_") and not callable(getattr(self, attr))]

    def _setup(self, request, session):
        """
        Set up the endpoint for a request.

        Args:
            request: The HTTP request.
            session: The database session.

        Returns:
            Response: Error response if setup fails, None otherwise.
        """
        self.request = request
        self.session = session

        # Handle authentication first
        auth_response = self._setup_auth()
        if auth_response:
            return auth_response

        self._setup_cache()
        self._setup_filter()
        self._setup_validator()
        self._setup_pagination()

        return None

    def _setup_auth(self):
        """
        Set up authentication for the endpoint.

        Returns:
            Response: Authentication error response if authentication fails, None otherwise.
        """
        config = getattr(self, "Configuration", None)
        if config and hasattr(config, "authentication_class") and config.authentication_class:
            self.auth = config.authentication_class()
            if not self.auth.authenticate(self.request):
                return Response({"error": "not allowed"}, status_code=403)

    def _setup_cache(self):
        config = getattr(self, "Configuration", None)
        if config and hasattr(config, "caching_class") and config.caching_class:
            self.cache = config.caching_class()

    def _setup_filter(self):
        config = getattr(self, "Configuration", None)
        if config and hasattr(config, "filter_class") and config.filter_class:
            self.filter = config.filter_class()

    def _setup_validator(self):
        config = getattr(self, "Configuration", None)
        if config and hasattr(config, "validator_class") and config.validator_class:
            self.validator = config.validator_class()

    def _setup_pagination(self):
        config = getattr(self, "Configuration", None)
        if config and hasattr(config, "pagination_class") and config.pagination_class:
            self.paginator = config.pagination_class()

    def get(self, request):
        """
        Handle GET requests.

        Retrieves a list of objects from the database, applying filtering and pagination
        if configured.

        Args:
            request: The HTTP request.

        Returns:
            tuple: A tuple containing the response data and status code.
        """
        query = self.session.query(self.__class__)

        # Check for ID filter in query parameters
        object_id = None
        if hasattr(request, "query_params"):
            object_id = request.query_params.get("id")

        # Filter by ID if provided
        if object_id:
            query = query.filter_by(id=object_id)

        if hasattr(self, "filter"):
            query = self.filter.filter_queryset(query, request)

        if hasattr(self, "paginator"):
            results = self.paginator.paginate(query)
        else:
            results = query.all()

        data = []
        for obj in results:
            item = {}
            if self._is_sa_model():
                for column in sql_inspect(obj.__class__).columns:
                    item[column.name] = getattr(obj, column.name)
            else:
                for attr in self._get_columns():
                    item[attr] = getattr(obj, attr)
            data.append(item)

        return {"results": data}, 200

    def post(self, request):
        """
        Handle POST requests.

        Creates a new object in the database using the request data.
        Validates the data if a validator is configured.

        Args:
            request: The HTTP request.

        Returns:
            tuple: A tuple containing the response data and status code.
        """
        try:
            data = getattr(request, "data", {})

            if hasattr(self, "validator"):
                validated_data = self.validator.validate(data)
                data = validated_data

            instance = self.__class__(**data)
            self.session.add(instance)
            self.session.commit()

            result = {}
            if self._is_sa_model():
                for column in sql_inspect(instance.__class__).columns:
                    result[column.name] = getattr(instance, column.name)
            else:
                for attr in self._get_columns():
                    result[attr] = getattr(instance, attr)

            return {"result": result}, 201
        except Exception as e:
            self.session.rollback()
            return {"error": str(e)}, 400

    def put(self, request):
        """
        Handle PUT requests.

        Updates an existing object in the database using the request data.
        Validates the data if a validator is configured.

        Args:
            request: The HTTP request.

        Returns:
            tuple: A tuple containing the response data and status code.
        """
        try:
            # First try to get ID from path parameters
            object_id = request.path_params.get("id")

            # If not found, try query parameters
            if not object_id and hasattr(request, "query_params"):
                object_id = request.query_params.get("id")

            if not object_id:
                return {"error": "ID is required"}, 400

            instance = self.session.query(self.__class__).filter_by(id=object_id).first()
            if not instance:
                return {"error": "Object not found"}, 404

            data = getattr(request, "data", {})

            if hasattr(self, "validator"):
                validated_data = self.validator.validate(data)
                data = validated_data

            for field, value in data.items():
                setattr(instance, field, value)

            self.session.commit()

            result = {}
            if self._is_sa_model():
                for column in sql_inspect(instance.__class__).columns:
                    result[column.name] = getattr(instance, column.name)
            else:
                for attr in self._get_columns():
                    result[attr] = getattr(instance, attr)

            return {"result": result}, 200
        except Exception as e:
            self.session.rollback()
            return {"error": str(e)}, 400

    def delete(self, request):
        """
        Handle DELETE requests.

        Deletes an object from the database.

        Args:
            request: The HTTP request.

        Returns:
            tuple: A tuple containing the response data and status code.
        """
        try:
            # First try to get ID from path parameters
            object_id = request.path_params.get("id")

            # If not found, try query parameters
            if not object_id and hasattr(request, "query_params"):
                object_id = request.query_params.get("id")

            if not object_id:
                return {"error": "ID is required"}, 400

            instance = self.session.query(self.__class__).filter_by(id=object_id).first()
            if not instance:
                return {"error": "Object not found"}, 404

            self.session.delete(instance)
            self.session.commit()

            return {"result": "Object deleted"}, 204
        except Exception as e:
            self.session.rollback()
            return {"error": str(e)}, 400

    def patch(self, request):
        """
        Handle PATCH requests.

        Partially updates an existing object in the database using the request data.
        Validates the data if a validator is configured.

        Args:
            request: The HTTP request.

        Returns:
            tuple: A tuple containing the response data and status code.
        """
        try:
            # First try to get ID from path parameters
            object_id = request.path_params.get("id")

            # If not found, try query parameters
            if not object_id and hasattr(request, "query_params"):
                object_id = request.query_params.get("id")

            if not object_id:
                return {"error": "ID is required"}, 400

            instance = self.session.query(self.__class__).filter_by(id=object_id).first()
            if not instance:
                return {"error": "Object not found"}, 404

            data = getattr(request, "data", {})

            if hasattr(self, "validator"):
                validated_data = self.validator.validate(data)
                data = validated_data

            for field, value in data.items():
                setattr(instance, field, value)

            self.session.commit()

            result = {}
            if self._is_sa_model():
                for column in sql_inspect(instance.__class__).columns:
                    result[column.name] = getattr(instance, column.name)
            else:
                for attr in self._get_columns():
                    result[attr] = getattr(instance, attr)

            return {"result": result}, 200
        except Exception as e:
            self.session.rollback()
            return {"error": str(e)}, 400

    def options(self, request):
        """
        Handle OPTIONS requests.

        Returns the list of allowed HTTP methods for this endpoint.

        Args:
            request: The HTTP request.

        Returns:
            tuple: A tuple containing the response data and status code.
        """
        return {"allowed_methods": self.Configuration.http_method_names}, 200

    def __getattr__(self, name):
        """
        Return NotImplemented for unspecified HTTP methods.

        Args:
            name (str): The name of the attribute being accessed.

        Returns:
            NotImplemented: If the method is not implemented.
        """
        if name.upper() in self.Configuration.http_method_names:
            return lambda *args, **kwargs: ("Method not implemented", 501)
        raise AttributeError(f"'{self.__class__.__name__}' object has no attribute '{name}'")


class Validator:
    """
    Base class for request data validation.

    Provides a mechanism for validating and transforming request data
    through per-field validation methods. Subclasses can implement
    validate_<field_name> methods to validate and transform specific fields.
    """

    def validate(self, data):
        """
        Validate and transform request data.

        For each field in the data, looks for a validate_<field_name> method
        and calls it to validate and transform the field value.

        Args:
            data: The data to validate.

        Returns:
            dict: The validated and transformed data.
        """
        validated_data = {}
        for field, value in data.items():
            validate_method = getattr(self, f"validate_{field}", None)
            if validate_method:
                validated_data[field] = validate_method(value)
            else:
                validated_data[field] = value
        return validated_data
