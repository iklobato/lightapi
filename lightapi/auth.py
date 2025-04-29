import time
from typing import Any, Dict, Optional

import jwt


class BaseAuthentication:
    def authenticate(self, request):
        return True


class JWTAuthentication(BaseAuthentication):
    secret_key = "your_secret_key"
    algorithm = "HS256"
    expiration = 3600

    def authenticate(self, request):
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
        payload = {**user_data, "exp": time.time() + cls.expiration}
        return jwt.encode(payload, cls.secret_key, algorithm=cls.algorithm)
