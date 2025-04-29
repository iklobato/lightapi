# Filtering Reference

The Filtering module provides advanced query filtering capabilities for LightAPI endpoints.

## Basic Filtering

### Field Filtering

```python
from lightapi.filters import Filterable

class UserEndpoint(RESTEndpoint):
    filter_fields = ['name', 'email', 'status']
```

### Filter Operators

```python
# Supported operators
operators = {
    'eq': 'Equal to',
    'ne': 'Not equal to',
    'gt': 'Greater than',
    'lt': 'Less than',
    'gte': 'Greater than or equal to',
    'lte': 'Less than or equal to',
    'like': 'Pattern matching',
    'in': 'In list',
    'not_in': 'Not in list'
}
```

## Advanced Filtering

### Custom Filter Methods

```python
class UserEndpoint(RESTEndpoint):
    def filter_active_users(self, query):
        return query.filter_by(status='active')

    def filter_by_role(self, query, role):
        return query.filter_by(role=role)
```

### Complex Filters

```python
class UserEndpoint(RESTEndpoint):
    filter_fields = {
        'name': ['eq', 'like'],
        'age': ['gt', 'lt', 'between'],
        'status': ['eq', 'in'],
        'created_at': ['gt', 'lt', 'between']
    }
```

## Filter Chains

### Chaining Multiple Filters

```python
from lightapi.filters import FilterChain

class UserEndpoint(RESTEndpoint):
    filter_chain = FilterChain([
        ('status', 'active'),
        ('role', ['admin', 'moderator']),
        ('created_at', {'gt': '2023-01-01'})
    ])
```

## Examples

### Basic Filtering Example

```python
from lightapi import LightAPI
from lightapi.rest import RESTEndpoint
from lightapi.filters import Filterable

app = LightAPI()

class UserEndpoint(RESTEndpoint):
    route = '/users'
    model = User
    filter_fields = ['name', 'email', 'status']

    def get(self, request):
        query = self.model.query
        filtered_query = self.apply_filters(query, request.args)
        users = filtered_query.all()
        return {'users': [user.to_dict() for user in users]}
```

### Advanced Filtering Example

```python
class UserEndpoint(RESTEndpoint):
    route = '/users'
    model = User
    filter_fields = {
        'name': ['eq', 'like'],
        'age': ['gt', 'lt', 'between'],
        'status': ['eq', 'in'],
        'created_at': ['gt', 'lt', 'between']
    }

    def get(self, request):
        query = self.model.query
        
        # Apply basic filters
        query = self.apply_filters(query, request.args)
        
        # Apply custom filters
        if 'role' in request.args:
            query = self.filter_by_role(query, request.args['role'])
            
        # Apply date range filter
        if 'date_range' in request.args:
            query = self.filter_by_date_range(query, request.args['date_range'])
            
        users = query.all()
        return {'users': [user.to_dict() for user in users]}

    def filter_by_role(self, query, role):
        return query.filter_by(role=role)

    def filter_by_date_range(self, query, date_range):
        start, end = date_range.split(',')
        return query.filter(
            self.model.created_at.between(start, end)
        )
```

## URL Query Parameters

### Basic Filtering

```
GET /users?name=John&status=active
GET /users?age__gt=25&age__lt=35
GET /users?role__in=admin,moderator
```

### Complex Filtering

```
GET /users?name__like=%john%&status__in=active,pending&created_at__gt=2023-01-01
```

## Best Practices

1. Define allowed filter fields explicitly
2. Use appropriate operators for each field
3. Implement proper validation for filter values
4. Consider performance implications of complex filters
5. Document available filters and operators

## See Also

- [REST API](rest.md) - REST endpoint implementation
- [Pagination](pagination.md) - Pagination configuration
- [Database](database.md) - Database integration 