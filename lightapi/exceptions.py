class ConfigurationError(Exception):
    """Raised when a RestEndpoint or LightApi configuration is invalid at startup."""


class SerializationError(Exception):
    """Raised when a database row cannot be converted to a serializable dict."""
