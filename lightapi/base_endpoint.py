import json
from abc import ABC, abstractmethod
from http.server import BaseHTTPRequestHandler


class RequestHandlerStrategy(ABC):
    """
    Abstract base class defining the interface for handling HTTP requests.
    """

    @abstractmethod
    def handle(self, request, endpoint) -> str:
        """
        Handle the HTTP request for the given endpoint.

        Args:
            request (BaseHTTPRequestHandler): The request handler instance.
            endpoint (Endpoint): The endpoint associated with the current path.

        Returns:
            str: The JSON-encoded response from the endpoint.

        Raises:
            NotImplementedError: If the method is not implemented by a concrete strategy.
        """
        pass


class GetRequestHandlerStrategy(RequestHandlerStrategy):
    """
    Concrete strategy for handling GET requests.
    """

    def handle(self, request, endpoint):
        """
        Handle a GET request.

        Args:
            request (BaseHTTPRequestHandler): The request handler instance.
            endpoint (Endpoint): The endpoint associated with the current path.

        Returns:
            str: The JSON-encoded response from the endpoint.

        Raises:
            NotImplementedError: If the GET method is not implemented by the endpoint.
        """
        if hasattr(endpoint, "get"):
            response = endpoint.get()
            return json.dumps(response)
        else:
            raise NotImplementedError("GET method not implemented for this endpoint")


class PostRequestHandlerStrategy(RequestHandlerStrategy):
    """
    Concrete strategy for handling POST requests.
    """

    def handle(self, request, endpoint):
        """
        Handle a POST request.

        Args:
            request (BaseHTTPRequestHandler): The request handler instance.
            endpoint (Endpoint): The endpoint associated with the current path.

        Returns:
            str: The JSON-encoded response from the endpoint.

        Raises:
            NotImplementedError: If the POST method is not implemented by the endpoint.
        """
        if hasattr(endpoint, "post"):
            response = endpoint.post()
            return json.dumps(response)
        else:
            raise NotImplementedError("POST method not implemented for this endpoint")


class RequestCommand(ABC):
    """
    Abstract base class defining the interface for executing HTTP requests.
    """

    @abstractmethod
    def execute(self, request, endpoint) -> str:
        """
        Execute the request using the provided strategy.

        Args:
            request (BaseHTTPRequestHandler): The request handler instance.
            endpoint (Endpoint): The endpoint associated with the current path.

        Returns:
            str: The JSON-encoded response from the strategy.
        """
        pass


class ConcreteRequestCommand(RequestCommand):
    """
    Concrete command for executing HTTP requests.
    """

    def __init__(self, strategy: RequestHandlerStrategy):
        """
        Initialize the command with a specific request handling strategy.

        Args:
            strategy (RequestHandlerStrategy): The strategy for handling the HTTP request.
        """
        self.strategy = strategy

    def execute(self, request, endpoint):
        """
        Execute the HTTP request using the encapsulated strategy.

        Args:
            request (BaseHTTPRequestHandler): The request handler instance.
            endpoint (Endpoint): The endpoint associated with the current path.

        Returns:
            str: The JSON-encoded response from the strategy.
        """
        return self.strategy.handle(request, endpoint)


class Router:
    """
    Router class responsible for mapping URLs to endpoint objects.
    """

    def __init__(self):
        """
        Initialize the router with an empty route map.
        """
        self.routes = {}

    def add_route(self, path, endpoint):
        """
        Add a route mapping a URL path to an endpoint.

        Args:
            path (str): The URL path.
            endpoint (Endpoint): The endpoint object to associate with the path.
        """
        self.routes[path] = endpoint

    def get_endpoint(self, path):
        """
        Retrieve the endpoint associated with a given path.

        Args:
            path (str): The URL path.

        Returns:
            Endpoint: The endpoint associated with the path, or None if not found.
        """
        return self.routes.get(path)


class MultiEndpointHandlerSingleton(type):
    """
    Singleton metaclass ensuring a single instance of the handler.
    """

    _instances = {}

    def __call__(cls, *args, **kwargs):
        """
        Create or return the single instance of the handler.

        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.

        Returns:
            Handler: The singleton instance of the handler.
        """
        if cls not in cls._instances:
            cls._instances[cls] = super(MultiEndpointHandlerSingleton, cls).__call__(
                *args, **kwargs
            )
        return cls._instances[cls]


class Handler(BaseHTTPRequestHandler, metaclass=MultiEndpointHandlerSingleton):
    """
    HTTP request handler using the Command Pattern for flexible request processing.
    """

    def __init__(self, *args, **kwargs):
        """
        Initialize the handler with a Router instance.

        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
        """
        self.router = Router()
        super().__init__(*args, **kwargs)

    def do_GET(self):
        """
        Handle the HTTP GET request.
        """
        self.handle_request(GetRequestHandlerStrategy())

    def do_POST(self):
        """
        Handle the HTTP POST request.
        """
        self.handle_request(PostRequestHandlerStrategy())

    def handle_request(self, strategy: RequestHandlerStrategy):
        """
        Handle the HTTP request using the specified strategy.

        Args:
            strategy (RequestHandlerStrategy): The strategy for handling the HTTP request.
        """
        endpoint = self.router.get_endpoint(self.path)
        if not endpoint:
            self.send_error(404, "Endpoint Not Found")
            return

        command = ConcreteRequestCommand(strategy)
        try:
            response = command.execute(self, endpoint)
            self.respond(body=response)
        except NotImplementedError as e:
            self.send_error(405, str(e))

    def respond(self, status_code=200, content_type="application/json", body=None):
        """
        Send an HTTP response with the given status code and body.

        Args:
            status_code (int): The HTTP status code.
            content_type (str): The content type of the response.
            body (str, optional): The body of the response. Defaults to None.
        """
        self.send_response(status_code)
        self.send_header("Content-type", content_type)
        self.end_headers()
        if body:
            self.wfile.write(body.encode("utf-8"))
