"""Authentication strategies for LightAPI.

Provides strategy pattern for different authentication backends.
"""

from typing import Protocol

from lightapi.auth import BaseAuthentication, BasicAuthentication, JWTAuthentication


class AuthStrategy(Protocol):
    """Protocol for authentication strategies."""

    def create(self, backend: type, config: dict) -> BaseAuthentication:
        """Create an authenticator instance."""
        ...


class DefaultAuthStrategy:
    """Default strategy that creates auth backend as-is."""

    def create(self, backend: type, config: dict) -> BaseAuthentication:
        return backend()


class JWTAuthStrategy:
    """Strategy for JWT authentication."""

    def create(self, backend: type, config: dict) -> BaseAuthentication:
        return JWTAuthentication(
            expiration=config.get("jwt_expiration"),
            algorithm=config.get("jwt_algorithm"),
        )


class BasicAuthStrategy:
    """Strategy for Basic authentication."""

    def __init__(self, login_validator=None):
        self._login_validator = login_validator

    def create(self, backend: type, config: dict) -> BaseAuthentication:
        validator = self._login_validator or config.get("login_validator")
        return BasicAuthentication(login_validator=validator)


class AuthStrategyFactory:
    """Factory for creating authentication strategies."""

    _STRATEGIES: dict[str, AuthStrategy] = {
        "JWTAuthentication": JWTAuthStrategy(),
        "BasicAuthentication": BasicAuthStrategy(),
    }
    _default_validator = None

    @classmethod
    def set_login_validator(cls, validator):
        cls._default_validator = validator
        cls._STRATEGIES["BasicAuthentication"] = BasicAuthStrategy(validator)

    @classmethod
    def create(cls, backend: type, config: dict) -> BaseAuthentication:
        if backend is None:
            return None
        strategy = cls._STRATEGIES.get(backend.__name__, DefaultAuthStrategy())
        return strategy.create(backend, config)
