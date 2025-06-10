import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import jwt
from starlette.responses import JSONResponse

from .config import config


class BaseAuthentication:
    """
    Base class for authentication.

    Provides a common interface for all authentication methods.
    By default, allows all requests.
    """

    def authenticate(self, request):
        """
        Authenticate a request.

        Args:
            request: The HTTP request to authenticate.

        Returns:
            bool: True if authentication succeeds, False otherwise.
        """
        return True

    def get_auth_error_response(self, request):
        """
        Get the response to return when authentication fails.

        Args:
            request: The HTTP request object.

        Returns:
            Response object for authentication error.
        """
        return JSONResponse({"error": "not allowed"}, status_code=403)


class JWTAuthentication(BaseAuthentication):
    """
    JWT (JSON Web Token) based authentication.

    Authenticates requests using JWT tokens from the Authorization header.
    Validates token signatures and expiration times.
    Automatically skips authentication for OPTIONS requests (CORS preflight).

    Attributes:
        secret_key: Secret key for signing tokens.
        algorithm: JWT algorithm to use.
        expiration: Token expiration time in seconds.
    """

    def __init__(self):
        if not config.jwt_secret:
            raise ValueError(
                "JWT secret key not configured. Set LIGHTAPI_JWT_SECRET environment variable."
            )
        self.secret_key = config.jwt_secret
        self.algorithm = "HS256"
        self.expiration = 3600  # 1 hour default

    def authenticate(self, request):
        """
        Authenticate a request using JWT token.
        Automatically allows OPTIONS requests for CORS preflight.

        Args:
            request: The HTTP request object.

        Returns:
            bool: True if authentication succeeds, False otherwise.
        """
        # Skip authentication for OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
            return True

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return False

        token = auth_header.split(" ")[1]
        try:
            payload = self.decode_token(token)
            request.state.user = payload
            return True
        except jwt.InvalidTokenError:
            return False

    def generate_token(self, payload: Dict, expiration: Optional[int] = None) -> str:
        """
        Generate a JWT token.

        Args:
            payload: The data to encode in the token.
            expiration: Token expiration time in seconds.

        Returns:
            str: The encoded JWT token.
        """
        exp_seconds = expiration or self.expiration
        token_data = {
            **payload,
            "exp": datetime.utcnow() + timedelta(seconds=exp_seconds),
        }
        return jwt.encode(token_data, self.secret_key, algorithm=self.algorithm)

    def decode_token(self, token: str) -> Dict:
        """
        Decode and verify a JWT token.

        Args:
            token: The JWT token to decode.

        Returns:
            dict: The decoded token payload.

        Raises:
            jwt.InvalidTokenError: If the token is invalid or expired.
        """
        return jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
