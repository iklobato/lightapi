"""LightAPI Authentication Module.

Provides authentication backends and permission classes for securing endpoints.
"""

from lightapi.authentication.base import (
    AllowAny,
    BaseAuthentication,
    BasePermission,
    IsAdminUser,
    IsAuthenticated,
)
from lightapi.authentication.basic import BasicAuthentication
from lightapi.authentication.jwt import JWTAuthentication

__all__ = [
    "BaseAuthentication",
    "BasePermission",
    "AllowAny",
    "IsAuthenticated",
    "IsAdminUser",
    "BasicAuthentication",
    "JWTAuthentication",
]
