"""Simple rate limiting for authentication endpoints."""

from __future__ import annotations

import time
from collections import defaultdict
from enum import Enum
from http import HTTPStatus

from starlette.requests import Request
from starlette.responses import JSONResponse


class RateLimitWindow(str, Enum):
    """A sliding window of the limiter; the value names it in store keys and headers."""

    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"

    @property
    def seconds(self) -> int:
        if self is RateLimitWindow.HOUR:
            return 3600
        if self is RateLimitWindow.DAY:
            return 86400
        return 60

    @classmethod
    def from_key(cls, key: str) -> "RateLimitWindow":
        """The window of a store key such as "auth:minute" or "minute"."""
        return cls(key.rsplit(":", 1)[-1])


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

    @classmethod
    def from_limits(
        cls, limits: dict[str, int], defaults: dict[str, int]
    ) -> RateLimiter:
        """A limiter from ``requests_per_*`` keys; a missing key takes its default."""
        return cls(
            **{name: limits.get(name, default) for name, default in defaults.items()}
        )

    def reset(self) -> None:
        """Reset all rate limit tracking. Useful for testing."""
        self._store.clear()
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
        """Seconds covered by a store key such as "auth:minute"."""
        return RateLimitWindow.from_key(window).seconds

    def _limit_for(self, window: RateLimitWindow) -> int:
        if window is RateLimitWindow.HOUR:
            return self.requests_per_hour
        if window is RateLimitWindow.DAY:
            return self.requests_per_day
        return self.requests_per_minute

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request."""
        # Always prefer the actual client host for security
        if request.client and request.client.host:
            return request.client.host

        # Fallback to headers only if client host is not available
        for header in ("X-Forwarded-For", "X-Real-IP", "X-Client-IP"):
            if header in request.headers:
                ip = request.headers[header].split(",")[0].strip()
                if ip:
                    return ip

        return "0.0.0.0"

    def is_rate_limited(
        self, request: Request, endpoint: str = ""
    ) -> tuple[bool, str | None]:
        """
        Check if request should be rate limited.

        Args:
            request: The HTTP request.
            endpoint: Optional endpoint identifier for per-endpoint limiting.

        Returns:
            tuple[bool, str | None]: (True if rate limited, window name) or
            (False, None)
        """
        self._cleanup_old_entries()

        client_ip = self._get_client_ip(request)
        current_time = time.time()

        for window in RateLimitWindow:
            window_key = f"{endpoint}:{window.value}" if endpoint else window.value

            # Count requests in this window
            count = 0
            for timestamp, request_count in self._store[client_ip][window_key].items():
                if current_time - timestamp < window.seconds:
                    count += request_count

            if count >= self._limit_for(window):
                # Don't count this request since it's being blocked
                return (True, window.value)

            # Add current request
            self._store[client_ip][window_key][current_time] = (
                self._store[client_ip][window_key].get(current_time, 0) + 1
            )

        return (False, None)

    def get_rate_limit_response(
        self, request: Request, window: str = RateLimitWindow.MINUTE.value
    ) -> JSONResponse:
        """Get standard rate limit exceeded response."""
        try:
            exceeded = RateLimitWindow(window)
        except ValueError:
            # An unknown window name has always been answered as the minute window.
            exceeded = RateLimitWindow.MINUTE

        return JSONResponse(
            {
                "error": "rate_limit_exceeded",
                "detail": "Too many requests. Please try again later.",
            },
            status_code=HTTPStatus.TOO_MANY_REQUESTS,
            headers={
                "Retry-After": str(exceeded.seconds),
                "X-RateLimit-Limit": str(self._limit_for(exceeded)),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(time.time() + exceeded.seconds)),
            },
        )
