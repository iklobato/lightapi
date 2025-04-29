# LightAPI

A lightweight API framework built with Starlette and SQLAlchemy that simplifies building REST APIs.

## Overview

LightAPI is a lightweight framework designed for quickly building API endpoints with minimal boilerplate code. It combines SQLAlchemy ORM models with API endpoints in a single class, providing a clean and efficient way to create RESTful services.

## Features

- **Unified Models and Endpoints**: Define your database models and API endpoints in a single class
- **Automatic CRUD Operations**: Generate standard REST operations based on your model
- **Custom HTTP Methods**: Control which HTTP methods are allowed per endpoint
- **Request Validation**: Built-in validation for incoming requests
- **Authentication**: JWT authentication support out of the box
- **Filtering**: Query parameter filtering for GET requests
- **Pagination**: Configurable response pagination
- **Caching**: Redis-based response caching
- **Middleware Support**: Extensible middleware architecture
- **Automatic OpenAPI Documentation**: Swagger UI for API exploration
- **Hot Reloading**: Automatic server restart during development

## Installation

### Using pip

```bash
pip install lightapi
```

### Using uv

```bash
# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create and activate virtual environment
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install the package
uv pip install lightapi
```

## Quick Start

```python
from lightapi.rest import RestEndpoint
from lightapi.core import LightApi
from sqlalchemy import Column, Integer, String

# Define your model and endpoint in one class
class User(RestEndpoint):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String, unique=True)
    
    class Configuration:
        http_method_names = ['GET', 'POST', 'PUT', 'DELETE']

# Create the application
app = LightApi(database_url="sqlite:///app.db")
app.register({'/users': User})

# Run with hot reloading during development
app.run(host="0.0.0.0", port=8000, debug=True, reload=True)
```

## Advanced Usage

### Custom Endpoint with Validators

```python
from lightapi.rest import RestEndpoint, Response, Validator
from lightapi.core import LightApi
from sqlalchemy import Column, Integer, String

class UserValidator(Validator):
    def validate_name(self, value):
        if len(value) < 3:
            raise ValueError("Name must be at least 3 characters")
        return value
        
    def validate_email(self, value):
        if '@' not in value:
            raise ValueError("Invalid email format")
        return value

class User(RestEndpoint):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String, unique=True)
    
    class Configuration:
        http_method_names = ['GET', 'POST', 'PUT', 'DELETE']
        validator_class = UserValidator
    
    def post(self, request):
        # Override default POST behavior
        return Response({'message': 'User created successfully'}, status_code=201)
```

### Authentication, Caching, and Pagination

```python
from lightapi.rest import RestEndpoint
from lightapi.pagination import Paginator
from lightapi.auth import JWTAuthentication
from lightapi.cache import RedisCache
from lightapi.core import LightApi
from sqlalchemy import Column, Integer, String

class CustomPaginator(Paginator):
    limit = 50
    sort = True

class Product(RestEndpoint):
    __tablename__ = 'products'
    
    id = Column(Integer, primary_key=True)
    name = Column(String)
    price = Column(Integer)
    
    class Configuration:
        http_method_names = ['GET', 'POST']
        authentication_class = JWTAuthentication
        caching_class = RedisCache
        caching_method_names = ['GET']
        pagination_class = CustomPaginator
```

### Middleware

```python
from lightapi.core import LightApi, Middleware
from lightapi.rest import RestEndpoint

class LoggingMiddleware(Middleware):
    def process(self, request, response):
        print(f"Request: {request.method} {request.url}")
        return response

class CORSMiddleware(Middleware):
    def process(self, request, response):
        if response:
            response.headers['Access-Control-Allow-Origin'] = '*'
        if request.method == 'OPTIONS':
            return Response(status_code=200)
        return response

app = LightApi()
app.register({'/products': Product})
app.add_middleware([LoggingMiddleware, CORSMiddleware])
app.run()
```

## Database Compatibility

LightAPI supports all databases that SQLAlchemy supports, including:
- SQLite
- PostgreSQL
- MySQL
- MariaDB
- Oracle
- MS-SQL

Set the database URL when creating the LightApi instance:

```python
app = LightApi(database_url="postgresql://user:password@localhost/db")
```

If no database URL is provided, LightAPI defaults to using an in-memory SQLite database.

## Swagger/OpenAPI Documentation

LightAPI automatically generates OpenAPI documentation for your API endpoints. When you run your application, the Swagger UI is available at `/docs` and the OpenAPI JSON specification at `/openapi.json`.

You can customize the Swagger documentation by providing docstrings to your endpoint classes and methods:

```python
class User(RestEndpoint):
    """User management endpoint.
    
    This endpoint handles user operations.
    """
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String, unique=True)
    
    def get(self, request):
        """Retrieve user information.
        
        Returns a list of users or a specific user if ID is provided.
        """
        return {'users': [...]}, 200
```

You can customize the Swagger documentation title, version, and description:

```python
app = LightApi(
    database_url="sqlite:///app.db",
    swagger_title="My API Documentation",
    swagger_version="2.0.0",
    swagger_description="Documentation for my awesome API"
)
```

## Development Features

### Hot Reloading

LightAPI supports automatic code reloading during development. When enabled, the server will automatically restart whenever your code changes, making the development process faster and more efficient.

To enable hot reloading, use the `reload` parameter in the `run` method:

```python
app.run(host="0.0.0.0", port=8000, debug=True, reload=True)
```

### Debug Mode

Debug mode provides more detailed error information and enables the Starlette debug middleware. To enable it:

```python
app.run(host="0.0.0.0", port=8000, debug=True)
```

It's recommended to use both debug mode and hot reloading during development, but disable them in production environments.

## API Endpoints

LightAPI automatically generates the following endpoints for each registered model:

| HTTP Method | Endpoint      | Description                           |
|-------------|---------------|---------------------------------------|
| GET         | /resource/    | List all resources                    |
| POST        | /resource/    | Create a new resource                 |
| GET         | /resource/{id}| Retrieve a specific resource          |
| PUT         | /resource/{id}| Replace a specific resource           |
| PATCH       | /resource/{id}| Partially update a specific resource  |
| DELETE      | /resource/{id}| Delete a specific resource            |
| OPTIONS     | /resource/    | Get allowed HTTP methods              |

## Development

To set up the development environment:

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run the example with hot reloading
python examples/example.py

# Run tests
pytest

# Format code
black lightapi tests
isort lightapi tests

# Type checking
mypy lightapi
```

## Why LightAPI?

LightAPI is designed to streamline API development by focusing on simplicity and efficiency. It's ideal for:
- Rapid prototyping
- Small to medium projects
- Scenarios where development speed is essential
- Projects that need a clean, unified approach to models and endpoints

## Contributing

Contributions are welcome! Fork the repository, submit a pull request, or open an issue for bugs or feature suggestions. The project's philosophy emphasizes simplicity, so contributions should aim to enhance functionality while keeping the API minimal and intuitive.

## License
MIT
