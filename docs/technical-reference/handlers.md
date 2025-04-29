---
title: Request Handlers
---

This document describes the built-in request handler classes used by LightAPI to process HTTP requests for SQLAlchemy models.

## AbstractHandler

Base class for all model handlers (`lightapi.handlers.AbstractHandler`). Implements:

- `__call__(request, *args, **kwargs) -> web.Response` – Entry point, manages session lifecycle.
- `async def handle(self, db: Session, request: web.Request) -> web.Response` – Override in subclasses to implement logic.
- Utility methods:
  - `get_request_json(request)` – Parse JSON body.
  - `get_item_by_id(db, item_id)` – Fetch a record by primary key.
  - `add_and_commit_item(db, item)` – Add and commit a new record.
  - `delete_and_commit_item(db, item)` – Delete and commit removal.
  - `json_response(item, status=200)` – Return a JSONResponse.
  - `json_error_response(error_message, status=404)` – Return error JSON.

## CreateHandler

Handles `POST /<tablename>/` to create a new record.
```python
class CreateHandler(AbstractHandler):
    async def handle(self, db, request):
        data = await self.get_request_json(request)
        item = self.model(**data)
        item = self.add_and_commit_item(db, item)
        return self.json_response(item, status=201)
```

## ReadHandler

Handles `GET /<tablename>/` and `GET /<tablename>/{id}` to list or retrieve records.
```python
class ReadHandler(AbstractHandler):
    async def handle(self, db, request):
        if 'id' in request.match_info:
            item_id = int(request.match_info['id'])
            item = self.get_item_by_id(db, item_id)
            return self.json_response(item) if item else self.json_error_response('Not found')
        items = db.query(self.model).all()
        return self.json_response([i.serialize() for i in items])
```

## UpdateHandler

Handles `PUT /<tablename>/{id}` to fully replace a record.

## PatchHandler

Handles `PATCH /<tablename>/{id}` to partially update fields.

## DeleteHandler

Handles `DELETE /<tablename>/{id}` to remove a record.

## RetrieveAllHandler

Internal alias for listing all records (`HEAD` on list route).

## OptionsHandler

Handles `OPTIONS /<tablename>/` to return allowed HTTP methods.

## HeadHandler

Handles `HEAD /<tablename>/` to return headers for list endpoint without body.
