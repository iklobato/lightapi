import json
from typing import Any, Dict, List, Optional, Type

from sqlalchemy import inspect as sql_inspect
from starlette.requests import Request

import typing  # noqa: F401
from .core import Response
from .database import Base


class RestEndpoint:
    def __init__(self, **kwargs):
        """
        Initialize endpoint instance and assign keyword arguments to attributes.
        Allows RestEndpoint subclasses to be instantiated with model fields.
        """
        for key, value in kwargs.items():
            setattr(self, key, value)
        # No need to call super() as we're not extending Base anymore
    
    # Class attributes that help with SQLAlchemy compatibility
    __tablename__ = None
    __table__ = None
    __abstract__ = True
    
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.__abstract__ = True
    
    id = None  # Will be defined by concrete classes

    class Configuration:
        http_method_names = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS']
        validator_class = None
        filter_class = None
        authentication_class = None
        caching_class = None
        caching_method_names = []
        pagination_class = None
        
    def _is_sa_model(self):
        """Check if this endpoint is a SQLAlchemy model (extends Base)"""
        return isinstance(self, Base)
        
    def _get_columns(self):
        """Get column names safely regardless of whether we're a SA model"""
        if self._is_sa_model():
            return [column.name for column in sql_inspect(self.__class__).columns]
        else:
            # For non-SA models, use instance attributes excluding methods and special attributes
            return [attr for attr in dir(self) 
                   if not attr.startswith('_') and not callable(getattr(self, attr))]

    def _setup(self, request, session):
        self.request = request
        self.session = session
        self._setup_auth()
        self._setup_cache()
        self._setup_filter()
        self._setup_validator()
        self._setup_pagination()

    def _setup_auth(self):
        config = getattr(self, 'Configuration', None)
        if (
            config
            and hasattr(config, 'authentication_class')
            and config.authentication_class
        ):
            self.auth = config.authentication_class()
            if not self.auth.authenticate(self.request):
                return Response({"error": "Authentication failed"}, status_code=401)

    def _setup_cache(self):
        config = getattr(self, 'Configuration', None)
        if config and hasattr(config, 'caching_class') and config.caching_class:
            self.cache = config.caching_class()

    def _setup_filter(self):
        config = getattr(self, 'Configuration', None)
        if config and hasattr(config, 'filter_class') and config.filter_class:
            self.filter = config.filter_class()

    def _setup_validator(self):
        config = getattr(self, 'Configuration', None)
        if config and hasattr(config, 'validator_class') and config.validator_class:
            self.validator = config.validator_class()

    def _setup_pagination(self):
        config = getattr(self, 'Configuration', None)
        if config and hasattr(config, 'pagination_class') and config.pagination_class:
            self.paginator = config.pagination_class()

    # Request data is now handled in the core handler

    def get(self, request):
        # Default implementation for GET - list all objects
        query = self.session.query(self.__class__)

        # Apply filtering if filter_class is set
        if hasattr(self, 'filter'):
            query = self.filter.filter_queryset(query, request)

        # Apply pagination if pagination_class is set
        if hasattr(self, 'paginator'):
            results = self.paginator.paginate(query)
        else:
            results = query.all()

        # Serialize results
        data = []
        for obj in results:
            item = {}
            # Use our helper method to safely get columns
            if self._is_sa_model():
                for column in sql_inspect(obj.__class__).columns:
                    item[column.name] = getattr(obj, column.name)
            else:
                for attr in self._get_columns():
                    item[attr] = getattr(obj, attr)
            data.append(item)

        return {"results": data}, 200

    def post(self, request):
        # Default implementation for POST - create object
        try:
            # Access data that was parsed in the handler
            data = getattr(request, 'data', {})

            # Validate data if validator_class is set
            if hasattr(self, 'validator'):
                validated_data = self.validator.validate(data)
                data = validated_data

            # Create instance
            instance = self.__class__(**data)
            self.session.add(instance)
            self.session.commit()

            result = {}
            # Use our helper method to safely get columns
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
        # Default implementation for PUT - update object
        try:
            object_id = request.path_params.get("id")
            if not object_id:
                return {"error": "ID is required"}, 400

            instance = (
                self.session.query(self.__class__).filter_by(id=object_id).first()
            )
            if not instance:
                return {"error": "Object not found"}, 404

            # Access data that was parsed in the handler
            data = getattr(request, 'data', {})

            # Validate data if validator_class is set
            if hasattr(self, 'validator'):
                validated_data = self.validator.validate(data)
                data = validated_data

            # Update instance
            for field, value in data.items():
                setattr(instance, field, value)

            self.session.commit()

            result = {}
            # Use our helper method to safely get columns
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
        # Default implementation for DELETE - delete object
        try:
            object_id = request.path_params.get("id")
            if not object_id:
                return {"error": "ID is required"}, 400

            instance = (
                self.session.query(self.__class__).filter_by(id=object_id).first()
            )
            if not instance:
                return {"error": "Object not found"}, 404

            self.session.delete(instance)
            self.session.commit()

            return {"result": "Object deleted"}, 204
        except Exception as e:
            self.session.rollback()
            return {"error": str(e)}, 400

    def options(self, request):
        # Default implementation for OPTIONS - return allowed methods
        return {"allowed_methods": self.Configuration.http_method_names}, 200


class Validator:
    def validate(self, data):
        validated_data = {}
        for field, value in data.items():
            validate_method = getattr(self, f"validate_{field}", None)
            if validate_method:
                validated_data[field] = validate_method(value)
            else:
                validated_data[field] = value
        return validated_data
