"""Simple rate limiting for authentication endpoints."""

from __future__ import annotations

import time
from collections import defaultdict

from starlette.requests import Request
from starlette.responses import JSONResponse


class RateLimiter:
    """
    Simple in-memory rate limiter.

    Tracks requests by IP address and endpoint.

    NOTE: This implementation uses process-local counters. In a multi-process
    deployment (e.g., with multiple workers), rate limiting will not be shared
    across processes. For production use with multiple workers, consider using
    a shared storage backend like Redis.
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
        # Extract window name from key (e.g., "auth:minute" -> "minute")
        window_name = window.split(":")[-1] if ":" in window else window

        if window_name == "minute":
            return 60
        elif window_name == "hour":
            return 3600
        elif window_name == "day":
            return 86400
        else:
            return 60

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

        # Check all windows first before incrementing
        windows = [
            ("minute", self.requests_per_minute),
            ("hour", self.requests_per_hour),
            ("day", self.requests_per_day),
        ]

        # First pass: check all windows
        for window_name, limit in windows:
            window_seconds = self._get_window_seconds(window_name)
            window_key = f"{endpoint}:{window_name}" if endpoint else window_name

            # Count requests in this window
            count = 0
            for timestamp, request_count in self._store[client_ip][window_key].items():
                if current_time - timestamp < window_seconds:
                    count += request_count

            if count >= limit:
                # Don't count this request since it's being blocked
                return (True, window_name)

        # Second pass: increment all windows (only if request is allowed)
        for window_name, _ in windows:
            window_seconds = self._get_window_seconds(window_name)
            window_key = f"{endpoint}:{window_name}" if endpoint else window_name
            self._store[client_ip][window_key][current_time] = (
                self._store[client_ip][window_key].get(current_time, 0) + 1
            )

        return (False, None)

    def get_rate_limit_response(self, window: str = "minute") -> JSONResponse:
        """Get standard rate limit exceeded response."""
        # Determine window-specific values
        if window == "hour":
            limit = self.requests_per_hour
            retry_after = 3600
            reset_seconds = 3600
        elif window == "day":
            limit = self.requests_per_day
            retry_after = 86400
            reset_seconds = 86400
        else:  # minute
            limit = self.requests_per_minute
            retry_after = 60
            reset_seconds = 60

        return JSONResponse(
            {
                "error": "rate_limit_exceeded",
                "detail": "Too many requests. Please try again later.",
            },
            status_code=429,
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(time.time() + reset_seconds)),
            },
        )
