"""LightAPI Example 16 - Rate Limiting.

Demonstrates:
- Built-in rate limiting on auth endpoints
- Protection against brute-force attacks
- Configurable rate limits

Prerequisites:
    PostgreSQL must be running.

Run with:
    python examples/16_rate_limit.py

Then try:
    # Make many rapid requests to trigger rate limit
    for i in {1..15}; do
        curl -s -o /dev/null -w "%{http_code}\n" \
            -X POST http://localhost:8000/auth/login \
            -H 'Content-Type: application/json' \
            -d '{"username":"admin","password":"wrong"}'
    done

    # After 10 requests, should get 429 Too Many Requests
"""

import os
from sqlalchemy import create_engine

from lightapi import (
    Authentication,
    JWTAuthentication,
    LightApi,
    RestEndpoint,
    HttpMethod,
)


DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/postgres"
os.environ.setdefault("LIGHTAPI_JWT_SECRET", "secret")


def login_validator(username: str, password: str):
    if username == "admin" and password == "secret":
        return {"sub": "1", "username": "admin"}
    return None


class DummyEndpoint(RestEndpoint, HttpMethod.GET):
    """Endpoint that requires JWT auth to test rate limiting."""

    class Meta:
        authentication = Authentication(backend=JWTAuthentication)


if __name__ == "__main__":
    engine = create_engine(DATABASE_URL)

    # Rate limiter is automatically applied to /auth/login endpoint
    # Default: 10 requests per minute, 100 per hour, 1000 per day
    app = LightApi(
        engine=engine,
        login_validator=login_validator,
    )
    app.register({"/dummy": DummyEndpoint})
    app.run(host="0.0.0.0", port=8000, debug=True)
