# LightAPI Examples

This directory contains comprehensive examples demonstrating all features of LightAPI. Each example is thoroughly tested and includes detailed documentation.

## 🚀 Quick Start

Each example is a standalone Python script that you can run directly:

```bash
python example_name.py
```

Then visit `http://localhost:8000/docs` to see the auto-generated API documentation.

## 📚 Examples Overview

### 🔧 Basic Examples
- **`rest_crud_basic_01.py`** - Basic CRUD operations with SQLAlchemy models
- **`example_01.py`** - Simple getting started example
- **`general_usage_01.py`** - General usage patterns and best practices

### ⚡ Performance & Async
- **`async_performance_06.py`** - Async/await support for high-performance APIs
- **`caching_redis_custom_05.py`** - Redis caching strategies and performance optimization
- **`advanced_caching_redis_05.py`** - Advanced caching with TTL, invalidation, and statistics

### 🔐 Security & Authentication
- **`authentication_jwt_02.py`** - JWT authentication with login/logout
- **`middleware_cors_auth_07.py`** - CORS and authentication middleware
- **`middleware_custom_07.py`** - Custom middleware development

### 🔍 Data Management
- **`filtering_pagination_04.py`** - Basic filtering and pagination
- **`advanced_filtering_pagination_04.py`** - Complex queries, search, and advanced filtering
- **`validation_custom_fields_03.py`** - Basic request validation
- **`advanced_validation_03.py`** - Comprehensive validation with edge cases

### 📖 Documentation & Configuration
- **`swagger_openapi_docs_08.py`** - OpenAPI/Swagger documentation customization
- **`yaml_configuration_09.py`** - YAML-driven API generation and configuration

### 🏗️ Complex Applications
- **`blog_post_10.py`** - Blog post management system
- **`relationships_sqlalchemy_10.py`** - SQLAlchemy relationships and foreign keys
- **`comprehensive_ideal_usage_10.py`** - Comprehensive feature showcase
- **`mega_example_10.py`** - Large-scale application example
- **`user_goal_example_10.py`** - User management with goals and relationships

## 🛠️ Prerequisites

### Basic Requirements
```bash
pip install lightapi
```

### Optional Dependencies
```bash
# For Redis caching examples
pip install redis
redis-server  # Start Redis server

# For PostgreSQL examples
pip install psycopg2-binary

# For MySQL examples
pip install pymysql

# For all features
pip install lightapi[all]
```

## 🚀 Running Examples

### 1. Basic CRUD Example
```bash
python examples/rest_crud_basic_01.py
```
- Visit: `http://localhost:8000/docs`
- Test endpoints: `/products`, `/products/{id}`
- Try: Create, read, update, delete operations

### 2. Async Performance Example
```bash
python examples/async_performance_06.py
```
- Compare sync vs async performance
- Test concurrent request handling
- Monitor response times

### 3. JWT Authentication Example
```bash
LIGHTAPI_JWT_SECRET="your-secret-key" python examples/authentication_jwt_02.py
```
- Login: `POST /authendpoint`
- Access protected: `GET /secretresource`
- Use token in Authorization header

### 4. Redis Caching Example
```bash
# Start Redis server first
redis-server

# Run example
python examples/advanced_caching_redis_05.py
```
- Test cache hits/misses
- Monitor cache statistics
- Try cache invalidation

### 5. Advanced Filtering Example
```bash
python examples/advanced_filtering_pagination_04.py
```
- Test complex queries
- Try pagination and sorting
- Use search functionality

### 6. Validation Example
```bash
python examples/advanced_validation_03.py
```
- Test field validation
- Try invalid data
- See error responses

## 🧪 Testing Examples

Each example includes test scenarios. You can test them using curl or the Swagger UI:

### Basic CRUD Testing
```bash
# Create a product
curl -X POST http://localhost:8000/products \
  -H "Content-Type: application/json" \
  -d '{"name": "Laptop", "price": 999.99, "category": "electronics"}'

# Get all products
curl http://localhost:8000/products

# Get specific product
curl http://localhost:8000/products/1
```

### Authentication Testing
```bash
# Login
curl -X POST http://localhost:8000/authendpoint \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "secret"}'

# Use token
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/secretresource
```

### Filtering Testing
```bash
# Filter by category
curl "http://localhost:8000/products?category=electronics"

# Price range filter
curl "http://localhost:8000/products?min_price=100&max_price=500"

# Complex query
curl "http://localhost:8000/products?category=electronics&sort_by=price&sort_order=desc&page=1&page_size=10"
```

## 📊 Performance Testing

### Load Testing with Apache Bench
```bash
# Install Apache Bench
sudo apt-get install apache2-utils  # Ubuntu/Debian
brew install httpie  # macOS

# Test basic endpoint
ab -n 1000 -c 10 http://localhost:8000/products

# Test with caching
ab -n 1000 -c 10 http://localhost:8000/cached_products/1
```

### Async Performance Testing
```bash
# Run async example
python examples/async_performance.py

# In another terminal, test concurrent requests
for i in {1..10}; do
  curl http://localhost:8000/async_items/$i &
done
wait
```

## 🔧 Feature Categories

### 🔧 Basic CRUD Operations
**Files**: `rest_crud_basic_01.py`, `example_01.py`

Learn the fundamentals of creating REST APIs with automatic CRUD operations:
- Model definition with SQLAlchemy
- Automatic endpoint generation
- Database integration
- Basic error handling

**Key Features Demonstrated**:
- `@register_model_class` decorator
- RestEndpoint inheritance
- Automatic CRUD endpoints
- SQLAlchemy model integration

### ⚡ Performance & Async
**Files**: `async_performance_06.py`, `caching_redis_custom_05.py`, `advanced_caching_redis_05.py`

Discover async/await patterns and caching strategies for high-performance APIs:
- Async endpoint methods
- Concurrent request handling
- Redis caching strategies
- Performance monitoring

**Key Features Demonstrated**:
- `async def` endpoint methods
- `cache_manager` usage
- TTL and cache invalidation
- Performance comparisons

### 🔐 Security & Authentication
**Files**: `authentication_jwt_02.py`, `middleware_cors_auth_07.py`, `middleware_custom_07.py`

Implement JWT authentication, CORS, and custom security middleware:
- JWT token generation and validation
- Protected endpoints
- CORS configuration
- Custom authentication middleware

**Key Features Demonstrated**:
- `AuthEndpoint` class
- JWT secret configuration
- Token-based authentication
- CORS origins setup

### 🔍 Data Management
**Files**: `filtering_pagination_04.py`, `advanced_filtering_pagination_04.py`, `validation_custom_fields_03.py`, `advanced_validation_03.py`

Master filtering, pagination, sorting, and complex queries:
- Query parameter handling
- Advanced filtering logic
- Pagination with metadata
- Comprehensive validation

**Key Features Demonstrated**:
- Query parameter parsing
- Filter application
- Pagination calculations
- Validation error handling

## 🐛 Troubleshooting

### Common Issues

1. **Redis Connection Error**
   ```bash
   # Start Redis server
   redis-server
   
   # Or use Docker
   docker run -d -p 6379:6379 redis:alpine
   ```

2. **Database Connection Error**
   ```python
   # Check database URL
   app = LightApi(database_url="sqlite:///./test.db")  # SQLite
   app = LightApi(database_url="postgresql://user:pass@localhost/db")  # PostgreSQL
   ```

3. **Import Errors**
   ```bash
   # Install missing dependencies
   pip install lightapi[all]
   ```

4. **Port Already in Use**
   ```bash
   # Kill processes using port 8000
   lsof -ti:8000 | xargs kill -9
   
   # Or use a different port
   python example.py --port 8001
   ```

5. **JWT Authentication Issues**
   ```bash
   # Set JWT secret
   export LIGHTAPI_JWT_SECRET="your-secret-key"
   
   # Or set in code
   app = LightApi(jwt_secret="your-secret-key")
   ```

### Debug Mode
```python
# Enable debug mode for detailed error messages
app = LightApi(debug=True)
app.run(debug=True)
```

## 📚 Learning Path

### Beginner (Start Here)
1. **`rest_crud_basic_01.py`** - Learn basic CRUD operations
2. **`example_01.py`** - Understand core concepts
3. **`swagger_openapi_docs_08.py`** - Explore auto-documentation

### Intermediate
1. **`async_performance_06.py`** - Learn async programming
2. **`authentication_jwt_02.py`** - Add security
3. **`caching_redis_custom_05.py`** - Implement caching

### Advanced
1. **`advanced_filtering_pagination_04.py`** - Master complex queries
2. **`advanced_validation_03.py`** - Implement comprehensive validation
3. **`comprehensive_ideal_usage_10.py`** - Build production-ready APIs

## 🤝 Contributing Examples

Want to contribute an example? Follow these guidelines:

1. **Clear Purpose**: Each example should demonstrate specific features
2. **Documentation**: Include detailed comments and docstrings
3. **Testing**: Provide test scenarios and expected outputs
4. **Dependencies**: List any additional requirements
5. **Error Handling**: Show proper error handling patterns

### Example Template
```python
#!/usr/bin/env python3
"""
LightAPI [Feature Name] Example

This example demonstrates [specific features].

Features demonstrated:
- Feature 1
- Feature 2
- Feature 3

Prerequisites:
- pip install [dependencies]
- [any setup required]
"""

# Your example code here...

if __name__ == "__main__":
    print("🚀 [Feature Name] Example")
    print("=" * 50)
    print("Server running at http://localhost:8000")
    print("API documentation at http://localhost:8000/docs")
    print()
    print("Test with:")
    print("  curl http://localhost:8000/endpoint")
    
    app.run()
```

## 🆘 Getting Help

- **Documentation**: Check the main README.md
- **Issues**: Open an issue on GitHub
- **Discussions**: Join GitHub Discussions
- **Examples**: All examples include detailed comments

## 📈 Next Steps

After exploring the examples:

1. **Build Your Own API**: Start with your own models and requirements
2. **Deploy to Production**: Use Docker, Heroku, or cloud platforms
3. **Add Monitoring**: Implement logging and metrics
4. **Scale Up**: Add load balancing and database optimization
5. **Contribute**: Share your improvements with the community

---

**Happy coding with LightAPI!** 🚀