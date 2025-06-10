# Filtering and Pagination Example

This example demonstrates advanced filtering and pagination in LightAPI for efficient data retrieval with large datasets.

## Overview

Learn how to implement:
- Custom parameter-based filtering
- Configurable pagination with metadata
- Sorting functionality
- Price range and text search filters
- Database query optimization

## Complete Example Code

```python
from sqlalchemy import Column, Integer, String, Float, create_engine
from sqlalchemy.orm import sessionmaker
from lightapi.core import LightApi
from lightapi.rest import RestEndpoint
from lightapi.filters import ParameterFilter
from lightapi.pagination import Paginator
from lightapi.models import Base, register_model_class

# Custom filter implementation
class ProductFilter(ParameterFilter):
    def filter_queryset(self, queryset, request):
        # Apply base filtering from parent class
        queryset = super().filter_queryset(queryset, request)
        
        # Get query parameters
        params = request.query_params
        
        # Filter by price range (stored as cents)
        min_price = params.get('min_price')
        if min_price and min_price.isdigit():
            queryset = queryset.filter(Product.price >= float(min_price) * 100)
            
        max_price = params.get('max_price')
        if max_price and max_price.isdigit():
            queryset = queryset.filter(Product.price <= float(max_price) * 100)
        
        # Filter by exact category match
        category = params.get('category')
        if category:
            queryset = queryset.filter(Product.category == category)
        
        # Search by name (case-insensitive partial match)
        search = params.get('search')
        if search:
            queryset = queryset.filter(Product.name.ilike(f'%{search}%'))
            
        return queryset

# Custom paginator with sorting
class ProductPaginator(Paginator):
    limit = 10                    # Default page size
    max_limit = 100              # Maximum items per page
    sort = True                  # Enable sorting
    default_sort_field = 'name'  # Default sort field
    valid_sort_fields = ['name', 'price', 'category']
    
    def paginate(self, queryset):
        # Get pagination parameters
        limit = self.limit
        page = 1
        
        if hasattr(self, 'request'):
            params = getattr(self.request, 'query_params', {})
            
            # Handle limit parameter with validation
            limit_param = params.get('limit')
            if limit_param and limit_param.isdigit():
                limit = min(int(limit_param), self.max_limit)
            
            # Handle page parameter
            page_param = params.get('page')
            if page_param and page_param.isdigit():
                page = int(page_param)
            
            # Apply sorting if enabled
            if self.sort:
                sort_param = params.get('sort', '')
                if sort_param:
                    # Handle descending sort (prefixed with '-')
                    descending = sort_param.startswith('-')
                    sort_field = sort_param[1:] if descending else sort_param
                    
                    # Validate and apply sort
                    if sort_field in self.valid_sort_fields:
                        column = getattr(queryset.column_descriptions[0]['type'], sort_field)
                        queryset = queryset.order_by(column.desc() if descending else column.asc())
        
        # Calculate pagination
        offset = (page - 1) * limit
        total = queryset.count()
        items = queryset.offset(offset).limit(limit).all()
        
        # Return page object with metadata
        class Page:
            def __init__(self, items, page, limit, total):
                self.items = items
                self.page = page
                self.limit = limit
                self.total = total
                self.pages = (total + limit - 1) // limit
                self.next_page = page + 1 if page < self.pages else None
                self.prev_page = page - 1 if page > 1 else None
                
        return Page(items, page, limit, total)

# Product model with integrated filtering and pagination
@register_model_class
class Product(RestEndpoint):
    __tablename__ = 'pagination_products'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    price = Column(Integer)  # Stored as cents for precision
    category = Column(String(50))
    description = Column(String(500))
    
    class Configuration:
        filter_class = ProductFilter
        pagination_class = ProductPaginator
    
    def get(self, request):
        # Provide request to paginator
        if hasattr(self, 'paginator'):
            self.paginator.request = request
            
        query = self.session.query(self.__class__)
        
        # Apply filtering
        if hasattr(self, 'filter'):
            query = self.filter.filter_queryset(query, request)
        
        # Apply pagination
        if hasattr(self, 'paginator'):
            page = self.paginator.paginate(query)
            results = page.items
            
            # Response with pagination metadata
            response = {
                "count": page.total,
                "next": page.next_page,
                "previous": page.prev_page,
                "page": page.page,
                "pages": page.pages,
                "results": []
            }
        else:
            results = query.all()
            response = {"results": []}
        
        # Format results (convert cents to dollars)
        for obj in results:
            response["results"].append({
                "id": obj.id,
                "name": obj.name,
                "price": obj.price / 100,  # Convert to dollars
                "category": obj.category,
                "description": obj.description
            })
        
        return response, 200
```

## Key Components

### 1. Custom Product Filter

The `ProductFilter` extends `ParameterFilter` for specialized filtering:

- **Price Range**: Filters by `min_price` and `max_price` (converts dollars to cents)
- **Category Filter**: Exact match filtering by product category  
- **Text Search**: Case-insensitive partial name matching using `ilike`
- **Parameter Validation**: Validates numeric parameters

### 2. Custom Paginator with Sorting

The `ProductPaginator` provides configurable pagination and sorting:

- **Configurable Limits**: Default 10 items, max 100 per page
- **Sorting Support**: Sort by name, price, or category
- **Descending Sort**: Use `-` prefix (e.g., `-price`)
- **Pagination Metadata**: Total count, page numbers, navigation info

### 3. Integrated Product Model

The Product model combines filtering and pagination seamlessly:

- **Price Storage**: Prices stored as cents (integers) for precision
- **Data Transformation**: Converts internal format to user-friendly format
- **Rich Response**: Includes pagination metadata and formatted results

## Usage Examples

### Basic Pagination

```bash
# Get first page (default 10 items)
curl http://localhost:8000/products

# Get second page with 5 items per page
curl "http://localhost:8000/products?page=2&limit=5"

# Large page size (capped at 100)
curl "http://localhost:8000/products?limit=150"
```

### Filtering

```bash
# Filter by category
curl "http://localhost:8000/products?category=Electronics"

# Price range filtering (in dollars)
curl "http://localhost:8000/products?min_price=50&max_price=100"

# Search by product name
curl "http://localhost:8000/products?search=phone"

# Combine multiple filters
curl "http://localhost:8000/products?category=Electronics&min_price=100"
```

### Sorting

```bash
# Sort by name (ascending)
curl "http://localhost:8000/products?sort=name"

# Sort by price (descending)
curl "http://localhost:8000/products?sort=-price"

# Sort by category
curl "http://localhost:8000/products?sort=category"
```

### Complex Queries

```bash
# Electronics under $100, sorted by price, page 2
curl "http://localhost:8000/products?category=Electronics&max_price=100&sort=price&page=2&limit=5"

# Search with sorting and pagination
curl "http://localhost:8000/products?search=laptop&sort=-price&page=1&limit=3"
```

## Response Format

### Paginated Response

```json
{
  "count": 20,
  "next": 2,
  "previous": null,
  "page": 1,
  "pages": 2,
  "results": [
    {
      "id": 1,
      "name": "Laptop",
      "price": 1250.0,
      "category": "Electronics",
      "description": "High-performance laptop"
    },
    {
      "id": 2,
      "name": "Smartphone", 
      "price": 850.0,
      "category": "Electronics",
      "description": "Latest smartphone model"
    }
  ]
}
```

### Filtered Results

```json
{
  "count": 3,
  "next": null,
  "previous": null,
  "page": 1,
  "pages": 1,
  "results": [
    {
      "id": 2,
      "name": "Smartphone",
      "price": 850.0,
      "category": "Electronics",
      "description": "Latest smartphone model"
    }
  ]
}
```

## Performance Optimization

### Database Indexes

Add indexes for frequently filtered/sorted columns:

```sql
CREATE INDEX idx_products_category ON pagination_products(category);
CREATE INDEX idx_products_price ON pagination_products(price);
CREATE INDEX idx_products_name ON pagination_products(name);

-- Composite index for common combinations
CREATE INDEX idx_products_cat_price ON pagination_products(category, price);
```

### Query Optimization

```python
def filter_queryset(self, queryset, request):
    params = request.query_params
    filters = []
    
    # Build filter conditions
    if 'category' in params:
        filters.append(Product.category == params['category'])
    
    if 'min_price' in params and params['min_price'].isdigit():
        filters.append(Product.price >= float(params['min_price']) * 100)
    
    # Apply all filters at once for efficiency
    if filters:
        queryset = queryset.filter(and_(*filters))
    
    return queryset
```

## Advanced Patterns

### Dynamic Filtering with Operators

```python
class DynamicProductFilter(ParameterFilter):
    def filter_queryset(self, queryset, request):
        params = request.query_params
        
        for param, value in params.items():
            if '__' in param:
                field_name, operator = param.split('__', 1)
                if hasattr(Product, field_name):
                    field = getattr(Product, field_name)
                    queryset = self._apply_operator(queryset, field, operator, value)
        
        return queryset
    
    def _apply_operator(self, queryset, field, operator, value):
        if operator == 'gte':
            return queryset.filter(field >= value)
        elif operator == 'lte':
            return queryset.filter(field <= value)
        elif operator == 'icontains':
            return queryset.filter(field.ilike(f'%{value}%'))
        return queryset
```

**Usage:**
```bash
curl "http://localhost:8000/products?price__gte=5000&name__icontains=laptop"
```

### Faceted Search

```python
def get_facets(self, request):
    """Return facet counts for UI filters"""
    base_query = self.session.query(Product)
    
    # Category facets
    categories = base_query.with_entities(
        Product.category,
        func.count(Product.id).label('count')
    ).group_by(Product.category).all()
    
    return {
        'categories': [{'name': cat, 'count': count} for cat, count in categories]
    }
```

## Running the Example

```bash
# Run the example server
python examples/filtering_pagination_example.py

# View API documentation
open http://localhost:8000/docs

# Test the endpoints
curl http://localhost:8000/products
curl "http://localhost:8000/products?category=Electronics&sort=-price"
```

## Next Steps

- **[Validation Example](validation.md)** - Request validation patterns
- **[Middleware Example](middleware.md)** - Custom middleware development  
- **[API Reference](../api-reference/filters.md)** - Filtering API details
- **[API Reference](../api-reference/pagination.md)** - Pagination API details 