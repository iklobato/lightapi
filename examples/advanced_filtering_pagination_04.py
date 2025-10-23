#!/usr/bin/env python3
"""
LightAPI Advanced Filtering and Pagination Example

This example demonstrates advanced filtering, pagination, and sorting capabilities.
It shows how to implement complex queries, search functionality, and efficient data retrieval.

Features demonstrated:
- Advanced filtering (multiple fields, ranges, text search)
- Pagination with custom page sizes
- Sorting (ascending/descending, multiple fields)
- Search functionality
- Query parameter validation
- Performance considerations
"""

from lightapi import LightApi
from lightapi.rest import RestEndpoint
from lightapi.models import Base
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text
from datetime import datetime, timedelta
import random

class AdvancedProduct(Base, RestEndpoint):
    """Product model with advanced filtering capabilities"""
    __tablename__ = "advanced_products"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    price = Column(Float, nullable=False)
    category = Column(String(50), nullable=False)
    brand = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    rating = Column(Float, default=0.0)
    in_stock = Column(Boolean, default=True)
    stock_quantity = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)
    
    def get(self, request):
        """Advanced GET with filtering, pagination, and sorting"""
        try:
            # Get query parameters
            params = request.query_params
            
            # Pagination parameters
            page = int(params.get('page', 1))
            page_size = int(params.get('page_size', 10))
            
            # Validate pagination parameters
            if page < 1:
                return {"error": "Page must be >= 1"}, 400
            if page_size < 1:
                return {"error": "Page size must be >= 1"}, 400
            if page_size > 100:
                return {"error": "Page size cannot exceed 100"}, 400
            
            # Filtering parameters
            category = params.get('category')
            brand = params.get('brand')
            min_price = params.get('min_price')
            max_price = params.get('max_price')
            min_rating = params.get('min_rating')
            max_rating = params.get('max_rating')
            in_stock = params.get('in_stock')
            search = params.get('search')  # Text search in name and description
            
            # Sorting parameters
            sort_by = params.get('sort_by', 'id')  # Default sort by id
            sort_order = params.get('sort_order', 'asc')  # asc or desc
            
            # Validate sort parameters
            valid_sort_fields = ['id', 'name', 'price', 'category', 'brand', 'rating', 'created_at', 'updated_at']
            if sort_by not in valid_sort_fields:
                return {
                    "error": f"Invalid sort field. Valid options: {', '.join(valid_sort_fields)}"
                }, 400
            
            if sort_order not in ['asc', 'desc']:
                return {"error": "Sort order must be 'asc' or 'desc'"}, 400
            
            # Generate sample data (in real app, this would be database queries)
            all_products = self.generate_sample_products()
            
            # Apply filters
            filtered_products = self.apply_filters(all_products, {
                'category': category,
                'brand': brand,
                'min_price': min_price,
                'max_price': max_price,
                'min_rating': min_rating,
                'max_rating': max_rating,
                'in_stock': in_stock,
                'search': search
            })
            
            # Apply sorting
            sorted_products = self.apply_sorting(filtered_products, sort_by, sort_order)
            
            # Apply pagination
            total_count = len(sorted_products)
            start_index = (page - 1) * page_size
            end_index = start_index + page_size
            paginated_products = sorted_products[start_index:end_index]
            
            # Calculate pagination metadata
            total_pages = (total_count + page_size - 1) // page_size
            has_next = page < total_pages
            has_prev = page > 1
            
            return {
                "products": paginated_products,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_count": total_count,
                    "total_pages": total_pages,
                    "has_next": has_next,
                    "has_prev": has_prev,
                    "next_page": page + 1 if has_next else None,
                    "prev_page": page - 1 if has_prev else None
                },
                "filters_applied": {
                    "category": category,
                    "brand": brand,
                    "price_range": f"{min_price}-{max_price}" if min_price or max_price else None,
                    "rating_range": f"{min_rating}-{max_rating}" if min_rating or max_rating else None,
                    "in_stock": in_stock,
                    "search": search
                },
                "sorting": {
                    "sort_by": sort_by,
                    "sort_order": sort_order
                }
            }
            
        except ValueError as e:
            return {"error": f"Invalid parameter value: {str(e)}"}, 400
        except Exception as e:
            return {"error": f"Internal server error: {str(e)}"}, 500
    
    def generate_sample_products(self):
        """Generate sample products for demonstration"""
        categories = ['electronics', 'clothing', 'books', 'home', 'sports', 'toys']
        brands = ['Apple', 'Samsung', 'Nike', 'Adidas', 'Sony', 'Microsoft', 'Amazon', 'Google']
        
        products = []
        for i in range(1, 101):  # Generate 100 sample products
            product = {
                "id": i,
                "name": f"Product {i}",
                "price": round(random.uniform(10.0, 1000.0), 2),
                "category": random.choice(categories),
                "brand": random.choice(brands),
                "description": f"This is a detailed description for Product {i}. It has many features and benefits.",
                "rating": round(random.uniform(1.0, 5.0), 1),
                "in_stock": random.choice([True, False]),
                "stock_quantity": random.randint(0, 100),
                "created_at": (datetime.utcnow() - timedelta(days=random.randint(1, 365))).isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }
            products.append(product)
        
        return products
    
    def apply_filters(self, products, filters):
        """Apply filters to product list"""
        filtered = products.copy()
        
        # Category filter
        if filters['category']:
            filtered = [p for p in filtered if p['category'].lower() == filters['category'].lower()]
        
        # Brand filter
        if filters['brand']:
            filtered = [p for p in filtered if p['brand'].lower() == filters['brand'].lower()]
        
        # Price range filter
        if filters['min_price']:
            try:
                min_price = float(filters['min_price'])
                filtered = [p for p in filtered if p['price'] >= min_price]
            except ValueError:
                pass  # Ignore invalid values
        
        if filters['max_price']:
            try:
                max_price = float(filters['max_price'])
                filtered = [p for p in filtered if p['price'] <= max_price]
            except ValueError:
                pass
        
        # Rating range filter
        if filters['min_rating']:
            try:
                min_rating = float(filters['min_rating'])
                filtered = [p for p in filtered if p['rating'] >= min_rating]
            except ValueError:
                pass
        
        if filters['max_rating']:
            try:
                max_rating = float(filters['max_rating'])
                filtered = [p for p in filtered if p['rating'] <= max_rating]
            except ValueError:
                pass
        
        # Stock filter
        if filters['in_stock'] is not None:
            if filters['in_stock'].lower() in ['true', '1', 'yes']:
                filtered = [p for p in filtered if p['in_stock']]
            elif filters['in_stock'].lower() in ['false', '0', 'no']:
                filtered = [p for p in filtered if not p['in_stock']]
        
        # Text search filter
        if filters['search']:
            search_term = filters['search'].lower()
            filtered = [
                p for p in filtered 
                if search_term in p['name'].lower() or search_term in p['description'].lower()
            ]
        
        return filtered
    
    def apply_sorting(self, products, sort_by, sort_order):
        """Apply sorting to product list"""
        reverse = sort_order == 'desc'
        
        try:
            if sort_by in ['price', 'rating']:
                # Numeric sorting
                return sorted(products, key=lambda x: x[sort_by], reverse=reverse)
            elif sort_by in ['created_at', 'updated_at']:
                # Date sorting
                return sorted(products, key=lambda x: x[sort_by], reverse=reverse)
            else:
                # String sorting
                return sorted(products, key=lambda x: str(x[sort_by]).lower(), reverse=reverse)
        except KeyError:
            # If sort field doesn't exist, return unsorted
            return products

class SearchableArticle(Base, RestEndpoint):
    """Article model with advanced search capabilities"""
    __tablename__ = "searchable_articles"
    
    id = Column(Integer, primary_key=True)
    title = Column(String(300), nullable=False)
    content = Column(Text, nullable=False)
    author = Column(String(100), nullable=False)
    tags = Column(String(500), nullable=True)  # Comma-separated tags
    published = Column(Boolean, default=False)
    views = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def get(self, request):
        """Advanced search with multiple criteria"""
        try:
            params = request.query_params
            
            # Pagination
            page = int(params.get('page', 1))
            page_size = int(params.get('page_size', 20))
            
            # Search parameters
            q = params.get('q')  # General search query
            title_search = params.get('title')
            author_search = params.get('author')
            tag_search = params.get('tag')
            published_only = params.get('published', 'false').lower() == 'true'
            min_views = params.get('min_views')
            
            # Date range
            date_from = params.get('date_from')
            date_to = params.get('date_to')
            
            # Sorting
            sort_by = params.get('sort_by', 'created_at')
            sort_order = params.get('sort_order', 'desc')
            
            # Generate sample articles
            articles = self.generate_sample_articles()
            
            # Apply search filters
            filtered_articles = self.apply_search_filters(articles, {
                'q': q,
                'title': title_search,
                'author': author_search,
                'tag': tag_search,
                'published_only': published_only,
                'min_views': min_views,
                'date_from': date_from,
                'date_to': date_to
            })
            
            # Apply sorting
            sorted_articles = self.apply_article_sorting(filtered_articles, sort_by, sort_order)
            
            # Apply pagination
            total_count = len(sorted_articles)
            start_index = (page - 1) * page_size
            end_index = start_index + page_size
            paginated_articles = sorted_articles[start_index:end_index]
            
            return {
                "articles": paginated_articles,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_count": total_count,
                    "total_pages": (total_count + page_size - 1) // page_size
                },
                "search_info": {
                    "query": q,
                    "filters_applied": {
                        "title_search": title_search,
                        "author_search": author_search,
                        "tag_search": tag_search,
                        "published_only": published_only,
                        "min_views": min_views,
                        "date_range": f"{date_from} to {date_to}" if date_from or date_to else None
                    },
                    "sorting": f"{sort_by} {sort_order}"
                }
            }
            
        except Exception as e:
            return {"error": f"Search error: {str(e)}"}, 500
    
    def generate_sample_articles(self):
        """Generate sample articles for search demonstration"""
        authors = ['John Doe', 'Jane Smith', 'Bob Johnson', 'Alice Brown', 'Charlie Wilson']
        tags_list = [
            'python,programming,tutorial',
            'javascript,web,frontend',
            'database,sql,backend',
            'machine-learning,ai,data-science',
            'devops,docker,kubernetes',
            'mobile,react-native,flutter',
            'security,encryption,privacy'
        ]
        
        articles = []
        for i in range(1, 51):  # Generate 50 sample articles
            article = {
                "id": i,
                "title": f"Article {i}: Advanced Programming Techniques",
                "content": f"This is the content of article {i}. It contains detailed information about programming, development, and technology trends. The article covers various topics including best practices, code examples, and real-world applications.",
                "author": random.choice(authors),
                "tags": random.choice(tags_list),
                "published": random.choice([True, False]),
                "views": random.randint(0, 10000),
                "created_at": (datetime.utcnow() - timedelta(days=random.randint(1, 365))).isoformat()
            }
            articles.append(article)
        
        return articles
    
    def apply_search_filters(self, articles, filters):
        """Apply search filters to articles"""
        filtered = articles.copy()
        
        # General search query (searches in title and content)
        if filters['q']:
            query = filters['q'].lower()
            filtered = [
                a for a in filtered 
                if query in a['title'].lower() or query in a['content'].lower()
            ]
        
        # Title search
        if filters['title']:
            title_query = filters['title'].lower()
            filtered = [a for a in filtered if title_query in a['title'].lower()]
        
        # Author search
        if filters['author']:
            author_query = filters['author'].lower()
            filtered = [a for a in filtered if author_query in a['author'].lower()]
        
        # Tag search
        if filters['tag']:
            tag_query = filters['tag'].lower()
            filtered = [a for a in filtered if tag_query in a['tags'].lower()]
        
        # Published filter
        if filters['published_only']:
            filtered = [a for a in filtered if a['published']]
        
        # Minimum views filter
        if filters['min_views']:
            try:
                min_views = int(filters['min_views'])
                filtered = [a for a in filtered if a['views'] >= min_views]
            except ValueError:
                pass
        
        return filtered
    
    def apply_article_sorting(self, articles, sort_by, sort_order):
        """Apply sorting to articles"""
        reverse = sort_order == 'desc'
        
        valid_fields = ['id', 'title', 'author', 'views', 'created_at']
        if sort_by not in valid_fields:
            sort_by = 'created_at'
        
        if sort_by == 'views':
            return sorted(articles, key=lambda x: x['views'], reverse=reverse)
        elif sort_by == 'created_at':
            return sorted(articles, key=lambda x: x['created_at'], reverse=reverse)
        else:
            return sorted(articles, key=lambda x: str(x[sort_by]).lower(), reverse=reverse)

def create_app():
    """Create the advanced filtering demo app"""
    app = LightApi(
        database_url="sqlite:///./advanced_filtering.db",
        swagger_title="Advanced Filtering & Pagination Demo",
        swagger_version="1.0.0",
        swagger_description="Demonstration of advanced filtering, pagination, and search in LightAPI",
    )
    
    app.register(AdvancedProduct)
    app.register(SearchableArticle)
    
    return app

if __name__ == "__main__":
    app = create_app()
    
    print("🔍 Advanced Filtering & Pagination Demo Server")
    print("=" * 60)
    print("Server running at http://localhost:8000")
    print("API documentation at http://localhost:8000/docs")
    print()
    print("Example queries:")
    print()
    print("📦 Product filtering examples:")
    print("  Basic pagination:")
    print("    GET /advanced_products?page=1&page_size=5")
    print()
    print("  Filter by category:")
    print("    GET /advanced_products?category=electronics")
    print()
    print("  Price range filter:")
    print("    GET /advanced_products?min_price=100&max_price=500")
    print()
    print("  Multiple filters with sorting:")
    print("    GET /advanced_products?category=electronics&min_price=200&sort_by=price&sort_order=desc")
    print()
    print("  Text search:")
    print("    GET /advanced_products?search=laptop")
    print()
    print("  Complex query:")
    print("    GET /advanced_products?category=electronics&brand=apple&min_rating=4.0&in_stock=true&sort_by=rating&sort_order=desc&page=1&page_size=10")
    print()
    print("📰 Article search examples:")
    print("  General search:")
    print("    GET /searchable_articles?q=programming")
    print()
    print("  Author search:")
    print("    GET /searchable_articles?author=john")
    print()
    print("  Tag search:")
    print("    GET /searchable_articles?tag=python")
    print()
    print("  Published articles only:")
    print("    GET /searchable_articles?published=true")
    print()
    print("  Popular articles (min views):")
    print("    GET /searchable_articles?min_views=1000&sort_by=views&sort_order=desc")
    
    app.run(host="localhost", port=8000, debug=True)