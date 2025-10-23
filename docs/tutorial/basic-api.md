---
title: Building Your First API
description: Step-by-step tutorial for creating a complete REST API with LightAPI
---

# Building Your First API

In this comprehensive tutorial, you'll learn how to build a complete REST API using LightAPI. We'll cover both YAML configuration (zero-code approach) and Python code approaches, then explore advanced features like validation, filtering, and documentation.

## What We'll Build

In this tutorial, we'll create a **Library Management API** with the following features:

- **Books**: Title, author, ISBN, publication year, availability
- **Authors**: Name, biography, birth year
- **Categories**: Name, description
- **Full CRUD operations** for all entities
- **Relationships** between books, authors, and categories
- **Validation** and error handling
- **Interactive documentation** with Swagger UI
- **Filtering and pagination** for large datasets

## Prerequisites

Before starting, make sure you have:

- Python 3.8+ installed
- LightAPI installed (`pip install lightapi`)
- Basic understanding of REST APIs
- Familiarity with databases (we'll use SQLite)

## Approach 1: YAML Configuration (Recommended)

Let's start with the YAML approach - perfect for rapid prototyping and getting started quickly.

### Step 1: Create the Database Schema

First, create a SQLite database with our library schema:

```sql
-- library.sql
-- Books table
CREATE TABLE books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(200) NOT NULL,
    isbn VARCHAR(13) UNIQUE,
    publication_year INTEGER,
    pages INTEGER,
    is_available BOOLEAN DEFAULT 1,
    author_id INTEGER,
    category_id INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (author_id) REFERENCES authors(id),
    FOREIGN KEY (category_id) REFERENCES categories(id)
);

-- Authors table
CREATE TABLE authors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    biography TEXT,
    birth_year INTEGER,
    nationality VARCHAR(50),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Categories table
CREATE TABLE categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(50) NOT NULL UNIQUE,
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Insert sample data
INSERT INTO authors (name, biography, birth_year, nationality) VALUES
('George Orwell', 'English novelist and essayist', 1903, 'British'),
('Jane Austen', 'English novelist known for romantic fiction', 1775, 'British'),
('Gabriel García Márquez', 'Colombian novelist and Nobel Prize winner', 1927, 'Colombian');

INSERT INTO categories (name, description) VALUES
('Fiction', 'Literary works of imaginative narration'),
('Classic', 'Literature of recognized and established value'),
('Romance', 'Fiction dealing with love in a sentimental way');

INSERT INTO books (title, isbn, publication_year, pages, author_id, category_id) VALUES
('1984', '9780451524935', 1949, 328, 1, 2),
('Animal Farm', '9780451526342', 1945, 112, 1, 2),
('Pride and Prejudice', '9780141439518', 1813, 432, 2, 3),
('One Hundred Years of Solitude', '9780060883287', 1967, 417, 3, 1);
```

Create the database:

```bash
sqlite3 library.db < library.sql
```

### Step 2: Create YAML Configuration

Create a YAML configuration file that defines our API:

```yaml
# library_api.yaml
database_url: "sqlite:///library.db"
swagger_title: "Library Management API"
swagger_version: "1.0.0"
swagger_description: |
  Complete library management system API
  
  ## Features
  - Book catalog management
  - Author information
  - Category organization
  - Full CRUD operations
  - Search and filtering
  - Relationship management
  
  ## Usage
  - Browse books, authors, and categories
  - Add new items to the library
  - Update existing records
  - Track book availability
enable_swagger: true

tables:
  # Books - Full CRUD operations
  - name: books
    crud: [get, post, put, patch, delete]
  
  # Authors - Full management
  - name: authors
    crud: [get, post, put, patch, delete]
  
  # Categories - No delete to preserve book relationships
  - name: categories
    crud: [get, post, put, patch]
```

### Step 3: Create and Run the API

Create a simple Python file to run your API:

```python
# app.py
from lightapi import LightApi

# Create API from YAML configuration
app = LightApi.from_config('library_api.yaml')

if __name__ == '__main__':
    print("🚀 Starting Library Management API...")
    print("📚 API Documentation: http://localhost:8000/docs")
    print("🔍 API Endpoints: http://localhost:8000/")
    app.run(host='0.0.0.0', port=8000)
```

Run your API:

```bash
python app.py
```

**That's it!** Your API is now running with:
- Full CRUD operations for books, authors, and categories
- Automatic input validation based on database schema
- Interactive Swagger documentation at http://localhost:8000/docs
- Proper HTTP status codes and error handling

### Step 4: Test Your API

Let's test the API with some sample requests:

```bash
# Get all books
curl http://localhost:8000/books/

# Get a specific book
curl http://localhost:8000/books/1

# Create a new book
curl -X POST http://localhost:8000/books/ \
  -H 'Content-Type: application/json' \
  -d '{
    "title": "The Great Gatsby",
    "isbn": "9780743273565",
    "publication_year": 1925,
    "pages": 180,
    "author_id": 2,
    "category_id": 2
  }'

# Update a book
curl -X PATCH http://localhost:8000/books/1 \
  -H 'Content-Type: application/json' \
  -d '{"is_available": false}'

# Get all authors
curl http://localhost:8000/authors/

# Create a new author
curl -X POST http://localhost:8000/authors/ \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "F. Scott Fitzgerald",
    "biography": "American novelist and short story writer",
    "birth_year": 1896,
    "nationality": "American"
  }'

# Get all categories
curl http://localhost:8000/categories/

# Create a new category
curl -X POST http://localhost:8000/categories/ \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Science Fiction",
    "description": "Fiction dealing with futuristic concepts"
  }'
```

## Approach 2: Python Code (Advanced)

For more control and custom business logic, let's rebuild the same API using Python code:

### Step 1: Define SQLAlchemy Models

```python
# models.py
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from lightapi import RestEndpoint, register_model_class


class Author(Base, RestEndpoint):
    __tablename__ = 'authors'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    biography = Column(Text)
    birth_year = Column(Integer)
    nationality = Column(String(50))
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationship to books
    books = relationship("Book", back_populates="author")


class Category(Base, RestEndpoint):
    __tablename__ = 'categories'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False, unique=True)
    description = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationship to books
    books = relationship("Book", back_populates="category")


class Book(Base, RestEndpoint):
    __tablename__ = 'books'
    
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    isbn = Column(String(13), unique=True)
    publication_year = Column(Integer)
    pages = Column(Integer)
    is_available = Column(Boolean, default=True)
    author_id = Column(Integer, ForeignKey('authors.id'))
    category_id = Column(Integer, ForeignKey('categories.id'))
    created_at = Column(DateTime, server_default=func.now())
    
    # Relationships
    author = relationship("Author", back_populates="books")
    category = relationship("Category", back_populates="books")
```

### Step 2: Create the Application

```python
# app.py
from lightapi import LightApi
from models import Book, Author, Category

# Create the application
app = LightApi(
    database_url="sqlite:///library.db",
    swagger_title="Library Management API",
    swagger_version="1.0.0",
    swagger_description="""
    Complete library management system API
    
    ## Features
    - Book catalog management
    - Author information
    - Category organization
    - Full CRUD operations
    - Search and filtering
    - Relationship management
    """,
    enable_swagger=True,
    cors_origins=["http://localhost:3000"],  # For frontend apps
    debug=True
)

# Register models with custom endpoints
app.register({
    '/books': Book,
    '/authors': Author,
    '/categories': Category
})

# Add custom endpoints
@app.get("/stats")
def get_library_stats():
    """Get library statistics"""
    return {
        "total_books": 150,
        "total_authors": 45,
        "total_categories": 12,
        "available_books": 132
    }

@app.get("/search")
def search_books(query: str):
    """Search books by title or author"""
    # This would implement actual search logic
    return {
        "query": query,
        "results": [
            {"id": 1, "title": "1984", "author": "George Orwell"},
            {"id": 2, "title": "Animal Farm", "author": "George Orwell"}
        ]
    }

if __name__ == '__main__':
    print("🚀 Starting Library Management API...")
    print("📚 API Documentation: http://localhost:8000/docs")
    print("🔍 API Endpoints: http://localhost:8000/")
    app.run(host='0.0.0.0', port=8000)
```

## Generated API Endpoints

Both approaches generate the same REST endpoints:

### Books Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/books/` | List all books with pagination |
| GET | `/books/{id}` | Get specific book by ID |
| POST | `/books/` | Create new book |
| PUT | `/books/{id}` | Update entire book record |
| PATCH | `/books/{id}` | Partially update book |
| DELETE | `/books/{id}` | Delete book |

### Authors Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/authors/` | List all authors |
| GET | `/authors/{id}` | Get specific author |
| POST | `/authors/` | Create new author |
| PUT | `/authors/{id}` | Update author |
| PATCH | `/authors/{id}` | Partially update author |
| DELETE | `/authors/{id}` | Delete author |

### Categories Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/categories/` | List all categories |
| GET | `/categories/{id}` | Get specific category |
| POST | `/categories/` | Create new category |
| PUT | `/categories/{id}` | Update category |
| PATCH | `/categories/{id}` | Partially update category |

## Advanced Features

### Filtering and Pagination

Your API automatically supports filtering and pagination:

```bash
# Pagination
curl "http://localhost:8000/books/?page=1&page_size=5"

# Filter by author
curl "http://localhost:8000/books/?author_id=1"

# Filter by availability
curl "http://localhost:8000/books/?is_available=true"

# Filter by publication year
curl "http://localhost:8000/books/?publication_year=1949"

# Combine filters
curl "http://localhost:8000/books/?author_id=1&is_available=true&page=1&page_size=10"

# Sort results
curl "http://localhost:8000/books/?sort=title"
curl "http://localhost:8000/books/?sort=-publication_year"  # Descending
```

### Validation and Error Handling

LightAPI automatically validates requests based on your database schema:

```bash
# This will fail - missing required field
curl -X POST http://localhost:8000/books/ \
  -H 'Content-Type: application/json' \
  -d '{"isbn": "123456789"}'
# Response: 400 Bad Request - "title is required"

# This will fail - duplicate ISBN
curl -X POST http://localhost:8000/books/ \
  -H 'Content-Type: application/json' \
  -d '{
    "title": "Duplicate Book",
    "isbn": "9780451524935"
  }'
# Response: 409 Conflict - "ISBN already exists"

# This will fail - invalid foreign key
curl -X POST http://localhost:8000/books/ \
  -H 'Content-Type: application/json' \
  -d '{
    "title": "New Book",
    "author_id": 999
  }'
# Response: 409 Conflict - "Invalid author_id"
```

### Interactive Documentation

Visit http://localhost:8000/docs to access the interactive Swagger UI where you can:

- Browse all available endpoints
- Test API calls directly from the browser
- View request/response schemas
- Download the OpenAPI specification
- See example requests and responses

## Testing Your API

### Using Python requests

```python
# test_api.py
import requests

BASE_URL = "http://localhost:8000"

# Test creating an author
author_data = {
    "name": "J.K. Rowling",
    "biography": "British author, best known for Harry Potter series",
    "birth_year": 1965,
    "nationality": "British"
}

response = requests.post(f"{BASE_URL}/authors/", json=author_data)
print(f"Created author: {response.json()}")
author_id = response.json()["id"]

# Test creating a book
book_data = {
    "title": "Harry Potter and the Philosopher's Stone",
    "isbn": "9780747532699",
    "publication_year": 1997,
    "pages": 223,
    "author_id": author_id,
    "category_id": 1
}

response = requests.post(f"{BASE_URL}/books/", json=book_data)
print(f"Created book: {response.json()}")

# Test getting all books
response = requests.get(f"{BASE_URL}/books/")
print(f"All books: {response.json()}")

# Test filtering
response = requests.get(f"{BASE_URL}/books/?author_id={author_id}")
print(f"Books by author: {response.json()}")
```

### Using pytest for automated testing

```python
# test_library_api.py
import pytest
import requests

BASE_URL = "http://localhost:8000"

def test_create_author():
    author_data = {
        "name": "Test Author",
        "biography": "Test biography",
        "birth_year": 1980,
        "nationality": "Test"
    }
    
    response = requests.post(f"{BASE_URL}/authors/", json=author_data)
    assert response.status_code == 201
    assert response.json()["name"] == "Test Author"

def test_get_authors():
    response = requests.get(f"{BASE_URL}/authors/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_create_book_validation():
    # Test missing required field
    book_data = {"isbn": "123456789"}
    
    response = requests.post(f"{BASE_URL}/books/", json=book_data)
    assert response.status_code == 400
    assert "title" in response.json()["detail"]

def test_book_filtering():
    response = requests.get(f"{BASE_URL}/books/?is_available=true")
    assert response.status_code == 200
    
    books = response.json()
    for book in books:
        assert book["is_available"] == True
```

Run tests:
```bash
pip install pytest
pytest test_library_api.py -v
```

## What You've Learned

Congratulations! You've successfully built a complete REST API with LightAPI. Here's what you've accomplished:

### ✅ **Core Concepts**
- Created REST APIs using both YAML and Python approaches
- Understood database reflection and automatic endpoint generation
- Implemented full CRUD operations for multiple entities
- Set up relationships between database tables

### ✅ **Advanced Features**
- Automatic input validation based on database schema
- Error handling with proper HTTP status codes
- Filtering, pagination, and sorting
- Interactive API documentation with Swagger UI
- Custom endpoints for business logic

### ✅ **Best Practices**
- Environment-based configuration
- Proper database schema design
- RESTful API design principles
- Comprehensive testing strategies

## Next Steps

Now that you have a solid foundation, explore these advanced topics:

1. **[Authentication](../advanced/authentication.md)** - Secure your API with JWT
2. **[Caching](../advanced/caching.md)** - Improve performance with Redis
3. **[Deployment](../deployment/production.md)** - Deploy to production
4. **[Advanced Examples](../examples/)** - Real-world use cases

## Troubleshooting

### Common Issues

**Database connection errors:**
- Ensure your database file exists and is accessible
- Check file permissions
- Verify the database URL format

**Validation errors:**
- Check that required fields are provided
- Ensure data types match the database schema
- Verify foreign key relationships exist

**Import errors:**
- Make sure LightAPI is installed: `pip install lightapi`
- Check Python version compatibility (3.8+)

For more help, see the [Troubleshooting Guide](../troubleshooting.md).

---

**Congratulations!** 🎉 You've built your first complete REST API with LightAPI. The combination of simplicity and power makes LightAPI perfect for rapid development while maintaining production-ready quality.
