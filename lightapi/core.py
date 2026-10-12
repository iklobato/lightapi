"""Middleware and Response classes for LightAPI v2."""

from __future__ import annotations

import json
from http import HTTPStatus
from typing import TYPE_CHECKING, Any, Final

from starlette.responses import JSONResponse

from lightapi.constants import HttpVerb
from lightapi.exceptions import ConfigurationError

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response as StarletteResponse


class Response(JSONResponse):
    """
    Custom JSON response class.

    Extends Starlette's JSONResponse with a simplified constructor
    and default application/json media type.
    """

    def __init__(
        self,
        content: Any = None,  # noqa: ANN401  any JSON value
        status_code: int = HTTPStatus.OK,
        headers: dict[str, str] | None = None,
        media_type: str | None = None,
        content_type: str | None = None,
    ):
        """
        Initialize a new Response.

        Args:
            content: The response content.
            status_code: HTTP status code.
            headers: HTTP headers.
            media_type: HTTP media type.
            content_type: HTTP content type (alias for media_type).
        """
        media_type = content_type or media_type or "application/json"

        super().__init__(
            content=content,
            status_code=status_code,
            headers=headers or {},
            media_type=media_type,
        )


class Middleware:
    """
    Base class for middleware components.

    Middleware can process requests before they reach the endpoint
    and responses before they are returned to the client.
    """

    def process(
        self,
        request: Request,  # noqa: ARG002  override point
        response: StarletteResponse | None,
    ) -> StarletteResponse | None:
        """
        Process a request or response.

        This method is called twice during request handling:
        1. Before the request reaches the endpoint (response is None)
        2. After the endpoint generates a response

        Args:
            request: The HTTP request.
            response: The HTTP response (None for pre-processing).

        Returns:
            The response (possibly modified) or None to continue processing.
        """
        return response


class CORSMiddleware(Middleware):
    """
    CORS (Cross-Origin Resource Sharing) middleware.

    Handles CORS preflight requests and adds appropriate headers to responses.
    """

    _DEFAULT_ALLOW_METHODS: Final = (
        HttpVerb.GET,
        HttpVerb.POST,
        HttpVerb.PUT,
        HttpVerb.DELETE,
        HttpVerb.OPTIONS,
    )

    def __init__(
        self,
        allow_origins: list[str] | None = None,
        allow_methods: list[str] | None = None,
        allow_headers: list[str] | None = None,
    ):
        if allow_origins is None:
            # B11-002: the old default was "*". Origins are spelled out here, as
            # LightApi(cors_origins=[...]) already requires.
            raise ConfigurationError(
                "CORSMiddleware needs allow_origins: pass the list, or subclass it "
                "with one; LightApi(cors_origins=[...]) is the documented route."
            )
        if allow_methods is None:
            allow_methods = [verb.value for verb in self._DEFAULT_ALLOW_METHODS]
        if allow_headers is None:
            allow_headers = ["Authorization", "Content-Type"]

        self.allow_origins = allow_origins
        self.allow_methods = allow_methods
        self.allow_headers = allow_headers

    def process(
        self, request: Request, response: StarletteResponse | None
    ) -> StarletteResponse | None:
        if response is None:
            if request.method == HttpVerb.OPTIONS:
                return JSONResponse(
                    {},
                    status_code=HTTPStatus.OK,
                    headers={
                        "Access-Control-Allow-Origin": ", ".join(self.allow_origins),
                        "Access-Control-Allow-Methods": ", ".join(self.allow_methods),
                        "Access-Control-Allow-Headers": ", ".join(self.allow_headers),
                    },
                )
            return None

        cors_headers = {
            "Access-Control-Allow-Origin": ", ".join(self.allow_origins),
            "Access-Control-Allow-Methods": ", ".join(self.allow_methods),
            "Access-Control-Allow-Headers": ", ".join(self.allow_headers),
        }

        all_headers = {**response.headers, **cors_headers}

        try:
            content = response.body
            if isinstance(content, bytes):
                content = json.loads(content.decode("utf-8"))
            return JSONResponse(
                content, status_code=response.status_code, headers=all_headers
            )
        except (json.JSONDecodeError, AttributeError, UnicodeDecodeError):
            response.headers.update(cors_headers)
            return response


class AuthenticationMiddleware(Middleware):
    """
    Authentication middleware that integrates with authentication classes.
    """

    def __init__(self, authentication_class: type | None = None):
        self.authentication_class = authentication_class
        if authentication_class:
            self.authenticator = authentication_class()
        else:
            self.authenticator = None

    def process(
        self, request: Request, response: StarletteResponse | None
    ) -> StarletteResponse | None:
        if response is None and self.authenticator:
            if not self.authenticator.authenticate(request):
                return JSONResponse(
                    {"error": "not allowed"}, status_code=HTTPStatus.FORBIDDEN
                )
            return None

        return response
