---
title: Environment Variables
---

# Environment Variables

LightAPI reads the following environment variables:

| Variable | Used by | Default |
|----------|---------|---------|
| `LIGHTAPI_DATABASE_URL` | `LightApi` constructor when no `engine` or `database_url` is given | `sqlite:///app.db` |
| `LIGHTAPI_JWT_SECRET` | `JWTAuthentication` | — (required when JWT auth is used) |
| `LIGHTAPI_REDIS_URL` | Cache backend | `redis://localhost:6379/0` |

## Using `.env` files

```bash
# .env
DATABASE_URL=postgresql+psycopg2://user:pass@localhost/mydb
LIGHTAPI_JWT_SECRET=change-me-in-production
LIGHTAPI_REDIS_URL=redis://localhost:6379/0
```

Load with `python-dotenv`:

```bash
uv add python-dotenv
```

```python
from dotenv import load_dotenv
load_dotenv()

import os
from sqlalchemy import create_engine
from lightapi import LightApi

engine = create_engine(os.environ["DATABASE_URL"])
app = LightApi(engine=engine)
```

## YAML `${VAR}` substitution

Any `${VAR}` placeholder in a YAML config is replaced at load time:

```yaml
# lightapi.yaml
database:
  url: "${DATABASE_URL}"
```

A missing variable raises `ConfigurationError` immediately:

```
lightapi.exceptions.ConfigurationError: Environment variable 'DATABASE_URL' is not set
```

## Multi-environment setup

```
.env.development
.env.staging
.env.production
```

```python
import os
from dotenv import load_dotenv
from lightapi import LightApi

env = os.getenv("APP_ENV", "development")
load_dotenv(f".env.{env}")

app = LightApi.from_config("lightapi.yaml")
app.run()
```

**`.env.development`:**

```bash
DATABASE_URL=sqlite:///dev.db
LIGHTAPI_JWT_SECRET=dev-secret
```

**`.env.production`:**

```bash
DATABASE_URL=postgresql+psycopg2://user:pass@prod-db/mydb
LIGHTAPI_JWT_SECRET=a-long-random-secret
LIGHTAPI_REDIS_URL=redis://:password@redis-host:6379/0
```

## Docker / Kubernetes

Pass environment variables via `docker run -e` or Kubernetes `env:` fields:

```yaml
# deployment.yaml
env:
  - name: DATABASE_URL
    valueFrom:
      secretKeyRef:
        name: app-secrets
        key: database-url
  - name: LIGHTAPI_JWT_SECRET
    valueFrom:
      secretKeyRef:
        name: app-secrets
        key: jwt-secret
```

## Security checklist

- Never commit `.env` files with real secrets.
- Rotate `LIGHTAPI_JWT_SECRET` regularly; all existing tokens become invalid.
- Use a strong, randomly generated JWT secret in production (`openssl rand -hex 32`).
- Restrict `LIGHTAPI_DATABASE_URL` credentials to minimum required permissions.
