"""LightAPI v2 public API."""

from lightapi.auth import (
    AllowAny,
    BasicAuthentication,
    IsAdminUser,
    IsAuthenticated,
    JWTAuthentication,
)
from lightapi.cache import RedisCache
from lightapi.config import Authentication, Cache, Filtering, Pagination, Serializer

# Backward-compatible re-exports from core.py
from lightapi.core import (
    AuthenticationMiddleware,
    CORSMiddleware,
    Middleware,
    Response,
)
from lightapi.exceptions import ConfigurationError, SerializationError
from lightapi.fields import Field
from lightapi.filters import FieldFilter, OrderingFilter, SearchFilter
from lightapi.lightapi import LightApi
from lightapi.methods import HttpMethod
from lightapi.rest import RestEndpoint
from lightapi.schema import SchemaFactory
from lightapi.session import get_async_session, get_sync_session  # noqa: E402

__all__ = [
    # Core
    "LightApi",
    "RestEndpoint",
    "Field",
    "HttpMethod",
    # Config
    "Authentication",
    "Cache",
    "Filtering",
    "Pagination",
    "Serializer",
    # Auth
    "BasicAuthentication",
    "JWTAuthentication",
    "AllowAny",
    "IsAuthenticated",
    "IsAdminUser",
    # Filters
    "FieldFilter",
    "SearchFilter",
    "OrderingFilter",
    # Schema
    "SchemaFactory",
    # Middleware (backward-compat)
    "Middleware",
    "CORSMiddleware",
    "AuthenticationMiddleware",
    "Response",
    "RedisCache",
    # Exceptions
    "ConfigurationError",
    "SerializationError",
    # Session helpers
    "get_sync_session",
    "get_async_session",
]
