# Environment Variables and Multi-Environment Deployment

This guide demonstrates how to use environment variables with LightAPI for flexible deployment across different environments (development, staging, production). Environment variables provide secure, configurable deployment without hardcoding sensitive information.

## Overview

Environment variables enable:

- **Secure Configuration**: Keep secrets out of source code
- **Multi-Environment Deployment**: Different settings per environment
- **Dynamic Configuration**: Change settings without code changes
- **Container-Friendly**: Perfect for Docker and Kubernetes
- **CI/CD Integration**: Automated deployment with different configurations

## Benefits

### 🔒 **Security**
- **No Hardcoded Secrets**: Database passwords, API keys stay out of code
- **Environment Isolation**: Different credentials per environment
- **Secret Management**: Integration with secret management systems
- **Audit Trail**: Track configuration changes through deployment

### 🚀 **Deployment Flexibility**
- **Environment-Specific Settings**: Different configurations per environment
- **Easy Scaling**: Modify settings without code changes
- **Container Support**: Native Docker and Kubernetes integration
- **CI/CD Friendly**: Automated deployment with environment-specific configs

### 🛠️ **Maintainability**
- **Single Codebase**: Same code runs in all environments
- **Configuration as Code**: Version control environment configurations
- **Easy Debugging**: Clear separation of code and configuration
- **Team Collaboration**: Shared configuration patterns

## Basic Environment Variable Usage

### Simple YAML Configuration with Environment Variables

```yaml
# config.yaml
database_url: "${DATABASE_URL}"
swagger_title: "${API_TITLE:-My API}"  # Default value if not set
swagger_version: "${API_VERSION:-1.0.0}"
swagger_description: "${API_DESCRIPTION}"
enable_swagger: ${ENABLE_SWAGGER:true}  # Boolean with default

tables:
  - name: users
    crud: [get, post, put, patch, delete]
  - name: posts
    crud: [get, post, put]
```

### Environment Variable Syntax

```yaml
# Basic usage
database_url: "${DATABASE_URL}"

# With default values
api_title: "${API_TITLE:-Default API Title}"
port: ${PORT:8000}
debug: ${DEBUG:false}

# Boolean values
enable_swagger: ${ENABLE_SWAGGER:true}
enable_cors: ${ENABLE_CORS:false}

# Numeric values
max_connections: ${MAX_CONNECTIONS:100}
timeout: ${TIMEOUT:30}
```

### Setting Environment Variables

```bash
# Linux/macOS
export DATABASE_URL="sqlite:///app.db"
export API_TITLE="My Application API"
export API_VERSION="2.0.0"
export ENABLE_SWAGGER="true"

# Windows Command Prompt
set DATABASE_URL=sqlite:///app.db
set API_TITLE=My Application API

# Windows PowerShell
$env:DATABASE_URL="sqlite:///app.db"
$env:API_TITLE="My Application API"
```

## Multi-Environment Configuration

### Development Environment

```yaml
# development.yaml
database_url: "${DEV_DATABASE_URL:-sqlite:///dev.db}"
swagger_title: "${API_TITLE} - Development"
swagger_version: "${API_VERSION:-1.0.0-dev}"
swagger_description: |
  Development environment for ${API_TITLE}
  
  ## Development Features
  - Debug mode enabled
  - Swagger UI available
  - Full CRUD operations
  - Sample data included
enable_swagger: true
debug: ${DEBUG:true}

tables:
  # Full access in development
  - name: users
    crud: [get, post, put, patch, delete]
  - name: posts
    crud: [get, post, put, patch, delete]
  - name: comments
    crud: [get, post, put, patch, delete]
  - name: categories
    crud: [get, post, put, patch, delete]
```

### Staging Environment

```yaml
# staging.yaml
database_url: "${STAGING_DATABASE_URL}"
swagger_title: "${API_TITLE} - Staging"
swagger_version: "${API_VERSION}"
swagger_description: |
  Staging environment for ${API_TITLE}
  
  ## Staging Features
  - Production-like environment
  - Limited Swagger access
  - Restricted operations
  - Performance testing
enable_swagger: ${ENABLE_SWAGGER:true}
debug: ${DEBUG:false}

tables:
  # Limited operations in staging
  - name: users
    crud: [get, post, put, patch]  # No delete
  - name: posts
    crud: [get, post, put, patch]
  - name: comments
    crud: [get, post, patch]  # No full replacement
  - name: categories
    crud: [get, post, put]  # No delete or patch
```

### Production Environment

```yaml
# production.yaml
database_url: "${PROD_DATABASE_URL}"
swagger_title: "${API_TITLE}"
swagger_version: "${API_VERSION}"
swagger_description: |
  Production API for ${API_TITLE}
  
  ## Production Features
  - High availability
  - Security optimized
  - Performance monitoring
  - Audit logging
enable_swagger: ${ENABLE_SWAGGER:false}  # Disabled by default
debug: false

tables:
  # Minimal operations in production
  - name: users
    crud: [get, patch]  # Very limited access
  - name: posts
    crud: [get, post, patch]
  - name: comments
    crud: [get, post]  # Create and read only
  - name: categories
    crud: [get]  # Read-only
```

## Environment-Specific Deployment

### Using Environment Files

Create `.env` files for each environment:

```bash
# .env.development
DATABASE_URL=sqlite:///dev.db
API_TITLE=Blog API
API_VERSION=1.0.0-dev
API_DESCRIPTION=Development blog API with full features
ENABLE_SWAGGER=true
DEBUG=true
CORS_ORIGINS=http://localhost:3000,http://localhost:3001
JWT_SECRET=dev-secret-key-not-for-production
REDIS_URL=redis://localhost:6379
LOG_LEVEL=DEBUG
```

```bash
# .env.staging
DATABASE_URL=postgresql://staging_user:staging_pass@staging-db:5432/blog_staging
API_TITLE=Blog API
API_VERSION=1.0.0-rc1
API_DESCRIPTION=Staging blog API for testing
ENABLE_SWAGGER=true
DEBUG=false
CORS_ORIGINS=https://staging.myblog.com
JWT_SECRET=staging-secret-key-change-in-production
REDIS_URL=redis://staging-redis:6379
LOG_LEVEL=INFO
```

```bash
# .env.production
DATABASE_URL=postgresql://prod_user:secure_password@prod-db:5432/blog_production
API_TITLE=Blog API
API_VERSION=1.0.0
API_DESCRIPTION=Production blog API
ENABLE_SWAGGER=false
DEBUG=false
CORS_ORIGINS=https://myblog.com,https://www.myblog.com
JWT_SECRET=super-secure-production-secret-key
REDIS_URL=redis://prod-redis:6379
LOG_LEVEL=WARNING
```

### Python Application with Environment Loading

```python
# app.py
import os
from dotenv import load_dotenv
from lightapi import LightApi

def load_environment():
    """Load environment-specific configuration"""
    env = os.getenv('ENVIRONMENT', 'development')
    env_file = f'.env.{env}'
    
    if os.path.exists(env_file):
        load_dotenv(env_file)
        print(f"✅ Loaded environment: {env}")
    else:
        print(f"⚠️  Environment file {env_file} not found, using system environment")
    
    return env

def create_app():
    """Create LightAPI application with environment configuration"""
    env = load_environment()
    
    # Determine config file based on environment
    config_file = f'{env}.yaml'
    
    if not os.path.exists(config_file):
        config_file = 'config.yaml'  # Fallback to default
    
    print(f"📄 Using configuration: {config_file}")
    
    # Create API from environment-specific config
    app = LightApi.from_config(config_file)
    
    # Add environment info to API
    @app.get("/info")
    def api_info():
        """Get API environment information"""
        return {
            "environment": env,
            "api_title": os.getenv("API_TITLE", "Unknown"),
            "api_version": os.getenv("API_VERSION", "Unknown"),
            "debug": os.getenv("DEBUG", "false").lower() == "true",
            "swagger_enabled": os.getenv("ENABLE_SWAGGER", "false").lower() == "true"
        }
    
    return app

if __name__ == '__main__':
    app = create_app()
    
    # Get host and port from environment
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 8000))
    
    print(f"🚀 Starting API on {host}:{port}")
    print(f"🌍 Environment: {os.getenv('ENVIRONMENT', 'development')}")
    print(f"📚 Documentation: http://{host}:{port}/docs")
    
    app.run(host=host, port=port)
```

### Deployment Scripts

```bash
#!/bin/bash
# deploy.sh - Environment-specific deployment script

set -e

ENVIRONMENT=${1:-development}

echo "🚀 Deploying to $ENVIRONMENT environment..."

# Set environment
export ENVIRONMENT=$ENVIRONMENT

# Load environment-specific variables
case $ENVIRONMENT in
  "development")
    echo "📝 Setting up development environment..."
    export DATABASE_URL="sqlite:///dev.db"
    export DEBUG="true"
    export ENABLE_SWAGGER="true"
    ;;
  "staging")
    echo "🧪 Setting up staging environment..."
    export DATABASE_URL="$STAGING_DATABASE_URL"
    export DEBUG="false"
    export ENABLE_SWAGGER="true"
    ;;
  "production")
    echo "🏭 Setting up production environment..."
    export DATABASE_URL="$PROD_DATABASE_URL"
    export DEBUG="false"
    export ENABLE_SWAGGER="false"
    ;;
  *)
    echo "❌ Unknown environment: $ENVIRONMENT"
    exit 1
    ;;
esac

# Validate required environment variables
required_vars=("DATABASE_URL" "API_TITLE" "API_VERSION")
for var in "${required_vars[@]}"; do
  if [ -z "${!var}" ]; then
    echo "❌ Required environment variable $var is not set"
    exit 1
  fi
done

echo "✅ Environment variables validated"

# Start the application
python app.py
```

Usage:
```bash
# Deploy to different environments
./deploy.sh development
./deploy.sh staging
./deploy.sh production
```

## Docker Integration

### Dockerfile with Environment Support

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY *.yaml ./
COPY app.py .

# Create non-root user
RUN useradd -m -u 1000 appuser
USER appuser

# Expose port (configurable via environment)
EXPOSE ${PORT:-8000}

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:${PORT:-8000}/info || exit 1

# Run application
CMD ["python", "app.py"]
```

### Docker Compose for Multiple Environments

```yaml
# docker-compose.yml
version: '3.8'

services:
  # Development environment
  api-dev:
    build: .
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=development
      - DATABASE_URL=sqlite:///dev.db
      - API_TITLE=Blog API
      - API_VERSION=1.0.0-dev
      - ENABLE_SWAGGER=true
      - DEBUG=true
    volumes:
      - ./data:/app/data
    profiles:
      - dev

  # Staging environment
  api-staging:
    build: .
    ports:
      - "8001:8000"
    environment:
      - ENVIRONMENT=staging
      - DATABASE_URL=postgresql://staging_user:staging_pass@db-staging:5432/blog
      - API_TITLE=Blog API
      - API_VERSION=1.0.0-rc1
      - ENABLE_SWAGGER=true
      - DEBUG=false
    depends_on:
      - db-staging
    profiles:
      - staging

  # Production environment
  api-prod:
    build: .
    ports:
      - "8002:8000"
    environment:
      - ENVIRONMENT=production
      - DATABASE_URL=postgresql://prod_user:${PROD_DB_PASSWORD}@db-prod:5432/blog
      - API_TITLE=Blog API
      - API_VERSION=1.0.0
      - ENABLE_SWAGGER=false
      - DEBUG=false
    depends_on:
      - db-prod
    profiles:
      - prod

  # Staging database
  db-staging:
    image: postgres:15
    environment:
      - POSTGRES_DB=blog
      - POSTGRES_USER=staging_user
      - POSTGRES_PASSWORD=staging_pass
    volumes:
      - staging_data:/var/lib/postgresql/data
    profiles:
      - staging

  # Production database
  db-prod:
    image: postgres:15
    environment:
      - POSTGRES_DB=blog
      - POSTGRES_USER=prod_user
      - POSTGRES_PASSWORD=${PROD_DB_PASSWORD}
    volumes:
      - prod_data:/var/lib/postgresql/data
    profiles:
      - prod

volumes:
  staging_data:
  prod_data:
```

Run different environments:
```bash
# Development
docker-compose --profile dev up

# Staging
docker-compose --profile staging up

# Production
PROD_DB_PASSWORD=secure_password docker-compose --profile prod up
```

## Kubernetes Deployment

### ConfigMap for Environment Configuration

```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: api-config
data:
  API_TITLE: "Blog API"
  API_VERSION: "1.0.0"
  ENABLE_SWAGGER: "false"
  DEBUG: "false"
  ENVIRONMENT: "production"
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: api-config-staging
data:
  API_TITLE: "Blog API"
  API_VERSION: "1.0.0-rc1"
  ENABLE_SWAGGER: "true"
  DEBUG: "false"
  ENVIRONMENT: "staging"
```

### Secret for Sensitive Data

```yaml
# secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: api-secrets
type: Opaque
data:
  DATABASE_URL: cG9zdGdyZXNxbDovL3VzZXI6cGFzc0BkYi5leGFtcGxlLmNvbTo1NDMyL2Jsb2c=  # base64 encoded
  JWT_SECRET: c3VwZXItc2VjdXJlLWp3dC1zZWNyZXQta2V5  # base64 encoded
  REDIS_URL: cmVkaXM6Ly9yZWRpcy5leGFtcGxlLmNvbTo2Mzc5  # base64 encoded
```

### Deployment with Environment Variables

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: blog-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: blog-api
  template:
    metadata:
      labels:
        app: blog-api
    spec:
      containers:
      - name: api
        image: blog-api:latest
        ports:
        - containerPort: 8000
        env:
        # From ConfigMap
        - name: API_TITLE
          valueFrom:
            configMapKeyRef:
              name: api-config
              key: API_TITLE
        - name: API_VERSION
          valueFrom:
            configMapKeyRef:
              name: api-config
              key: API_VERSION
        - name: ENABLE_SWAGGER
          valueFrom:
            configMapKeyRef:
              name: api-config
              key: ENABLE_SWAGGER
        # From Secret
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: api-secrets
              key: DATABASE_URL
        - name: JWT_SECRET
          valueFrom:
            secretKeyRef:
              name: api-secrets
              key: JWT_SECRET
        # Direct values
        - name: PORT
          value: "8000"
        - name: HOST
          value: "0.0.0.0"
        resources:
          requests:
            memory: "128Mi"
            cpu: "100m"
          limits:
            memory: "256Mi"
            cpu: "200m"
        livenessProbe:
          httpGet:
            path: /info
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /info
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5
```

## CI/CD Integration

### GitHub Actions Workflow

```yaml
# .github/workflows/deploy.yml
name: Deploy API

on:
  push:
    branches: [main, staging, develop]

jobs:
  deploy:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
    
    - name: Determine environment
      id: env
      run: |
        if [[ ${{ github.ref }} == 'refs/heads/main' ]]; then
          echo "environment=production" >> $GITHUB_OUTPUT
        elif [[ ${{ github.ref }} == 'refs/heads/staging' ]]; then
          echo "environment=staging" >> $GITHUB_OUTPUT
        else
          echo "environment=development" >> $GITHUB_OUTPUT
        fi
    
    - name: Set environment variables
      run: |
        echo "ENVIRONMENT=${{ steps.env.outputs.environment }}" >> $GITHUB_ENV
        echo "API_TITLE=Blog API" >> $GITHUB_ENV
        echo "API_VERSION=${{ github.sha }}" >> $GITHUB_ENV
    
    - name: Deploy to development
      if: steps.env.outputs.environment == 'development'
      run: |
        echo "Deploying to development..."
        export DATABASE_URL="${{ secrets.DEV_DATABASE_URL }}"
        export ENABLE_SWAGGER="true"
        export DEBUG="true"
        # Deploy commands here
    
    - name: Deploy to staging
      if: steps.env.outputs.environment == 'staging'
      run: |
        echo "Deploying to staging..."
        export DATABASE_URL="${{ secrets.STAGING_DATABASE_URL }}"
        export ENABLE_SWAGGER="true"
        export DEBUG="false"
        # Deploy commands here
    
    - name: Deploy to production
      if: steps.env.outputs.environment == 'production'
      run: |
        echo "Deploying to production..."
        export DATABASE_URL="${{ secrets.PROD_DATABASE_URL }}"
        export ENABLE_SWAGGER="false"
        export DEBUG="false"
        # Deploy commands here
```

## Advanced Environment Patterns

### Feature Flags via Environment Variables

```yaml
# config.yaml with feature flags
database_url: "${DATABASE_URL}"
swagger_title: "${API_TITLE}"
enable_swagger: ${ENABLE_SWAGGER:true}

# Feature flags
features:
  enable_caching: ${FEATURE_CACHING:false}
  enable_rate_limiting: ${FEATURE_RATE_LIMITING:false}
  enable_analytics: ${FEATURE_ANALYTICS:false}
  enable_new_ui: ${FEATURE_NEW_UI:false}

tables:
  - name: users
    crud: [get, post, put, patch, delete]
  - name: posts
    crud: [get, post, put]
```

```python
# app.py with feature flags
import os
from lightapi import LightApi

app = LightApi.from_config('config.yaml')

# Conditional features based on environment
if os.getenv('FEATURE_CACHING', 'false').lower() == 'true':
    from lightapi.cache import RedisCache
    cache = RedisCache(url=os.getenv('REDIS_URL'))
    app.add_cache(cache)
    print("✅ Caching enabled")

if os.getenv('FEATURE_RATE_LIMITING', 'false').lower() == 'true':
    from lightapi.middleware import RateLimitMiddleware
    rate_limiter = RateLimitMiddleware(requests_per_minute=100)
    app.add_middleware(rate_limiter)
    print("✅ Rate limiting enabled")

if os.getenv('FEATURE_ANALYTICS', 'false').lower() == 'true':
    @app.middleware("http")
    async def analytics_middleware(request, call_next):
        # Analytics logic here
        response = await call_next(request)
        return response
    print("✅ Analytics enabled")
```

### Environment-Specific Database Configurations

```yaml
# Database configurations per environment
development:
  database_url: "sqlite:///dev.db"
  pool_size: 5
  max_overflow: 10
  echo: true  # SQL logging

staging:
  database_url: "${STAGING_DATABASE_URL}"
  pool_size: 10
  max_overflow: 20
  echo: false

production:
  database_url: "${PROD_DATABASE_URL}"
  pool_size: 20
  max_overflow: 50
  echo: false
  pool_pre_ping: true
  pool_recycle: 3600
```

## Best Practices

### 1. Security

- **Never commit secrets** to version control
- **Use different secrets** for each environment
- **Rotate secrets regularly**
- **Use secret management systems** in production

### 2. Configuration Management

- **Validate required variables** at startup
- **Provide sensible defaults** where appropriate
- **Document all environment variables**
- **Use consistent naming conventions**

### 3. Deployment

- **Test configurations** in staging before production
- **Use infrastructure as code** for consistency
- **Implement health checks** for all environments
- **Monitor configuration changes**

### 4. Development Workflow

- **Local development** should work without external dependencies
- **Environment parity** - keep environments as similar as possible
- **Easy environment switching** for developers
- **Clear documentation** for setup and deployment

## Troubleshooting

### Common Issues

**Environment variable not found:**
```bash
# Check if variable is set
echo $DATABASE_URL

# List all environment variables
env | grep API_

# Check in Python
python -c "import os; print(os.getenv('DATABASE_URL', 'NOT SET'))"
```

**YAML parsing errors with environment variables:**
```yaml
# ❌ Wrong - will cause parsing errors
enable_swagger: $ENABLE_SWAGGER

# ✅ Correct - proper YAML syntax
enable_swagger: ${ENABLE_SWAGGER:true}
```

**Boolean environment variables:**
```python
# ❌ Wrong - string comparison
if os.getenv('DEBUG'):  # Always True if set, even if "false"

# ✅ Correct - proper boolean conversion
if os.getenv('DEBUG', 'false').lower() == 'true':
```

## Next Steps

- **[Deployment Guide](../deployment/production.md)** - Production deployment strategies
- **[Security Guide](../deployment/security.md)** - Security best practices
- **[Docker Guide](../deployment/docker.md)** - Containerization
- **[Kubernetes Guide](../deployment/kubernetes.md)** - Orchestration

---

**Environment variables are essential for modern application deployment.** They provide the flexibility and security needed for professional software development and deployment across multiple environments.