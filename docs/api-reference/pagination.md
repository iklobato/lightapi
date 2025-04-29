# Pagination Reference

The Pagination module provides tools for implementing paginated responses in LightAPI endpoints.

## Basic Pagination

### Enabling Pagination

```python
from lightapi.rest import RESTEndpoint

class UserEndpoint(RESTEndpoint):
    paginate = True
    items_per_page = 20
```

### Pagination Parameters

```python
# Default pagination parameters
pagination_params = {
    'page': 1,          # Current page number
    'per_page': 20,     # Items per page
    'max_per_page': 100 # Maximum items per page
}
```

## Advanced Pagination

### Custom Pagination

```python
from lightapi.pagination import Paginator

class CustomPaginator(Paginator):
    def get_pagination_data(self, total_items):
        return {
            'total': total_items,
            'pages': self.get_total_pages(total_items),
            'current_page': self.page,
            'has_next': self.has_next(total_items),
            'has_prev': self.has_prev()
        }
```

### Cursor-based Pagination

```python
from lightapi.pagination import CursorPaginator

class UserEndpoint(RESTEndpoint):
    paginator_class = CursorPaginator
    cursor_field = 'created_at'
```

## Response Format

### Default Format

```python
{
    "items": [...],
    "pagination": {
        "total": 100,
        "pages": 5,
        "current_page": 1,
        "per_page": 20,
        "has_next": true,
        "has_prev": false
    }
}
```

### Custom Format

```python
class UserEndpoint(RESTEndpoint):
    def format_paginated_response(self, items, pagination_data):
        return {
            'users': items,
            'meta': {
                'total_users': pagination_data['total'],
                'page': pagination_data['current_page'],
                'total_pages': pagination_data['pages']
            }
        }
```

## Examples

### Basic Pagination Example

```python
from lightapi import LightAPI
from lightapi.rest import RESTEndpoint
from lightapi.pagination import Paginator

app = LightAPI()

class UserEndpoint(RESTEndpoint):
    route = '/users'
    model = User
    paginate = True
    items_per_page = 20

    def get(self, request):
        query = self.model.query
        paginated_query = self.paginate_query(query)
        return self.format_paginated_response(
            paginated_query.items,
            paginated_query.pagination_data
        )
```

### Advanced Pagination Example

```python
class UserEndpoint(RESTEndpoint):
    route = '/users'
    model = User
    paginator_class = CursorPaginator
    cursor_field = 'created_at'
    items_per_page = 20

    def get(self, request):
        query = self.model.query.order_by(self.model.created_at.desc())
        
        # Get cursor from request
        cursor = request.args.get('cursor')
        
        # Apply cursor-based pagination
        if cursor:
            query = query.filter(self.model.created_at < cursor)
            
        # Get paginated results
        paginated = self.paginate_query(query)
        
        # Format response
        return {
            'users': [user.to_dict() for user in paginated.items],
            'next_cursor': paginated.next_cursor,
            'has_more': paginated.has_more
        }
```

## URL Parameters

### Basic Pagination

```
GET /users?page=2&per_page=20
```

### Cursor Pagination

```
GET /users?cursor=2023-01-01T12:00:00Z&per_page=20
```

## Best Practices

1. Set reasonable default and maximum page sizes
2. Use cursor-based pagination for large datasets
3. Include proper metadata in responses
4. Handle invalid pagination parameters
5. Document pagination parameters and response format

## See Also

- [REST API](rest.md) - REST endpoint implementation
- [Filtering](filters.md) - Query filtering
- [Database](database.md) - Database integration 