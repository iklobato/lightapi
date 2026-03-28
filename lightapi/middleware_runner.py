"""Middleware runner for pre/post middleware execution."""

import asyncio
from typing import Any

from starlette.requests import Request
from starlette.responses import Response


async def run_pre_middlewares(
    middlewares: list[type], request: Request
) -> Response | None:
    """Run pre-request middleware; supports both sync and async process() methods."""
    for mw_cls in middlewares:
        mw = mw_cls()
        if asyncio.iscoroutinefunction(mw.process):
            result = await mw.process(request, None)
        else:
            result = mw.process(request, None)
        if result is not None:
            return result
    return None


async def run_post_middlewares(
    middlewares: list[type], request: Request, response: Response
) -> Response:
    """Run post-response middleware in reverse order; supports sync and async process()."""
    for mw_cls in reversed(middlewares):
        mw = mw_cls()
        if asyncio.iscoroutinefunction(mw.process):
            result = await mw.process(request, response)
        else:
            result = mw.process(request, response)
        if result is not None:
            response = result
    return response
