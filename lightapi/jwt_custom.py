
import base64
import json
import hmac
import hashlib
import time

def b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")

def b64_decode(data: str) -> bytes:
    padding = b"=" * (4 - (len(data) % 4))
    return base64.urlsafe_b64decode(data.encode("utf-8") + padding)

def jwt_encode(payload: dict, secret: str, algorithm: str = "HS256") -> str:
    header = {"alg": algorithm, "typ": "JWT"}
    
    encoded_header = b64_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    encoded_payload = b64_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    
    signing_input = f"{encoded_header}.{encoded_payload}".encode("utf-8")
    
    if algorithm == "HS256":
        signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    else:
        raise ValueError("Unsupported algorithm")
        
    encoded_signature = b64_encode(signature)
    
    return f"{encoded_header}.{encoded_payload}.{encoded_signature}"

def jwt_decode(token: str, secret: str, algorithms: list[str] = ["HS256"]) -> dict:
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
    except ValueError:
        raise ValueError("Invalid token")

    header_data = json.loads(b64_decode(encoded_header))
    alg = header_data.get("alg")

    if not alg or alg not in algorithms:
        raise ValueError("Invalid algorithm")

    signing_input = f"{encoded_header}.{encoded_payload}".encode("utf-8")
    
    if alg == "HS256":
        expected_signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    else:
        raise ValueError("Unsupported algorithm")

    decoded_signature = b64_decode(encoded_signature)

    if not hmac.compare_digest(decoded_signature, expected_signature):
        raise ValueError("Invalid signature")

    payload = json.loads(b64_decode(encoded_payload))
    
    if "exp" in payload and payload["exp"] < time.time():
        raise ValueError("Token has expired")
        
    return payload
