from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import jwt
from starlette.requests import Request
from starlette.responses import JSONResponse

from ._registry import LoginValidator, get_login_validator
from .config import config


class BaseAuthentication:
    """
    Base class for authentication.

    Provides a common interface for all authentication methods.
    By default, allows all requests.
    """

    def authenticate(self, request: Request) -> bool:
        """
        Authenticate a request.

        Args:
            request: The HTTP request to authenticate.

        Returns:
            bool: True if authentication succeeds, False otherwise.
        """
        return True


def get_auth_error_response(self, request: Request) -> JSONResponse:
    """
    Get the response to return when authentication fails.

    Args:
        request: The HTTP request object.

    Returns:
        Response object for authentication error.
    """
    return JSONResponse(
        {"error": "authentication failed"},
        status_code=401,
        headers={"WWW-Authenticate": 'Basic realm="Restricted Area"'},
    )


class BasicAuthentication(BaseAuthentication):
    """
    Basic (Base64) authentication.

    Authenticates requests using Authorization: Basic <base64(username:password)>.
    Delegates credential validation to the app-level login_validator from the registry.
    """

    def __init__(
        self,
        login_validator: Optional[LoginValidator] = None,
    ) -> None:
        self.login_validator = login_validator

    def authenticate(self, request: Request) -> bool:
        if request.method == "OPTIONS":
            return True

        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return False

        # Use the shared Basic auth parsing function
        from lightapi._login import _parse_basic_header

        credentials = _parse_basic_header(auth_header)
        if credentials is None:
            return False

        username, password = credentials
        from lightapi._registry import get_login_validator

        validator = self.login_validator or get_login_validator()
        if validator is None:
            return False

        try:
            payload = validator(username, password)
        except Exception:
            return False

        if payload is None:
            return False

        request.state.user = payload
        return True

    def get_auth_error_response(self, request: Request) -> JSONResponse:
        """
        Get the response to return when authentication fails.

        Args:
            request: The HTTP request object.

        Returns:
            Response object for authentication error.
        """
        return JSONResponse({"error": "authentication failed"}, status_code=401)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.lower().startswith("basic "):
            return False

        try:
            import base64

            token = auth_header.split(" ", 1)[1]
            decoded = base64.b64decode(token).decode("utf-8")
        except (ValueError, IndexError, UnicodeDecodeError):
            return False

        parts = decoded.split(":", 1)
        if len(parts) != 2:
            return False

        username, password = parts[0], parts[1]
        from lightapi._registry import get_login_validator

        validator = get_login_validator()
        if validator is None:
            return False

        try:
            payload = validator(username, password)
        except Exception:
            return False

        if payload is None:
            return False

        request.state.user = payload
        return True


class AllowAny:
    """Permits all requests regardless of authentication state."""

    def has_permission(self, request: Request) -> bool:
        return True


class IsAuthenticated:
    """Permits requests with a valid JWT already decoded into request.state.user."""

    def has_permission(self, request: Request) -> bool:
        return getattr(request.state, "user", None) is not None


class IsAdminUser:
    """Permits requests whose JWT payload contains is_admin == True."""

    def has_permission(self, request: Request) -> bool:
        user = getattr(request.state, "user", None)
        return isinstance(user, dict) and user.get("is_admin") is True
