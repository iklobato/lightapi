"""Base authentication classes and permissions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from starlette.requests import Request
from starlette.responses import JSONResponse

if TYPE_CHECKING:
    from lightapi.authentication.basic import BasicAuthentication
    from lightapi.authentication.jwt import JWTAuthentication


class BaseAuthentication:
    """Base class for authentication backends.

    Provides a common interface for all authentication methods.
    By default, allows all requests.
    """

    def authenticate(self, request: Request) -> bool:
        """Authenticate a request.

        Args:
            request: The HTTP request to authenticate.

        Returns:
            bool: True if authentication succeeds, False otherwise.
        """
        return True

    def get_auth_error_response(self, request: Request) -> JSONResponse:
        """Get the response to return when authentication fails.

        Args:
            request: The HTTP request object.

        Returns:
            Response object for authentication error.
        """
        return JSONResponse(
            {"error": "authentication failed"},
            status_code=401,
        )

    def validate_credentials(
        self, username: str, password: str
    ) -> dict[str, Any] | None:
        """Validate user credentials.

        Override this method in subclasses to provide custom validation logic.

        Args:
            username: The username from login request.
            password: The password from login request.

        Returns:
            A user payload dict on success, or None on failure.
        """
        return None


class BasePermission:
    """Base class for permission classes.

    Permission classes determine whether an authenticated user
    is allowed to access a particular endpoint.
    """

    def has_permission(self, request: Request) -> bool:
        """Check if the request has permission.

        Args:
            request: The HTTP request with authentication state.

        Returns:
            bool: True if permission is granted, False otherwise.
        """
        return True


class AllowAny(BasePermission):
    """Permits all requests regardless of authentication state."""

    def has_permission(self, request: Request) -> bool:
        return True


class IsAuthenticated(BasePermission):
    """Permits requests with a valid JWT already decoded into request.state.user."""

    def has_permission(self, request: Request) -> bool:
        return getattr(request.state, "user", None) is not None


class IsAdminUser(BasePermission):
    """Permits requests whose JWT payload contains is_admin == True."""

    def has_permission(self, request: Request) -> bool:
        user = getattr(request.state, "user", None)
        return isinstance(user, dict) and user.get("is_admin") is True
