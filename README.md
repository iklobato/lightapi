# LightAPI

A lightweight, high-performance async API framework for Python with built-in middleware, authentication, caching, and filtering capabilities. Configure your API through code or YAML configuration files.

## Features

- **📝 YAML Configuration**: Define your entire API structure through YAML files
- **🚀 Async First**: Built on aiohttp for high-performance async request handling
- **🔒 Authentication**: Built-in JWT authentication with customizable token management
- **💾 Caching**: Redis-based caching system with flexible invalidation
- **🔍 Request Filtering**: Advanced parameter filtering with multiple operators
- **📊 Pagination**: Automatic result pagination with customizable limits
- **🌍 CORS Support**: Configurable CORS middleware
- **📝 Logging**: Detailed request/response logging with masking for sensitive data
- **✨ Clean API**: Minimal boilerplate with maximum flexibility

## Installation

```bash
pip install lightapi
```

## Quick Start

### Using YAML Configuration

1. Create a `config.yaml` file:

```yaml
api:
  name: "My Company API"
  environment: "dev"
  database: "${DATABASE_URL}"

endpoints:
  users:
    access: "custom"
    operations: ["GET", "POST"]
    filters: ["name", "email"]
    auth: true
    cache:
      enabled: true
      methods: ["GET"]

middleware:
  - name: "cors"
    enabled: true
    settings:
      origins: ["*"]
      methods: ["GET", "POST"]
```

2. Start your API:

```python
from lightapi import LightApi

api = LightApi.from_yaml('config.yaml')
api.run()
```

### Using Python Code

```python
from lightapi import LightApi, RestEndpoint
from lightapi.auth import JWTAuthentication

class UserEndpoint(RestEndpoint):
    class Configuration:
        authentication_class = JWTAuthentication
        http_method_names = ['GET', 'POST']
        caching_method_names = ['GET']
    
    async def get(self, request):
        return {'message': 'Hello, World!'}

api = LightApi()
api.register({'/users': UserEndpoint})
api.run()
```

## Configuration Guide

### Full YAML Configuration Example

```yaml
# Basic Information
api:
  name: "My Company API"
  environment: "dev"
  database: "${DATABASE_URL}"

# API Endpoints Configuration
endpoints:
  company:
    access: "custom"
    operations: ["GET", "POST"]
    filters: ["name", "email", "website"]
    headers:
      add:
        X-New-Header: "my new header value"

  custom_endpoint:
    access: "custom"
    operations: ["GET", "POST"]
    auth: true
    cache:
      enabled: true
      methods: ["GET"]
    pagination:
      limit: 100
      sort: true

# Authentication Configuration
auth:
  jwt:
    enabled: true
    secret: "${JWT_SECRET}"
    algorithm: "HS256"
    expire_hours: 24
    exclude_paths: ["/health", "/docs"]

# Cache Configuration
cache:
  default:
    enabled: false
    type: "redis"
    url: "${REDIS_URL}"
    ttl: 300
    methods: ["GET"]
```

### Configuration Sections

#### 1. Endpoints Configuration
```yaml
endpoints:
  users:
    access: "custom"
    operations: ["GET", "POST"]
    filters: ["name", "email"]
    auth: true
    cache:
      enabled: true
      methods: ["GET"]
```

#### 2. Middleware Configuration
```yaml
middleware:
  - name: "cors"
    enabled: true
    settings:
      origins: ["*"]
      methods: ["GET", "POST"]
      headers: ["Authorization"]

  - name: "logging"
    enabled: true
    settings:
      request_body: true
      response_body: true
```

#### 3. Authentication Configuration
```yaml
auth:
  jwt:
    enabled: true
    secret: "${JWT_SECRET}"
    algorithm: "HS256"
    expire_hours: 24
```

## Environment Variables

LightAPI supports environment variable substitution in YAML configs:

```yaml
api:
  database: "${DATABASE_URL}"
auth:
  jwt:
    secret: "${JWT_SECRET}"
cache:
  default:
    url: "${REDIS_URL}"
```

Set your environment variables:
```bash
export DATABASE_URL="postgresql://user:pass@localhost:5432/db"
export JWT_SECRET="your-secret-key"
export REDIS_URL="redis://localhost:6379"
```

## Advanced Usage

### Custom Endpoint with YAML Config

```python
from lightapi import RestEndpoint

class CustomEndpoint(RestEndpoint):
    async def get(self, request):
        return {'data': 'custom response'}

# config.yaml
endpoints:
  custom:
    class: "app.endpoints.CustomEndpoint"
    auth: true
    cache:
      enabled: true
```

### Response Formatting

Configure global response formatting:

```yaml
responses:
  envelope: true
  format:
    success:
      data: null
      message: "Success"
      status: 200
    error:
      error: true
      message: null
      status: null
```

Results in:
```json
{
    "data": { ... },
    "message": "Success",
    "status": 200
}
```

## Best Practices

1. **Environment Configuration**
   - Use environment variables for sensitive data
   - Create separate YAML files for different environments

2. **YAML Organization**
   - Split large YAML files into logical sections
   - Use comments to document configuration choices

3. **Configuration Precedence**
   - Code-level configuration overrides YAML configuration
   - Environment variables override both

## Error Handling

LightAPI provides consistent error responses based on your YAML configuration:

```yaml
responses:
  error:
    error: true
    message: "An error occurred"
    status: 400
```

## Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contact

- Author: Henrique Lobato
- Email: iklobato1@gmail.com
- GitHub: [https://github.com/yourusername/lightapi](https://github.com/yourusername/lightapi)