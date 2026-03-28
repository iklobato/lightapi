"""Response wrapper for handling dict responses."""

from typing import Any

from starlette.responses import JSONResponse, Response


def wrap_dict_response(result: Any) -> Response:
    """Wrap dict responses in JSONResponse."""
    if isinstance(result, dict):
        return JSONResponse(result)
    return result
