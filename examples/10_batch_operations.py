#!/usr/bin/env python3
"""
LightAPI Batch Operations Example

This example demonstrates batch operations in LightAPI.
It shows bulk create, update, and delete operations with
proper validation and error handling.

Features demonstrated:
- Bulk create operations
- Bulk update operations
- Bulk delete with validation
- Batch processing with transactions
- Error handling for batch operations
- Progress tracking for large batches
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime
from sqlalchemy.exc import IntegrityError
from lightapi import LightApi, Response
from lightapi.models import Base
from lightapi.rest import RestEndpoint


class Product(Base, RestEndpoint):
    """Product model for batch operations demo."""
    __tablename__ = "batch_products"
    __table_args__ = {"extend_existing": True}
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    price = Column(Float, nullable=False)
    category = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)


class BatchOperationService(Base, RestEndpoint):
    """Service for handling batch operations."""
    __tablename__ = "batch_operation_service"
    __table_args__ = {"extend_existing": True}
    
    id = Column(Integer, primary_key=True)
    
    def post(self, request):
        """Bulk create products."""
        try:
            data = request.json()
            products_data = data.get('products', [])
            
            if not products_data:
                return Response(
                    body={"error": "No products provided"},
                    status_code=400
                )
            
            if len(products_data) > 100:
                return Response(
                    body={"error": "Maximum 100 products allowed per batch"},
                    status_code=400
                )
            
            # Validate all products first
            validated_products = []
            errors = []
            
            for i, product_data in enumerate(products_data):
                try:
                    # Validate required fields
                    if not product_data.get('name'):
                        errors.append(f"Product {i+1}: Name is required")
                        continue
                    
                    if not product_data.get('price'):
                        errors.append(f"Product {i+1}: Price is required")
                        continue
                    
                    price = float(product_data['price'])
                    if price <= 0:
                        errors.append(f"Product {i+1}: Price must be positive")
                        continue
                    
                    validated_products.append({
                        'name': product_data['name'],
                        'price': price,
                        'category': product_data.get('category')
                    })
                    
                except ValueError:
                    errors.append(f"Product {i+1}: Invalid price format")
                    continue
            
            if errors:
                return Response(
                    body={
                        "error": "Validation failed",
                        "errors": errors,
                        "valid_products": len(validated_products)
                    },
                    status_code=400
                )
            
            # Create products in batch
            created_products = []
            failed_products = []
            
            try:
                for product_data in validated_products:
                    try:
                        product = Product(
                            name=product_data['name'],
                            price=product_data['price'],
                            category=product_data['category']
                        )
                        self.db.add(product)
                        self.db.flush()  # Get ID without committing
                        
                        created_products.append({
                            "id": product.id,
                            "name": product.name,
                            "price": product.price,
                            "category": product.category
                        })
                        
                    except IntegrityError:
                        failed_products.append(product_data['name'])
                        self.db.rollback()
                        continue
                
                # Commit all successful creations
                self.db.commit()
                
                return Response(
                    body={
                        "message": "Batch creation completed",
                        "created_products": created_products,
                        "total_created": len(created_products),
                        "failed_products": failed_products,
                        "total_failed": len(failed_products)
                    },
                    status_code=201
                )
                
            except Exception as e:
                self.db.rollback()
                return Response(
                    body={"error": "Batch creation failed"},
                    status_code=500
                )
                
        except Exception as e:
            return Response(
                body={"error": "Invalid request format"},
                status_code=400
            )
    
    def put(self, request):
        """Bulk update products."""
        try:
            data = request.json()
            updates_data = data.get('updates', [])
            
            if not updates_data:
                return Response(
                    body={"error": "No updates provided"},
                    status_code=400
                )
            
            if len(updates_data) > 50:
                return Response(
                    body={"error": "Maximum 50 updates allowed per batch"},
                    status_code=400
                )
            
            # Validate updates
            validated_updates = []
            errors = []
            
            for i, update_data in enumerate(updates_data):
                try:
                    product_id = int(update_data.get('id'))
                    
                    if not update_data.get('name') and not update_data.get('price'):
                        errors.append(f"Update {i+1}: At least name or price must be provided")
                        continue
                    
                    update_info = {'id': product_id}
                    
                    if update_data.get('name'):
                        update_info['name'] = update_data['name']
                    
                    if update_data.get('price'):
                        price = float(update_data['price'])
                        if price <= 0:
                            errors.append(f"Update {i+1}: Price must be positive")
                            continue
                        update_info['price'] = price
                    
                    if update_data.get('category'):
                        update_info['category'] = update_data['category']
                    
                    validated_updates.append(update_info)
                    
                except ValueError:
                    errors.append(f"Update {i+1}: Invalid ID or price format")
                    continue
            
            if errors:
                return Response(
                    body={
                        "error": "Validation failed",
                        "errors": errors
                    },
                    status_code=400
                )
            
            # Perform bulk updates
            updated_products = []
            failed_updates = []
            
            try:
                for update_info in validated_updates:
                    product_id = update_info['id']
                    
                    # Get product
                    product = self.db.query(Product).filter(Product.id == product_id).first()
                    if not product:
                        failed_updates.append(f"Product {product_id} not found")
                        continue
                    
                    # Update fields
                    if 'name' in update_info:
                        product.name = update_info['name']
                    if 'price' in update_info:
                        product.price = update_info['price']
                    if 'category' in update_info:
                        product.category = update_info['category']
                    
                    updated_products.append({
                        "id": product.id,
                        "name": product.name,
                        "price": product.price,
                        "category": product.category
                    })
                
                # Commit all updates
                self.db.commit()
                
                return Response(
                    body={
                        "message": "Batch update completed",
                        "updated_products": updated_products,
                        "total_updated": len(updated_products),
                        "failed_updates": failed_updates,
                        "total_failed": len(failed_updates)
                    },
                    status_code=200
                )
                
            except Exception as e:
                self.db.rollback()
                return Response(
                    body={"error": "Batch update failed"},
                    status_code=500
                )
                
        except Exception as e:
            return Response(
                body={"error": "Invalid request format"},
                status_code=400
            )
    
    def delete(self, request):
        """Bulk delete products with validation."""
        try:
            data = request.json()
            product_ids = data.get('product_ids', [])
            
            if not product_ids:
                return Response(
                    body={"error": "No product IDs provided"},
                    status_code=400
                )
            
            if len(product_ids) > 50:
                return Response(
                    body={"error": "Maximum 50 products allowed per batch delete"},
                    status_code=400
                )
            
            # Validate product IDs
            validated_ids = []
            errors = []
            
            for i, product_id in enumerate(product_ids):
                try:
                    validated_id = int(product_id)
                    validated_ids.append(validated_id)
                except ValueError:
                    errors.append(f"Invalid product ID: {product_id}")
            
            if errors:
                return Response(
                    body={
                        "error": "Validation failed",
                        "errors": errors
                    },
                    status_code=400
                )
            
            # Check which products exist
            existing_products = self.db.query(Product).filter(Product.id.in_(validated_ids)).all()
            existing_ids = {p.id for p in existing_products}
            missing_ids = [pid for pid in validated_ids if pid not in existing_ids]
            
            if missing_ids:
                return Response(
                    body={
                        "error": "Some products not found",
                        "missing_ids": missing_ids,
                        "found_ids": list(existing_ids)
                    },
                    status_code=404
                )
            
            # Perform bulk delete
            try:
                deleted_count = self.db.query(Product).filter(Product.id.in_(validated_ids)).delete(synchronize_session=False)
                self.db.commit()
                
                return Response(
                    body={
                        "message": "Batch delete completed",
                        "deleted_count": deleted_count,
                        "deleted_ids": validated_ids
                    },
                    status_code=200
                )
                
            except Exception as e:
                self.db.rollback()
                return Response(
                    body={"error": "Batch delete failed"},
                    status_code=500
                )
                
        except Exception as e:
            return Response(
                body={"error": "Invalid request format"},
                status_code=400
            )
    
    def patch(self, request):
        """Bulk operations with progress tracking."""
        try:
            data = request.json()
            operation = data.get('operation')
            batch_size = int(data.get('batch_size', 10))
            
            if operation == 'create_sample_data':
                # Create sample products in batches
                total_products = int(data.get('total_products', 100))
                
                created_count = 0
                batch_results = []
                
                for batch_start in range(0, total_products, batch_size):
                    batch_end = min(batch_start + batch_size, total_products)
                    batch_products = []
                    
                    for i in range(batch_start, batch_end):
                        product = Product(
                            name=f"Sample Product {i+1}",
                            price=10.0 + (i % 100),
                            category=f"Category {(i % 5) + 1}"
                        )
                        batch_products.append(product)
                    
                    try:
                        self.db.add_all(batch_products)
                        self.db.commit()
                        
                        created_count += len(batch_products)
                        batch_results.append({
                            "batch": len(batch_results) + 1,
                            "created": len(batch_products),
                            "total_created": created_count
                        })
                        
                    except Exception as e:
                        self.db.rollback()
                        return Response(
                            body={
                                "error": f"Batch {len(batch_results) + 1} failed",
                                "created_so_far": created_count
                            },
                            status_code=500
                        )
                
                return Response(
                    body={
                        "message": "Sample data creation completed",
                        "total_created": created_count,
                        "batch_results": batch_results
                    },
                    status_code=200
                )
            
            else:
                return Response(
                    body={"error": "Invalid operation. Use: create_sample_data"},
                    status_code=400
                )
                
        except Exception as e:
            return Response(
                body={"error": "Invalid request format"},
                status_code=400
            )


if __name__ == "__main__":
    print("📦 LightAPI Batch Operations Example")
    print("=" * 50)
    
    # Initialize the API
    app = LightApi(
        database_url="sqlite:///batch_operations_example.db",
        swagger_title="Batch Operations API",
        swagger_version="1.0.0",
        swagger_description="Demonstrates batch create, update, and delete operations",
        enable_swagger=True
    )
    
    # Register endpoints
    app.register(Product)
    app.register(BatchOperationService)
    
    print("Server running at http://localhost:8000")
    print("API documentation at http://localhost:8000/docs")
    print()
    print("Test batch operations:")
    print("  # Bulk create products")
    print("  curl -X POST http://localhost:8000/batchoperationservice/ -H 'Content-Type: application/json' -d '{\"products\": [{\"name\": \"Product 1\", \"price\": 10.99, \"category\": \"Electronics\"}, {\"name\": \"Product 2\", \"price\": 25.50, \"category\": \"Books\"}]}'")
    print()
    print("  # Bulk update products")
    print("  curl -X PUT http://localhost:8000/batchoperationservice/ -H 'Content-Type: application/json' -d '{\"updates\": [{\"id\": 1, \"price\": 12.99}, {\"id\": 2, \"name\": \"Updated Product 2\"}]}'")
    print()
    print("  # Bulk delete products")
    print("  curl -X DELETE http://localhost:8000/batchoperationservice/ -H 'Content-Type: application/json' -d '{\"product_ids\": [1, 2]}'")
    print()
    print("  # Create sample data")
    print("  curl -X PATCH http://localhost:8000/batchoperationservice/ -H 'Content-Type: application/json' -d '{\"operation\": \"create_sample_data\", \"total_products\": 50, \"batch_size\": 10}'")
    
    # Run the server
    app.run(host="localhost", port=8000, debug=True)
