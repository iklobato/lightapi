import datetime
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Type

from aiohttp import web
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session, sessionmaker

from lightapi.database import Base, SessionLocal


def create_handler(model: Type[Base], session_factory=SessionLocal) -> List[web.RouteDef]:
    """
    Creates a list of route handlers for the given model.
    Accepts a session_factory to use for DB sessions.
    """
    return [
        web.post(f"/{model.__tablename__}/", CreateHandler(model, session_factory)),
        web.get(f"/{model.__tablename__}/", RetrieveAllHandler(model, session_factory)),
        web.get(f"/{model.__tablename__}/{{id}}", ReadHandler(model, session_factory)),
        web.put(f"/{model.__tablename__}/{{id}}", UpdateHandler(model, session_factory)),
        web.delete(f"/{model.__tablename__}/{{id}}", DeleteHandler(model, session_factory)),
        web.patch(f"/{model.__tablename__}/{{id}}", PatchHandler(model, session_factory)),
    ]


@dataclass
class AbstractHandler(ABC):
    """
    Abstract base class for handling HTTP requests related to a specific model.

    Attributes:
        model (Base): The SQLAlchemy model class to operate on.
        session_factory (sessionmaker): The session factory to use for database operations.
    """

    model: Type[Base] = field(default=None)
    session_factory: sessionmaker = field(default=SessionLocal)

    @abstractmethod
    async def handle(self, db: Session, request: web.Request):
        """
        Abstract method to handle the HTTP request.

        Args:
            db (Session): The SQLAlchemy session for database operations.
            request (web.Request): The aiohttp web request object.

        Raises:
            NotImplementedError: If the method is not implemented by subclasses.
        """
        raise NotImplementedError("Method not implemented")

    async def __call__(self, request: web.Request, *args, **kwargs):
        """
        Calls the handler with the provided request.

        Args:
            request (web.Request): The aiohttp web request object.

        Returns:
            web.Response: The response returned by the handler.
        """
        db: Session = self.session_factory()
        try:
            return await self.handle(db, request)
        finally:
            db.close()

    async def get_request_json(self, request: web.Request):
        """
        Extracts JSON data from the request body.

        Args:
            request (web.Request): The aiohttp web request object.

        Returns:
            dict: The JSON data from the request body.
        """
        return await request.json()

    def get_item_by_id(self, db: Session, item_id: int):
        """
        Retrieves an item by its primary key.

        Args:
            db (Session): The SQLAlchemy session for database operations.
            item_id (int): The primary key of the item to retrieve.

        Returns:
            Base: The item retrieved from the database, or None if not found.
        """
        return db.query(self.model).filter(self.model.id == item_id).first()

    def add_and_commit_item(self, db: Session, item):
        """
        Adds and commits a new item to the database.

        Args:
            db (Session): The SQLAlchemy session for database operations.
            item (Base): The item to add and commit.

        Returns:
            Base: The item after committing to the database.
        """
        try:
            db.add(item)
            db.commit()
            db.refresh(item)

            if hasattr(self.model, "id"):
                if isinstance(self.model.id, tuple):
                    filters = [col == getattr(item, col.name) for col in self.model.id]
                    item = db.query(self.model).filter(*filters).first()
                else:
                    item = db.query(self.model).filter(self.model.id == getattr(item, self.model.id.name)).first()

            mapper = inspect(self.model)
            for col in self.model.__table__.columns:
                if getattr(item, col.name) is None and col.default is not None and col.default.is_scalar:
                    setattr(item, col.name, col.default.arg)

                if hasattr(col.type, "python_type"):
                    if col.type.python_type is datetime.datetime and isinstance(getattr(item, col.name), str):
                        try:
                            setattr(item, col.name, datetime.datetime.fromisoformat(getattr(item, col.name)))
                        except ValueError:
                            pass
                    elif col.type.python_type is datetime.date and isinstance(getattr(item, col.name), str):
                        try:
                            setattr(item, col.name, datetime.date.fromisoformat(getattr(item, col.name)))
                        except ValueError:
                            return self.json_error_response(f"Invalid date format for field '{col.name}'", status=400)
            return item
        except (IntegrityError, StatementError) as e:
            db.rollback()
            return self.json_error_response(str(e), status=409)

    def delete_and_commit_item(self, db: Session, item):
        """
        Deletes and commits the removal of an item from the database.

        Args:
            db (Session): The SQLAlchemy session for database operations.
            item (Base): The item to delete.
        """
        db.delete(item)
        db.commit()

    def json_response(self, item, status=200):
        """
        Creates a JSON response for the given item.

        Args:
            item (Base): The item to serialize and return.
            status (int, optional): The HTTP status code. Defaults to 200.

        Returns:
            web.Response: The JSON response containing the serialized item.
        """
        return web.json_response(item.serialize(), status=status)

    def json_error_response(self, error_message, status=404):
        """
        Creates a JSON response for an error message.

        Args:
            error_message (str): The error message to return.
            status (int, optional): The HTTP status code. Defaults to 404.

        Returns:
            web.Response: The JSON response containing the error message.
        """
        return web.json_response({"error": error_message}, status=status)

    def _parse_pk_value(self, value, col):
        try:
            if hasattr(col.type, "python_type") and col.type.python_type is int:
                return int(value)
        except Exception:
            pass
        return value


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class CreateHandler(AbstractHandler):
    """
    Handles HTTP POST requests to create a new item.
    """

    def __init__(self, model, session_factory=SessionLocal):
        super().__init__(model, session_factory)

    async def handle(self, db, request):
        """
        Processes the POST request to create and save a new item.

        Args:
            db (Session): The SQLAlchemy session for database operations.
            request (web.Request): The aiohttp web request object.

        Returns:
            web.Response: The JSON response containing the created item.
        """
        data = await self.get_request_json(request)

        missing = []
        for col in self.model.__table__.columns:
            if not col.nullable and col.default is None and not col.autoincrement:
                if col.name not in data:
                    missing.append(col.name)
        if missing:
            return web.json_response({"error": f"Missing required fields: {', '.join(missing)}"}, status=400)

        if "amount" in data and isinstance(data["amount"], (int, float)):
            if data["amount"] < 0:
                return web.json_response({"error": "Amount must be non-negative"}, status=400)

        for col in self.model.__table__.columns:
            if col.name in data:
                val = data[col.name]
                if hasattr(col.type, "python_type"):
                    if col.type.python_type is datetime.datetime and isinstance(val, str):
                        try:
                            data[col.name] = datetime.datetime.fromisoformat(val)
                        except ValueError:
                            return web.json_response({"error": f"Invalid datetime format for field '{col.name}'"}, status=400)
                    elif col.type.python_type is datetime.date and isinstance(val, str):
                        try:
                            data[col.name] = datetime.date.fromisoformat(val)
                        except ValueError:
                            return web.json_response({"error": f"Invalid date format for field '{col.name}'"}, status=400)
        item = self.model(**data)
        item = self.add_and_commit_item(db, item)
        if isinstance(item, web.Response):
            return item
        return self.json_response(item, status=201)


class ReadHandler(AbstractHandler):
    """
    Handles HTTP GET requests to retrieve one or all items.
    """

    def __init__(self, model, session_factory=SessionLocal, pk_cols=None):
        super().__init__(model, session_factory)
        self.pk_cols = pk_cols

    async def handle(self, db, request):
        """
        Processes the GET request to retrieve an item by ID or all items.

        Args:
            db (Session): The SQLAlchemy session for database operations.
            request (web.Request): The aiohttp web request object.

        Returns:
            web.Response: The JSON response containing the item(s) or an error message.
        """

        if self.pk_cols and len(self.pk_cols) > 1:
            pk_values = [request.match_info.get(col) for col in self.pk_cols]
            if None in pk_values:
                return web.json_response({"error": "Missing composite key(s)"}, status=400)
            filters = [
                getattr(self.model, col) == self._parse_pk_value(val, getattr(self.model, col)) for col, val in zip(self.pk_cols, pk_values)
            ]
            item = db.query(self.model).filter(*filters).first()
        else:
            pk_col = self.pk_cols[0] if self.pk_cols else "id"
            pk_value = request.match_info.get(pk_col)
            item = (
                db.query(self.model)
                .filter(getattr(self.model, pk_col) == self._parse_pk_value(pk_value, getattr(self.model, pk_col)))
                .first()
            )
        if not item:
            return web.json_response({"error": "Not found"}, status=404)
        return self.json_response(item, status=200)


class UpdateHandler(AbstractHandler):
    """
    Handles HTTP PUT requests to update an existing item.
    """

    def __init__(self, model, session_factory=SessionLocal, pk_cols=None):
        super().__init__(model, session_factory)
        self.pk_cols = pk_cols

    async def handle(self, db, request):
        """
        Processes the PUT request to update an existing item.

        Args:
            db (Session): The SQLAlchemy session for database operations.
            request (web.Request): The aiohttp web request object.

        Returns:
            web.Response: The JSON response containing the updated item or an error message.
        """
        if self.pk_cols and len(self.pk_cols) > 1:
            pk_values = [request.match_info.get(col) for col in self.pk_cols]
            if None in pk_values:
                return self.json_error_response("Missing composite key(s)", status=400)
            filters = [
                getattr(self.model, col) == self._parse_pk_value(val, getattr(self.model, col)) for col, val in zip(self.pk_cols, pk_values)
            ]
            item = db.query(self.model).filter(*filters).first()
        else:
            pk_col = self.pk_cols[0] if self.pk_cols else "id"
            pk_value = request.match_info.get(pk_col)
            item = (
                db.query(self.model)
                .filter(getattr(self.model, pk_col) == self._parse_pk_value(pk_value, getattr(self.model, pk_col)))
                .first()
            )
        if not item:
            return self.json_error_response("Item not found", status=404)

        data = await self.get_request_json(request)
        for key, value in data.items():
            setattr(item, key, value)

        item = self.add_and_commit_item(db, item)
        if isinstance(item, web.Response):
            return item
        return self.json_response(item, status=200)


class PatchHandler(AbstractHandler):
    """
    Handles HTTP PATCH requests to partially update an existing item.
    """

    def __init__(self, model, session_factory=SessionLocal, pk_cols=None):
        super().__init__(model, session_factory)
        self.pk_cols = pk_cols

    async def handle(self, db, request):
        """
        Processes the PATCH request to partially update an existing item.

        Args:
            db (Session): The SQLAlchemy session for database operations.
            request (web.Request): The aiohttp web request object.

        Returns:
            web.Response: The JSON response containing the updated item or an error message.
        """
        if self.pk_cols and len(self.pk_cols) > 1:
            pk_values = [request.match_info.get(col) for col in self.pk_cols]
            if None in pk_values:
                return self.json_error_response("Missing composite key(s)", status=400)
            filters = [
                getattr(self.model, col) == self._parse_pk_value(val, getattr(self.model, col)) for col, val in zip(self.pk_cols, pk_values)
            ]
            item = db.query(self.model).filter(*filters).first()
        else:
            pk_col = self.pk_cols[0] if self.pk_cols else "id"
            pk_value = request.match_info.get(pk_col)
            item = (
                db.query(self.model)
                .filter(getattr(self.model, pk_col) == self._parse_pk_value(pk_value, getattr(self.model, pk_col)))
                .first()
            )
        if not item:
            return self.json_error_response("Item not found", status=404)

        data = await self.get_request_json(request)

        for col in self.model.__table__.columns:
            if col.name in data:
                val = data[col.name]
                if hasattr(col.type, "python_type"):
                    if col.type.python_type is datetime.datetime and isinstance(val, str):
                        try:
                            data[col.name] = datetime.datetime.fromisoformat(val)
                        except ValueError:
                            return web.json_response({"error": f"Invalid datetime format for field '{col.name}'"}, status=400)
                    elif col.type.python_type is datetime.date and isinstance(val, str):
                        try:
                            data[col.name] = datetime.date.fromisoformat(val)
                        except ValueError:
                            return web.json_response({"error": f"Invalid date format for field '{col.name}'"}, status=400)
        for key, value in data.items():
            setattr(item, key, value)

        item = self.add_and_commit_item(db, item)
        if isinstance(item, web.Response):
            return item
        return self.json_response(item, status=200)


class DeleteHandler(AbstractHandler):
    """
    Handles HTTP DELETE requests to delete an existing item.
    """

    def __init__(self, model, session_factory=SessionLocal, pk_cols=None):
        super().__init__(model, session_factory)
        self.pk_cols = pk_cols

    async def handle(self, db, request):
        """
        Processes the DELETE request to remove an existing item.

        Args:
            db (Session): The SQLAlchemy session for database operations.
            request (web.Request): The aiohttp web request object.

        Returns:
            web.Response: An empty response with status 204 if the item is deleted.
        """
        if self.pk_cols and len(self.pk_cols) > 1:
            pk_values = [request.match_info.get(col) for col in self.pk_cols]
            if None in pk_values:
                return self.json_error_response("Missing composite key(s)", status=400)
            filters = [
                getattr(self.model, col) == self._parse_pk_value(val, getattr(self.model, col)) for col, val in zip(self.pk_cols, pk_values)
            ]
            item = db.query(self.model).filter(*filters).first()
        else:
            pk_col = self.pk_cols[0] if self.pk_cols else "id"
            pk_value = request.match_info.get(pk_col)
            item = (
                db.query(self.model)
                .filter(getattr(self.model, pk_col) == self._parse_pk_value(pk_value, getattr(self.model, pk_col)))
                .first()
            )
        if not item:
            return self.json_error_response("Item not found", status=404)

        self.delete_and_commit_item(db, item)
        return web.Response(status=204)


class RetrieveAllHandler(AbstractHandler):
    """
    Handles HTTP GET requests to retrieve all items.
    """

    def __init__(self, model, session_factory=SessionLocal):
        super().__init__(model, session_factory)

    async def handle(self, db, request):
        """
        Processes the GET request to retrieve all items.

        Args:
            db (Session): The SQLAlchemy session for database operations.
            request (web.Request): The aiohttp web request object.

        Returns:
            web.Response: The JSON response containing all items.
        """
        items = db.query(self.model).all()
        response = [item.serialize() for item in items]
        return web.json_response(response, status=200, dumps=json.dumps)
