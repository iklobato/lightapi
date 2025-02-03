# LightAPI

## Overview
LightAPI is a lightweight framework for building RESTful APIs using Python's native libraries. Designed for simplicity and minimalism, it provides essential tools for API development while allowing gradual adoption of features like JWT authentication and database integration.

## Features
- **Native Core**: Built on Python's `http.server` with zero dependencies for basic endpoints
- **Optional Extensions**:
  - JWT Authentication (requires `pyjwt`)
  - SQLAlchemy ORM integration (requires `sqlalchemy`)
- **Threaded Server**: Handle concurrent requests with `ThreadingHTTPServer`
- **Middleware Pipeline**: Customize request/response processing
- **Validation System**: Clean data validation through validator classes
- **Flexible Routing**: Manual endpoint configuration with explicit control

## Core Principles
1. **Minimal Base**: Start with pure Python, add only what you need
2. **Explicit Over Magic**: Clear code flow without hidden behaviors
3. **Gradual Complexity**: Scale features as your project grows

## Installation
```bash
pip install lightapi
```

## Basic Usage
### Simple Endpoint
```python
from lightapi import LightApi, RestEndpoint

class HealthCheck(RestEndpoint):
    def get(self, request):
        return {'status': 'healthy'}

app = LightApi()
app.register({'/health': HealthCheck})
app.run(port=8080)
```

## Advanced Features
### Database Integration
```python
from lightapi import LightApi, RestEndpoint, ModelEndpoint
from sqlalchemy import Column, Integer, String

# Define model
class Product(ModelEndpoint.Base):
    __tablename__ = 'products'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    price = Column(Integer)

# Create endpoint with CRUD operations
class ProductEndpoint(RestEndpoint, ModelEndpoint):
    model = Product

    def get(self, request):
        products = self.get_queryset(request).all()
        return {'data': [{'id': p.id, 'name': p.name} for p in products]}

    def post(self, request):
        new_product = Product(name=request.data['name'], price=request.data['price'])
        request.db.add(new_product)
        request.db.commit()
        return {'id': new_product.id}, 201

# Configure database
import os
os.environ['DATABASE_URL'] = "sqlite:///products.db"

if __name__ == '__main__':
    from lightapi.db import database
    database.create_all()
    
    app = LightApi()
    app.register({'/products': ProductEndpoint})
    app.run()
```

### JWT Authentication
```python
from lightapi import LightApi, RestEndpoint, JWTAuthentication

class SecureEndpoint(RestEndpoint):
    authentication_class = JWTAuthentication

    def get(self, request):
        return {'user': request.user}  # Authenticated user from JWT

app = LightApi()
app.register({'/secure': SecureEndpoint})
app.run()
```

### Custom Middleware
```python
from lightapi import LightApi, Middleware, RestEndpoint
import time

class TimingMiddleware(Middleware):
    def process(self, request, response):
        response.headers['X-Processing-Time'] = f"{time.process_time()}s"
        return response

class StatsEndpoint(RestEndpoint):
    def get(self, request):
        return {'requests_handled': 1000}

app = LightApi()
app.add_middleware([TimingMiddleware])
app.register({'/stats': StatsEndpoint})
app.run()
```

## Database Support
LightAPI's SQLAlchemy integration supports all major databases:
- SQLite
- PostgreSQL
- MySQL
- MariaDB
- Oracle
- Microsoft SQL Server

Configure using standard SQLAlchemy connection strings:
```python
import os
os.environ['DATABASE_URL'] = "postgresql://user:password@localhost/mydb"
```

## Development Philosophy
LightAPI follows three core principles:
1. **Native First**: Use Python's built-in capabilities whenever possible
2. **Explicit Over Implicit**: Avoid magic behavior - code should show clear logic
3. **Modular Growth**: Add features through composition, not inheritance

## Contribution Guidelines
1. Maintain 100% test coverage
2. Keep dependencies minimal
3. Preserve the native-first approach
4. Document all new features clearly

## License
MIT License - See [LICENSE](LICENSE) for details

## Resources
- [PyPI Package](https://pypi.org/project/lightapi/)
- [Documentation](https://lightapi.readthedocs.io)
- [Issue Tracker](https://github.com/yourusername/lightapi/issues)
