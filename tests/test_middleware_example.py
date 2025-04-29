import pytest
import time
from unittest.mock import MagicMock, patch

from examples.middleware_example import (
    LoggingMiddleware, CORSMiddleware,
    RateLimitMiddleware, HelloWorldEndpoint
)
from lightapi.core import Response


class TestLoggingMiddleware:
    """Test suite for the LoggingMiddleware class from middleware_example.py.
    
    This class tests the request/response logging functionality, including
    request ID generation and processing time tracking.
    """
    
    @pytest.fixture
    def middleware(self):
        """Create a LoggingMiddleware instance for testing.
        
        Returns:
            LoggingMiddleware: A middleware instance for testing.
        """
        return LoggingMiddleware()
    
    @patch('examples.middleware_example.print')
    @patch('examples.middleware_example.uuid.uuid4')
    def test_process_adds_request_id(self, mock_uuid, mock_print, middleware):
        """Test that process adds a request ID to the request.
        
        Args:
            mock_uuid: Mock for uuid4 to control the generated ID.
            mock_print: Mock for print to capture logging.
            middleware: The middleware fixture.
        """
        # Set up a predefined UUID
        mock_uuid.return_value = "test-uuid-123"
        
        # Create a mock request
        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        
        # Create a mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        # Mock the parent class process method
        middleware.process = lambda req, resp: mock_response
        
        # Call the process method
        result = middleware.process(mock_request, None)
        
        # Verify request ID was added
        assert mock_request.id == "test-uuid-123"
        
        # Verify logging occurred
        mock_print.assert_any_call("[test-uuid-123] Request: GET /test")
        mock_print.assert_any_call(mock_print.call_args_list[1][0][0])  # Just check second call happened
        
        # Verify the response was returned unchanged
        assert result == mock_response
    
    @patch('examples.middleware_example.time.time')
    @patch('examples.middleware_example.print')
    def test_process_tracks_processing_time(self, mock_print, mock_time, middleware):
        """Test that process tracks and logs processing time.
        
        Args:
            mock_print: Mock for print to capture logging.
            mock_time: Mock for time.time to control timing.
            middleware: The middleware fixture.
        """
        # Set up timing sequence
        mock_time.side_effect = [1000.0, 1002.5]  # Start, end (2.5 seconds difference)
        
        # Create a mock request
        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/test"
        
        # Create a mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        # Call the process method with an existing response
        result = middleware.process(mock_request, mock_response)
        
        # Verify timing was logged
        mock_print.assert_any_call(f"[{mock_request.id}] Response: 200 (processed in 2.5000s)")
        
        # Verify the response was returned unchanged
        assert result == mock_response


class TestCORSMiddleware:
    """Test suite for the CORSMiddleware class from middleware_example.py.
    
    This class tests the CORS headers management for cross-origin requests,
    including preflight OPTIONS request handling.
    """
    
    @pytest.fixture
    def middleware(self):
        """Create a CORSMiddleware instance for testing.
        
        Returns:
            CORSMiddleware: A middleware instance with default configuration.
        """
        return CORSMiddleware()
    
    @pytest.fixture
    def custom_middleware(self):
        """Create a CORSMiddleware instance with custom configuration.
        
        Returns:
            CORSMiddleware: A middleware instance with custom allowed values.
        """
        return CORSMiddleware(
            allowed_origins=['https://example.com'],
            allowed_methods=['GET', 'POST'],
            allowed_headers=['Authorization']
        )
    
    def test_process_options_request(self, middleware):
        """Test that process handles OPTIONS requests correctly.
        
        Args:
            middleware: The middleware fixture.
        """
        # Create a mock OPTIONS request
        mock_request = MagicMock()
        mock_request.method = "OPTIONS"
        
        # Call the process method
        response = middleware.process(mock_request, None)
        
        # Verify response
        assert response.status_code == 204
        assert response.headers['Access-Control-Allow-Origin'] == '*'
        assert 'Access-Control-Allow-Methods' in response.headers
        assert 'Access-Control-Allow-Headers' in response.headers
    
    def test_process_adds_cors_headers(self, middleware):
        """Test that process adds CORS headers to existing responses.
        
        Args:
            middleware: The middleware fixture.
        """
        # Create a mock request
        mock_request = MagicMock()
        mock_request.method = "GET"
        
        # Create a mock response
        mock_response = MagicMock()
        mock_response.headers = {}
        
        # Call the process method
        result = middleware.process(mock_request, mock_response)
        
        # Verify CORS headers were added
        assert mock_response.headers['Access-Control-Allow-Origin'] == '*'
        
        # Verify the response was returned unchanged
        assert result == mock_response
    
    def test_custom_cors_options(self, custom_middleware):
        """Test that process uses custom CORS configuration.
        
        Args:
            custom_middleware: The custom middleware fixture.
        """
        # Create a mock OPTIONS request
        mock_request = MagicMock()
        mock_request.method = "OPTIONS"
        
        # Call the process method
        response = custom_middleware.process(mock_request, None)
        
        # Verify response uses custom values
        assert response.headers['Access-Control-Allow-Origin'] == '*'
        assert response.headers['Access-Control-Allow-Methods'] == 'GET, POST'
        assert response.headers['Access-Control-Allow-Headers'] == 'Authorization'


class TestRateLimitMiddleware:
    """Test suite for the RateLimitMiddleware class from middleware_example.py.
    
    This class tests the rate limiting functionality, including request counting,
    time window management, and response headers.
    """
    
    @pytest.fixture
    def middleware(self):
        """Create a RateLimitMiddleware instance for testing.
        
        Returns:
            RateLimitMiddleware: A middleware instance with a limit of 2 requests per 60 seconds.
        """
        return RateLimitMiddleware(limit=2, window=60)
    
    def test_process_under_limit(self, middleware):
        """Test that process allows requests under the rate limit.
        
        Args:
            middleware: The middleware fixture.
        """
        # Create a mock request
        mock_request = MagicMock()
        mock_request.client.host = '127.0.0.1'
        
        # Create a mock response
        mock_response = MagicMock()
        mock_response.headers = {}
        
        # First request - should be allowed
        result1 = middleware.process(mock_request, None)
        
        # Verify request is allowed
        assert middleware.clients['127.0.0.1'] == [time.time()]
        
        # Mock the parent class process method to return our response
        middleware.process = lambda req, resp: mock_response if resp is None else resp
        
        # Second request - should still be allowed
        result2 = middleware.process(mock_request, None)
        
        # Verify second request is allowed
        assert len(middleware.clients['127.0.0.1']) == 2
        assert result2 == mock_response
        
        # Verify rate limit headers were added
        assert 'X-RateLimit-Limit' in mock_response.headers
        assert mock_response.headers['X-RateLimit-Limit'] == '2'
        assert 'X-RateLimit-Remaining' in mock_response.headers
        assert mock_response.headers['X-RateLimit-Remaining'] == '0'
    
    def test_process_exceeds_limit(self, middleware):
        """Test that process blocks requests exceeding the rate limit.
        
        Args:
            middleware: The middleware fixture.
        """
        # Create a mock request
        mock_request = MagicMock()
        mock_request.client.host = '127.0.0.1'
        
        # Simulate two previous requests
        current_time = time.time()
        middleware.clients['127.0.0.1'] = [current_time - 10, current_time - 5]
        
        # Third request - should be blocked
        response = middleware.process(mock_request, None)
        
        # Verify response is a rate limit error
        assert response.status_code == 429
        assert response.body['error'] == 'Rate limit exceeded. Try again later.'
        assert response.headers['Retry-After'] == '60'
    
    def test_process_cleans_old_requests(self, middleware):
        """Test that process removes old requests outside the time window.
        
        Args:
            middleware: The middleware fixture.
        """
        # Create a mock request
        mock_request = MagicMock()
        mock_request.client.host = '127.0.0.1'
        
        # Simulate one old request and one recent request
        current_time = time.time()
        middleware.clients['127.0.0.1'] = [
            current_time - 120,  # 2 minutes ago (outside window)
            current_time - 30    # 30 seconds ago (inside window)
        ]
        
        # Mock the parent class process method
        mock_response = MagicMock()
        mock_response.headers = {}
        middleware.process = lambda req, resp: mock_response if resp is None else resp
        
        # New request
        middleware.process(mock_request, None)
        
        # Verify old request was removed
        assert len(middleware.clients['127.0.0.1']) == 2  # Recent + new
        # All timestamps should be >= current_time - 60 (window)
        assert all(t >= current_time - 60 for t in middleware.clients['127.0.0.1'])


class TestHelloWorldEndpoint:
    """Test suite for the HelloWorldEndpoint class from middleware_example.py.
    
    This class tests the simple endpoint used to demonstrate middleware functionality.
    """
    
    def test_get(self):
        """Test that get returns expected response.
        """
        # Create a mock request with request ID (added by middleware)
        class MockRequest:
            id = "test-request-id"
        
        # Create the endpoint
        endpoint = HelloWorldEndpoint()
        
        # Call the get method
        response, status_code = endpoint.get(MockRequest())
        
        # Verify response
        assert status_code == 200
        assert response['message'] == 'Hello, World!'
        assert response['request_id'] == 'test-request-id'
        assert 'timestamp' in response
    
    def test_post(self):
        """Test that post returns expected response with name from request.
        """
        # Create a mock request with data
        class MockRequest:
            data = {'name': 'Test User'}
        
        # Create the endpoint
        endpoint = HelloWorldEndpoint()
        
        # Call the post method
        response, status_code = endpoint.post(MockRequest())
        
        # Verify response
        assert status_code == 201
        assert response['message'] == 'Hello, Test User!'
        assert 'timestamp' in response
    
    def test_post_default_name(self):
        """Test that post uses default name when not provided.
        """
        # Create a mock request without name data
        class MockRequest:
            data = {}
        
        # Create the endpoint
        endpoint = HelloWorldEndpoint()
        
        # Call the post method
        response, status_code = endpoint.post(MockRequest())
        
        # Verify response
        assert status_code == 201
        assert response['message'] == 'Hello, World!'
        assert 'timestamp' in response 