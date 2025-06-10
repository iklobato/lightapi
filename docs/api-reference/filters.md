# Filters API Reference

This document provides comprehensive reference for LightAPI's filtering system, including built-in filter classes and how to create custom filters.

## Overview

LightAPI's filtering system allows you to add query parameters to filter database results. The system is designed to be:

- **Flexible**: Support multiple filter types and operators
- **Secure**: Automatic parameter validation and sanitization
- **Extensible**: Easy to create custom filter classes
- **Performant**: Generates efficient SQL queries

## Base Classes

### BaseFilter

The foundation class for all filters.

```python
from lightapi.filters import BaseFilter

class BaseFilter:
    def filter_queryset(self, queryset, request):
        """
        Filter a SQLAlchemy queryset based on request parameters.
        
        Args:
            queryset: SQLAlchemy Query object
            request: HTTP request object with query_params
            
        Returns:
            SQLAlchemy Query object with filters applied
        """
        return queryset
```

**Usage:**
```python
class CustomFilter(BaseFilter):
    def filter_queryset(self, queryset, request):
        # Implement your filtering logic
        return queryset
```

### ParameterFilter

Built-in filter that applies exact matches for query parameters.

```python
from lightapi.filters import ParameterFilter

class ParameterFilter(BaseFilter):
    def filter_queryset(self, queryset, request):
        """
        Apply filters based on query parameters that match model fields.
        
        Automatically filters by:
        - Exact field matches (e.g., ?category=electronics)
        - Model attributes that exist in query parameters
        """
```

## Built-in Filter Classes

### ParameterFilter

Provides automatic filtering based on query parameters.

#### Configuration

```python
@register_model_class
class Product(RestEndpoint):
    __tablename__ = 'products'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    category = Column(String(50))
    price = Column(Float)
    
    class Configuration:
        filter_class = ParameterFilter
```

#### Supported Parameters

- **Field Matching**: `?category=electronics` filters by exact category match
- **Multiple Fields**: `?category=electronics&price=99.99` combines filters
- **Automatic Type Conversion**: Converts string parameters to appropriate types

#### Example Usage

```bash
# Filter by category
GET /products?category=electronics

# Filter by multiple fields
GET /products?category=electronics&active=true

# Combine with pagination
GET /products?category=electronics&page=1&limit=10
```

## Custom Filter Examples

### Advanced Parameter Filter

```python
from lightapi.filters import ParameterFilter
from sqlalchemy import and_, or_

class AdvancedParameterFilter(ParameterFilter):
    def filter_queryset(self, queryset, request):
        # Apply base parameter filtering
        queryset = super().filter_queryset(queryset, request)
        
        params = request.query_params
        entity = queryset.column_descriptions[0]['entity']
        
        # Price range filtering
        min_price = params.get('min_price')
        max_price = params.get('max_price')
        
        if min_price:
            try:
                queryset = queryset.filter(entity.price >= float(min_price))
            except (ValueError, TypeError):
                pass
        
        if max_price:
            try:
                queryset = queryset.filter(entity.price <= float(max_price))
            except (ValueError, TypeError):
                pass
        
        # Text search across multiple fields
        search = params.get('search')
        if search:
            search_filter = or_(
                entity.name.ilike(f'%{search}%'),
                entity.description.ilike(f'%{search}%')
            )
            queryset = queryset.filter(search_filter)
        
        # Date range filtering
        from_date = params.get('from_date')
        to_date = params.get('to_date')
        
        if from_date:
            try:
                date_obj = datetime.fromisoformat(from_date)
                queryset = queryset.filter(entity.created_at >= date_obj)
            except ValueError:
                pass
        
        if to_date:
            try:
                date_obj = datetime.fromisoformat(to_date)
                queryset = queryset.filter(entity.created_at <= date_obj)
            except ValueError:
                pass
        
        return queryset
```

### Dynamic Operator Filter

```python
from lightapi.filters import BaseFilter
from sqlalchemy import and_

class DynamicOperatorFilter(BaseFilter):
    """
    Filter that supports Django-style field lookups.
    
    Supports operators like:
    - field__eq=value (exact match)
    - field__ilike=value (case-insensitive partial match)
    - field__gte=value (greater than or equal)
    - field__lte=value (less than or equal)
    - field__in=value1,value2 (in list)
    """
    
    def filter_queryset(self, queryset, request):
        params = request.query_params
        entity = queryset.column_descriptions[0]['entity']
        filters = []
        
        for param, value in params.items():
            # Skip pagination and sorting parameters
            if param in ['page', 'limit', 'sort', 'sort_by', 'sort_order']:
                continue
            
            if '__' in param:
                field_name, operator = param.split('__', 1)
            else:
                field_name, operator = param, 'eq'
            
            # Check if field exists on model
            if not hasattr(entity, field_name):
                continue
            
            field = getattr(entity, field_name)
            filter_condition = self._apply_operator(field, operator, value)
            
            if filter_condition is not None:
                filters.append(filter_condition)
        
        if filters:
            queryset = queryset.filter(and_(*filters))
        
        return queryset
    
    def _apply_operator(self, field, operator, value):
        """Apply the specified operator to the field and value."""
        try:
            if operator == 'eq':
                return field == value
            elif operator == 'ilike':
                return field.ilike(f'%{value}%')
            elif operator == 'like':
                return field.like(f'%{value}%')
            elif operator == 'gte':
                return field >= self._convert_value(value)
            elif operator == 'lte':
                return field <= self._convert_value(value)
            elif operator == 'gt':
                return field > self._convert_value(value)
            elif operator == 'lt':
                return field < self._convert_value(value)
            elif operator == 'in':
                values = [v.strip() for v in value.split(',')]
                return field.in_(values)
            elif operator == 'notin':
                values = [v.strip() for v in value.split(',')]
                return ~field.in_(values)
            elif operator == 'isnull':
                is_null = value.lower() in ['true', '1', 'yes']
                return field.is_(None) if is_null else field.isnot(None)
            else:
                return None
        except (ValueError, TypeError):
            return None
    
    def _convert_value(self, value):
        """Convert string value to appropriate type."""
        # Try integer
        if value.isdigit():
            return int(value)
        
        # Try float
        try:
            return float(value)
        except ValueError:
            pass
        
        # Try boolean
        if value.lower() in ['true', 'false']:
            return value.lower() == 'true'
        
        # Return as string
        return value
```

### Faceted Search Filter

```python
from lightapi.filters import BaseFilter
from sqlalchemy import func

class FacetedSearchFilter(BaseFilter):
    """
    Filter that also provides facet counts for building search UIs.
    """
    
    def filter_queryset(self, queryset, request):
        # Apply standard filtering
        params = request.query_params
        entity = queryset.column_descriptions[0]['entity']
        
        # Store original query for facet calculations
        self.base_queryset = queryset
        
        # Apply filters
        category = params.get('category')
        if category:
            queryset = queryset.filter(entity.category == category)
        
        min_price = params.get('min_price')
        if min_price:
            try:
                queryset = queryset.filter(entity.price >= float(min_price))
            except (ValueError, TypeError):
                pass
        
        max_price = params.get('max_price')
        if max_price:
            try:
                queryset = queryset.filter(entity.price <= float(max_price))
            except (ValueError, TypeError):
                pass
        
        # Store filtered query for facet calculations
        self.filtered_queryset = queryset
        
        return queryset
    
    def get_facets(self, session):
        """
        Calculate facet counts based on current filters.
        
        Returns:
            dict: Facet data with counts
        """
        if not hasattr(self, 'base_queryset'):
            return {}
        
        entity = self.base_queryset.column_descriptions[0]['entity']
        
        # Category facets
        category_facets = self.base_queryset.with_entities(
            entity.category,
            func.count(entity.id).label('count')
        ).group_by(entity.category).all()
        
        # Price range facets
        price_ranges = [
            ('0-50', self.base_queryset.filter(entity.price <= 50).count()),
            ('50-100', self.base_queryset.filter(
                and_(entity.price > 50, entity.price <= 100)
            ).count()),
            ('100-500', self.base_queryset.filter(
                and_(entity.price > 100, entity.price <= 500)
            ).count()),
            ('500+', self.base_queryset.filter(entity.price > 500).count())
        ]
        
        return {
            'categories': [
                {'value': cat, 'count': count} 
                for cat, count in category_facets
            ],
            'price_ranges': [
                {'range': range_name, 'count': count}
                for range_name, count in price_ranges
            ]
        }
```

## Filter Integration

### With REST Endpoints

```python
@register_model_class
class Product(RestEndpoint):
    __tablename__ = 'products'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    category = Column(String(50))
    price = Column(Float)
    
    class Configuration:
        filter_class = DynamicOperatorFilter
        
    def get(self, request):
        # Filter is automatically applied in parent class
        result = super().get(request)
        
        # Add facets if requested
        if request.query_params.get('include_facets') == 'true':
            facets = self.filter.get_facets(self.session)
            if isinstance(result, tuple):
                data, status = result
                data['facets'] = facets
                return data, status
            else:
                result['facets'] = facets
        
        return result
```

### With Pagination

```python
@register_model_class
class Product(RestEndpoint):
    class Configuration:
        filter_class = AdvancedParameterFilter
        pagination_class = CustomPaginator
        
    def get(self, request):
        query = self.session.query(self.__class__)
        
        # Apply filtering first
        if hasattr(self, 'filter'):
            query = self.filter.filter_queryset(query, request)
        
        # Then apply pagination
        if hasattr(self, 'paginator'):
            self.paginator.request = request
            page = self.paginator.paginate(query)
            
            return {
                'results': [item.as_dict() for item in page.items],
                'pagination': {
                    'page': page.page,
                    'limit': page.limit,
                    'total': page.total,
                    'pages': page.pages
                }
            }, 200
        
        # No pagination
        results = query.all()
        return [item.as_dict() for item in results], 200
```

### With Caching

```python
from lightapi.cache import RedisCache

class CachedFilter(ParameterFilter):
    """Filter with caching support"""
    
    def __init__(self):
        self.cache = RedisCache()
    
    def filter_queryset(self, queryset, request):
        # Generate cache key from query parameters
        cache_key = self._generate_cache_key(request)
        
        # Try to get from cache
        cached_result = self.cache.get(cache_key)
        if cached_result:
            # Return cached query result
            return self._build_queryset_from_cache(queryset, cached_result)
        
        # Apply filtering
        filtered_query = super().filter_queryset(queryset, request)
        
        # Cache the filter parameters
        self.cache.set(cache_key, {
            'applied_filters': dict(request.query_params),
            'timestamp': time.time()
        }, timeout=300)  # 5 minutes
        
        return filtered_query
    
    def _generate_cache_key(self, request):
        """Generate cache key from request parameters"""
        key_parts = ['filter']
        
        # Sort query params for consistent cache keys
        if request.query_params:
            sorted_params = sorted(request.query_params.items())
            for key, value in sorted_params:
                if key not in ['page', 'limit']:  # Exclude pagination
                    key_parts.append(f"{key}:{value}")
        
        return ":".join(key_parts)
```

## Performance Optimization

### Database Indexes

```sql
-- Add indexes for commonly filtered fields
CREATE INDEX idx_products_category ON products(category);
CREATE INDEX idx_products_price ON products(price);
CREATE INDEX idx_products_active ON products(active);
CREATE INDEX idx_products_created_at ON products(created_at);

-- Composite indexes for common filter combinations
CREATE INDEX idx_products_cat_active ON products(category, active);
CREATE INDEX idx_products_cat_price ON products(category, price);
CREATE INDEX idx_products_price_active ON products(price, active);
```

### Query Optimization

```python
class OptimizedFilter(BaseFilter):
    """Filter optimized for performance"""
    
    def filter_queryset(self, queryset, request):
        params = request.query_params
        entity = queryset.column_descriptions[0]['entity']
        
        # Build all filter conditions first
        conditions = []
        
        # Category filter
        if 'category' in params:
            conditions.append(entity.category == params['category'])
        
        # Price range filters
        if 'min_price' in params:
            try:
                min_price = float(params['min_price'])
                conditions.append(entity.price >= min_price)
            except (ValueError, TypeError):
                pass
        
        if 'max_price' in params:
            try:
                max_price = float(params['max_price'])
                conditions.append(entity.price <= max_price)
            except (ValueError, TypeError):
                pass
        
        # Active status filter
        if 'active' in params:
            active = params['active'].lower() in ['true', '1', 'yes']
            conditions.append(entity.active == active)
        
        # Apply all conditions at once for better query planning
        if conditions:
            queryset = queryset.filter(and_(*conditions))
        
        return queryset
```

### Memory Optimization

```python
class MemoryEfficientFilter(BaseFilter):
    """Filter that minimizes memory usage"""
    
    def filter_queryset(self, queryset, request):
        # Only load specific columns if filtering
        params = request.query_params
        
        if params:
            # Use query.options(load_only()) for large datasets
            # Or implement cursor-based pagination for very large results
            pass
        
        return super().filter_queryset(queryset, request)
```

## Error Handling

### Validation and Error Responses

```python
class ValidatedFilter(BaseFilter):
    """Filter with comprehensive validation"""
    
    def filter_queryset(self, queryset, request):
        try:
            return self._apply_filters(queryset, request)
        except ValueError as e:
            # Re-raise as a structured error
            raise ValueError({
                'error': 'Invalid filter parameters',
                'details': str(e),
                'valid_filters': self._get_valid_filters(queryset)
            })
    
    def _apply_filters(self, queryset, request):
        params = request.query_params
        entity = queryset.column_descriptions[0]['entity']
        
        # Validate each parameter
        for param, value in params.items():
            if param.startswith('min_') or param.startswith('max_'):
                self._validate_numeric_param(param, value)
            elif param == 'category':
                self._validate_category_param(value)
            elif param == 'search':
                self._validate_search_param(value)
        
        # Apply validated filters
        return super().filter_queryset(queryset, request)
    
    def _validate_numeric_param(self, param, value):
        """Validate numeric parameters"""
        try:
            num_value = float(value)
            if num_value < 0:
                raise ValueError(f"{param} must be non-negative")
        except (ValueError, TypeError):
            raise ValueError(f"{param} must be a valid number")
    
    def _validate_category_param(self, value):
        """Validate category parameters"""
        valid_categories = ['electronics', 'clothing', 'books', 'home']
        if value not in valid_categories:
            raise ValueError(f"Category must be one of: {', '.join(valid_categories)}")
    
    def _validate_search_param(self, value):
        """Validate search parameters"""
        if len(value) < 2:
            raise ValueError("Search term must be at least 2 characters")
        if len(value) > 100:
            raise ValueError("Search term cannot exceed 100 characters")
    
    def _get_valid_filters(self, queryset):
        """Return list of valid filter parameters"""
        entity = queryset.column_descriptions[0]['entity']
        return [column.name for column in entity.__table__.columns]
```

## Testing Filters

### Unit Tests

```python
import pytest
from your_app import AdvancedParameterFilter

def test_parameter_filter():
    filter_instance = AdvancedParameterFilter()
    
    # Mock request and queryset
    class MockRequest:
        def __init__(self, params):
            self.query_params = params
    
    class MockEntity:
        def __init__(self):
            self.price = MockColumn()
            self.category = MockColumn()
    
    class MockColumn:
        def __eq__(self, other):
            return f"= {other}"
        
        def __ge__(self, other):
            return f">= {other}"
        
        def ilike(self, pattern):
            return f"ILIKE {pattern}"
    
    # Test price filtering
    request = MockRequest({'min_price': '100', 'max_price': '500'})
    # Test filter application...
```

### Integration Tests

```python
def test_filter_integration(client):
    # Create test data
    create_test_products()
    
    # Test category filtering
    response = client.get('/products?category=electronics')
    assert response.status_code == 200
    data = response.json()
    assert all(item['category'] == 'electronics' for item in data)
    
    # Test price range filtering
    response = client.get('/products?min_price=100&max_price=500')
    assert response.status_code == 200
    data = response.json()
    assert all(100 <= item['price'] <= 500 for item in data)
    
    # Test search filtering
    response = client.get('/products?search=laptop')
    assert response.status_code == 200
    data = response.json()
    assert all('laptop' in item['name'].lower() for item in data)
```

## Best Practices

### Security

1. **Validate Input**: Always validate filter parameters
2. **Sanitize Values**: Prevent SQL injection through parameter binding
3. **Limit Scope**: Only allow filtering on intended fields
4. **Rate Limiting**: Prevent abuse through expensive filter queries

### Performance

1. **Database Indexes**: Create indexes for filtered columns
2. **Query Optimization**: Combine filters efficiently
3. **Caching**: Cache filter results when appropriate
4. **Pagination**: Always use pagination with filters

### User Experience

1. **Clear Documentation**: Document available filters and formats
2. **Error Messages**: Provide helpful validation error messages
3. **Consistent Format**: Use consistent parameter naming conventions
4. **Default Values**: Provide sensible defaults for optional filters

## Next Steps

- **[Pagination API Reference](pagination.md)** - Pagination system details
- **[REST API Reference](rest.md)** - Complete REST API documentation
- **[Examples](../examples/filtering-pagination.md)** - Practical filtering examples 