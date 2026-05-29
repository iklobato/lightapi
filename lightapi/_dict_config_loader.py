"""Simple programmatic configuration loader for LightAPI.

Provides a simpler alternative to YAML config for programmatic setup.
"""

from __future__ import annotations

from typing import Any


def load_from_dict(
    app_cls: type,
    config: dict[str, Any],
    **overrides: Any,
) -> Any:
    """Load LightApi configuration from a Python dictionary.

    Args:
        app_cls: LightApi class
        config: Configuration dictionary with keys:
            - database_url: str
            - mode: "sync" | "async"
            - cors: list[str]
            - endpoints: dict[str, dict]
            - login_validator: callable
        overrides: Additional kwargs to override config values

    Example::

        config = {
            "database_url": "sqlite:///db.sqlite3",
            "endpoints": {
                "/books": {
                    "fields": {"title": str, "author": str},
                    "auth": "jwt",
                },
            },
        }
    """
    from lightapi import RestEndpoint
    from lightapi.auth import AllowAny, JWTAuthentication
    from lightapi.config import Authentication, Pagination

    database_url = config.get("database_url")
    mode = config.get("mode", "sync")
    cors_origins = config.get("cors")
    endpoints_config = config.get("endpoints", {})
    login_validator = config.get("login_validator")

    # Create app instance
    constructor_kwargs: dict[str, Any] = {
        "database_url": database_url,
        "mode": mode,
        "cors_origins": cors_origins,
        "login_validator": login_validator,
    }
    constructor_kwargs.update(overrides)

    instance = app_cls(**constructor_kwargs)

    # Build endpoint classes from config
    mapping: dict[str, type] = {}

    for route, endpoint_config in endpoints_config.items():
        fields = endpoint_config.get("fields", {})
        auth = endpoint_config.get("auth")
        paginate = endpoint_config.get("paginate")
        filters = endpoint_config.get("filters")
        methods = endpoint_config.get("methods")

        # Build class attributes
        class_attrs: dict[str, Any] = {}

        # Add fields — __annotations__ is required for RestEndpointMeta to
        # detect field names; values must be Field() instances (or absent).
        annotations: dict[str, Any] = {}
        for field_name, field_type in fields.items():
            if isinstance(field_type, type):
                annotations[field_name] = field_type
            else:
                annotations[field_name] = type(field_type)
        class_attrs["__annotations__"] = annotations

        # Build Meta class
        meta_attrs: dict[str, Any] = {}

        if auth:
            if auth == "jwt":
                meta_attrs["authentication"] = Authentication(
                    backend=JWTAuthentication,
                    permission=AllowAny,
                )
            elif auth == "basic":
                from lightapi.auth import BasicAuthentication

                meta_attrs["authentication"] = Authentication(
                    backend=BasicAuthentication,
                    permission=AllowAny,
                )

        if paginate:
            if isinstance(paginate, dict):
                meta_attrs["pagination"] = Pagination(**paginate)
            elif paginate is True:
                meta_attrs["pagination"] = Pagination()

        if filters:
            from lightapi.config import Filtering

            if isinstance(filters, dict):
                meta_attrs["filtering"] = Filtering(**filters)
            elif isinstance(filters, list):
                meta_attrs["filtering"] = Filtering(backends=filters)

        Meta = type("Meta", (), meta_attrs)
        class_attrs["Meta"] = Meta

        # Resolve HttpMethod mixin bases so _allowed_methods is set correctly.
        # Setting class_attrs["__bases__"] has no effect on type(); the bases
        # must be passed as the second argument to type().
        http_bases: list[type] = []
        if methods:
            from lightapi.methods import HttpMethod

            _method_map = {
                "GET": HttpMethod.GET,
                "POST": HttpMethod.POST,
                "PUT": HttpMethod.PUT,
                "PATCH": HttpMethod.PATCH,
                "DELETE": HttpMethod.DELETE,
            }
            for method in methods:
                mixin = _method_map.get(method.upper())
                if mixin is not None:
                    http_bases.append(mixin)

        # Create endpoint class — include HttpMethod mixins in bases so that
        # RestEndpointMeta._process picks them up via the MRO scan.
        class_name = _route_to_class_name(route)
        endpoint_cls = type(class_name, (RestEndpoint, *http_bases), class_attrs)

        mapping[route] = endpoint_cls

    if mapping:
        instance.register(mapping)

    return instance


def _route_to_class_name(route: str) -> str:
    """Convert /books to BooksEndpoint."""
    parts = route.strip("/").split("/")
    return "".join(part.capitalize() for part in parts) + "Endpoint"
