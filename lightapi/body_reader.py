"""Body reader for parsing request bodies."""

import json
from typing import Any

from starlette.requests import Request


async def read_body(request: Request) -> dict[str, Any]:
    """Read and parse JSON body; return {} on failure."""
    try:
        body = await request.body()
        return json.loads(body) if body else {}
    except Exception:
        return {}
