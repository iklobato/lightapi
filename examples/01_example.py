#!/usr/bin/env python3
"""
LightAPI Hello World Example

This is the simplest possible LightAPI example demonstrating:
- Basic API setup
- Single endpoint creation
- Minimal configuration

Features demonstrated:
- LightApi initialization
- Custom endpoint creation
- Basic HTTP methods
- Swagger documentation
"""

from lightapi import LightApi, Response, RestEndpoint

# Constants
DEFAULT_PORT = 8000

if __name__ == "__main__":
    # Define endpoint class in main section
    class HelloEndpoint(RestEndpoint):
        """Simple hello world endpoint without database."""
        __tablename__ = "hello_endpoint"
        
        def get(self, request):
            """Return a simple hello message."""
            return Response(
                body={"message": "Hello, World!", "framework": "LightAPI"},
                status_code=200
            )
        
        def post(self, request):
            """Echo back the request data."""
            try:
                data = request.json()
                return Response(
                    body={"echo": data, "message": "Data received successfully"},
                    status_code=201
                )
            except Exception as e:
                return Response(
                    body={"error": "Invalid JSON", "details": str(e)},
                    status_code=400
                )

    def _print_usage():
        """Print usage instructions."""
        print("🚀 LightAPI Hello World Example")
        print("=" * 50)
        print("Server running at http://localhost:8000")
        print("API documentation available at http://localhost:8000/docs")
        print()
        print("Available endpoints:")
        print("• GET /hello_endpoint - Returns hello message")
        print("• POST /hello_endpoint - Echoes back request data")
        print()
        print("Try these example queries:")
        print("  curl http://localhost:8000/hello_endpoint")
        print("  curl -X POST http://localhost:8000/hello_endpoint -H 'Content-Type: application/json' -d '{\"name\": \"World\"}'")

    # Create and run the application
    app = LightApi()
    app.register(HelloEndpoint)
    
    _print_usage()
    
    # Run the server
    app.run(host="localhost", port=DEFAULT_PORT, debug=True)