import os
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type, Union
from functools import partial

from lightapi import (
    LightApi,
    JWTAuthentication,
    RedisCache,
    ParameterFilter,
    Validator,
    RestEndpoint
)
from starlette.middleware.cors import CORSMiddleware

from middleware import LoggingMiddleware
from pagination import Paginator


class ConfigurationError(Exception):
    pass


@dataclass
class EndpointConfig:
    access: str
    operations: list[str]
    filters: Optional[list[str]] = None
    headers: Optional[Dict[str, Dict[str, str]]] = None
    auth: bool = False
    cache: Optional[Dict[str, Any]] = None
    pagination: Optional[Dict[str, Any]] = None
    validator_class: Optional[Type] = None

    def __post_init__(self):
        if self.cache is None:
            self.cache = {"enabled": False}
        if self.pagination is None:
            self.pagination = {"enabled": False}


@dataclass
class MiddlewareConfig:
    name: str
    enabled: bool
    settings: Optional[Dict[str, Any]] = None
    response: Optional[Dict[str, Any]] = None


@dataclass
class AuthConfig:
    enabled: bool = False
    secret: str = ""
    algorithm: str = "HS256"
    expire_hours: int = 24
    exclude_paths: list[str] = field(default_factory=lambda: ["/health", "/docs"])
    token_prefix: str = "Bearer"


@dataclass
class CacheConfig:
    enabled: bool = False
    type: str = "redis"
    url: str = "redis://localhost"
    ttl: int = 300
    prefix: str = "api:cache:"
    methods: list[str] = field(default_factory=lambda: ["GET"])


@dataclass
class PaginationConfig:
    enabled: bool = True
    limit: int = 20
    max_limit: int = 100
    sort_enabled: bool = True


@dataclass
class ResponseConfig:
    envelope: bool = True
    format: Dict[str, Dict[str, Any]] = field(
        default_factory=lambda: {
            "success": {"data": None, "message": "Success", "status": 200},
            "error": {"error": True, "message": None, "status": None},
        }
    )


@dataclass
class APIConfig:
    name: str
    environment: str
    database: str
    endpoints: Dict[str, EndpointConfig]
    middleware: list[MiddlewareConfig]
    auth: AuthConfig
    filters: Dict[str, list[str]]
    pagination: PaginationConfig
    cache: CacheConfig
    responses: ResponseConfig


class ConfigLoader:
    def __init__(self, config_path: Union[str, Path]):
        self.config_path = Path(config_path)
        self.config: Optional[APIConfig] = None
        self._env_cache: Dict[str, str] = {}

    def _resolve_env_vars(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {k: self._resolve_env_vars(v) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._resolve_env_vars(v) for v in value]
        elif isinstance(value, str) and value.startswith("${") and value.endswith("}"):
            env_var = value[2:-1]
            if env_var not in self._env_cache:
                self._env_cache[env_var] = os.environ.get(env_var, "")
            return self._env_cache[env_var]
        return value

    def _load_yaml(self) -> dict:
        if not self.config_path.exists():
            raise ConfigurationError(
                f"Configuration file not found: {self.config_path}"
            )

        try:
            with open(self.config_path) as f:
                config = yaml.safe_load(f)
            return self._resolve_env_vars(config)
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML configuration: {e}")
        except Exception as e:
            raise ConfigurationError(f"Error reading configuration file: {e}")

    def _get_nested_value(self, data: dict, path: str, default: Any = None) -> Any:
        try:
            for key in path.split('.'):
                data = data[key]
            return data
        except (KeyError, TypeError):
            return default

    def _create_endpoint_configs(
        self, endpoints_data: dict
    ) -> Dict[str, EndpointConfig]:
        endpoints = {}
        for endpoint_name, endpoint_config in endpoints_data.items():
            try:
                validator_class = None
                if "validator" in endpoint_config:
                    # Dynamic validator class creation based on config
                    validator_fields = endpoint_config["validator"].get("fields", {})
                    validator_class = type(
                        f"{endpoint_name.title()}Validator",
                        (Validator,),
                        {
                            f"validate_{field}": lambda x, field=field: x
                            for field in validator_fields
                        },
                    )

                endpoints[endpoint_name] = EndpointConfig(
                    access=endpoint_config["access"],
                    operations=endpoint_config["operations"],
                    filters=endpoint_config.get("filters"),
                    headers=endpoint_config.get("headers"),
                    auth=endpoint_config.get("auth", False),
                    cache=endpoint_config.get("cache"),
                    pagination=endpoint_config.get("pagination"),
                    validator_class=validator_class,
                )
            except KeyError as e:
                raise ConfigurationError(
                    f"Missing required field {e} in endpoint configuration for {endpoint_name}"
                )
        return endpoints

    def _create_middleware_configs(
        self, middleware_data: list
    ) -> List[MiddlewareConfig]:
        middleware = []
        for idx, mw_config in enumerate(middleware_data):
            try:
                middleware.append(
                    MiddlewareConfig(
                        name=mw_config["name"],
                        enabled=mw_config["enabled"],
                        settings=mw_config.get("settings"),
                        response=mw_config.get("response"),
                    )
                )
            except KeyError as e:
                raise ConfigurationError(
                    f"Missing required field {e} in middleware configuration at index {idx}"
                )
        return middleware

    def _create_auth_config(self, auth_data: dict) -> AuthConfig:
        jwt_config = auth_data.get("jwt", {})
        return AuthConfig(
            enabled=jwt_config.get("enabled", False),
            secret=jwt_config.get("secret", ""),
            algorithm=jwt_config.get("algorithm", "HS256"),
            expire_hours=jwt_config.get("expire_hours", 24),
            exclude_paths=jwt_config.get("exclude_paths", []),
            token_prefix=jwt_config.get("token_prefix", "Bearer"),
        )

    def _create_cache_config(self, cache_data: dict) -> CacheConfig:
        default_cache = cache_data.get("default", {})
        return CacheConfig(
            enabled=default_cache.get("enabled", False),
            type=default_cache.get("type", "redis"),
            url=default_cache.get("url", "redis://localhost"),
            ttl=default_cache.get("ttl", 300),
            prefix=default_cache.get("prefix", "api:cache:"),
            methods=default_cache.get("methods", ["GET"]),
        )

    def _create_pagination_config(self, pagination_data: dict) -> PaginationConfig:
        default_pagination = pagination_data.get("default", {})
        return PaginationConfig(
            enabled=default_pagination.get("enabled", True),
            limit=default_pagination.get("limit", 20),
            max_limit=default_pagination.get("max_limit", 100),
            sort_enabled=default_pagination.get("sort_enabled", True),
        )

    def _create_response_config(self, response_data: dict) -> ResponseConfig:
        return ResponseConfig(
            envelope=response_data.get("envelope", True),
            format=response_data.get(
                "format",
                {
                    "success": {"data": None, "message": "Success", "status": 200},
                    "error": {"error": True, "message": None, "status": None},
                },
            ),
        )

    def _validate_required_fields(self, data: dict) -> None:
        required_fields = {
            "api.name": "API name",
            "api.database": "Database configuration",
        }

        get_value = partial(self._get_nested_value, data)
        missing_fields = [
            desc for path, desc in required_fields.items() if not get_value(path)
        ]

        if missing_fields:
            raise ConfigurationError(
                f"Missing required configuration: {', '.join(missing_fields)}"
            )

    def load(self) -> APIConfig:
        try:
            raw_config = self._load_yaml()
            self._validate_required_fields(raw_config)

            api_config = raw_config.get("api", {})

            self.config = APIConfig(
                name=api_config["name"],
                environment=api_config.get("environment", "dev"),
                database=api_config["database"],
                endpoints=self._create_endpoint_configs(
                    raw_config.get("endpoints", {})
                ),
                middleware=self._create_middleware_configs(
                    raw_config.get("middleware", [])
                ),
                auth=self._create_auth_config(raw_config.get("auth", {})),
                filters=raw_config.get("filters", {}),
                pagination=self._create_pagination_config(
                    raw_config.get("pagination", {})
                ),
                cache=self._create_cache_config(raw_config.get("cache", {})),
                responses=self._create_response_config(raw_config.get("responses", {})),
            )

            return self.config

        except ConfigurationError:
            raise
        except Exception as e:
            raise ConfigurationError(
                f"Unexpected error loading configuration: {e}"
            ) from e

    def get_endpoint_config(self, endpoint_name: str) -> Optional[EndpointConfig]:
        if self.config is None:
            self.load()
        return self.config.endpoints.get(endpoint_name)


class ConfigurableEndpoint(RestEndpoint):
    def __init__(self, config: EndpointConfig):
        super().__init__()
        self.endpoint_config = config

        if config.auth:
            self.Configuration.authentication_class = JWTAuthentication

        self.Configuration.http_method_names = config.operations

        if config.validator_class:
            self.Configuration.validator_class = config.validator_class

        if config.cache and config.cache.get("enabled", False):
            self.Configuration.caching_class = RedisCache
            self.Configuration.caching_method_names = config.cache.get(
                "methods", ["GET"]
            )

        if config.pagination:
            self.Configuration.pagination_class = Paginator
            self._configure_pagination(config.pagination)

        if config.filters:
            self.Configuration.filter_class = ParameterFilter
            self._configure_filters(config.filters)

    def _configure_pagination(self, pagination_config: Dict[str, Any]):
        if isinstance(self.paginator, Paginator):
            self.paginator.limit = pagination_config.get("limit", 20)
            self.paginator.sort = pagination_config.get("sort", False)

    def _configure_filters(self, allowed_fields: list[str]):
        if isinstance(self.filter, ParameterFilter):
            self.filter.allowed_fields = allowed_fields


class CustomAuthMiddleware:
    pass


class ConfigurableLightApi(LightApi):
    def __init__(self, config_path: Union[str, Path]):
        super().__init__()
        self.config_loader = ConfigLoader(config_path)
        self.config = self.config_loader.load()
        self._configure_global_settings()

    def _configure_global_settings(self):
        # Configure middleware
        middleware_classes = []
        for mw_config in self.config.middleware:
            if mw_config.enabled:
                middleware_map = {
                    "cors": CORSMiddleware,
                    "custom_auth": CustomAuthMiddleware,
                    "logging": LoggingMiddleware,
                }

                if mw_config.name in middleware_map:
                    middleware_class = middleware_map[mw_config.name]
                    if mw_config.settings:
                        middleware_classes.append(
                            lambda: middleware_class(**mw_config.settings)
                        )
                    else:
                        middleware_classes.append(middleware_class)

        if middleware_classes:
            self.add_middleware(middleware_classes)

    def register_from_config(self):
        routes = {}
        for endpoint_name, endpoint_config in self.config.endpoints.items():
            endpoint_class = type(
                f"Configured{endpoint_name.title()}Endpoint",
                (ConfigurableEndpoint,),
                {},
            )
            routes[f"/{endpoint_name}"] = lambda conf=endpoint_config: endpoint_class(
                conf
            )

        self.register(routes)

    @classmethod
    def from_config(cls, config_path: Union[str, Path]) -> 'ConfigurableLightApi':
        return cls(config_path)
