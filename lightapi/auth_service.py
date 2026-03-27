"""Authentication service for LightAPI.

Extracts auth logic from LightApi class for better SRP.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from starlette.requests import Request
from starlette.responses import JSONResponse


class AuthService:
    """Handles authentication and authorization for endpoints.

    Separates auth logic from the main LightApi class.
    """

    def __init__(
        self,
        login_validator: Optional[Callable] = None,
        jwt_secret: Optional[str] = None,
        jwt_algorithm: str = "HS256",
        jwt_expiration: int = 3600,
    ) -> None:
        self._login_validator = login_validator
        self._jwt_secret = jwt_secret
        self._jwt_algorithm = jwt_algorithm
        self._jwt_expiration = jwt_expiration

    @property
    def login_validator(self) -> Optional[Callable]:
        return self._login_validator

    @property
    def jwt_secret(self) -> Optional[str]:
        return self._jwt_secret

    @property
    def jwt_algorithm(self) -> str:
        return self._jwt_algorithm

    @property
    def jwt_expiration(self) -> int:
        return self._jwt_expiration

    def check_auth(
        self,
        request: Request,
        backend: Optional[type],
        permission: Optional[type],
        login_validator: Optional[Callable] = None,
    ) -> tuple[bool, Optional[JSONResponse]]:
        """Check authentication and authorization for a request.

        Args:
            request: The HTTP request
            backend: Authentication backend class
            permission: Permission class
            login_validator: Login validator function

        Returns:
            Tuple of (is_authenticated, error_response)
        """
        if backend is None:
            return True, None

        # Get validator (from parameter or instance)
        validator = login_validator or self._login_validator

        # Instantiate authenticator
        try:
            if backend.__name__ == "JWTAuthentication":
                authenticator = backend(
                    expiration=getattr(backend, "jwt_expiration", None),
                    algorithm=getattr(backend, "jwt_algorithm", None),
                )
            elif backend.__name__ == "BasicAuthentication":
                authenticator = backend(login_validator=validator)
            else:
                authenticator = backend()
        except Exception:
            return True, None

        # Authenticate
        if not authenticator.authenticate(request):
            error_response = getattr(
                authenticator,
                "get_auth_error_response",
                lambda r: JSONResponse(
                    {"detail": "Authentication credentials invalid."}, status_code=401
                ),
            )(request)
            return False, error_response

        # Check permission
        if permission is not None:
            perm = permission()
            if not perm.has_permission(request):
                return False, JSONResponse(
                    {"detail": "You do not have permission to perform this action."},
                    status_code=403,
                )

        return True, None
