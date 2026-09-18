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

from lightapi.constants import RESPONSE_KEY_DETAIL, HTTPStatus

if TYPE_CHECKING:
    from lightapi.authentication.base import BaseAuthentication, LoginValidator
    from lightapi.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class LoginRequest(BaseModel):
    """Request body for POST /auth/login and /auth/token."""

    model_config = ConfigDict(frozen=True)

    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


def _parse_basic_header(auth_header: str) -> tuple[str, str] | None:
    """
    Decode Authorization: Basic header.

    Returns (username, password) or None if malformed.
    """
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


async def _parse_credentials(request: Request) -> tuple[str, str] | None:
    """
    Extract (username, password) from request.

    - If Authorization: Basic present: returns (u, p) or None if malformed.
    - If no Basic header: reads body, validates with LoginRequest.
      Returns (u, p) if valid. Raises ValidationError for body (caller returns 422).
    - None means malformed Basic (caller returns 401).
    """
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Basic "):
        return _parse_basic_header(auth_header)

    body = await _read_body(request)
    parsed = LoginRequest.model_validate(body if body else {})
    return parsed.username, parsed.password


async def _read_body(request: Request) -> dict[str, Any]:
    """Read JSON body; return {} on empty or invalid."""
    try:
        body = await request.body()
        return json.loads(body) if body else {}
    except (json.JSONDecodeError, TypeError):
        return {}


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
        is_limited, window = self._rate_limiter.is_rate_limited(
            request, endpoint="auth"
        )
        if is_limited:
            return self._rate_limiter.get_rate_limit_response(request, window)

        if request.method != "POST":
            return JSONResponse(
                {RESPONSE_KEY_DETAIL: "method not allowed"},
                status_code=HTTPStatus.METHOD_NOT_ALLOWED,
                headers={"Allow": "POST"},
            )

        try:
            creds = await _parse_credentials(request)
        except ValidationError as exc:
            return JSONResponse(
                {RESPONSE_KEY_DETAIL: exc.errors()},
                status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            )

        user = await self._validated_user(*creds) if creds is not None else None
        if user is None:
            return JSONResponse(
                {RESPONSE_KEY_DETAIL: "Invalid credentials"},
                status_code=HTTPStatus.UNAUTHORIZED,
            )
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
        except Exception as exc:
            logger.warning("validate_credentials raised: %s", exc)
            return None
        return user
