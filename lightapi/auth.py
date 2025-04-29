import time
from typing import Any, Dict, Optional

import jwt


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


class JWTAuthentication(BaseAuthentication):
    """
    JWT (JSON Web Token) based authentication.
    
    Authenticates requests using JWT tokens from the Authorization header.
    Validates token signatures and expiration times.
    
    Attributes:
        secret_key: Secret key for signing tokens.
        algorithm: JWT algorithm to use.
        expiration: Token expiration time in seconds.
    """
    
    secret_key = "your_secret_key"
    algorithm = "HS256"
    expiration = 3600

    def authenticate(self, request):
        """
        Authenticate a request using a JWT token.
        
        Extracts the token from the Authorization header,
        validates it, and adds the payload to request.user.
        
        Args:
            request: The HTTP request to authenticate.
            
        Returns:
            bool: True if authentication succeeds, False otherwise.
        """
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return False

        token = auth_header[7:]
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            if payload.get("exp", 0) < time.time():
                return False
            request.user = payload
            return True
        except jwt.PyJWTError:
            return False

    @classmethod
    def generate_token(cls, user_data: Dict[str, Any]) -> str:
        """
        Generate a new JWT token.
        
        Args:
            user_data: User data to include in the token payload.
            
        Returns:
            str: The encoded JWT token.
        """
        payload = {**user_data, "exp": time.time() + cls.expiration}
        return jwt.encode(payload, cls.secret_key, algorithm=cls.algorithm)
