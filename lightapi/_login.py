"""Login and token endpoint handlers."""

from __future__ import annotations

import base64
import logging
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from starlette.requests import Request
from starlette.responses import JSONResponse

from lightapi.auth import JWTAuthentication
from lightapi.rate_limiter import rate_limit_auth_endpoint

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
    if not auth_header.startswith("Basic "):
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
    import json

    try:
        body = await request.body()
        return json.loads(body) if body else {}
    except (json.JSONDecodeError, TypeError):
        return {}


@rate_limit_auth_endpoint
async def login_handler(
    request: Request,
    *,
    login_validator: Callable[[str, str], dict[str, Any] | None],
    has_jwt: bool,
    jwt_expiration: int | None = None,
    jwt_extra_claims: list[str] | None = None,
    jwt_algorithm: str | None = None,
) -> JSONResponse:
    """
    Handle POST /auth/login and POST /auth/token.

    Returns 422 for body validation, 401 for malformed Basic or invalid credentials,
    500 for validator exception, 200 with token+user (JWT) or user only (Basic).
    """
    from pydantic import ValidationError

    if request.method != "POST":
        return JSONResponse(
            {"detail": "method not allowed"},
            status_code=405,
            headers={"Allow": "POST"},
        )

    try:
        creds = await _parse_credentials(request)
    except ValidationError as exc:
        return JSONResponse({"detail": exc.errors()}, status_code=422)

    if creds is None:
        return JSONResponse({"detail": "Invalid credentials"}, status_code=401)

    username, password = creds
    try:
        payload = login_validator(username, password)
    except Exception as e:
        logger.exception("login_validator raised: %s", e)
        raise

    if payload is None:
        return JSONResponse({"detail": "Invalid credentials"}, status_code=401)

    if has_jwt:
        jwt_auth = JWTAuthentication(algorithm=jwt_algorithm)
        if jwt_extra_claims and isinstance(payload, dict):
            token_payload = {k: payload[k] for k in jwt_extra_claims if k in payload}
            if not token_payload:
                token_payload = payload
        else:
            token_payload = payload
        token = jwt_auth.generate_token(token_payload, expiration=jwt_expiration)
        return JSONResponse({"token": token, "user": payload})

    return JSONResponse({"user": payload})
