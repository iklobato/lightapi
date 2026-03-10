from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import jwt
from starlette.requests import Request
from starlette.responses import JSONResponse

from ._registry import LoginValidator
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
        return JSONResponse({"error": "not allowed"}, status_code=403)


class JWTAuthentication(BaseAuthentication):
    """
    JWT (JSON Web Token) based authentication.

    Authenticates requests using JWT tokens from the Authorization header.
    Validates token signatures and expiration times.
    Automatically skips authentication for OPTIONS requests (CORS preflight).

    Attributes:
        secret_key: Secret key for signing tokens.
        algorithm: JWT algorithm to use.
        expiration: Token expiration time in seconds.
    """

    def __init__(
        self,
        secret_key: str | None = None,
        algorithm: str | None = None,
        expiration: int | None = None,
    ):
        self.secret_key = secret_key or config.jwt_secret
        if not self.secret_key:
            raise ValueError(
                "JWT secret key not configured. Set LIGHTAPI_JWT_SECRET environment variable."
            )

        self.algorithm = algorithm or config.jwt_algorithm
        self.expiration = expiration or 3600  # 1 hour default

    def authenticate(self, request: Request) -> bool:
        """
        Authenticate a request using JWT token.
        Automatically allows OPTIONS requests for CORS preflight.

        Args:
            request: The HTTP request object.

        Returns:
            bool: True if authentication succeeds, False otherwise.
        """
        # Skip authentication for OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
            return True

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return False

        token = auth_header.split(" ")[1]
        try:
            payload = self.decode_token(token)
            request.state.user = payload
            return True
        except jwt.InvalidTokenError:
            return False

    def generate_token(self, payload: Dict, expiration: Optional[int] = None) -> str:
        """
        Generate a JWT token.

        Args:
            payload: The data to encode in the token.
            expiration: Token expiration time in seconds.

        Returns:
            str: The encoded JWT token.

        Raises:
            ValueError: If payload contains 'exp' claim which will be overwritten.
        """
        # Check for 'exp' in payload since we overwrite it
        if "exp" in payload:
            raise ValueError(
                "Payload contains 'exp' claim which will be overwritten. "
                "Use the 'expiration' parameter instead."
            )

        exp_seconds = expiration or self.expiration
        token_data = {
            **payload,
            "exp": datetime.utcnow() + timedelta(seconds=exp_seconds),
        }
        return jwt.encode(token_data, self.secret_key, algorithm=self.algorithm)

    def decode_token(self, token: str) -> Dict:
        """
        Decode and verify a JWT token.

        Args:
            token: The JWT token to decode.

        Returns:
            dict: The decoded token payload.

        Raises:
            jwt.InvalidTokenError: If the token is invalid or expired.
        """
        return jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

    def get_auth_error_response(self, request: Request) -> JSONResponse:
        """
        Get the response to return when authentication fails.

        Args:
            request: The HTTP request object.

        Returns:
            Response object for authentication error.
        """
        return JSONResponse({"error": "authentication failed"}, status_code=401)


class BasicAuthentication(BaseAuthentication):
    """
    Basic (Base64) authentication.

    Authenticates requests using Authorization: Basic <base64(username:password)>.
    Delegates credential validation to the app-level login_validator from the registry.
    """

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
        if not auth_header or not auth_header.startswith("Basic "):
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
