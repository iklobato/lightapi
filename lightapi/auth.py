import jwt
import time
import os


class JWTAuthentication:
    def __init__(self):
        self.secret = os.getenv('JWT_SECRET', 'your-secret-key')
        self.algorithm = os.getenv('JWT_ALGORITHM', 'HS256')

    @classmethod
    def generate_token(cls, payload):
        instance = cls()
        payload['exp'] = time.time() + 3600  # 1 hour expiration
        return jwt.encode(payload, instance.secret, algorithm=instance.algorithm)

    @classmethod
    def decode_token(cls, token):
        instance = cls()
        try:
            return jwt.decode(token, instance.secret, algorithms=[instance.algorithm])
        except jwt.PyJWTError:
            return None
