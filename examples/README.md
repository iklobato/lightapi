# LightAPI Examples

This directory contains example applications demonstrating various features of the LightAPI framework.

## Basic Examples

- **basic_rest_api.py**: A simple REST API with default CRUD operations
  - Demonstrates minimal setup for a REST endpoint
  - Shows automatic handling of GET, POST, PUT, DELETE operations
  - Illustrates SQLAlchemy model integration with LightAPI

- **validation_example.py**: Data validation with custom validators
  - Shows field-specific validation rules using Validator class
  - Demonstrates error handling for validation failures
  - Illustrates data transformation (price conversion between dollars and cents)

- **auth_example.py**: JWT authentication with protected resources
  - Implements JWT token generation and verification
  - Shows protected endpoints requiring authentication
  - Demonstrates user information extraction from token
  - Includes public and private resource examples

## Advanced Features

- **middleware_example.py**: Custom middleware implementation for request/response processing
  - Demonstrates request/response lifecycle hooks
  - Includes logging middleware with request timing
  - Shows CORS headers management for cross-origin requests
  - Implements rate limiting with custom window controls

- **filtering_pagination_example.py**: Query filtering and result pagination
  - Shows parameter-based filtering for REST endpoints
  - Implements custom filter logic for search and range queries
  - Demonstrates paginated results with metadata
  - Illustrates dynamic sorting by different fields

- **caching_example.py**: Response caching for improved performance
  - Shows in-memory cache implementation (simulating Redis)
  - Demonstrates cache key generation strategies
  - Includes time-to-live (TTL) management
  - Shows manual cache invalidation (DELETE operations)
  - Implements cache hit/miss HTTP headers

- **swagger_example.py**: Enhanced OpenAPI/Swagger documentation
  - Demonstrates docstring-based API documentation
  - Shows custom SwaggerGenerator implementation
  - Illustrates request/response schema documentation
  - Implements API grouping with tags
  - Demonstrates security scheme definitions

- **relationships_example.py**: Complex SQLAlchemy relationships (one-to-many, many-to-many)
  - Shows many-to-many relationships with association tables
  - Demonstrates one-to-many relationships with back references
  - Illustrates cascade behaviors on related objects
  - Shows nested data serialization across relationships
  - Implements relationship handling in POST/PUT operations

## Running the Examples

Each example is self-contained and can be run directly:

```bash
python examples/basic_rest_api.py
```

Most examples will:
1. Create a SQLite database in the current directory
2. Initialize tables and sample data
3. Start a web server on localhost:8000
4. Generate Swagger documentation at http://localhost:8000/docs

## Example API Requests

Each example includes instructions for testing the API endpoints using `curl` or through the Swagger UI.

For example, to test the basic REST API:

```bash
# List all users
curl http://localhost:8000/users

# Create a new user
curl -X POST http://localhost:8000/users \
  -H "Content-Type: application/json" \
  -d '{"name": "John Doe", "email": "john@example.com", "role": "admin"}'

# Get a user by ID
curl http://localhost:8000/users/1

# Update a user
curl -X PUT http://localhost:8000/users/1 \
  -H "Content-Type: application/json" \
  -d '{"name": "John Smith", "email": "john.smith@example.com", "role": "admin"}'

# Delete a user
curl -X DELETE http://localhost:8000/users/1
```

## Notes

- These examples are designed for learning and demonstration purposes
- For production use, you should implement proper security, error handling, and database configuration
- The examples use SQLite for simplicity, but LightAPI works with any SQLAlchemy-supported database 