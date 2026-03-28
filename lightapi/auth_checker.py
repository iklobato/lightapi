"""Authentication and authorization checker."""

from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from lightapi.authentication import AllowAny
from lightapi.constants import HTTPStatus


def check_auth(cls: type, request: Request) -> Response | None:
    """Run authentication + permission checks; return 401/403 response or None."""
    from lightapi.authentication import BasicAuthentication, JWTAuthentication

    auth_cfg = cls._meta.get("authentication")
    if auth_cfg is None:
        return None

    backend = auth_cfg.backend
    permission_cls = auth_cfg.permission
    is_per_method = isinstance(permission_cls, dict)

    if is_per_method:
        perm_cls = permission_cls.get(request.method)
        if perm_cls is None:
            perm_cls = AllowAny
    elif permission_cls is not None:
        perm_cls = permission_cls
    else:
        perm_cls = AllowAny

    requires_auth = backend is not None and (
        not is_per_method or perm_cls is not AllowAny
    )

    if requires_auth:
        login_validator = getattr(auth_cfg, "_login_validator", None)

        if backend.__name__ == "JWTAuthentication":
            authenticator = backend(
                expiration=getattr(auth_cfg, "jwt_expiration", None),
                algorithm=getattr(auth_cfg, "jwt_algorithm", None),
                rate_limiter=getattr(auth_cfg, "rate_limiter", None),
            )
        elif backend.__name__ == "BasicAuthentication":
            authenticator = backend(
                rate_limiter=getattr(auth_cfg, "rate_limiter", None),
                login_validator=login_validator,
            )
        else:
            authenticator = backend()

        authenticated = authenticator.authenticate(request)

        if not authenticated:
            return JSONResponse(
                {"detail": "Authentication required"},
                status_code=HTTPStatus.UNAUTHORIZED,
                headers={"WWW-Authenticate": "Bearer"},
            )

    if perm_cls is not AllowAny:
        if not perm_cls().has_permission(request):
            return JSONResponse(
                {"detail": "Insufficient permissions"},
                status_code=HTTPStatus.FORBIDDEN,
            )

    return None
