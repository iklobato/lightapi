"""LightAPI Example 04 - Basic Authentication.

Demonstrates:
- Basic Authentication (username:password in Authorization header)
- Protected endpoints requiring valid Basic credentials
- Login via /auth/login with JSON body

Prerequisites:
    PostgreSQL must be running with default credentials.

Run with:
    python examples/04_auth_basic.py

Then try:
    # Login to get token (Basic auth returns token too)
    curl -X POST http://localhost:8000/auth/login \
        -H 'Content-Type: application/json' \
        -d '{"username":"admin","password":"secret"}'

    # Or use Basic header directly on protected endpoint
    curl -H 'Authorization: Basic YWRtaW46c2VjcmV0' http://localhost:8000/books
    # (YWRtaW46c2VjcmV0 is base64 of "admin:secret")

    # Without credentials returns 401
    curl http://localhost:8000/books
"""

from sqlalchemy import create_engine

from lightapi import (
    Authentication,
    BasicAuthentication,
    HttpMethod,
    LightApi,
    RestEndpoint,
)
from lightapi.fields import Field

DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/postgres"


def login_validator(username: str, password: str):
    """Validate credentials and return user payload."""
    if username == "admin" and password == "secret":
        return {"sub": "1", "username": "admin"}
    return None


class BookEndpoint(RestEndpoint, HttpMethod.GET, HttpMethod.POST):
    """Book endpoint protected by Basic authentication."""

    title: str = Field(min_length=1)
    author: str = Field(min_length=1)

    class Meta:
        authentication = Authentication(
            backend=BasicAuthentication,
        )


if __name__ == "__main__":
    engine = create_engine(DATABASE_URL)
    app = LightApi(
        engine=engine,
        login_validator=login_validator,
    )
    app.register({"/books": BookEndpoint})
    app.run(host="0.0.0.0", port=8000, debug=True)
