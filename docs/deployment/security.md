---
title: Security Considerations
---

This guide outlines best practices for securing your LightAPI application in production.

## 1. Secure Communication (TLS)
Always serve your API over HTTPS to encrypt data in transit. If using a reverse proxy (e.g., Nginx), configure SSL certificates:

```nginx
server {
    listen 443 ssl;
    server_name api.example.com;

    ssl_certificate     /etc/ssl/fullchain.pem;
    ssl_certificate_key /etc/ssl/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 2. Cross-Origin Resource Sharing (CORS)
Control which domains can access your API. Use Starlette's `CORSMiddleware`:

```python
from starlette.middleware.cors import CORSMiddleware
from lightapi import LightApi

app = LightApi()
app.app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://example.com"],
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## 3. Input Validation & Sanitization
Always validate and sanitize inputs using `validator_class` to prevent SQL injection and ensure data integrity.

## 4. Authentication & Authorization
- Use strong, randomly generated secrets for JWT (`LIGHTAPI_JWT_SECRET`).
- Protect endpoints with `authentication_class` and implement role checks in your logic.

## 5. Rate Limiting
Thwart abuse by implementing rate limiting. Options include:
- Nginx rate limiting
- ASGI middleware (e.g., `slowapi`)

## 6. Secret Management
Manage secrets and credentials via environment variables or secret managers (e.g., Vault, AWS Secrets Manager). Do not commit secrets to source control.

## 7. Logging & Monitoring
Enable structured logging and monitor metrics. Use tools like Prometheus, Grafana, or ELK stack to track performance and detect anomalies.
