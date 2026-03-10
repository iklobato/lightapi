"""Simple rate limiting for authentication endpoints."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any, Callable

from starlette.requests import Request
from starlette.responses import JSONResponse


class RateLimiter:
    """
    Simple in-memory rate limiter.

    Tracks requests by IP address and endpoint.
    """

    def __init__(
        self,
        requests_per_minute: int = 10,
        requests_per_hour: int = 100,
        requests_per_day: int = 1000,
    ) -> None:
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.requests_per_day = requests_per_day

        # Storage: {ip: {window: {timestamp: count}}}
        self._store: dict[str, dict[str, dict[float, int]]] = defaultdict(
            lambda: defaultdict(lambda: defaultdict(int))
        )
        self._cleanup_interval = 300  # Cleanup every 5 minutes
        self._last_cleanup = time.time()

    def _cleanup_old_entries(self) -> None:
        """Remove old entries to prevent memory leak."""
        current_time = time.time()
        if current_time - self._last_cleanup < self._cleanup_interval:
            return

        for ip in list(self._store.keys()):
            for window in list(self._store[ip].keys()):
                # Remove entries older than window size
                window_seconds = self._get_window_seconds(window)
                cutoff = current_time - window_seconds

                # Remove old timestamps
                for timestamp in list(self._store[ip][window].keys()):
                    if timestamp < cutoff:
                        del self._store[ip][window][timestamp]

                # Remove empty windows
                if not self._store[ip][window]:
                    del self._store[ip][window]

            # Remove IPs with no windows
            if not self._store[ip]:
                del self._store[ip]

        self._last_cleanup = current_time

    def _get_window_seconds(self, window: str) -> int:
        """Convert window name to seconds."""
        if window == "minute":
            return 60
        elif window == "hour":
            return 3600
        elif window == "day":
            return 86400
        else:
            return 60

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request."""
        # Try common headers for proxy setups
        for header in ("X-Forwarded-For", "X-Real-IP", "X-Client-IP"):
            if header in request.headers:
                ip = request.headers[header].split(",")[0].strip()
                if ip:
                    return ip

        # Fall back to client host
        return request.client.host if request.client else "0.0.0.0"

    def is_rate_limited(self, request: Request, endpoint: str = "") -> bool:
        """
        Check if request should be rate limited.

        Args:
            request: The HTTP request.
            endpoint: Optional endpoint identifier for per-endpoint limiting.

        Returns:
            bool: True if rate limited, False otherwise.
        """
        self._cleanup_old_entries()

        client_ip = self._get_client_ip(request)
        current_time = time.time()

        # Check each window
        windows = [
            ("minute", self.requests_per_minute),
            ("hour", self.requests_per_hour),
            ("day", self.requests_per_day),
        ]

        for window_name, limit in windows:
            window_seconds = self._get_window_seconds(window_name)
            window_key = f"{endpoint}:{window_name}" if endpoint else window_name

            # Count requests in this window
            count = 0
            for timestamp, request_count in self._store[client_ip][window_key].items():
                if current_time - timestamp < window_seconds:
                    count += request_count

            if count >= limit:
                return True

            # Add current request
            self._store[client_ip][window_key][current_time] = (
                self._store[client_ip][window_key].get(current_time, 0) + 1
            )

        return False

    def get_rate_limit_response(self, request: Request) -> JSONResponse:
        """Get standard rate limit exceeded response."""
        return JSONResponse(
            {
                "error": "rate_limit_exceeded",
                "detail": "Too many requests. Please try again later.",
            },
            status_code=429,
            headers={
                "Retry-After": "60",  # Retry after 60 seconds
                "X-RateLimit-Limit": str(self.requests_per_minute),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(time.time() + 60)),
            },
        )


# Global rate limiter instance for auth endpoints
_auth_rate_limiter = RateLimiter(
    requests_per_minute=10,  # 10 requests per minute
    requests_per_hour=100,  # 100 requests per hour
    requests_per_day=1000,  # 1000 requests per day
)


def rate_limit_auth_endpoint(func: Callable) -> Callable:
    """
    Decorator to rate limit authentication endpoints.

    Args:
        func: The endpoint function to decorate.

    Returns:
        Decorated function with rate limiting.
    """

    async def wrapper(request: Request, *args: Any, **kwargs: Any) -> Any:
        if _auth_rate_limiter.is_rate_limited(request, endpoint="auth"):
            return _auth_rate_limiter.get_rate_limit_response(request)
        return await func(request, *args, **kwargs)

    return wrapper
