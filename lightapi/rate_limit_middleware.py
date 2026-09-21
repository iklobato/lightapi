"""Middleware for per-endpoint rate limiting."""

import time

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from lightapi.core import Middleware


class RateLimitEntry:
    """Stores request count and window expiration for a client/endpoint pair."""

    def __init__(self, reset_time: float) -> None:
        self.count = 0
        self.reset_time = reset_time

    def is_expired(self, now: float) -> bool:
        return now >= self.reset_time


class EndpointRateLimitMiddleware(Middleware):
    """
    Rate-limit requests per endpoint using the endpoint's `Meta.rate_limit`.

    Example on a `RestEndpoint` subclass::

        class BookEndpoint(RestEndpoint):
            title: str = Field(min_length=1)

            class Meta:
                rate_limit = {"requests": 5, "window": 60}

    The window is measured in seconds. The client is identified by IP
    (or `X-Forwarded-For` when present). Responses include these headers::

        X-RateLimit-Limit
        X-RateLimit-Remaining
        X-RateLimit-Reset

    When the limit is exceeded the middleware short-circuits with HTTP 429.
    """

    _storage: dict[tuple[str, str], RateLimitEntry] = {}

    @classmethod
    def reset(cls) -> None:
        """Clear all rate-limit counters (useful for tests)."""
        cls._storage.clear()

    def _get_client_id(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _get_endpoint_class(self, request: Request) -> type | None:
        handler = request.scope.get("endpoint")
        if handler is None:
            return None
        return getattr(handler, "__endpoint_cls__", None)

    def _get_limit_config(self, request: Request) -> dict[str, int] | None:
        endpoint_cls = self._get_endpoint_class(request)
        if endpoint_cls is None:
            return None
        meta = getattr(endpoint_cls, "Meta", None)
        if meta is None:
            return None
        return getattr(meta, "rate_limit", None)

    def process(self, request: Request, response: Response | None) -> Response | None:
        limit_config = self._get_limit_config(request)
        if limit_config is None:
            return response

        now = time.monotonic()
        max_requests = int(limit_config["requests"])
        window_seconds = int(limit_config["window"])

        client_id = self._get_client_id(request)
        key = (client_id, request.url.path)

        entry = self._storage.get(key)
        if entry is None or entry.is_expired(now):
            reset_time = now + window_seconds
            entry = RateLimitEntry(reset_time)
            self._storage[key] = entry

        if response is None:
            if entry.count >= max_requests:
                headers = {
                    "X-RateLimit-Limit": str(max_requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(entry.reset_time - now)),
                }
                return JSONResponse(
                    {"detail": "Rate limit exceeded. Try again later."},
                    status_code=429,
                    headers=headers,
                )

            entry.count += 1
            request.state._rate_limit_entry = entry
            request.state._rate_limit_max = max_requests
            return None

        entry = getattr(request.state, "_rate_limit_entry", entry)
        max_requests = getattr(request.state, "_rate_limit_max", max_requests)
        remaining = max(0, max_requests - entry.count)
        response.headers["X-RateLimit-Limit"] = str(max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(entry.reset_time - now))
        return response
