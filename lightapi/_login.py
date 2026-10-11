"""Login and token endpoint handlers."""

from __future__ import annotations

import base64
import inspect
import json
import logging
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse

from lightapi.constants import ApiError, HttpVerb

if TYPE_CHECKING:
    from lightapi.authentication.base import BaseAuthentication, LoginValidator
    from lightapi.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class LoginRequest(BaseModel):
    """Credentials of POST /auth/login and /auth/token: JSON body or Basic header."""

    model_config = ConfigDict(frozen=True)

    username: str = Field(min_length=1)
    password: str = Field(min_length=1)

    @classmethod
    async def from_request(cls, request: Request) -> LoginRequest | None:
        """The credentials sent, or None for a malformed Basic header (a 401).

        Without a Basic header the JSON body is validated, so a bad body raises
        ValidationError (a 422). Basic credentials are taken as sent, unvalidated,
        as they always were.
        """
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Basic "):
            parsed = cls.parse_basic_header(auth_header)
            if parsed is None:
                return None
            return cls.model_construct(username=parsed[0], password=parsed[1])

        try:
            body = await request.json()
        except (json.JSONDecodeError, UnicodeDecodeError):
            body = {}
        return cls.model_validate(body if body else {})

    @staticmethod
    def parse_basic_header(auth_header: str) -> tuple[str, str] | None:
        """(username, password) of an ``Authorization: Basic`` header; None if bad."""
        if not auth_header.lower().startswith("basic "):
            return None
        try:
            token = auth_header.split(" ", 1)[1]
            decoded = base64.b64decode(token).decode("utf-8")
        except (ValueError, IndexError, UnicodeDecodeError):
            return None
        parts = decoded.split(":", 1)
        if len(parts) != 2:
            return None
        return parts[0], parts[1]


class LoginEndpoint:
    """POST /auth/login and POST /auth/token.

    Returns 422 for body validation, 401 for malformed Basic, invalid credentials,
    or any exception raised while validating; 200 with whatever the backend puts
    in a login response (token and user for JWT, user for Basic).
    """

    def __init__(
        self,
        backend: BaseAuthentication,
        login_validator: LoginValidator | None,
        rate_limiter: RateLimiter,
    ) -> None:
        self._backend = backend
        self._login_validator = login_validator
        self._rate_limiter = rate_limiter

    async def handle(self, request: Request) -> JSONResponse:
        # The limiter names the exhausted window; None when the request passes.
        _, exhausted_window = self._rate_limiter.is_rate_limited(
            request, endpoint="auth"
        )
        if exhausted_window is not None:
            return self._rate_limiter.get_rate_limit_response(request, exhausted_window)

        if request.method != HttpVerb.POST:
            return ApiError.LOGIN_METHOD_NOT_ALLOWED.response()

        try:
            credentials = await LoginRequest.from_request(request)
        except ValidationError as exc:
            return ApiError.validation_failed(exc.errors())

        user = None
        if credentials is not None:
            user = await self._validated_user(
                credentials.username, credentials.password
            )
        if user is None:
            return ApiError.INVALID_CREDENTIALS.response()
        return JSONResponse(self._backend.login_response(user))

    async def _validated_user(
        self, username: str, password: str
    ) -> dict[str, Any] | None:
        """The app's login_validator wins; otherwise the backend's own override."""
        validate = self._login_validator or self._backend.validate_credentials
        try:
            user = validate(username, password)
            # The README shows `async def validate_credentials` on a subclass.
            if inspect.isawaitable(user):
                user = await user
        except Exception:
            logger.warning("validate_credentials raised", exc_info=True)
            return None
        return user
