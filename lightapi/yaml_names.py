"""Names a YAML config may use: built-ins by short name, the rest by dotted path."""

from __future__ import annotations

import importlib
from typing import Any

from lightapi.exceptions import ConfigurationError


def name_registry() -> dict[str, type]:
    from lightapi.auth import (
        AllowAny,
        BasicAuthentication,
        IsAdminUser,
        IsAuthenticated,
        JWTAuthentication,
    )
    from lightapi.core import AuthenticationMiddleware, CORSMiddleware, Middleware
    from lightapi.filters import FieldFilter, OrderingFilter, SearchFilter
    from lightapi.methods import HttpMethod

    return {
        # Auth backends
        "JWTAuthentication": JWTAuthentication,
        "BasicAuthentication": BasicAuthentication,
        # Permissions
        "AllowAny": AllowAny,
        "IsAuthenticated": IsAuthenticated,
        "IsAdminUser": IsAdminUser,
        # Filter backends
        "FieldFilter": FieldFilter,
        "SearchFilter": SearchFilter,
        "OrderingFilter": OrderingFilter,
        # Middleware
        "Middleware": Middleware,
        "CORSMiddleware": CORSMiddleware,
        "AuthenticationMiddleware": AuthenticationMiddleware,
        # HttpMethod mixins (for bases resolution)
        "GET": HttpMethod.GET,
        "POST": HttpMethod.POST,
        "PUT": HttpMethod.PUT,
        "PATCH": HttpMethod.PATCH,
        "DELETE": HttpMethod.DELETE,
    }


def resolve_callable(dotted_path: str) -> Any:
    """Resolve a dotted path like 'myapp.validators.validate_login' to a callable."""
    if "." not in dotted_path:
        raise ConfigurationError(
            f"login_validator must be a dotted path (e.g. myapp.validators.check), "
            f"got '{dotted_path}'"
        )
    module_path, attr_name = dotted_path.rsplit(".", 1)
    try:
        mod = importlib.import_module(module_path)
        fn = getattr(mod, attr_name)
    except (ImportError, AttributeError) as exc:
        raise ConfigurationError(
            f"Cannot resolve login_validator '{dotted_path}': {exc}"
        ) from exc
    if not callable(fn):
        raise ConfigurationError(f"login_validator '{dotted_path}' is not callable.")

    # Validate signature: must be sync function with exactly 2 positional args
    import inspect

    if inspect.iscoroutinefunction(fn):
        raise ConfigurationError(
            f"login_validator '{dotted_path}' is async, but sync function required. "
            f"Login validation must be a synchronous function."
        )

    try:
        sig = inspect.signature(fn)
    except ValueError:
        # Some callables (e.g., builtins) don't have inspectable signatures
        return fn

    # Count required positional parameters
    required_params = 0
    for param in sig.parameters.values():
        if param.kind in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        ):
            if param.default is inspect.Parameter.empty:
                required_params += 1

    if required_params != 2:
        raise ConfigurationError(
            f"login_validator '{dotted_path}' must accept exactly 2 required "
            f"positional parameters (username, password), got {required_params}"
        )

    return fn


def resolve_name(name: str) -> Any:
    """Resolve a class name string to a class.

    Tries the built-in registry first, then falls back to dotted import path
    (e.g. 'myapp.middleware.RequestIdMiddleware').
    """
    registry = name_registry()
    if name in registry:
        return registry[name]
    # Dotted path fallback
    if "." in name:
        module_path, class_name = name.rsplit(".", 1)
        try:
            mod = importlib.import_module(module_path)
            return getattr(mod, class_name)
        except (ImportError, AttributeError) as exc:
            raise ConfigurationError(f"Cannot resolve '{name}': {exc}") from exc
    raise ConfigurationError(
        f"Unknown class name '{name}'. "
        "Use a fully dotted import path for custom classes."
    )
