---
title: Custom Middleware
---

LightAPI provides a middleware system that lets you process requests and responses globally before and after your endpoint logic.

## 1. Creating Middleware

1. Subclass the `Middleware` base class:

```python
from lightapi.core import Middleware, Response

class TimingMiddleware(Middleware):
    def process(self, request, response):
        import time
        # Before handling (response is None)
        if response is None:
            request.start_time = time.time()
            return None

        # After handling
        duration = time.time() - request.start_time
        response.headers['X-Process-Time'] = str(round(duration, 4))
        return response
```

- The `process` method is called twice per request:
  - **Before** the endpoint: `response` is `None`.
  - **After** the endpoint: `response` is the generated response.
- To short-circuit the request (e.g., authentication), return a `Response` directly.

## 2. Registering Middleware

Add your middleware classes to the application via `add_middleware`:

```python
from lightapi import LightApi
from app.middleware import TimingMiddleware

app = LightApi()
app.add_middleware([TimingMiddleware])
app.register({'/items': Item})
app.run()
```

All incoming requests and outgoing responses will pass through your middleware in the order they are registered.
