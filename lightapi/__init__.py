# lightapi/__init__.py
from .rest import RestEndpoint, ModelEndpoint, Response, Validator  # Add this line
from .api import LightApi
from .auth import JWTAuthentication
from .middleware import (
    Middleware,
    CORSMiddleware,
    RateLimitingMiddleware,
    DatabaseMiddleware,
)
from .db import database, Base
from .pagination import Paginator
from .logging import RequestLogger
from .exceptions import UnauthorizedError, ValidationError

__version__ = "0.1.0"

__all__ = [
    'LightApi',
    'RestEndpoint',  # Make sure this is included
    'Response',
    'Validator',
    'JWTAuthentication',
    'Middleware',
    'CORSMiddleware',
    'RateLimitingMiddleware',
    'DatabaseMiddleware',
    'ModelEndpoint',
    'database',
    'Base',
    'Paginator',
    'RequestLogger',
    'UnauthorizedError',
    'ValidationError',
]
