---
title: Production Deployment Guide
description: Complete guide for deploying LightAPI applications to production
---

# Production Deployment Guide

This comprehensive guide covers everything you need to deploy LightAPI applications to production environments, including server configuration, security, monitoring, and scaling strategies.

## Production Architecture Overview

A typical LightAPI production deployment consists of:

```
Internet → Load Balancer → Reverse Proxy → Application Servers → Database
                      ↓
                   Static Files
                      ↓
                   Monitoring
```

### Key Components

- **Load Balancer**: Distributes traffic across multiple application instances
- **Reverse Proxy**: Handles SSL termination, static files, and request routing
- **Application Servers**: Multiple LightAPI instances running with ASGI servers
- **Database**: Production database with connection pooling and replication
- **Caching**: Redis for application caching and session storage
- **Monitoring**: Logging, metrics, and health checks

## Application Server Configuration

### Using Gunicorn with Uvicorn Workers (Recommended)

Gunicorn provides process management while Uvicorn handles ASGI:

```bash
# Basic production configuration
gunicorn app:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --worker-connections 1000 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --timeout 30 \
    --keepalive 5 \
    --preload
```

### Advanced Gunicorn Configuration

Create a `gunicorn.conf.py` file:

```python
# gunicorn.conf.py
import multiprocessing
import os

# Server socket
bind = f"0.0.0.0:{os.getenv('PORT', 8000)}"
backlog = 2048

# Worker processes
workers = int(os.getenv('WORKERS', multiprocessing.cpu_count() * 2 + 1))
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100
timeout = 30
keepalive = 5

# Restart workers after this many requests (prevents memory leaks)
max_requests = 1000
max_requests_jitter = 100

# Preload application for better performance
preload_app = True

# Logging
accesslog = "-"  # Log to stdout
errorlog = "-"   # Log to stderr
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = "lightapi"

# Server mechanics
daemon = False
pidfile = "/tmp/gunicorn.pid"
user = None
group = None
tmp_upload_dir = None

# SSL (if terminating SSL at application level)
# keyfile = "/path/to/keyfile"
# certfile = "/path/to/certfile"

def when_ready(server):
    server.log.info("Server is ready. Spawning workers")

def worker_int(worker):
    worker.log.info("worker received INT or QUIT signal")

def pre_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_fork(server, worker):
    server.log.info("Worker spawned (pid: %s)", worker.pid)

def post_worker_init(worker):
    worker.log.info("Worker initialized (pid: %s)", worker.pid)

def worker_abort(worker):
    worker.log.info("Worker aborted (pid: %s)", worker.pid)
```

Run with configuration file:
```bash
gunicorn -c gunicorn.conf.py app:app
```

### Using Uvicorn Directly

For simpler deployments or development:

```bash
# Single process
uvicorn app:app --host 0.0.0.0 --port 8000 --workers 1

# Multiple workers (experimental)
uvicorn app:app --host 0.0.0.0 --port 8000 --workers 4
```

## Environment Configuration

### Production Environment Variables

```bash
# Application
export ENVIRONMENT=production
export DEBUG=false
export HOST=0.0.0.0
export PORT=8000
export WORKERS=4

# Database
export DATABASE_URL=postgresql://user:password@db-host:5432/production_db
export DATABASE_POOL_SIZE=20
export DATABASE_MAX_OVERFLOW=30

# Security
export JWT_SECRET=your-super-secure-jwt-secret-key-256-bits
export CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
export ENABLE_SWAGGER=false  # Disable in production

# Caching
export REDIS_URL=redis://redis-host:6379/0
export CACHE_TTL=3600

# Monitoring
export LOG_LEVEL=INFO
export SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id

# Performance
export MAX_REQUEST_SIZE=10485760  # 10MB
export REQUEST_TIMEOUT=30
```

### Environment File Management

```bash
# .env.production
ENVIRONMENT=production
DEBUG=false
DATABASE_URL=postgresql://user:password@prod-db:5432/app
JWT_SECRET=production-secret-key
CORS_ORIGINS=https://myapp.com
ENABLE_SWAGGER=false
REDIS_URL=redis://prod-redis:6379/0
LOG_LEVEL=WARNING
```

Load environment in your application:

```python
# app.py
import os
from dotenv import load_dotenv
from lightapi import LightApi

# Load environment-specific configuration
env = os.getenv('ENVIRONMENT', 'development')
load_dotenv(f'.env.{env}')

# Create application
app = LightApi.from_config('production.yaml')

if __name__ == '__main__':
    # Production should use gunicorn, not app.run()
    print("Use gunicorn for production deployment")
    print("gunicorn -c gunicorn.conf.py app:app")
```

## Reverse Proxy Configuration

### Nginx Configuration

```nginx
# /etc/nginx/sites-available/lightapi
upstream lightapi_backend {
    # Multiple application servers for load balancing
    server 127.0.0.1:8000 max_fails=3 fail_timeout=30s;
    server 127.0.0.1:8001 max_fails=3 fail_timeout=30s;
    server 127.0.0.1:8002 max_fails=3 fail_timeout=30s;
    
    # Health check
    keepalive 32;
}

# HTTP to HTTPS redirect
server {
    listen 80;
    server_name api.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

# HTTPS server
server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;

    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.yourdomain.com/privkey.pem;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:50m;
    ssl_session_tickets off;

    # Modern SSL configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;

    # HSTS
    add_header Strict-Transport-Security "max-age=63072000" always;

    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    add_header Referrer-Policy "strict-origin-when-cross-origin";

    # Gzip compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/xml text/javascript application/javascript application/xml+rss application/json;

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req zone=api burst=20 nodelay;

    # Client settings
    client_max_body_size 10M;
    client_body_timeout 30s;
    client_header_timeout 30s;

    # Proxy settings
    proxy_connect_timeout 30s;
    proxy_send_timeout 30s;
    proxy_read_timeout 30s;
    proxy_buffering on;
    proxy_buffer_size 4k;
    proxy_buffers 8 4k;

    # API endpoints
    location / {
        proxy_pass http://lightapi_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port $server_port;
        
        # WebSocket support (if needed)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Health check endpoint
    location /health {
        proxy_pass http://lightapi_backend/health;
        access_log off;
    }

    # Static files (if serving any)
    location /static/ {
        alias /var/www/lightapi/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Deny access to sensitive files
    location ~ /\. {
        deny all;
        access_log off;
        log_not_found off;
    }

    # Custom error pages
    error_page 502 503 504 /50x.html;
    location = /50x.html {
        root /var/www/html;
    }
}
```

### Apache Configuration

```apache
# /etc/apache2/sites-available/lightapi.conf
<VirtualHost *:80>
    ServerName api.yourdomain.com
    Redirect permanent / https://api.yourdomain.com/
</VirtualHost>

<VirtualHost *:443>
    ServerName api.yourdomain.com
    
    # SSL Configuration
    SSLEngine on
    SSLCertificateFile /etc/letsencrypt/live/api.yourdomain.com/cert.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/api.yourdomain.com/privkey.pem
    SSLCertificateChainFile /etc/letsencrypt/live/api.yourdomain.com/chain.pem
    
    # Security headers
    Header always set Strict-Transport-Security "max-age=63072000"
    Header always set X-Frame-Options DENY
    Header always set X-Content-Type-Options nosniff
    
    # Proxy configuration
    ProxyPreserveHost On
    ProxyRequests Off
    
    # Load balancing
    ProxyPass / balancer://lightapi-cluster/
    ProxyPassReverse / balancer://lightapi-cluster/
    
    <Proxy balancer://lightapi-cluster>
        BalancerMember http://127.0.0.1:8000
        BalancerMember http://127.0.0.1:8001
        BalancerMember http://127.0.0.1:8002
        ProxySet hcmethod GET
        ProxySet hcuri /health
    </Proxy>
    
    # Logging
    ErrorLog ${APACHE_LOG_DIR}/lightapi_error.log
    CustomLog ${APACHE_LOG_DIR}/lightapi_access.log combined
</VirtualHost>
```

## Database Configuration

### PostgreSQL Production Setup

```python
# Database configuration for production
DATABASE_CONFIG = {
    'url': os.getenv('DATABASE_URL'),
    'pool_size': int(os.getenv('DATABASE_POOL_SIZE', 20)),
    'max_overflow': int(os.getenv('DATABASE_MAX_OVERFLOW', 30)),
    'pool_timeout': int(os.getenv('DATABASE_POOL_TIMEOUT', 30)),
    'pool_recycle': int(os.getenv('DATABASE_POOL_RECYCLE', 3600)),
    'pool_pre_ping': True,  # Verify connections before use
    'echo': False,  # Disable SQL logging in production
}

app = LightApi(
    database_url=DATABASE_CONFIG['url'],
    **{k: v for k, v in DATABASE_CONFIG.items() if k != 'url'}
)
```

### Database Connection String Examples

```bash
# PostgreSQL with connection pooling
DATABASE_URL="postgresql://user:password@host:5432/dbname?pool_size=20&max_overflow=30"

# PostgreSQL with SSL
DATABASE_URL="postgresql://user:password@host:5432/dbname?sslmode=require"

# MySQL with charset
DATABASE_URL="mysql+pymysql://user:password@host:3306/dbname?charset=utf8mb4"

# SQLite with WAL mode (for better concurrency)
DATABASE_URL="sqlite:///app.db?check_same_thread=false"
```

### Database Migrations with Alembic

```bash
# Install Alembic
pip install alembic

# Initialize Alembic
alembic init migrations

# Configure alembic.ini
# sqlalchemy.url = postgresql://user:password@host:5432/dbname

# Create migration
alembic revision --autogenerate -m "Initial migration"

# Apply migration
alembic upgrade head

# Production deployment script
#!/bin/bash
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting application..."
gunicorn -c gunicorn.conf.py app:app
```

## Security Configuration

### Production Security Checklist

```yaml
# production.yaml - Security-focused configuration
database_url: "${DATABASE_URL}"
swagger_title: "Production API"
enable_swagger: false  # ✅ Disabled in production
debug: false          # ✅ Disabled in production

# Security headers
security:
  cors_origins: 
    - "https://yourdomain.com"
    - "https://www.yourdomain.com"
  cors_allow_credentials: true
  cors_max_age: 86400

# Rate limiting
rate_limiting:
  enabled: true
  requests_per_minute: 60
  requests_per_hour: 1000

tables:
  - name: users
    crud: [get, patch]  # ✅ Limited operations in production
  - name: posts
    crud: [get, post, patch]
```

### Environment Security

```bash
# Use strong secrets
export JWT_SECRET=$(openssl rand -base64 32)

# Restrict database permissions
export DATABASE_URL="postgresql://readonly_user:password@host:5432/db"

# Use secure Redis
export REDIS_URL="rediss://user:password@redis-host:6380/0"  # SSL enabled

# Enable security headers
export SECURITY_HEADERS=true
```

## Monitoring and Logging

### Application Logging

```python
# logging_config.py
import logging
import sys
from pythonjsonlogger import jsonlogger

def setup_logging():
    """Configure structured logging for production"""
    
    # Create formatter
    formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(name)s %(levelname)s %(message)s'
    )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Application logger
    app_logger = logging.getLogger('lightapi')
    app_logger.setLevel(logging.INFO)
    
    return app_logger

# app.py
import logging
from logging_config import setup_logging

logger = setup_logging()

app = LightApi.from_config('production.yaml')

@app.middleware("http")
async def logging_middleware(request, call_next):
    """Log all requests"""
    start_time = time.time()
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    logger.info(
        "Request processed",
        extra={
            "method": request.method,
            "url": str(request.url),
            "status_code": response.status_code,
            "process_time": process_time,
            "user_agent": request.headers.get("user-agent"),
            "remote_addr": request.client.host
        }
    )
    
    return response
```

### Health Checks

```python
# health.py
from lightapi import LightApi
import psutil
import time

app = LightApi.from_config('production.yaml')

@app.get("/health")
def health_check():
    """Comprehensive health check"""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "1.0.0",
        "environment": os.getenv("ENVIRONMENT", "unknown")
    }

@app.get("/health/detailed")
def detailed_health_check():
    """Detailed health check for monitoring"""
    try:
        # Database check
        db_status = check_database_connection()
        
        # Redis check
        redis_status = check_redis_connection()
        
        # System metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            "status": "healthy",
            "timestamp": time.time(),
            "checks": {
                "database": db_status,
                "redis": redis_status,
                "system": {
                    "cpu_percent": cpu_percent,
                    "memory_percent": memory.percent,
                    "disk_percent": (disk.used / disk.total) * 100
                }
            }
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": time.time()
        }, 503

def check_database_connection():
    """Check database connectivity"""
    try:
        # Perform a simple query
        result = app.database.execute("SELECT 1")
        return {"status": "connected", "response_time": "< 100ms"}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def check_redis_connection():
    """Check Redis connectivity"""
    try:
        # Ping Redis
        app.cache.redis_client.ping()
        return {"status": "connected"}
    except Exception as e:
        return {"status": "error", "error": str(e)}
```

### Metrics Collection

```python
# metrics.py
from prometheus_client import Counter, Histogram, generate_latest
import time

# Metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('http_request_duration_seconds', 'HTTP request duration')

@app.middleware("http")
async def metrics_middleware(request, call_next):
    """Collect metrics for monitoring"""
    start_time = time.time()
    
    response = await call_next(request)
    
    # Record metrics
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()
    
    REQUEST_DURATION.observe(time.time() - start_time)
    
    return response

@app.get("/metrics")
def metrics():
    """Prometheus metrics endpoint"""
    return Response(generate_latest(), media_type="text/plain")
```

## Deployment Strategies

### Blue-Green Deployment

```bash
#!/bin/bash
# blue-green-deploy.sh

set -e

CURRENT_COLOR=$(cat /etc/lightapi/current_color 2>/dev/null || echo "blue")
NEW_COLOR=$([ "$CURRENT_COLOR" = "blue" ] && echo "green" || echo "blue")

echo "Current deployment: $CURRENT_COLOR"
echo "Deploying to: $NEW_COLOR"

# Deploy to new environment
docker-compose -f docker-compose.$NEW_COLOR.yml up -d

# Health check
echo "Waiting for health check..."
for i in {1..30}; do
    if curl -f http://localhost:800$([[ "$NEW_COLOR" = "green" ]] && echo "1" || echo "0")/health; then
        echo "Health check passed"
        break
    fi
    sleep 10
done

# Switch traffic
echo "Switching traffic to $NEW_COLOR"
cp nginx.$NEW_COLOR.conf /etc/nginx/sites-enabled/lightapi
nginx -s reload

# Update current color
echo "$NEW_COLOR" > /etc/lightapi/current_color

# Stop old environment
docker-compose -f docker-compose.$CURRENT_COLOR.yml down

echo "Deployment complete: $NEW_COLOR is now active"
```

### Rolling Deployment

```bash
#!/bin/bash
# rolling-deploy.sh

set -e

SERVERS=("server1:8000" "server2:8000" "server3:8000")

for server in "${SERVERS[@]}"; do
    echo "Deploying to $server..."
    
    # Remove from load balancer
    curl -X POST "http://loadbalancer/remove/$server"
    
    # Wait for connections to drain
    sleep 30
    
    # Deploy new version
    ssh "$server" "cd /app && git pull && systemctl restart lightapi"
    
    # Health check
    for i in {1..10}; do
        if curl -f "http://$server/health"; then
            echo "$server is healthy"
            break
        fi
        sleep 10
    done
    
    # Add back to load balancer
    curl -X POST "http://loadbalancer/add/$server"
    
    echo "$server deployment complete"
done

echo "Rolling deployment complete"
```

## Performance Optimization

### Application Performance

```python
# performance.py
from lightapi import LightApi
import asyncio
import uvloop  # Faster event loop

# Use faster event loop
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

app = LightApi.from_config('production.yaml')

# Connection pooling
app.configure_database(
    pool_size=20,
    max_overflow=30,
    pool_timeout=30,
    pool_recycle=3600
)

# Caching configuration
app.configure_cache(
    backend='redis',
    url=os.getenv('REDIS_URL'),
    default_ttl=3600,
    max_connections=20
)

# Compression middleware
@app.middleware("http")
async def compression_middleware(request, call_next):
    """Add compression for large responses"""
    response = await call_next(request)
    
    # Add compression headers
    if 'gzip' in request.headers.get('accept-encoding', ''):
        response.headers['content-encoding'] = 'gzip'
    
    return response
```

### Database Optimization

```sql
-- Database indexes for common queries
CREATE INDEX CONCURRENTLY idx_users_email ON users(email);
CREATE INDEX CONCURRENTLY idx_posts_created_at ON posts(created_at DESC);
CREATE INDEX CONCURRENTLY idx_posts_user_id ON posts(user_id);

-- Partial indexes for common filters
CREATE INDEX CONCURRENTLY idx_posts_published ON posts(created_at) WHERE published = true;

-- Composite indexes for complex queries
CREATE INDEX CONCURRENTLY idx_posts_user_published ON posts(user_id, published, created_at DESC);
```

## Monitoring and Alerting

### Prometheus Configuration

```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'lightapi'
    static_configs:
      - targets: ['localhost:8000', 'localhost:8001', 'localhost:8002']
    metrics_path: '/metrics'
    scrape_interval: 30s

  - job_name: 'nginx'
    static_configs:
      - targets: ['localhost:9113']

  - job_name: 'postgres'
    static_configs:
      - targets: ['localhost:9187']

  - job_name: 'redis'
    static_configs:
      - targets: ['localhost:9121']
```

### Grafana Dashboard

```json
{
  "dashboard": {
    "title": "LightAPI Production Dashboard",
    "panels": [
      {
        "title": "Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(http_requests_total[5m])",
            "legendFormat": "{{method}} {{endpoint}}"
          }
        ]
      },
      {
        "title": "Response Time",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))",
            "legendFormat": "95th percentile"
          }
        ]
      },
      {
        "title": "Error Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(http_requests_total{status=~\"5..\"}[5m])",
            "legendFormat": "5xx errors"
          }
        ]
      }
    ]
  }
}
```

### Alerting Rules

```yaml
# alerts.yml
groups:
  - name: lightapi
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value }} errors per second"

      - alert: HighResponseTime
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High response time detected"
          description: "95th percentile response time is {{ $value }}s"

      - alert: DatabaseConnectionFailure
        expr: up{job="postgres"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Database connection failure"
          description: "PostgreSQL is down"
```

## Backup and Disaster Recovery

### Database Backup

```bash
#!/bin/bash
# backup.sh

set -e

BACKUP_DIR="/backups/lightapi"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="production_db"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Database backup
pg_dump "$DATABASE_URL" | gzip > "$BACKUP_DIR/db_backup_$DATE.sql.gz"

# Upload to S3 (optional)
aws s3 cp "$BACKUP_DIR/db_backup_$DATE.sql.gz" "s3://your-backup-bucket/lightapi/"

# Clean old backups (keep last 30 days)
find "$BACKUP_DIR" -name "db_backup_*.sql.gz" -mtime +30 -delete

echo "Backup completed: db_backup_$DATE.sql.gz"
```

### Disaster Recovery Plan

```bash
#!/bin/bash
# disaster-recovery.sh

set -e

echo "Starting disaster recovery..."

# 1. Restore database from latest backup
LATEST_BACKUP=$(aws s3 ls s3://your-backup-bucket/lightapi/ | sort | tail -n 1 | awk '{print $4}')
aws s3 cp "s3://your-backup-bucket/lightapi/$LATEST_BACKUP" /tmp/
gunzip "/tmp/$LATEST_BACKUP"
psql "$DATABASE_URL" < "/tmp/${LATEST_BACKUP%.gz}"

# 2. Deploy application
docker-compose up -d

# 3. Run health checks
sleep 30
curl -f http://localhost:8000/health

echo "Disaster recovery completed"
```

## Troubleshooting

### Common Production Issues

**High Memory Usage:**
```bash
# Monitor memory usage
ps aux --sort=-%mem | head -10

# Check for memory leaks
valgrind --tool=memcheck --leak-check=full python app.py

# Restart workers periodically
# In gunicorn.conf.py:
max_requests = 1000
max_requests_jitter = 100
```

**Database Connection Issues:**
```bash
# Check connection pool
SELECT count(*) FROM pg_stat_activity WHERE datname = 'your_db';

# Monitor slow queries
SELECT query, mean_time, calls FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;

# Connection pool configuration
export DATABASE_POOL_SIZE=20
export DATABASE_MAX_OVERFLOW=30
```

**High CPU Usage:**
```bash
# Profile application
py-spy top --pid $(pgrep -f gunicorn)

# Check for inefficient queries
EXPLAIN ANALYZE SELECT * FROM your_table WHERE condition;

# Optimize with indexes
CREATE INDEX CONCURRENTLY idx_your_table_column ON your_table(column);
```

## Next Steps

- **[Docker Deployment](docker.md)** - Containerized deployment
- **[Kubernetes](kubernetes.md)** - Orchestrated deployment
- **[Security Guide](security.md)** - Advanced security configuration
- **[Monitoring](monitoring.md)** - Comprehensive monitoring setup

---

**Production deployment requires careful planning and monitoring.** This guide provides the foundation for a robust, scalable LightAPI deployment. Adapt the configurations to your specific requirements and infrastructure.
