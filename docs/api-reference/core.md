# Core API Reference

The Core API module provides the fundamental building blocks of LightAPI. It contains the base classes and utilities that power the framework's core functionality.

## Core Components

### LightAPI Class

The main class that initializes and configures the framework.

```python
from lightapi import LightAPI

app = LightAPI()
```

#### Configuration Options

- `debug` (bool): Enable debug mode
- `config_file` (str): Path to configuration file
- `middleware` (list): List of middleware classes
- `error_handlers` (dict): Custom error handlers

### Request Handling

The core module provides robust request handling capabilities:

```python
@app.route('/api/endpoint')
def handle_request(request):
    return {'status': 'success'}
```

### Response Types

Supported response types include:

- JSON responses
- File responses
- Stream responses
- Custom response types

### Error Handling

Built-in error handling with support for custom error handlers:

```python
@app.error_handler(404)
def handle_not_found(error):
    return {'error': 'Resource not found'}, 404
```

## Core Utilities

### Context Management

```python
from lightapi.core import RequestContext

with RequestContext() as ctx:
    # Access request context
    current_user = ctx.user
```

### Configuration Management

```python
from lightapi.core import Config

config = Config()
config.load_from_file('config.yml')
```

## Best Practices

1. Always initialize the LightAPI instance at the module level
2. Use context managers for request-scoped operations
3. Configure error handlers early in the application lifecycle
4. Utilize built-in utilities instead of implementing custom solutions

## Examples

Here's a complete example of using core features:

```python
from lightapi import LightAPI
from lightapi.core import RequestContext, Config

# Initialize app
app = LightAPI(debug=True)

# Configure app
config = Config()
config.load_from_file('config.yml')
app.config = config

# Define routes
@app.route('/api/data')
def get_data(request):
    with RequestContext() as ctx:
        user = ctx.user
        if not user.is_authenticated:
            return {'error': 'Unauthorized'}, 401
        return {'data': 'Success'}

# Error handling
@app.error_handler(500)
def handle_server_error(error):
    return {'error': 'Internal server error'}, 500

if __name__ == '__main__':
    app.run()
```

## See Also

- [Overview](index.md) - API Reference Overview
- [Middleware](../advanced/middleware.md) - Custom middleware 