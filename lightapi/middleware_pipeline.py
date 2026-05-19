"""Middleware pipeline for request/response processing."""

from __future__ import annotations

import asyncio

from starlette.requests import Request
from starlette.responses import Response


class MiddlewarePipeline:
    """Pipeline for processing middleware in order.

    Supports both sync and async middleware processors.
    """

    def __init__(self, middlewares: list[type] | None = None) -> None:
        """Initialize the middleware pipeline.

        Args:
            middlewares: List of middleware classes to apply
        """
        self._middlewares: list[type] = middlewares or []

    def add(self, middleware: type) -> "MiddlewarePipeline":
        """Add a middleware to the pipeline.

        Args:
            middleware: Middleware class to add

        Returns:
            Self for chaining
        """
        self._middlewares.append(middleware)
        return self

    async def process_request(self, request: Request) -> Response | None:
        """Process request through all pre-request middleware.

        Args:
            request: The incoming request

        Returns:
            Response if a middleware returned early, None to continue
        """
        for mw_cls in self._middlewares:
            mw = mw_cls()
            if asyncio.iscoroutinefunction(mw.process):
                result = await mw.process(request, None)
            else:
                result = mw.process(request, None)
            if result is not None:
                return result
        return None

    async def process_response(self, request: Request, response: Response) -> Response:
        """Process response through all post-request middleware.

        Runs middleware in reverse order (LIFO).

        Args:
            request: The original request
            response: The response to process

        Returns:
            The processed response
        """
        for mw_cls in reversed(self._middlewares):
            mw = mw_cls()
            if asyncio.iscoroutinefunction(mw.process):
                result = await mw.process(request, response)
            else:
                result = mw.process(request, response)
            if result is not None:
                response = result
        return response

    def __len__(self) -> int:
        """Return the number of middlewares in the pipeline."""
        return len(self._middlewares)

    def __bool__(self) -> bool:
        """Return True if the pipeline has middlewares."""
        return bool(self._middlewares)
