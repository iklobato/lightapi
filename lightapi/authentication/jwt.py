"""JWT Authentication backend."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

import jwt
from starlette.requests import Request
from starlette.responses import JSONResponse

from lightapi.authentication.base import BaseAuthentication
from lightapi.config import config

if TYPE_CHECKING:
    from lightapi.rate_limiter import RateLimiter


class JWTAuthentication(BaseAuthentication):
    """JWT token authentication backend.

    Authenticates requests using Authorization: Bearer <token>.
    Supports custom credential validation by overriding validate_credentials.
    """

    def __init__(
        self,
        algorithm: str | None = None,
        expiration: int | None = None,
        rate_limiter: "RateLimiter | None" = None,
    ) -> None:
        self.algorithm = algorithm
        self.expiration = expiration
        self.rate_limiter = rate_limiter

    def authenticate(self, request: Request) -> bool:
        if request.method == "OPTIONS":
            return True

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.lower().startswith("bearer "):
            return False

        token = auth_header.split(" ", 1)[1]
        try:
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

    def validate_credentials(
        self, username: str, password: str
    ) -> dict[str, Any] | None:
        """Validate user credentials.

        Override this method in a subclass to provide custom validation logic.

        Args:
            username: The username from login request.
            password: The password from login request.

        Returns:
            A user payload dict on success, or None on failure.
        """
        return None

    def generate_token(
        self, payload: dict[str, Any], expiration: int | None = None
    ) -> str:
        """Generate a JWT token."""
        secret = config.jwt_secret_value
        if not secret:
            raise ValueError("JWT secret not configured")

        if expiration is None:
            expiration = self.expiration or 3600

        payload_copy = payload.copy()
        payload_copy["exp"] = datetime.now(timezone.utc) + timedelta(seconds=expiration)

        algorithm = self.algorithm or config.jwt_algorithm_value

        return jwt.encode(
            payload_copy,
            secret,
            algorithm=algorithm,
        )
