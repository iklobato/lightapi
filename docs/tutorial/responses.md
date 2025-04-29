---
title: Working with Responses
---

LightAPI makes it easy to return HTTP responses from your endpoints with flexible JSON and custom response types.

## 1. Default JSON Responses

By default, any Python `dict`, list, or sequence returned from a handler is automatically converted into a JSON response with status code 200:

```python
async def get(self, request):
    return {"message": "Hello, World!"}
```

For methods that return `(body, status_code)` tuples, LightAPI sets both the JSON body and the HTTP status:

```python
async def post(self, request):
    data = request.data
    # ... create object ...
    return {"result": created_obj}, 201
```

## 2. Using the `Response` Class

You can also use the imported `Response` class for more control over headers, media type, and status:

```python
from lightapi import Response

async def delete(self, request):
    # ... delete logic ...
    return Response({"detail": "Deleted"}, status_code=204, headers={"X-Deleted": "true"})
```

## 3. Custom Headers

When using `Response`, you can include custom headers directly:

```python
return Response(
    {"message": "Created"}, 
    status_code=201, 
    headers={"Location": f"/items/{item.id}"}
)
```

## 4. Error Responses

LightAPI's `Response` and default handlers can generate error JSON:

```python
# Return a 404 Not Found
return {"error": "Item not found"}, 404

# Return a 400 Bad Request with detailed message
return Response({"detail": "Invalid input"}, status_code=400)
```

Unallowed HTTP methods automatically return a 405 Method Not Allowed with a JSON body indicating the error.

## 5. Advanced Response Types

Since LightAPI is built on Starlette, you can import and return any Starlette response directly for specialized use cases, such as:

- `PlainTextResponse` for text data
- `FileResponse` for serving files
- `StreamingResponse` for streaming content

```python
from starlette.responses import FileResponse

async def get_file(self, request):
    return FileResponse("/path/to/file.zip")
```

## 6. Working with Responses in Tests

When testing endpoints that return `Response` objects, you can access the original content via the `body` property:

```python
# In your test
response = endpoint.get(request)
assert response.body['message'] == 'Success'  # Access original Python dict
```

The `Response.body` property returns:
- The original Python object (dict, list, etc.) when accessed in tests
- Attempts to decode JSON data from bytes when necessary
- Falls back to the raw body when decoding fails

This makes it easier to write assertions in tests without having to manually decode JSON.
