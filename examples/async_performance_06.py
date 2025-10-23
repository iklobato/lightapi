#!/usr/bin/env python3
"""
LightAPI Async Performance Example

This example demonstrates how to use LightAPI's async capabilities for high-performance APIs.
It shows how async endpoints can handle concurrent requests efficiently.

Features demonstrated:
- Async endpoint methods
- Concurrent request handling
- Performance improvements with async/await
- Error handling in async context
"""

import asyncio
import time
from lightapi import LightApi
from lightapi.rest import RestEndpoint
from lightapi.models import Base
from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime

class AsyncItem(Base, RestEndpoint):
    """Example model with async-optimized endpoints"""
    __tablename__ = "async_items"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    value = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    async def get(self, request):
        """Async GET method with simulated processing time"""
        # Simulate some async processing (e.g., external API call, complex computation)
        await asyncio.sleep(0.1)  # 100ms simulated processing
        
        item_id = request.path_params.get('id')
        if item_id:
            # Simulate async database lookup
            return {
                "id": int(item_id),
                "name": f"Async Item {item_id}",
                "value": float(item_id) * 10.0,
                "created_at": datetime.utcnow().isoformat(),
                "processing_time": 0.1,
                "message": "Retrieved with async processing"
            }
        else:
            # List all items
            items = []
            for i in range(1, 11):  # Simulate 10 items
                items.append({
                    "id": i,
                    "name": f"Async Item {i}",
                    "value": float(i) * 10.0,
                    "created_at": datetime.utcnow().isoformat()
                })
            
            return {
                "items": items,
                "count": len(items),
                "processing_time": 0.1,
                "message": "Listed with async processing"
            }
    
    async def post(self, request):
        """Async POST method with validation"""
        try:
            # Get request data asynchronously
            data = await request.json()
            
            # Simulate async validation
            await asyncio.sleep(0.05)  # 50ms validation time
            
            if not data.get('name'):
                return {"error": "Name is required"}, 400
            
            # Simulate async save operation
            await asyncio.sleep(0.1)  # 100ms save time
            
            new_item = {
                "id": 999,  # Simulated auto-generated ID
                "name": data['name'],
                "value": data.get('value', 0.0),
                "created_at": datetime.utcnow().isoformat(),
                "message": "Created with async processing"
            }
            
            return new_item, 201
            
        except Exception as e:
            return {"error": f"Async processing error: {str(e)}"}, 500

class FastItem(Base, RestEndpoint):
    """Example model for comparison - synchronous processing"""
    __tablename__ = "fast_items"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    value = Column(Float, default=0.0)
    
    def get(self, request):
        """Synchronous GET method"""
        # Simulate some processing time
        time.sleep(0.1)  # 100ms processing (blocking)
        
        item_id = request.path_params.get('id')
        if item_id:
            return {
                "id": int(item_id),
                "name": f"Fast Item {item_id}",
                "value": float(item_id) * 5.0,
                "processing_time": 0.1,
                "message": "Retrieved with sync processing"
            }
        else:
            items = []
            for i in range(1, 11):
                items.append({
                    "id": i,
                    "name": f"Fast Item {i}",
                    "value": float(i) * 5.0
                })
            
            return {
                "items": items,
                "count": len(items),
                "processing_time": 0.1,
                "message": "Listed with sync processing"
            }

def create_app():
    """Create the async performance demo app"""
    app = LightApi(
        database_url="sqlite:///./async_performance.db",
        swagger_title="Async Performance Demo",
        swagger_version="1.0.0",
        swagger_description="Demonstration of async performance benefits in LightAPI",
    )
    
    # Register async and sync endpoints for comparison
    app.register(AsyncItem)
    app.register(FastItem)
    
    return app

if __name__ == "__main__":
    app = create_app()
    
    print("🚀 Async Performance Demo Server")
    print("=" * 50)
    print("Server running at http://localhost:8000")
    print("API documentation at http://localhost:8000/docs")
    print()
    print("Endpoints for testing:")
    print("  Async endpoints:")
    print("    GET  /async_items     - List all async items")
    print("    GET  /async_items/1   - Get specific async item")
    print("    POST /async_items     - Create new async item")
    print()
    print("  Sync endpoints (for comparison):")
    print("    GET  /fast_items      - List all sync items")
    print("    GET  /fast_items/1    - Get specific sync item")
    print()
    print("Performance Testing:")
    print("  Test concurrent requests to see async benefits:")
    print("  curl -s http://localhost:8000/async_items/1 &")
    print("  curl -s http://localhost:8000/async_items/2 &")
    print("  curl -s http://localhost:8000/async_items/3 &")
    print("  wait")
    print()
    print("  Compare with sync endpoints:")
    print("  curl -s http://localhost:8000/fast_items/1 &")
    print("  curl -s http://localhost:8000/fast_items/2 &")
    print("  curl -s http://localhost:8000/fast_items/3 &")
    print("  wait")
    print()
    print("Expected behavior:")
    print("- Async endpoints handle concurrent requests efficiently")
    print("- Sync endpoints process requests sequentially")
    print("- Async endpoints show better performance under load")
    
    app.run(host="localhost", port=8000, debug=True)