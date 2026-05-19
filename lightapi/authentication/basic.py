"""Basic Authentication backend."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from starlette.requests import Request
from starlette.responses import JSONResponse

from lightapi._login import _parse_basic_header
from lightapi.authentication.base import BaseAuthentication

if TYPE_CHECKING:
    from lightapi.rate_limiter import RateLimiter


class BasicAuthentication(BaseAuthentication):
    """Basic (Base64) authentication backend.

    Authenticates requests using Authorization: Basic <base64(username:password)>.
    Supports custom credential validation by overriding validate_credentials.
    """

    def __init__(
        self,
        rate_limiter: "RateLimiter | None" = None,
        login_validator: Callable[[str, str], dict[str, Any] | None] | None = None,
    ) -> None:
        self.rate_limiter = rate_limiter
        self._login_validator = login_validator

    def authenticate(self, request: Request) -> bool:
        if request.method == "OPTIONS":
            return True

        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return False

        credentials = _parse_basic_header(auth_header)
        if credentials is None:
            return False

        username, password = credentials

        payload = self.validate_credentials(username, password)
        if payload is None:
            return False

        request.state.user = payload
        return True

    def get_auth_error_response(self, request: Request) -> JSONResponse:
        return JSONResponse(
            {"error": "authentication failed"},
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="Restricted Area"'},
        )

    def validate_credentials(
        self, username: str, password: str
    ) -> dict[str, Any] | None:
        """Validate user credentials.

        Uses login_validator if provided, otherwise falls back to subclass override.

        Args:
            username: The username from login request.
            password: The password from login request.

        Returns:
            A user payload dict on success, or None on failure.
        """
        # Use login_validator if provided
        if self._login_validator is not None:
            return self._login_validator(username, password)
        return None
