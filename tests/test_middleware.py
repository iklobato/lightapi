from unittest.mock import MagicMock

import pytest

from lightapi.core import Middleware, Response


class LoggingMiddleware(Middleware):
    def process(self, request, response):
        self.logged_request = request
        return response


class HeaderModifyingMiddleware(Middleware):
    def process(self, request, response):
        if response:
            response.headers["X-Test-Header"] = "test-value"
        return response


class ResponseModifyingMiddleware(Middleware):
    def process(self, request, response):
        if response:
            return Response({"modified": "response"}, 200)
        return response


class RequestBlockingMiddleware(Middleware):
    def process(self, request, response):
        return Response({"error": "blocked"}, 403)


class TestMiddleware:
    def test_base_middleware(self):
        middleware = Middleware()
        mock_request = MagicMock()
        mock_response = MagicMock()

        result = middleware.process(mock_request, mock_response)

        assert result == mock_response

    def test_logging_middleware(self):
        middleware = LoggingMiddleware()
        mock_request = MagicMock()
        mock_response = MagicMock()

        result = middleware.process(mock_request, mock_response)

        assert middleware.logged_request == mock_request
        assert result == mock_response

    def test_header_modifying_middleware(self):
        middleware = HeaderModifyingMiddleware()
        mock_request = MagicMock()
        mock_response = MagicMock()
        mock_response.headers = {}

        result = middleware.process(mock_request, mock_response)

        assert result == mock_response
        assert result.headers["X-Test-Header"] == "test-value"

    def test_response_modifying_middleware(self):
        middleware = ResponseModifyingMiddleware()
        mock_request = MagicMock()
        mock_response = MagicMock()

        result = middleware.process(mock_request, mock_response)

        assert result != mock_response
        assert isinstance(result, Response)
        assert result.status_code == 200
        assert "modified" in str(result.body) or "modified" in result.body

    def test_request_blocking_middleware(self):
        middleware = RequestBlockingMiddleware()
        mock_request = MagicMock()

        result = middleware.process(mock_request, None)

        assert isinstance(result, Response)
        assert result.status_code == 403
        assert "error" in str(result.body) or "error" in result.body

    def test_middleware_with_no_response(self):
        middleware = HeaderModifyingMiddleware()
        mock_request = MagicMock()

        result = middleware.process(mock_request, None)

        assert result is None
