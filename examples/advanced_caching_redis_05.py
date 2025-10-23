#!/usr/bin/env python3
"""
LightAPI Advanced Redis Caching Example

This example demonstrates advanced Redis caching capabilities in LightAPI.
It shows cache strategies, TTL management, cache invalidation, and performance optimization.

Features demonstrated:
- Redis caching with TTL (Time To Live)
- Cache invalidation strategies
- Cache key management
- Performance monitoring
- Cache hit/miss statistics
- Complex data caching (JSON serialization)
"""

import json
import time
from datetime import datetime, timedelta
from lightapi import LightApi
from lightapi.rest import RestEndpoint
from lightapi.models import Base
from lightapi.cache import cache_manager
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Boolean

class CachedProduct(Base, RestEndpoint):
    """Product model with advanced caching strategies"""
    __tablename__ = "cached_products"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    price = Column(Float, nullable=False)
    category = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    last_updated = Column(DateTime, default=datetime.utcnow)
    
    def get(self, request):
        """GET with intelligent caching"""
        product_id = request.path_params.get('id')
        
        if product_id:
            return self.get_single_product(int(product_id))
        else:
            return self.get_product_list(request.query_params)
    
    def get_single_product(self, product_id):
        """Get single product with caching"""
        cache_key = f"product:{product_id}"
        
        # Try to get from cache first
        cached_product = cache_manager.get(cache_key)
        if cached_product:
            return {
                **cached_product,
                "cache_info": {
                    "cache_hit": True,
                    "cached_at": cached_product.get("cached_at"),
                    "ttl_remaining": cache_manager.ttl(cache_key)
                }
            }
        
        # Simulate database query (expensive operation)
        time.sleep(0.1)  # Simulate DB query time
        
        # Generate product data
        product = {
            "id": product_id,
            "name": f"Product {product_id}",
            "price": 99.99 + (product_id * 10),
            "category": "electronics",
            "description": f"This is a detailed description for product {product_id}",
            "last_updated": datetime.utcnow().isoformat(),
            "cached_at": datetime.utcnow().isoformat()
        }
        
        # Cache the product for 5 minutes
        cache_manager.set(cache_key, product, ttl=300)
        
        return {
            **product,
            "cache_info": {
                "cache_hit": False,
                "cached_at": product["cached_at"],
                "ttl": 300
            }
        }
    
    def get_product_list(self, query_params):
        """Get product list with query-based caching"""
        # Create cache key based on query parameters
        page = query_params.get('page', '1')
        page_size = query_params.get('page_size', '10')
        category = query_params.get('category', '')
        
        cache_key = f"products:page:{page}:size:{page_size}:cat:{category}"
        
        # Try cache first
        cached_list = cache_manager.get(cache_key)
        if cached_list:
            return {
                **cached_list,
                "cache_info": {
                    "cache_hit": True,
                    "cache_key": cache_key,
                    "ttl_remaining": cache_manager.ttl(cache_key)
                }
            }
        
        # Simulate expensive database query
        time.sleep(0.2)  # Simulate complex query time
        
        # Generate product list
        products = []
        start_id = (int(page) - 1) * int(page_size) + 1
        for i in range(start_id, start_id + int(page_size)):
            products.append({
                "id": i,
                "name": f"Product {i}",
                "price": 99.99 + (i * 10),
                "category": category or "electronics",
                "last_updated": datetime.utcnow().isoformat()
            })
        
        result = {
            "products": products,
            "pagination": {
                "page": int(page),
                "page_size": int(page_size),
                "total_count": 1000  # Simulated total
            },
            "cached_at": datetime.utcnow().isoformat()
        }
        
        # Cache for 2 minutes (shorter TTL for lists)
        cache_manager.set(cache_key, result, ttl=120)
        
        return {
            **result,
            "cache_info": {
                "cache_hit": False,
                "cache_key": cache_key,
                "ttl": 120
            }
        }
    
    def post(self, request):
        """Create product and invalidate related caches"""
        try:
            data = request.data
            
            # Simulate product creation
            new_product = {
                "id": 999,  # Simulated new ID
                "name": data.get('name'),
                "price": data.get('price'),
                "category": data.get('category'),
                "description": data.get('description'),
                "last_updated": datetime.utcnow().isoformat()
            }
            
            # Cache the new product
            cache_key = f"product:{new_product['id']}"
            cache_manager.set(cache_key, new_product, ttl=300)
            
            # Invalidate list caches (since we added a new product)
            self.invalidate_list_caches()
            
            return {
                **new_product,
                "message": "Product created and cached",
                "cache_operations": {
                    "cached_product": cache_key,
                    "invalidated_lists": "All product list caches cleared"
                }
            }, 201
            
        except Exception as e:
            return {"error": str(e)}, 500
    
    def put(self, request):
        """Update product and manage cache"""
        try:
            product_id = int(request.path_params.get('id'))
            data = request.data
            
            # Update product data
            updated_product = {
                "id": product_id,
                "name": data.get('name', f'Product {product_id}'),
                "price": data.get('price', 99.99),
                "category": data.get('category', 'electronics'),
                "description": data.get('description', ''),
                "last_updated": datetime.utcnow().isoformat()
            }
            
            # Update cache
            cache_key = f"product:{product_id}"
            cache_manager.set(cache_key, updated_product, ttl=300)
            
            # Invalidate related list caches
            self.invalidate_list_caches()
            
            return {
                **updated_product,
                "message": "Product updated and cache refreshed",
                "cache_operations": {
                    "updated_cache": cache_key,
                    "invalidated_lists": "Related list caches cleared"
                }
            }
            
        except Exception as e:
            return {"error": str(e)}, 500
    
    def delete(self, request):
        """Delete product and remove from cache"""
        try:
            product_id = int(request.path_params.get('id'))
            
            # Remove from cache
            cache_key = f"product:{product_id}"
            cache_deleted = cache_manager.delete(cache_key)
            
            # Invalidate list caches
            self.invalidate_list_caches()
            
            return {
                "message": f"Product {product_id} deleted",
                "cache_operations": {
                    "deleted_from_cache": cache_deleted,
                    "cache_key": cache_key,
                    "invalidated_lists": "All product list caches cleared"
                }
            }
            
        except Exception as e:
            return {"error": str(e)}, 500
    
    def invalidate_list_caches(self):
        """Invalidate all product list caches"""
        # In a real application, you might use cache tags or patterns
        # For this demo, we'll use a simple pattern-based deletion
        pattern = "products:*"
        deleted_count = cache_manager.delete_pattern(pattern)
        return deleted_count

class CacheStats(Base, RestEndpoint):
    """Endpoint for cache statistics and management"""
    __tablename__ = "cache_stats"
    
    id = Column(Integer, primary_key=True)
    
    def get(self, request):
        """Get cache statistics"""
        try:
            # Get cache info
            cache_info = cache_manager.get_info()
            
            # Get specific cache keys
            product_keys = cache_manager.get_keys("product:*")
            list_keys = cache_manager.get_keys("products:*")
            
            # Calculate cache sizes
            total_keys = len(product_keys) + len(list_keys)
            
            return {
                "cache_statistics": {
                    "redis_info": cache_info,
                    "key_counts": {
                        "product_keys": len(product_keys),
                        "list_keys": len(list_keys),
                        "total_keys": total_keys
                    },
                    "sample_keys": {
                        "product_keys": product_keys[:5],  # First 5
                        "list_keys": list_keys[:5]
                    }
                },
                "cache_operations": {
                    "available_operations": [
                        "GET /cache_stats - View cache statistics",
                        "POST /cache_stats - Clear all caches",
                        "DELETE /cache_stats/{pattern} - Clear caches by pattern"
                    ]
                }
            }
            
        except Exception as e:
            return {"error": f"Cache stats error: {str(e)}"}, 500
    
    def post(self, request):
        """Clear all caches"""
        try:
            # Clear all caches
            cleared_count = cache_manager.clear_all()
            
            return {
                "message": "All caches cleared",
                "cleared_keys": cleared_count,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {"error": f"Cache clear error: {str(e)}"}, 500
    
    def delete(self, request):
        """Clear caches by pattern"""
        try:
            pattern = request.path_params.get('id', '*')  # Using 'id' as pattern
            
            cleared_count = cache_manager.delete_pattern(pattern)
            
            return {
                "message": f"Caches cleared for pattern: {pattern}",
                "cleared_keys": cleared_count,
                "pattern": pattern,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {"error": f"Pattern delete error: {str(e)}"}, 500

class CacheDemo(Base, RestEndpoint):
    """Demo endpoint for cache performance testing"""
    __tablename__ = "cache_demo"
    
    id = Column(Integer, primary_key=True)
    
    def get(self, request):
        """Cache performance demonstration"""
        demo_type = request.path_params.get('id', 'basic')
        
        if demo_type == 'performance':
            return self.performance_demo()
        elif demo_type == 'ttl':
            return self.ttl_demo()
        elif demo_type == 'complex':
            return self.complex_data_demo()
        else:
            return self.basic_demo()
    
    def basic_demo(self):
        """Basic cache demonstration"""
        cache_key = "demo:basic"
        
        # Check cache
        cached_data = cache_manager.get(cache_key)
        if cached_data:
            return {
                "message": "Data retrieved from cache",
                "data": cached_data,
                "cache_hit": True,
                "ttl_remaining": cache_manager.ttl(cache_key)
            }
        
        # Generate expensive data
        time.sleep(0.5)  # Simulate expensive operation
        data = {
            "generated_at": datetime.utcnow().isoformat(),
            "expensive_calculation": sum(range(1000000)),
            "random_data": [i * 2 for i in range(100)]
        }
        
        # Cache for 30 seconds
        cache_manager.set(cache_key, data, ttl=30)
        
        return {
            "message": "Data generated and cached",
            "data": data,
            "cache_hit": False,
            "ttl": 30
        }
    
    def performance_demo(self):
        """Performance comparison demo"""
        results = []
        
        # Test without cache
        start_time = time.time()
        for i in range(5):
            time.sleep(0.1)  # Simulate DB query
        no_cache_time = time.time() - start_time
        
        # Test with cache
        cache_key = "demo:performance"
        start_time = time.time()
        
        for i in range(5):
            cached = cache_manager.get(f"{cache_key}:{i}")
            if not cached:
                time.sleep(0.1)  # Simulate DB query
                data = {"query_result": f"Result {i}"}
                cache_manager.set(f"{cache_key}:{i}", data, ttl=60)
        
        cache_time = time.time() - start_time
        
        return {
            "performance_comparison": {
                "without_cache": f"{no_cache_time:.3f} seconds",
                "with_cache": f"{cache_time:.3f} seconds",
                "improvement": f"{(no_cache_time / cache_time):.1f}x faster" if cache_time > 0 else "N/A"
            },
            "note": "Run this endpoint multiple times to see cache benefits"
        }
    
    def ttl_demo(self):
        """TTL (Time To Live) demonstration"""
        cache_key = "demo:ttl"
        
        # Set data with short TTL
        data = {
            "message": "This data will expire in 10 seconds",
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(seconds=10)).isoformat()
        }
        
        cache_manager.set(cache_key, data, ttl=10)
        
        return {
            "ttl_demo": data,
            "ttl_remaining": cache_manager.ttl(cache_key),
            "instructions": "Call this endpoint again within 10 seconds to see cached data, after 10 seconds it will be regenerated"
        }
    
    def complex_data_demo(self):
        """Complex data structure caching demo"""
        cache_key = "demo:complex"
        
        cached = cache_manager.get(cache_key)
        if cached:
            return {
                "message": "Complex data from cache",
                "data": cached,
                "cache_hit": True
            }
        
        # Generate complex nested data
        complex_data = {
            "user_profiles": [
                {
                    "id": i,
                    "name": f"User {i}",
                    "preferences": {
                        "theme": "dark" if i % 2 else "light",
                        "notifications": {
                            "email": True,
                            "push": i % 3 == 0,
                            "sms": False
                        }
                    },
                    "activity": [
                        {"action": "login", "timestamp": datetime.utcnow().isoformat()},
                        {"action": "view_page", "timestamp": datetime.utcnow().isoformat()}
                    ]
                } for i in range(10)
            ],
            "metadata": {
                "generated_at": datetime.utcnow().isoformat(),
                "version": "1.0",
                "total_users": 10
            }
        }
        
        # Cache complex data
        cache_manager.set(cache_key, complex_data, ttl=120)
        
        return {
            "message": "Complex data generated and cached",
            "data": complex_data,
            "cache_hit": False,
            "note": "This demonstrates caching of nested JSON structures"
        }

def create_app():
    """Create the advanced caching demo app"""
    app = LightApi(
        database_url="sqlite:///./caching_demo.db",
        swagger_title="Advanced Redis Caching Demo",
        swagger_version="1.0.0",
        swagger_description="Demonstration of advanced Redis caching strategies in LightAPI",
    )
    
    app.register(CachedProduct)
    app.register(CacheStats)
    app.register(CacheDemo)
    
    return app

if __name__ == "__main__":
    app = create_app()
    
    print("🚀 Advanced Redis Caching Demo Server")
    print("=" * 50)
    print("Server running at http://localhost:8000")
    print("API documentation at http://localhost:8000/docs")
    print()
    print("🔧 Prerequisites:")
    print("  Make sure Redis server is running:")
    print("  redis-server")
    print()
    print("📊 Cache Testing Examples:")
    print()
    print("1. Basic caching:")
    print("   GET /cached_products/1    # First call - cache miss")
    print("   GET /cached_products/1    # Second call - cache hit")
    print()
    print("2. List caching:")
    print("   GET /cached_products?page=1&page_size=5")
    print("   GET /cached_products?page=1&page_size=5  # Cached")
    print()
    print("3. Cache invalidation:")
    print("   POST /cached_products     # Creates product, invalidates lists")
    print("   PUT /cached_products/1    # Updates product, refreshes cache")
    print("   DELETE /cached_products/1 # Deletes product, removes from cache")
    print()
    print("4. Cache statistics:")
    print("   GET /cache_stats          # View cache statistics")
    print("   POST /cache_stats         # Clear all caches")
    print("   DELETE /cache_stats/product:* # Clear products cache")
    print()
    print("5. Performance demos:")
    print("   GET /cache_demo/basic     # Basic cache demo")
    print("   GET /cache_demo/performance # Performance comparison")
    print("   GET /cache_demo/ttl       # TTL demonstration")
    print("   GET /cache_demo/complex   # Complex data caching")
    print()
    print("💡 Tips:")
    print("  - Watch cache hit/miss in responses")
    print("  - Notice TTL (time to live) values")
    print("  - Test performance improvements")
    print("  - Monitor cache statistics")
    
    app.run(host="localhost", port=8000, debug=True)