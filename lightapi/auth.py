from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from starlette.requests import Request
from starlette.responses import JSONResponse

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
        login_validator: Optional[Any] = None,
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

        validator = self.login_validator
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


class JWTAuthentication(BaseAuthentication):
    """JWT token authentication."""

    def __init__(self, algorithm: str = None, expiration: int = None):
        self.algorithm = algorithm
        self.expiration = expiration

    def authenticate(self, request: Request) -> bool:
        if request.method == "OPTIONS":
            return True

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.lower().startswith("bearer "):
            return False

        token = auth_header.split(" ", 1)[1]
        try:
            # Get secret from config
            secret = config.jwt_secret_value
            if not secret:
                return False

            payload = jwt.decode(
                token,
                secret,
                algorithms=[config.jwt_algorithm_value],
                options={"verify_exp": True},
            )
        except jwt.InvalidTokenError:
            return False

        request.state.user = payload
        return True

    def get_auth_error_response(self, request: Request) -> JSONResponse:
        return JSONResponse(
            {"detail": "Authentication credentials invalid."},
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
        )

    def generate_token(
        self, payload: dict[str, Any], expiration: int | None = None
    ) -> str:
        """Generate a JWT token."""
        secret = config.jwt_secret_value
        if not secret:
            raise ValueError("JWT secret not configured")

        if expiration is None:
            # Default to 1 hour if not configured
            expiration = 3600

        payload_copy = payload.copy()
        payload_copy["exp"] = datetime.now(timezone.utc) + timedelta(seconds=expiration)

        algorithm = self.algorithm or config.jwt_algorithm_value

        return jwt.encode(
            payload_copy,
            secret,
            algorithm=algorithm,
        )
