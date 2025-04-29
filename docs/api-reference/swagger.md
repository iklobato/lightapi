# Swagger Integration Reference

The Swagger module provides automatic OpenAPI/Swagger documentation generation for LightAPI endpoints.

## Basic Setup

### Enabling Swagger

```python
from lightapi import LightAPI
from lightapi.swagger import SwaggerUI

app = LightAPI()
swagger = SwaggerUI(app)
```

### Configuration Options

```python
swagger = SwaggerUI(
    app,
    title='My API',
    version='1.0.0',
    description='API documentation',
    base_url='/api',
    swagger_url='/docs'
)
```

## API Documentation

### Endpoint Documentation

```python
from lightapi.rest import RESTEndpoint
from lightapi.swagger import swagger_doc

@swagger_doc(
    summary='Get user information',
    description='Retrieve user details by ID',
    responses={
        200: {'description': 'User found'},
        404: {'description': 'User not found'}
    }
)
class UserEndpoint(RESTEndpoint):
    route = '/users/{user_id}'
```

### Request Parameters

```python
@swagger_doc(
    parameters=[
        {
            'name': 'user_id',
            'in': 'path',
            'required': True,
            'schema': {'type': 'integer'}
        },
        {
            'name': 'include_posts',
            'in': 'query',
            'schema': {'type': 'boolean'}
        }
    ]
)
def get(self, request, user_id):
    pass
```

### Request Body

```python
@swagger_doc(
    request_body={
        'content': {
            'application/json': {
                'schema': {
                    'type': 'object',
                    'properties': {
                        'name': {'type': 'string'},
                        'email': {'type': 'string'}
                    },
                    'required': ['name', 'email']
                }
            }
        }
    }
)
def post(self, request):
    pass
```

## Advanced Features

### Security Schemes

```python
swagger = SwaggerUI(
    app,
    security_schemes={
        'bearerAuth': {
            'type': 'http',
            'scheme': 'bearer',
            'bearerFormat': 'JWT'
        }
    }
)

@swagger_doc(security=[{'bearerAuth': []}])
class ProtectedEndpoint(RESTEndpoint):
    pass
```

### Tags and Categories

```python
@swagger_doc(
    tags=['users'],
    summary='User management endpoints'
)
class UserEndpoint(RESTEndpoint):
    pass
```

## Examples

### Complete Swagger Setup

```python
from lightapi import LightAPI
from lightapi.rest import RESTEndpoint
from lightapi.swagger import SwaggerUI, swagger_doc

# Initialize app and Swagger
app = LightAPI()
swagger = SwaggerUI(
    app,
    title='User Management API',
    version='1.0.0',
    description='API for managing users and posts',
    security_schemes={
        'bearerAuth': {
            'type': 'http',
            'scheme': 'bearer',
            'bearerFormat': 'JWT'
        }
    }
)

# Document endpoints
@swagger_doc(
    tags=['users'],
    summary='User operations',
    security=[{'bearerAuth': []}]
)
class UserEndpoint(RESTEndpoint):
    route = '/users/{user_id}'

    @swagger_doc(
        summary='Get user details',
        parameters=[
            {
                'name': 'user_id',
                'in': 'path',
                'required': True,
                'schema': {'type': 'integer'}
            }
        ],
        responses={
            200: {
                'description': 'User found',
                'content': {
                    'application/json': {
                        'schema': {
                            'type': 'object',
                            'properties': {
                                'id': {'type': 'integer'},
                                'name': {'type': 'string'},
                                'email': {'type': 'string'}
                            }
                        }
                    }
                }
            },
            404: {'description': 'User not found'}
        }
    )
    def get(self, request, user_id):
        pass

    @swagger_doc(
        summary='Update user',
        request_body={
            'content': {
                'application/json': {
                    'schema': {
                        'type': 'object',
                        'properties': {
                            'name': {'type': 'string'},
                            'email': {'type': 'string'}
                        }
                    }
                }
            }
        }
    )
    def put(self, request, user_id):
        pass
```

## Best Practices

1. Document all endpoints thoroughly
2. Include response schemas
3. Document error responses
4. Use appropriate tags for organization
5. Keep documentation up to date

## See Also

- [REST API](rest.md) - REST endpoint implementation
- [Authentication](auth.md) - Authentication setup
- [Models](models.md) - Data model definitions 