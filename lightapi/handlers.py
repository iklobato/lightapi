import datetime
import json
import logging
import re
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Type

from dateutil import parser
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session, sessionmaker
from starlette.responses import JSONResponse, Response

from lightapi.database import Base, SessionLocal


def create_handler(model: Type[Base], session_factory=SessionLocal):
    """Creates a list of route handlers for the given model.

    Args:
        model: The SQLAlchemy model class to create handlers for.
        session_factory: The session factory to use for database connections.
    """
    # This function is no longer the primary way of creating routes,
    # but we'll keep it for now and adapt it.
    # The actual route creation will be handled in LightApi.register
    pass


@dataclass
class AbstractHandler(ABC):
    """Abstract base class for handling HTTP requests related to a specific model."""

    model: Type[Base] = field(default=None)
    session_factory: sessionmaker = field(default=SessionLocal)

    @abstractmethod
    async def handle(self, db: Session, request):
        """Abstract method to handle the HTTP request.

        Args:
            db: The SQLAlchemy session for database operations.
            request: The Starlette request object.
        """
        raise NotImplementedError("Method not implemented")

    async def __call__(self, scope, receive, send):
        """Makes the handler a callable ASGI application.

        Args:
            scope: The ASGI scope.
            receive: The ASGI receive channel.
            send: The ASGI send channel.
        """
        from starlette.requests import Request
        request = Request(scope, receive)
        db: Session = self.session_factory()
        try:
            response = await self.handle(db, request)
            await response(scope, receive, send)
        except Exception as e:
            logging.error(f"Unhandled exception: {e}\n{traceback.format_exc()}")
            # TODO: check for debug mode from app config
            response = JSONResponse(
                {"error": "Internal Server Error", "message": str(e), "traceback": traceback.format_exc()},
                status_code=500,
            )
            await response(scope, receive, send)
        finally:
            db.close()

    async def get_request_json(self, request):
        """Extracts JSON data from the request body.

        Args:
            request: The Starlette request object.

        Returns:
            A dictionary of the JSON body.
        """
        return await request.json()

    def add_and_commit_item(self, db: Session, item):
        """Adds and commits a new item to the database.

        Args:
            db: The SQLAlchemy session for database operations.
            item: The item to add and commit.

        Returns:
            The item after committing to the database, or a JSONResponse on error.
        """
        try:
            db.add(item)
            db.commit()
            db.refresh(item)
            return item
        except IntegrityError as e:
            db.rollback()
            if "UNIQUE constraint failed" in str(e.orig) or "Duplicate entry" in str(e.orig):
                match = re.search(r"failed: ([\w\.]+)", str(e.orig))
                if match:
                    column = match.group(1)
                    return self.json_error_response(f"Unique constraint violated for {column}.", status=409)
                return self.json_error_response("Unique constraint violated.", status=409)
            return self.json_error_response(f"Database integrity error: {e.orig}", status=400)
        except StatementError as e:
            db.rollback()
            return self.json_error_response(f"Database statement error: {e.orig}", status=400)

    def delete_and_commit_item(self, db: Session, item):
        """Deletes and commits the removal of an item from the database.

        Args:
            db: The SQLAlchemy session for database operations.
            item: The item to delete.
        """
        db.delete(item)
        db.commit()

    def json_response(self, item, status=200):
        """Creates a JSON response for the given item.

        Args:
            item: The item to serialize and return.
            status: The HTTP status code.

        Returns:
            A Starlette JSONResponse.
        """
        return JSONResponse(item.serialize(), status_code=status)

    def json_error_response(self, error_details, status=404):
        """Creates a JSON response for an error message.

        Args:
            error_details: The error message or a dict with details.
            status: The HTTP status code.

        Returns:
            A Starlette JSONResponse.
        """
        if isinstance(error_details, str):
            error_payload = {"error": error_details}
        else:
            error_payload = error_details
        return JSONResponse(error_payload, status_code=status)

    def _parse_pk_value(self, value, col):
        """Parses a primary key value to the correct type.

        Args:
            value: The value to parse.
            col: The SQLAlchemy column object.

        Returns:
            The parsed value.
        """
        try:
            if hasattr(col.type, "python_type") and col.type.python_type is int:
                return int(value)
        except Exception:
            pass
        return value


class CreateHandler(AbstractHandler):
    """Handles HTTP POST requests to create a new item."""

    async def handle(self, db, request):
        """Processes the POST request to create and save a new item.

        Args:
            db: The SQLAlchemy session for database operations.
            request: The Starlette request object.

        Returns:
            A Starlette JSONResponse containing the created item or an error.
        """
        data = await self.get_request_json(request)

        missing = []
        for col in self.model.__table__.columns:
            if not col.nullable and col.default is None and not col.autoincrement:
                if col.name not in data:
                    missing.append(col.name)
        if missing:
            return JSONResponse({"error": f"Missing required fields: {', '.join(missing)}"}, status_code=400)

        for col in self.model.__table__.columns:
            if col.name in data:
                val = data[col.name]
                if hasattr(col.type, "python_type"):
                    if col.type.python_type is datetime.datetime and isinstance(val, str):
                        try:
                            data[col.name] = parser.parse(val)
                        except ValueError:
                            return JSONResponse({"error": f"Invalid datetime format for field '{col.name}'"}, status_code=400)
                    elif col.type.python_type is datetime.date and isinstance(val, str):
                        try:
                            data[col.name] = parser.parse(val).date()
                        except ValueError:
                            return JSONResponse({"error": f"Invalid date format for field '{col.name}'"}, status_code=400)
        
        item = self.model(**data)
        item = self.add_and_commit_item(db, item)
        if isinstance(item, JSONResponse):
            return item
        return self.json_response(item, status=201)


class ReadHandler(AbstractHandler):
    """Handles HTTP GET requests to retrieve a single item."""

    async def handle(self, db, request):
        """Processes the GET request to retrieve an item by ID.

        Args:
            db: The SQLAlchemy session for database operations.
            request: The Starlette request object.

        Returns:
            A Starlette JSONResponse containing the item or a 404 error.
        """
        pk_col = "id" # Assuming 'id' for now
        pk_value = request.path_params.get(pk_col)
        
        item = db.query(self.model).filter(getattr(self.model, pk_col) == pk_value).first()
        
        if not item:
            return self.json_error_response(f"{self.model.__name__} with id {pk_value} not found", status=404)
        return self.json_response(item, status=200)


class RetrieveAllHandler(AbstractHandler):
    """Handles HTTP GET requests to retrieve all items."""

    async def handle(self, db, request):
        """Processes the GET request to retrieve all items.

        Args:
            db: The SQLAlchemy session for database operations.
            request: The Starlette request object.

        Returns:
            A Starlette JSONResponse containing all items.
        """
        items = db.query(self.model).all()
        response = [item.serialize() for item in items]
        return JSONResponse(response, status_code=200)


class UpdateHandler(AbstractHandler):
    """Handles HTTP PUT requests to update an existing item."""

    async def handle(self, db, request):
        """Processes the PUT request to update an existing item.

        Args:
            db: The SQLAlchemy session for database operations.
            request: The Starlette request object.

        Returns:
            A Starlette JSONResponse containing the updated item or an error.
        """
        pk_col = "id"
        pk_value = request.path_params.get(pk_col)
        
        item = db.query(self.model).filter(getattr(self.model, pk_col) == pk_value).first()
        if not item:
            return self.json_error_response(f"{self.model.__name__} with id {pk_value} not found", status=404)

        data = await self.get_request_json(request)
        for key, value in data.items():
            setattr(item, key, value)

        item = self.add_and_commit_item(db, item)
        if isinstance(item, JSONResponse):
            return item
        return self.json_response(item, status=200)


class PatchHandler(UpdateHandler):
    """Handles HTTP PATCH requests to partially update an existing item."""
    pass


class DeleteHandler(AbstractHandler):
    """Handles HTTP DELETE requests to delete an existing item."""

    async def handle(self, db, request):
        """Processes the DELETE request to remove an existing item.

        Args:
            db: The SQLAlchemy session for database operations.
            request: The Starlette request object.

        Returns:
            A Starlette Response with status 204.
        """
        pk_col = "id"
        pk_value = request.path_params.get(pk_col)
        
        item = db.query(self.model).filter(getattr(self.model, pk_col) == pk_value).first()
        if not item:
            return self.json_error_response(f"{self.model.__name__} with id {pk_value} not found", status=404)

        self.delete_and_commit_item(db, item)
        return Response(status_code=204)
