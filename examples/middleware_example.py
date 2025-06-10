import time
import uuid

from sqlalchemy import Column, Integer, String

from lightapi.core import LightApi, Middleware, Response
from lightapi.rest import RestEndpoint


# Logging middleware to track request/response times
class LoggingMiddleware(Middleware):
    """
    Middleware for request logging.

    Logs request details and adds a unique ID to each request.
    """

    def process(self, request, response=None):
        """
        Process an HTTP request.

        If the response is None, this is being called before the request is handled.
        Otherwise, it's being called after the request has been handled.

        Args:
            request: The HTTP request.
            response: The HTTP response, or None if processing a new request.

        Returns:
            Response: A custom response, or None to continue processing.
        """
        if response is None:
            # Generate a unique ID for this request
            request_id = str(uuid.uuid4())
            # Actually set the ID as an attribute of the request object, not just via mock behavior
            request.id = request_id

            # Log request details - match expected format in test
            print(f"[{request_id}] Request: {request.method} {request.url.path}")

            # Continue processing
            return super().process(request, response)
        else:
            # Log response details
            print(
                f"[{getattr(request, 'id', 'unknown')}] Response: {response.status_code}"
            )

            # Add response headers
            if not hasattr(response, "headers"):
                response.headers = {}
            response.headers["X-Request-ID"] = getattr(request, "id", "unknown")

            return response


# CORS middleware to handle cross-origin requests
class CORSMiddleware(Middleware):
    """
    Middleware for handling Cross-Origin Resource Sharing (CORS).

    Adds CORS headers to responses and handles preflight OPTIONS requests.
    """

    # CORS configuration
    allowed_origins = ["*"]
    allowed_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    allowed_headers = ["Authorization", "Content-Type"]
    max_age = 86400  # 24 hours

    def process(self, request, response=None):
        """
        Process an HTTP request.

        Adds CORS headers to responses and handles OPTIONS requests.

        Args:
            request: The HTTP request.
            response: The HTTP response, or None if processing a new request.

        Returns:
            Response: A custom response, or None to continue processing.
        """
        if request.method == "OPTIONS":
            # Handle preflight request
            return Response(
                None,
                status_code=204,
                headers={
                    "Access-Control-Allow-Origin": ",".join(self.allowed_origins),
                    "Access-Control-Allow-Methods": ",".join(self.allowed_methods),
                    "Access-Control-Allow-Headers": ",".join(self.allowed_headers),
                    "Access-Control-Max-Age": str(self.max_age),
                },
            )
        elif response:
            # Add CORS headers to the response
            response.headers["Access-Control-Allow-Origin"] = ",".join(
                self.allowed_origins
            )
            return response
        else:
            # Continue processing
            return super().process(request, response)


# Rate limiting middleware
class RateLimitMiddleware(Middleware):
    """
    Middleware for rate limiting requests.

    Limits the number of requests per client IP address within a time window.
    """

    def __init__(self):
        """
        Initialize the middleware.
        """
        self.clients = {}
        self.requests_per_minute = 2  # Maximum 2 requests per minute
        self.window = 60  # 60 second window

    def process(self, request, response=None):
        """
        Process an HTTP request.

        Rate limits requests based on client IP address.

        Args:
            request: The HTTP request.
            response: The HTTP response, or None if processing a new request.

        Returns:
            Response: A custom response, or None to continue processing.
        """
        if response:
            # Just pass through if we already have a response
            return response

        # Get client IP address
        client_ip = getattr(request.client, "host", "127.0.0.1")

        # Get current time
        current_time = time.time()

        # Initialize client entry if needed
        if client_ip not in self.clients:
            self.clients[client_ip] = []

        # Clean up old requests
        # For tests, we need to move this to only occur on actual new requests
        recent_requests = []
        for req_time in self.clients[client_ip]:
            # Use greater than or equal to avoid test flakiness
            if req_time >= current_time - self.window:
                recent_requests.append(req_time)
        self.clients[client_ip] = recent_requests

        # Check rate limit
        if len(self.clients[client_ip]) >= self.requests_per_minute:
            # Rate limit exceeded
            return Response(
                {"error": "Rate limit exceeded. Try again later."},
                status_code=429,
                headers={"Retry-After": str(self.window)},
            )

        # Add this request to the list
        self.clients[client_ip].append(current_time)

        # Continue processing
        return super().process(request, response)


# A simple resource for testing middleware
class HelloWorldEndpoint(RestEndpoint):
    __abstract__ = True  # Not a database model

    def get(self, request):
        # Access the request ID added by middleware
        request_id = getattr(request, "id", "unknown")

        return {
            "message": "Hello, World!",
            "request_id": request_id,
            "timestamp": time.time(),
        }, 200

    def post(self, request):
        data = getattr(request, "data", {})
        name = data.get("name", "World")

        return {"message": f"Hello, {name}!", "timestamp": time.time()}, 201


if __name__ == "__main__":
    app = LightApi(
        database_url="sqlite:///middleware_example.db",
        swagger_title="Middleware Example",
        swagger_version="1.0.0",
        swagger_description="Example showing middleware usage with LightAPI",
    )

    # Register endpoints
    app.register(
        {
            "/hello": HelloWorldEndpoint,
        }
    )

    # Add middleware (order matters - they're processed in sequence)
    app.add_middleware([LoggingMiddleware, CORSMiddleware, RateLimitMiddleware])

    print("Server running at http://localhost:8000")
    print("API documentation available at http://localhost:8000/docs")
    print("\nTest the endpoints:")
    print("curl -X GET http://localhost:8000/hello")
    print(
        "curl -X POST http://localhost:8000/hello -H 'Content-Type: application/json' -d '{\"name\": \"Alice\"}'"
    )

    app.run(host="localhost", port=8000, debug=True)
