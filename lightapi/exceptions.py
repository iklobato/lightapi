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
        super().__init__(
            f"Missing implementation for {handler_name} required for HTTP verb: {verb}. "
            f"Please implement this handler in the subclass."
        )
