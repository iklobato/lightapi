"""LightAPI Authentication - Backward compatibility module.

This module re-exports authentication classes from the new authentication submodule.
For new code, use: from lightapi.authentication import JWTAuthentication, BasicAuthentication
"""

from lightapi.authentication import (
    AllowAny,
    BaseAuthentication,
    BasePermission,
    BasicAuthentication,
    IsAdminUser,
    IsAuthenticated,
    JWTAuthentication,
)

__all__ = [
    "BaseAuthentication",
    "BasePermission",
    "AllowAny",
    "IsAuthenticated",
    "IsAdminUser",
    "BasicAuthentication",
    "JWTAuthentication",
]
