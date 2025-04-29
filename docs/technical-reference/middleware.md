---
title: Middleware Reference
---

## Middleware (lightapi.core.Middleware)

The `Middleware` base class enables global request/response processing within LightAPI.

### Class Definition

```python
class Middleware:
    def process(self, request, response):
        """
        Called for each request both before and after endpoint handling.

        Args:
            request: The Starlette `Request` object.
            response: The `Response` instance (None for pre-processing).

        Returns:
            - On pre-processing (`response` is None): return a `Response` to short-circuit handling, or None to continue.
            - On post-processing: return a `Response` to modify the final output.
        """
        return response
```

### Usage

1. Subclass `Middleware` and override `process`.
2. Register with the application:

```python
from lightapi import LightApi
from lightapi.core import Middleware

class ExampleMiddleware(Middleware):
    def process(self, request, response):
        # Pre-processing: response is None
        if response is None:
            request.state.start_time = time.time()
            return None
        # Post-processing: add header
        response.headers['X-Time'] = str(time.time() - request.state.start_time)
        return response

app = LightApi()
app.add_middleware([ExampleMiddleware])
```

Middleware is executed in the order registered for both incoming requests and outgoing responses.
