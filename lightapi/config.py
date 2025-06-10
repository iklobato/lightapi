"""Configuration management for LightAPI."""
import json
import os
from typing import List, Optional, Union


class Config:
    """Configuration class that handles environment variables and defaults."""

    def __init__(self):
        # Server settings
        self.host: str = os.getenv("LIGHTAPI_HOST", "127.0.0.1")
        self.port: int = int(os.getenv("LIGHTAPI_PORT", "8000"))
        self.debug: bool = self._parse_bool(os.getenv("LIGHTAPI_DEBUG", "False"))
        self.reload: bool = self._parse_bool(os.getenv("LIGHTAPI_RELOAD", "False"))

        # Database settings
        self.database_url: str = os.getenv(
            "LIGHTAPI_DATABASE_URL", "sqlite:///./app.db"
        )

        # CORS settings
        self.cors_origins: List[str] = self._parse_list(
            os.getenv("LIGHTAPI_CORS_ORIGINS", "[]")
        )

        # JWT settings
        self.jwt_secret: Optional[str] = os.getenv("LIGHTAPI_JWT_SECRET")

        # Swagger settings
        self.swagger_title: str = os.getenv(
            "LIGHTAPI_SWAGGER_TITLE", "LightAPI Documentation"
        )
        self.swagger_version: str = os.getenv("LIGHTAPI_SWAGGER_VERSION", "1.0.0")
        self.swagger_description: str = os.getenv(
            "LIGHTAPI_SWAGGER_DESCRIPTION", "API automatic documentation"
        )
        self.enable_swagger: bool = self._parse_bool(
            os.getenv("LIGHTAPI_ENABLE_SWAGGER", "True")
        )

        # Cache settings
        self.cache_timeout: int = int(
            os.getenv("LIGHTAPI_CACHE_TIMEOUT", "3600")
        )  # Default 1 hour

    @staticmethod
    def _parse_bool(value: str) -> bool:
        """Parse string to boolean."""
        return value.lower() in ("true", "1", "yes", "on")

    @staticmethod
    def _parse_list(value: str) -> List[str]:
        """Parse JSON string to list."""
        try:
            result = json.loads(value)
            if isinstance(result, list):
                return result
            return []
        except json.JSONDecodeError:
            return []

    def update(self, **kwargs):
        """Update configuration with provided values."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)


# Global configuration instance
config = Config()
