"""LightAPI Example 13 - Custom Middleware.

Demonstrates:
- Custom Middleware class
- Pre-request hook (process request before endpoint)
- Post-response hook (process response after endpoint)
- Adding headers to responses

Prerequisites:
    PostgreSQL must be running.

Run with:
    python examples/13_middleware.py

Then try:
    # Check response headers for X-Request-Id and X-Response-Time
    curl -v http://localhost:8000/books
"""

import time
import uuid

from sqlalchemy import create_engine
from starlette.requests import Request
from starlette.responses import Response

from lightapi import HttpMethod, LightApi, Middleware, RestEndpoint
from lightapi.fields import Field


class RequestIdMiddleware(Middleware):
    """Middleware that adds a unique request ID to each request."""

    def process(self, request: Request, response: Response | None) -> Response | None:
        if response is None:
            # Pre-request: generate request ID
            request.state.request_id = str(uuid.uuid4())
            return None

        # Post-response: add header
        response.headers["X-Request-Id"] = getattr(
            request.state, "request_id", "unknown"
        )
        return response


class ResponseTimeMiddleware(Middleware):
    """Middleware that measures and adds response time."""

    def process(self, request: Request, response: Response | None) -> Response | None:
        if response is None:
            # Pre-request: start timer
            request.state._start_time = time.monotonic()
            return None

        # Post-response: calculate elapsed time
        elapsed = time.monotonic() - getattr(
            request.state, "_start_time", time.monotonic()
        )
        response.headers["X-Response-Time"] = f"{elapsed:.4f}s"
        return response


DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/postgres"


class BookEndpoint(RestEndpoint, HttpMethod.GET, HttpMethod.POST):
    """Simple book endpoint."""

    title: str = Field(min_length=1)
    author: str = Field(min_length=1)


if __name__ == "__main__":
    engine = create_engine(DATABASE_URL)
    app = LightApi(
        engine=engine,
        middlewares=[RequestIdMiddleware, ResponseTimeMiddleware],
    )
    app.register({"/books": BookEndpoint})
    app.run(host="0.0.0.0", port=8000, debug=True)
