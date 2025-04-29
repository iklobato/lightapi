---
title: Production Deployment
---

## Running in Production

For production environments, it's recommended to run LightAPI with a robust ASGI server and process manager.

### Using Gunicorn with Uvicorn Workers

```bash
gunicorn app.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000
```

- `--workers`: Number of worker processes.
- `--worker-class`: Use Uvicorn worker for ASGI support.

### Environment Variables

Set critical configuration via environment variables:

- `LIGHTAPI_DATABASE_URL`: Database connection URL
- `LIGHTAPI_HOST` / `LIGHTAPI_PORT`: Host and port bindings
- `LIGHTAPI_DEBUG`: Disable in production (`False`)
- `LIGHTAPI_JWT_SECRET`: Secret key for JWT authentication

Example:
```bash
export LIGHTAPI_DATABASE_URL=postgresql+asyncpg://user:pass@db/db
export LIGHTAPI_JWT_SECRET=supersecret
```

### Reverse Proxy and TLS

Use Nginx or similar for TLS termination, load balancing, and static file serving:

```nginx
server {
    listen 443 ssl;
    server_name api.example.com;

    ssl_certificate     /etc/ssl/fullchain.pem;
    ssl_certificate_key /etc/ssl/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;  # Gunicorn/Uvicorn
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

### Database Migrations

LightAPI does not bundle migrations; we recommend Alembic:

1. Initialize Alembic:
   ```bash
   alembic init migrations
   ```
2. Configure `alembic.ini` with `sqlalchemy.url = $LIGHTAPI_DATABASE_URL`.
3. Generate and apply migrations:
   ```bash
   alembic revision --autogenerate -m "create tables"
   alembic upgrade head
   ```
