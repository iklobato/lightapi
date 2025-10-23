#!/usr/bin/env python3
"""
LightAPI Response Customization Example

This example demonstrates how to customize HTTP responses in LightAPI.
It shows different content types, custom headers, caching headers,
and various status codes.

Features demonstrated:
- Custom response headers
- Different content types (JSON, XML, CSV)
- Caching headers (Cache-Control, ETag)
- Status code handling
- Response compression
- Custom response formats
"""

import json
import csv
import io
from datetime import datetime, timedelta
from sqlalchemy import Column, Integer, String, DateTime, Float
from lightapi import LightApi, Response
from lightapi.models import Base
from lightapi.rest import RestEndpoint


class SalesRecord(Base, RestEndpoint):
    """Sales record model for response customization demo."""
    __tablename__ = "sales_records"
    __table_args__ = {"extend_existing": True}
    
    id = Column(Integer, primary_key=True)
    product_name = Column(String(100), nullable=False)
    amount = Column(Float, nullable=False)
    sale_date = Column(DateTime, default=datetime.utcnow)
    region = Column(String(50))
    
    def get(self, request):
        """Get sales records with customizable response format."""
        try:
            # Get format from query parameter
            format_type = request.query_params.get('format', 'json')
            
            # Get records
            records = self.db.query(SalesRecord).all()
            
            if format_type == 'json':
                return self._json_response(records)
            elif format_type == 'xml':
                return self._xml_response(records)
            elif format_type == 'csv':
                return self._csv_response(records)
            else:
                return Response(
                    body={"error": "Unsupported format. Use: json, xml, or csv"},
                    status_code=400
                )
                
        except Exception as e:
            return Response(
                body={"error": "Failed to retrieve records"},
                status_code=500
            )
    
    def _json_response(self, records):
        """Return JSON response with custom headers."""
        data = {
            "records": [
                {
                    "id": r.id,
                    "product_name": r.product_name,
                    "amount": r.amount,
                    "sale_date": r.sale_date.isoformat(),
                    "region": r.region
                }
                for r in records
            ],
            "total_records": len(records),
            "generated_at": datetime.utcnow().isoformat()
        }
        
        return Response(
            body=data,
            status_code=200,
            headers={
                "Content-Type": "application/json",
                "Cache-Control": "public, max-age=300",  # 5 minutes cache
                "ETag": f'"{hash(str(data))}"',
                "X-Total-Count": str(len(records)),
                "X-Generated-At": datetime.utcnow().isoformat()
            }
        )
    
    def _xml_response(self, records):
        """Return XML response."""
        xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n'
        xml_content += '<sales_records>\n'
        
        for record in records:
            xml_content += f'  <record id="{record.id}">\n'
            xml_content += f'    <product_name>{record.product_name}</product_name>\n'
            xml_content += f'    <amount>{record.amount}</amount>\n'
            xml_content += f'    <sale_date>{record.sale_date.isoformat()}</sale_date>\n'
            xml_content += f'    <region>{record.region or ""}</region>\n'
            xml_content += '  </record>\n'
        
        xml_content += f'  <total_records>{len(records)}</total_records>\n'
        xml_content += f'  <generated_at>{datetime.utcnow().isoformat()}</generated_at>\n'
        xml_content += '</sales_records>'
        
        return Response(
            body=xml_content,
            status_code=200,
            headers={
                "Content-Type": "application/xml",
                "Cache-Control": "public, max-age=300",
                "X-Total-Count": str(len(records))
            }
        )
    
    def _csv_response(self, records):
        """Return CSV response."""
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write header
        writer.writerow(['ID', 'Product Name', 'Amount', 'Sale Date', 'Region'])
        
        # Write data
        for record in records:
            writer.writerow([
                record.id,
                record.product_name,
                record.amount,
                record.sale_date.isoformat(),
                record.region or ''
            ])
        
        csv_content = output.getvalue()
        output.close()
        
        return Response(
            body=csv_content,
            status_code=200,
            headers={
                "Content-Type": "text/csv",
                "Content-Disposition": "attachment; filename=sales_records.csv",
                "Cache-Control": "no-cache",
                "X-Total-Count": str(len(records))
            }
        )
    
    def post(self, request):
        """Create a new sales record."""
        try:
            data = request.json()
            
            # Validate required fields
            if not data.get('product_name'):
                return Response(
                    body={"error": "Product name is required"},
                    status_code=400
                )
            
            if not data.get('amount'):
                return Response(
                    body={"error": "Amount is required"},
                    status_code=400
                )
            
            # Create record
            record = SalesRecord(
                product_name=data['product_name'],
                amount=float(data['amount']),
                region=data.get('region')
            )
            
            self.db.add(record)
            self.db.commit()
            
            # Return created record with custom headers
            return Response(
                body={
                    "message": "Sales record created successfully",
                    "record": {
                        "id": record.id,
                        "product_name": record.product_name,
                        "amount": record.amount,
                        "sale_date": record.sale_date.isoformat(),
                        "region": record.region
                    }
                },
                status_code=201,
                headers={
                    "Location": f"/salesrecord/{record.id}/",
                    "X-Created-At": record.sale_date.isoformat(),
                    "X-Record-ID": str(record.id)
                }
            )
            
        except ValueError as e:
            return Response(
                body={"error": "Invalid data format"},
                status_code=400
            )
        except Exception as e:
            return Response(
                body={"error": "Failed to create record"},
                status_code=500
            )
    
    def get_id(self, request):
        """Get a specific sales record with conditional headers."""
        try:
            record_id = int(request.path_params['id'])
            record = self.db.query(SalesRecord).filter(SalesRecord.id == record_id).first()
            
            if not record:
                return Response(
                    body={"error": "Record not found"},
                    status_code=404,
                    headers={
                        "Cache-Control": "no-cache"
                    }
                )
            
            # Check If-Modified-Since header
            if_modified_since = request.headers.get('If-Modified-Since')
            if if_modified_since:
                try:
                    if_modified_date = datetime.fromisoformat(if_modified_since.replace('Z', '+00:00'))
                    if record.sale_date <= if_modified_date:
                        return Response(
                            body="",
                            status_code=304,  # Not Modified
                            headers={
                                "Cache-Control": "public, max-age=300"
                            }
                        )
                except ValueError:
                    pass  # Invalid date format, proceed normally
            
            return Response(
                body={
                    "record": {
                        "id": record.id,
                        "product_name": record.product_name,
                        "amount": record.amount,
                        "sale_date": record.sale_date.isoformat(),
                        "region": record.region
                    }
                },
                status_code=200,
                headers={
                    "Cache-Control": "public, max-age=300",
                    "Last-Modified": record.sale_date.isoformat(),
                    "ETag": f'"{record.id}-{hash(str(record.sale_date))}"'
                }
            )
            
        except ValueError:
            return Response(
                body={"error": "Invalid record ID"},
                status_code=400
            )
        except Exception as e:
            return Response(
                body={"error": "Failed to retrieve record"},
                status_code=500
            )


if __name__ == "__main__":
    print("📊 LightAPI Response Customization Example")
    print("=" * 50)
    
    # Initialize the API
    app = LightApi(
        database_url="sqlite:///response_customization_example.db",
        swagger_title="Response Customization API",
        swagger_version="1.0.0",
        swagger_description="Demonstrates custom response formats and headers",
        enable_swagger=True
    )
    
    # Register our endpoint
    app.register(SalesRecord)
    
    print("Server running at http://localhost:8000")
    print("API documentation at http://localhost:8000/docs")
    print()
    print("Test different response formats:")
    print("  # JSON response (default)")
    print("  curl http://localhost:8000/salesrecord/")
    print()
    print("  # XML response")
    print("  curl http://localhost:8000/salesrecord/?format=xml")
    print()
    print("  # CSV response")
    print("  curl http://localhost:8000/salesrecord/?format=csv")
    print()
    print("  # Create a record")
    print("  curl -X POST http://localhost:8000/salesrecord/ -H 'Content-Type: application/json' -d '{\"product_name\": \"Widget\", \"amount\": 99.99, \"region\": \"North\"}'")
    print()
    print("  # Test conditional headers")
    print("  curl -H 'If-Modified-Since: 2023-01-01T00:00:00Z' http://localhost:8000/salesrecord/1/")
    
    # Run the server
    app.run(host="localhost", port=8000, debug=True)
