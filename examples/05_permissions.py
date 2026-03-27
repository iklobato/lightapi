"""LightAPI Example 05 - Permission Levels.

Demonstrates:
- AllowAny: No authentication required
- IsAuthenticated: Any valid JWT/Basic auth
- IsAdminUser: Requires is_admin=True in JWT payload
- Three endpoints with different permission levels

Prerequisites:
    PostgreSQL must be running with default credentials.

Run with:
    LIGHTAPI_JWT_SECRET=secret python examples/05_permissions.py

Then try:
    # Public endpoint - no auth needed
    curl http://localhost:8000/public

    # Private endpoint - needs any valid JWT
    curl -H 'Authorization: Bearer <TOKEN>' http://localhost:8000/private

    # Admin endpoint - needs JWT with is_admin=true
    # Get admin token:
    # python -c "import jwt; print(jwt.encode({'sub':'1','is_admin':True}, 'secret', algorithm='HS256'))"
"""

import os
from sqlalchemy import create_engine

from lightapi import (
    AllowAny,
    Authentication,
    HttpMethod,
    IsAdminUser,
    IsAuthenticated,
    JWTAuthentication,
    LightApi,
    RestEndpoint,
)
from lightapi.fields import Field


DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/postgres"
os.environ.setdefault("LIGHTAPI_JWT_SECRET", "secret")


def login_validator(username: str, password: str):
    if username == "admin" and password == "secret":
        return {"sub": "1", "username": "admin", "is_admin": True}
    if username == "user" and password == "password":
        return {"sub": "2", "username": "user", "is_admin": False}
    return None


class PublicEndpoint(RestEndpoint, HttpMethod.GET):
    """Public endpoint - anyone can access."""

    message: str = "This is a public endpoint"

    class Meta:
        authentication = Authentication(permission=AllowAny)


class PrivateEndpoint(RestEndpoint, HttpMethod.GET):
    """Private endpoint - requires authentication."""

    message: str = "This is a private endpoint"

    class Meta:
        authentication = Authentication(
            backend=JWTAuthentication,
            permission=IsAuthenticated,
        )


class AdminEndpoint(RestEndpoint, HttpMethod.GET, HttpMethod.DELETE):
    """Admin endpoint - requires is_admin=True."""

    message: str = "This is an admin endpoint"

    class Meta:
        authentication = Authentication(
            backend=JWTAuthentication,
            permission=IsAdminUser,
        )


if __name__ == "__main__":
    engine = create_engine(DATABASE_URL)
    app = LightApi(engine=engine, login_validator=login_validator)
    app.register(
        {
            "/public": PublicEndpoint,
            "/private": PrivateEndpoint,
            "/admin": AdminEndpoint,
        }
    )
    app.run(host="0.0.0.0", port=8000, debug=True)
