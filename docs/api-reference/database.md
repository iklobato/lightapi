# Database Reference

The Database module provides integration with SQLAlchemy and other ORMs for data persistence in LightAPI.

## Database Configuration

### Basic Setup

```python
from lightapi.database import Database

db = Database('sqlite:///app.db')
```

### Connection Options

```python
db = Database(
    'postgresql://user:pass@localhost/dbname',
    pool_size=5,
    max_overflow=10
)
```

## Model Definition

### Basic Model

```python
from lightapi.database import Model
from lightapi.models import Column, String, Integer

class User(Model):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(50))
    email = Column(String(120), unique=True)
```

### Relationships

```python
class Post(Model):
    __tablename__ = 'posts'
    
    id = Column(Integer, primary_key=True)
    title = Column(String(100))
    user_id = Column(Integer, ForeignKey('users.id'))
    user = relationship('User', backref='posts')
```

## Query Operations

### Basic Queries

```python
# Create
user = User(name='John', email='john@example.com')
db.session.add(user)
db.session.commit()

# Read
user = User.query.filter_by(name='John').first()

# Update
user.email = 'new@example.com'
db.session.commit()

# Delete
db.session.delete(user)
db.session.commit()
```

### Advanced Queries

```python
# Join queries
users = User.query.join(Post).filter(Post.title.like('%python%')).all()

# Aggregate functions
from sqlalchemy import func
post_count = db.session.query(func.count(Post.id)).scalar()
```

## Migration Support

### Creating Migrations

```python
from lightapi.database import create_migration

create_migration('add_user_table')
```

### Running Migrations

```python
from lightapi.database import migrate

migrate()
```

## Examples

### Complete Database Setup

```python
from lightapi import LightAPI
from lightapi.database import Database, Model
from lightapi.models import Column, String, Integer, relationship

# Initialize app and database
app = LightAPI()
db = Database('sqlite:///app.db')

# Define models
class User(Model):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(50))
    email = Column(String(120), unique=True)
    posts = relationship('Post', backref='author')

class Post(Model):
    __tablename__ = 'posts'
    
    id = Column(Integer, primary_key=True)
    title = Column(String(100))
    content = Column(String)
    user_id = Column(Integer, ForeignKey('users.id'))

# Create tables
db.create_all()
```

## Best Practices

1. Use migrations for database schema changes
2. Implement proper indexing for better performance
3. Use relationships appropriately
4. Handle database errors properly
5. Use connection pooling in production

## See Also

- [Models](models.md) - Model definitions and validation
- [REST API](rest.md) - REST endpoint implementation
- [Core API](core.md) - Core framework functionality 