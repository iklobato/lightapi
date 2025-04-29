from sqlalchemy import Column, Integer, String
from lightapi.core import LightApi, Middleware, Response
from lightapi.rest import RestEndpoint
import time
import uuid

# Logging middleware to track request/response times
class LoggingMiddleware(Middleware):
    def process(self, request, response):
        # Add request ID for tracking
        request_id = str(uuid.uuid4())
        request.id = request_id
        
        # Log request details
        print(f"[{request_id}] Request: {request.method} {request.url.path}")
        
        # Measure processing time
        start_time = time.time()
        
        # Process the request and get the response
        # If response is already passed, use it as is
        if response is None:
            response = super().process(request, response)
        
        # Calculate processing time
        processing_time = time.time() - start_time
        
        # Log response details
        status_code = getattr(response, 'status_code', '???')
        print(f"[{request_id}] Response: {status_code} (processed in {processing_time:.4f}s)")
        
        return response

# CORS middleware to handle cross-origin requests
class CORSMiddleware(Middleware):
    def __init__(self, allowed_origins=None, allowed_methods=None, allowed_headers=None):
        self.allowed_origins = allowed_origins or ['*']
        self.allowed_methods = allowed_methods or ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
        self.allowed_headers = allowed_headers or ['Authorization', 'Content-Type']
    
    def process(self, request, response):
        # Handle preflight OPTIONS request
        if request.method == 'OPTIONS':
            return Response(
                status_code=204,
                headers={
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Methods': ', '.join(self.allowed_methods),
                    'Access-Control-Allow-Headers': ', '.join(self.allowed_headers),
                    'Access-Control-Max-Age': '86400',  # 24 hours
                }
            )
        
        # Process the request
        if response is None:
            response = super().process(request, response)
        
        # Add CORS headers to response
        if hasattr(response, 'headers'):
            response.headers['Access-Control-Allow-Origin'] = '*'
        
        return response

# Rate limiting middleware
class RateLimitMiddleware(Middleware):
    def __init__(self, limit=100, window=60):
        self.limit = limit  # Maximum number of requests
        self.window = window  # Time window in seconds
        self.clients = {}  # Tracks client request history
    
    def process(self, request, response):
        # Get client IP (or use another identifier like API key)
        client_ip = request.client.host
        current_time = time.time()
        
        # Initialize client tracking if needed
        if client_ip not in self.clients:
            self.clients[client_ip] = []
        
        # Remove old requests outside the current window
        self.clients[client_ip] = [t for t in self.clients[client_ip] 
                                  if current_time - t < self.window]
        
        # Check if client has exceeded rate limit
        if len(self.clients[client_ip]) >= self.limit:
            return Response(
                {"error": "Rate limit exceeded. Try again later."},
                status_code=429,
                headers={"Retry-After": str(self.window)}
            )
        
        # Add current request timestamp
        self.clients[client_ip].append(current_time)
        
        # Process the request
        if response is None:
            response = super().process(request, response)
        
        # Add rate limit headers
        if hasattr(response, 'headers'):
            remaining = self.limit - len(self.clients[client_ip])
            response.headers['X-RateLimit-Limit'] = str(self.limit)
            response.headers['X-RateLimit-Remaining'] = str(remaining)
            response.headers['X-RateLimit-Reset'] = str(int(current_time + self.window))
        
        return response

# A simple resource for testing middleware
class HelloWorldEndpoint(RestEndpoint):
    __abstract__ = True  # Not a database model
    
    def get(self, request):
        # Access the request ID added by middleware
        request_id = getattr(request, 'id', 'unknown')
        
        return {
            "message": "Hello, World!",
            "request_id": request_id,
            "timestamp": time.time()
        }, 200
    
    def post(self, request):
        data = getattr(request, 'data', {})
        name = data.get('name', 'World')
        
        return {
            "message": f"Hello, {name}!",
            "timestamp": time.time()
        }, 201

if __name__ == "__main__":
    app = LightApi(
        database_url="sqlite:///middleware_example.db",
        swagger_title="Middleware Example",
        swagger_version="1.0.0",
        swagger_description="Example showing middleware usage with LightAPI",
    )
    
    # Register endpoints
    app.register({
        '/hello': HelloWorldEndpoint,
    })
    
    # Add middleware (order matters - they're processed in sequence)
    app.add_middleware([
        LoggingMiddleware,
        CORSMiddleware,
        RateLimitMiddleware(limit=10, window=60)  # 10 requests per minute
    ])
    
    print("Server running at http://localhost:8000")
    print("API documentation available at http://localhost:8000/docs")
    print("\nTest the endpoints:")
    print("curl -X GET http://localhost:8000/hello")
    print("curl -X POST http://localhost:8000/hello -H 'Content-Type: application/json' -d '{\"name\": \"Alice\"}'")
    
    app.run(host="localhost", port=8000, debug=True) 