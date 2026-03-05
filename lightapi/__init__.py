"""LightAPI v2 public API."""
from lightapi.auth import AllowAny, IsAdminUser, IsAuthenticated, JWTAuthentication
from lightapi.cache import RedisCache
from lightapi.config import Authentication, Cache, Filtering, Pagination, Serializer
from lightapi.exceptions import ConfigurationError, SerializationError
from lightapi.fields import Field
from lightapi.filters import FieldFilter, OrderingFilter, SearchFilter
from lightapi.lightapi import LightApi
from lightapi.methods import HttpMethod
from lightapi.rest import RestEndpoint
from lightapi.schema import SchemaFactory

# Backward-compatible re-exports from core.py
from lightapi.core import (
    AuthenticationMiddleware,
    CORSMiddleware,
    Middleware,
    Response,
)

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
]
