"""Authentication and permission check for one endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from lightapi.authentication import AllowAny
from lightapi.constants import HTTPStatus

if TYPE_CHECKING:
    from lightapi.authentication.base import LoginValidator
    from lightapi.config import Authentication


class EndpointGuard:
    """Decides whether a request may reach an endpoint."""

    def __init__(
        self,
        authentication: Authentication | None,
        login_validator: LoginValidator | None = None,
    ) -> None:
        self._authentication = authentication
        self._login_validator = login_validator

    def check(self, request: Request) -> Response | None:
        """The 401 or 403 response that stops the request, or None to let it in."""
        authentication = self._authentication
        if authentication is None:
            return None

        if authentication.requires_login(request.method):
            backend = authentication.build_backend(self._login_validator)
            if not backend.authenticate(request):
                return JSONResponse(
                    {"detail": "Authentication required"},
                    status_code=HTTPStatus.UNAUTHORIZED,
                    headers={"WWW-Authenticate": "Bearer"},
                )

        permission = authentication.permission_for(request.method)
        if permission is not AllowAny and not permission().has_permission(request):
            return JSONResponse(
                {"detail": "Insufficient permissions"},
                status_code=HTTPStatus.FORBIDDEN,
            )

        return None
