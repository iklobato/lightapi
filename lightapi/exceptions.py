class ConfigurationError(Exception):
    """Raised when a RestEndpoint or LightApi configuration is invalid at startup."""


class SerializationError(Exception):
    """Raised when a database row cannot be converted to a serializable dict."""


class MissingHandlerImplementationError(Exception):
    """
    Exception raised when a required HTTP handler is not implemented.

    This exception is raised when a subclass of a handler class does not implement
    a method that is required to handle a specific HTTP verb.

    Attributes:
        handler_name: The name of the handler that should be implemented.
        verb: The HTTP verb that requires the handler.
    """

    def __init__(self, handler_name: str, verb: str) -> None:
        """
        Initialize the exception.

        Args:
            handler_name: The name of the handler that should be implemented.
            verb: The HTTP verb that requires the handler.
        """
        msg = (
            f"Missing implementation for {handler_name} required for HTTP verb: "
            f"{verb}. Please implement this handler in the subclass."
        )
        super().__init__(msg)
