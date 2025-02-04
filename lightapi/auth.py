import jwt
import time
import os


class JWTAuthentication:
    def __init__(self):
        self.secret = os.getenv('JWT_SECRET', 'your-secret-key')
        self.algorithm = os.getenv('JWT_ALGORITHM', 'HS256')

    @classmethod
    def generate_token(cls, payload, expiration=None):
        instance = cls()
        if 'exp' not in payload:
            payload['exp'] = expiration or time.time() + 3600  
        return jwt.encode(payload, instance.secret, algorithm=instance.algorithm)

    @classmethod
    def decode_token(cls, token):
        instance = cls()
        try:
            return jwt.decode(token, instance.secret, algorithms=[instance.algorithm])
        except jwt.ExpiredSignatureError:
            return None
        except jwt.PyJWTError:
            return None

