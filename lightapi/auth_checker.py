"""Authentication and permission check for one endpoint."""

from __future__ import annotations

from functools import cached_property
from typing import TYPE_CHECKING

from starlette.requests import Request
from starlette.responses import Response

from lightapi.constants import ApiError

if TYPE_CHECKING:
    from lightapi.authentication.base import BaseAuthentication, LoginValidator
    from lightapi.config import Authentication


class EndpointGuard:
    """Decides whether a request may reach an endpoint with an Authentication."""

    def __init__(
        self,
        authentication: Authentication,
        login_validator: LoginValidator | None = None,
    ) -> None:
        self._authentication = authentication
        self._login_validator = login_validator

    @cached_property
    def backend(self) -> BaseAuthentication:
        """Built on the first request that needs it, then shared by every later one."""
        return self._authentication.build_backend(self._login_validator)

    def check(self, request: Request) -> Response | None:
        """The 401 or 403 response that stops the request, or None to let it in."""
        authentication = self._authentication
        if authentication.requires_login(request.method) and not (
            self.backend.authenticate(request)
        ):
            return ApiError.AUTHENTICATION_REQUIRED.response()

        permission = authentication.permission_for(request.method)
        if permission is not None and not permission().has_permission(request):
            return ApiError.INSUFFICIENT_PERMISSIONS.response()

        return None
