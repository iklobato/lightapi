"""Authentication and permission check for one endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING

from starlette.requests import Request
from starlette.responses import Response

from lightapi.authentication import AllowAny
from lightapi.constants import ApiError

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
                return ApiError.AUTHENTICATION_REQUIRED.response()

        permission = authentication.permission_for(request.method)
        if permission is not AllowAny and not permission().has_permission(request):
            return ApiError.INSUFFICIENT_PERMISSIONS.response()

        return None
