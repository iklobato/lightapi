> **Note:** This page describes the v1 API and has not yet been updated for v2. See the [README](../../README.md) for current documentation.

> **Note:** This page describes the v1 API and has not yet been updated for v2. The v2 API is described in the [README](../../README.md).

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

class Product(Base, RestEndpoint):
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
                entity.name.ilike(f'