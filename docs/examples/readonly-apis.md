# Read-Only APIs for Analytics and Reporting

This example demonstrates how to create read-only APIs perfect for analytics dashboards, reporting systems, and data visualization applications. Read-only APIs provide secure access to data without allowing modifications.

## Overview

Read-only APIs are ideal for:

- **Analytics Dashboards**: Business intelligence and metrics
- **Reporting Systems**: Financial reports, user statistics
- **Data Visualization**: Charts, graphs, and interactive displays
- **Public Data Access**: Open datasets and information sharing
- **Legacy System Integration**: Expose existing data without modification risks

## Benefits of Read-Only APIs

### 🔒 **Security**
- **No Data Modification**: Eliminates risk of accidental data changes
- **Safe Public Access**: Can be exposed publicly without security concerns
- **Audit Compliance**: Maintains data integrity for regulatory requirements
- **Reduced Attack Surface**: Only GET operations limit potential vulnerabilities

### ⚡ **Performance**
- **Aggressive Caching**: Read-only data can be cached extensively
- **Database Optimization**: Read replicas and optimized queries
- **CDN Distribution**: Static-like data can be distributed globally
- **Concurrent Access**: Multiple users can access simultaneously without conflicts

### 🛠️ **Maintainability**
- **Simple Architecture**: No complex business logic for modifications
- **Easy Scaling**: Read operations scale horizontally
- **Predictable Behavior**: No side effects from API calls
- **Clear Purpose**: Single responsibility for data access

## Example 1: Analytics Dashboard API

Let's create an analytics API for a web application with user metrics, page views, and sales data.

### Database Schema

```sql
-- analytics.sql
-- User analytics table
CREATE TABLE user_analytics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    session_id VARCHAR(50),
    page_url VARCHAR(500),
    referrer VARCHAR(500),
    user_agent TEXT,
    ip_address VARCHAR(45),
    country VARCHAR(50),
    city VARCHAR(100),
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    session_duration INTEGER  -- in seconds
);

-- Page views table
CREATE TABLE page_views (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_url VARCHAR(500) NOT NULL,
    page_title VARCHAR(200),
    views_count INTEGER DEFAULT 1,
    unique_visitors INTEGER DEFAULT 1,
    bounce_rate DECIMAL(5,2),
    avg_time_on_page INTEGER,  -- in seconds
    date DATE NOT NULL,
    hour INTEGER,  -- 0-23
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Sales analytics table
CREATE TABLE sales_analytics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    product_id INTEGER,
    product_name VARCHAR(200),
    category VARCHAR(100),
    quantity INTEGER NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    total_amount DECIMAL(10,2) NOT NULL,
    discount_amount DECIMAL(10,2) DEFAULT 0,
    customer_id INTEGER,
    customer_segment VARCHAR(50),
    sales_channel VARCHAR(50),
    region VARCHAR(100),
    sale_date DATE NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Monthly reports table
CREATE TABLE monthly_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_month DATE NOT NULL,
    total_revenue DECIMAL(12,2),
    total_orders INTEGER,
    new_customers INTEGER,
    returning_customers INTEGER,
    avg_order_value DECIMAL(10,2),
    conversion_rate DECIMAL(5,2),
    top_product_category VARCHAR(100),
    growth_rate DECIMAL(5,2),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Insert sample analytics data
INSERT INTO user_analytics (user_id, session_id, page_url, referrer, country, city, session_duration) VALUES
(1, 'sess_001', '/home', 'https://google.com', 'USA', 'New York', 120),
(1, 'sess_001', '/products', '/home', 'USA', 'New York', 45),
(2, 'sess_002', '/home', 'https://facebook.com', 'UK', 'London', 200),
(3, 'sess_003', '/about', 'direct', 'Canada', 'Toronto', 90);

INSERT INTO page_views (page_url, page_title, views_count, unique_visitors, bounce_rate, avg_time_on_page, date, hour) VALUES
('/home', 'Homepage', 1250, 980, 35.5, 125, '2024-01-15', 14),
('/products', 'Products', 890, 720, 28.2, 180, '2024-01-15', 14),
('/about', 'About Us', 340, 310, 45.8, 95, '2024-01-15', 14),
('/contact', 'Contact', 180, 165, 52.1, 75, '2024-01-15', 14);

INSERT INTO sales_analytics (order_id, product_id, product_name, category, quantity, unit_price, total_amount, customer_id, customer_segment, sales_channel, region, sale_date) VALUES
(1001, 101, 'Wireless Headphones', 'Electronics', 2, 99.99, 199.98, 501, 'Premium', 'Online', 'North America', '2024-01-15'),
(1002, 102, 'Running Shoes', 'Sports', 1, 129.99, 129.99, 502, 'Regular', 'Store', 'Europe', '2024-01-15'),
(1003, 103, 'Coffee Maker', 'Home', 1, 79.99, 79.99, 503, 'Budget', 'Online', 'Asia', '2024-01-15');

INSERT INTO monthly_reports (report_month, total_revenue, total_orders, new_customers, returning_customers, avg_order_value, conversion_rate, top_product_category, growth_rate) VALUES
('2024-01-01', 125000.50, 1250, 380, 870, 100.00, 3.2, 'Electronics', 12.5),
('2023-12-01', 118000.25, 1180, 350, 830, 100.00, 3.0, 'Electronics', 8.3),
('2023-11-01', 109000.75, 1090, 320, 770, 100.00, 2.8, 'Home', 15.2);
```

Create the database:
```bash
sqlite3 analytics.db < analytics.sql
```

### YAML Configuration

```yaml
# analytics_api.yaml
database_url: "sqlite:///analytics.db"
swagger_title: "Analytics Dashboard API"
swagger_version: "1.0.0"
swagger_description: |
  Read-only analytics API for business intelligence and reporting
  
  ## Data Sources
  - **User Analytics**: User behavior and session data
  - **Page Views**: Website traffic and engagement metrics
  - **Sales Analytics**: Revenue and product performance data
  - **Monthly Reports**: Aggregated business metrics
  
  ## Features
  - Real-time analytics data access
  - Historical trend analysis
  - Performance metrics and KPIs
  - Secure read-only access
  - Optimized for dashboard consumption
  
  ## Security
  - Read-only operations only
  - No data modification possible
  - Safe for public dashboards
  - Audit-compliant data access
enable_swagger: true

tables:
  # All tables are read-only for security and data integrity
  - name: user_analytics
    crud: [get]
  
  - name: page_views
    crud: [get]
  
  - name: sales_analytics
    crud: [get]
  
  - name: monthly_reports
    crud: [get]
```

### Running the Analytics API

```python
# analytics_app.py
from lightapi import LightApi
import os

# Set database URL
os.environ['DATABASE_URL'] = 'sqlite:///analytics.db'

# Create read-only analytics API
app = LightApi.from_config('analytics_api.yaml')

if __name__ == '__main__':
    print("📊 Starting Analytics Dashboard API...")
    print("📈 Read-only data access for business intelligence")
    print("🔍 API Documentation: http://localhost:8000/docs")
    print("📊 Analytics Endpoints: http://localhost:8000/")
    app.run(host='0.0.0.0', port=8000)
```

### Generated Endpoints

The read-only API generates these endpoints:

```bash
# User Analytics
GET /user_analytics/          # List user sessions and behavior
GET /user_analytics/{id}      # Get specific user session

# Page Views
GET /page_views/              # List page performance metrics
GET /page_views/{id}          # Get specific page metrics

# Sales Analytics
GET /sales_analytics/         # List sales transactions
GET /sales_analytics/{id}     # Get specific sale details

# Monthly Reports
GET /monthly_reports/         # List monthly business reports
GET /monthly_reports/{id}     # Get specific monthly report
```

### Usage Examples

```bash
# Get recent user sessions
curl "http://localhost:8000/user_analytics/?page=1&page_size=10"

# Filter by country
curl "http://localhost:8000/user_analytics/?country=USA"

# Get page views for specific date
curl "http://localhost:8000/page_views/?date=2024-01-15"

# Get top performing pages
curl "http://localhost:8000/page_views/?sort=-views_count&page_size=5"

# Get sales by category
curl "http://localhost:8000/sales_analytics/?category=Electronics"

# Get sales for date range (if supported by filtering)
curl "http://localhost:8000/sales_analytics/?sale_date=2024-01-15"

# Get latest monthly reports
curl "http://localhost:8000/monthly_reports/?sort=-report_month&page_size=3"
```

## Example 2: Public Data API

Create a read-only API for public datasets like weather data, census information, or open government data.

### Database Schema

```sql
-- public_data.sql
-- Weather data table
CREATE TABLE weather_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    station_id VARCHAR(20) NOT NULL,
    station_name VARCHAR(100),
    city VARCHAR(100),
    state VARCHAR(50),
    country VARCHAR(50),
    latitude DECIMAL(10,8),
    longitude DECIMAL(11,8),
    temperature DECIMAL(5,2),  -- Celsius
    humidity DECIMAL(5,2),     -- Percentage
    pressure DECIMAL(7,2),     -- hPa
    wind_speed DECIMAL(5,2),   -- km/h
    wind_direction INTEGER,    -- Degrees
    visibility DECIMAL(5,2),   -- km
    weather_condition VARCHAR(50),
    recorded_at DATETIME NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Census data table
CREATE TABLE census_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    region_code VARCHAR(20) NOT NULL,
    region_name VARCHAR(100),
    region_type VARCHAR(50),  -- city, county, state
    population INTEGER,
    area_km2 DECIMAL(10,2),
    population_density DECIMAL(10,2),
    median_age DECIMAL(4,1),
    median_income DECIMAL(10,2),
    unemployment_rate DECIMAL(5,2),
    education_level VARCHAR(50),
    census_year INTEGER,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Economic indicators table
CREATE TABLE economic_indicators (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    indicator_name VARCHAR(100) NOT NULL,
    indicator_code VARCHAR(20),
    country VARCHAR(50),
    value DECIMAL(15,4),
    unit VARCHAR(50),
    frequency VARCHAR(20),  -- daily, monthly, quarterly, yearly
    period_start DATE,
    period_end DATE,
    source VARCHAR(100),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Insert sample public data
INSERT INTO weather_data (station_id, station_name, city, state, country, latitude, longitude, temperature, humidity, pressure, wind_speed, wind_direction, visibility, weather_condition, recorded_at) VALUES
('NYC001', 'Central Park', 'New York', 'NY', 'USA', 40.7829, -73.9654, 22.5, 65.0, 1013.25, 15.2, 180, 10.0, 'Partly Cloudy', '2024-01-15 14:00:00'),
('LAX001', 'LAX Airport', 'Los Angeles', 'CA', 'USA', 33.9425, -118.4081, 28.1, 45.0, 1015.80, 8.5, 270, 16.0, 'Clear', '2024-01-15 14:00:00'),
('LON001', 'Heathrow', 'London', 'England', 'UK', 51.4700, -0.4543, 12.3, 78.0, 1008.50, 22.1, 225, 8.0, 'Overcast', '2024-01-15 14:00:00');

INSERT INTO census_data (region_code, region_name, region_type, population, area_km2, population_density, median_age, median_income, unemployment_rate, education_level, census_year) VALUES
('NYC', 'New York City', 'city', 8336817, 778.2, 10715.0, 36.2, 65850.00, 4.2, 'Bachelor+', 2020),
('LAC', 'Los Angeles County', 'county', 10014009, 12305.0, 814.0, 35.8, 68044.00, 5.1, 'Some College', 2020),
('LON', 'Greater London', 'region', 9648110, 1572.0, 6140.0, 35.6, 52000.00, 3.8, 'Bachelor+', 2021);

INSERT INTO economic_indicators (indicator_name, indicator_code, country, value, unit, frequency, period_start, period_end, source) VALUES
('GDP Growth Rate', 'GDP_GROWTH', 'USA', 2.3, 'Percent', 'quarterly', '2023-10-01', '2023-12-31', 'Bureau of Economic Analysis'),
('Inflation Rate', 'CPI_INFLATION', 'USA', 3.1, 'Percent', 'monthly', '2024-01-01', '2024-01-31', 'Bureau of Labor Statistics'),
('Unemployment Rate', 'UNEMPLOYMENT', 'USA', 3.7, 'Percent', 'monthly', '2024-01-01', '2024-01-31', 'Bureau of Labor Statistics');
```

### YAML Configuration

```yaml
# public_data_api.yaml
database_url: "sqlite:///public_data.db"
swagger_title: "Public Data API"
swagger_version: "1.0.0"
swagger_description: |
  Open access to public datasets and information
  
  ## Available Datasets
  - **Weather Data**: Real-time and historical weather information
  - **Census Data**: Population and demographic statistics
  - **Economic Indicators**: Key economic metrics and trends
  
  ## Features
  - Free public access
  - Real-time data updates
  - Historical data archives
  - RESTful API design
  - Comprehensive filtering
  
  ## Usage
  - No authentication required
  - Rate limiting may apply
  - Data provided as-is
  - Attribution appreciated
enable_swagger: true

tables:
  # All public data is read-only
  - name: weather_data
    crud: [get]
  
  - name: census_data
    crud: [get]
  
  - name: economic_indicators
    crud: [get]
```

### Advanced Read-Only Features

#### Custom Aggregation Endpoints

```python
# public_data_app.py
from lightapi import LightApi
from sqlalchemy import func
import json

app = LightApi.from_config('public_data_api.yaml')

@app.get("/weather/summary")
def weather_summary(city: str = None):
    """Get weather summary statistics"""
    # This would implement actual database queries
    return {
        "city": city or "All Cities",
        "avg_temperature": 18.5,
        "avg_humidity": 62.3,
        "total_stations": 150,
        "last_updated": "2024-01-15T14:00:00Z"
    }

@app.get("/census/demographics")
def demographics_summary(region_type: str = None):
    """Get demographic summary by region type"""
    return {
        "region_type": region_type or "All Regions",
        "total_population": 50000000,
        "avg_median_age": 35.8,
        "avg_median_income": 58000,
        "regions_count": 25
    }

@app.get("/economic/trends")
def economic_trends(indicator: str = None, period: str = "monthly"):
    """Get economic indicator trends"""
    return {
        "indicator": indicator or "All Indicators",
        "period": period,
        "trend": "increasing",
        "latest_value": 3.2,
        "change_percent": 0.5,
        "data_points": 12
    }

if __name__ == '__main__':
    print("🌍 Starting Public Data API...")
    print("📊 Open access to public datasets")
    print("🔍 API Documentation: http://localhost:8000/docs")
    app.run(host='0.0.0.0', port=8000)
```

## Example 3: Multi-Database Read-Only API

Combine data from multiple sources into a unified read-only API.

### YAML Configuration

```yaml
# multi_source_api.yaml
database_url: "${PRIMARY_DATABASE_URL}"
swagger_title: "Multi-Source Data API"
swagger_version: "1.0.0"
swagger_description: |
  Unified read-only access to multiple data sources
  
  ## Data Sources
  - Production database (read replica)
  - Analytics warehouse
  - External API cache
  - Historical archives
  
  ## Benefits
  - Single API for multiple sources
  - Consistent data format
  - Optimized read performance
  - Cached responses
enable_swagger: true

tables:
  # Production data (read replica)
  - name: users
    crud: [get]
  
  - name: orders
    crud: [get]
  
  # Analytics data
  - name: user_metrics
    crud: [get]
  
  - name: sales_reports
    crud: [get]
  
  # Cached external data
  - name: market_data
    crud: [get]
  
  # Historical archives
  - name: archived_transactions
    crud: [get]
```

## Performance Optimization for Read-Only APIs

### Database Optimization

```sql
-- Create indexes for common queries
CREATE INDEX idx_user_analytics_timestamp ON user_analytics(timestamp);
CREATE INDEX idx_user_analytics_country ON user_analytics(country);
CREATE INDEX idx_page_views_date ON page_views(date);
CREATE INDEX idx_sales_analytics_date ON sales_analytics(sale_date);
CREATE INDEX idx_sales_analytics_category ON sales_analytics(category);

-- Create composite indexes for complex queries
CREATE INDEX idx_user_analytics_country_date ON user_analytics(country, timestamp);
CREATE INDEX idx_sales_category_date ON sales_analytics(category, sale_date);
```

### Caching Strategy

```python
# cached_readonly_app.py
from lightapi import LightApi
from lightapi.cache import RedisCache

app = LightApi.from_config('analytics_api.yaml')

# Add aggressive caching for read-only data
redis_cache = RedisCache(
    url="redis://localhost:6379",
    default_ttl=3600,  # 1 hour cache
    key_prefix="analytics_api:"
)

app.add_cache(redis_cache)

# Custom caching for specific endpoints
@app.get("/stats/daily")
@app.cache(ttl=1800)  # 30 minutes
def daily_stats():
    """Get daily statistics with caching"""
    return {
        "date": "2024-01-15",
        "total_views": 15420,
        "unique_visitors": 8930,
        "bounce_rate": 32.5,
        "avg_session_duration": 145
    }
```

## Security Considerations

### Access Control

```yaml
# secure_readonly_api.yaml
database_url: "${READONLY_DATABASE_URL}"  # Use read-only database user
swagger_title: "Secure Analytics API"
enable_swagger: false  # Disable in production

tables:
  # Only expose necessary tables
  - name: public_metrics
    crud: [get]
  
  # Exclude sensitive tables
  # - name: user_personal_data  # Not exposed
  # - name: financial_details   # Not exposed
```

### Rate Limiting

```python
# rate_limited_app.py
from lightapi import LightApi
from lightapi.middleware import RateLimitMiddleware

app = LightApi.from_config('analytics_api.yaml')

# Add rate limiting
rate_limiter = RateLimitMiddleware(
    requests_per_minute=100,
    requests_per_hour=1000
)
app.add_middleware(rate_limiter)
```

## Deployment Patterns

### Docker Configuration

```dockerfile
# Dockerfile.readonly
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY analytics_api.yaml .
COPY analytics_app.py .

# Create non-root user
RUN useradd -m -u 1000 readonly
USER readonly

# Expose port
EXPOSE 8000

# Run read-only API
CMD ["python", "analytics_app.py"]
```

### Kubernetes Deployment

```yaml
# readonly-api-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: readonly-analytics-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: readonly-analytics-api
  template:
    metadata:
      labels:
        app: readonly-analytics-api
    spec:
      containers:
      - name: api
        image: readonly-analytics-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-credentials
              key: readonly-url
        resources:
          requests:
            memory: "128Mi"
            cpu: "100m"
          limits:
            memory: "256Mi"
            cpu: "200m"
---
apiVersion: v1
kind: Service
metadata:
  name: readonly-analytics-service
spec:
  selector:
    app: readonly-analytics-api
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

## Monitoring and Analytics

### API Usage Tracking

```python
# monitored_readonly_app.py
from lightapi import LightApi
from lightapi.middleware import LoggingMiddleware
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = LightApi.from_config('analytics_api.yaml')

# Add request logging
logging_middleware = LoggingMiddleware(
    log_requests=True,
    log_responses=True,
    include_headers=False
)
app.add_middleware(logging_middleware)

@app.middleware("http")
async def track_usage(request, call_next):
    """Track API usage metrics"""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    
    # Log usage metrics
    logger.info(f"API Usage: {request.method} {request.url.path} - {response.status_code} - {process_time:.3f}s")
    
    return response
```

## Best Practices

### 1. Database Design

- **Use read replicas** for production systems
- **Create appropriate indexes** for common query patterns
- **Denormalize data** for better read performance
- **Archive old data** to maintain performance

### 2. API Design

- **Consistent naming** for endpoints and parameters
- **Comprehensive filtering** options
- **Pagination** for large datasets
- **Clear documentation** with examples

### 3. Performance

- **Implement caching** at multiple levels
- **Use connection pooling** for database connections
- **Monitor query performance** and optimize slow queries
- **Consider CDN** for static-like data

### 4. Security

- **Use read-only database users**
- **Implement rate limiting**
- **Validate all inputs** even for read operations
- **Monitor for unusual access patterns**

## Use Cases Summary

### ✅ **Perfect for Read-Only APIs:**
- Analytics dashboards and business intelligence
- Public data access and open datasets
- Reporting systems and data visualization
- Legacy system integration
- Compliance and audit data access

### ⚠️ **Consider Alternatives For:**
- Applications requiring data modifications
- Real-time collaborative systems
- Complex business logic workflows
- User-generated content platforms

## Next Steps

- **[Caching Guide](../advanced/caching.md)** - Optimize performance with caching
- **[Authentication](../advanced/authentication.md)** - Secure your read-only APIs
- **[Deployment](../deployment/production.md)** - Deploy to production
- **[Monitoring](../deployment/monitoring.md)** - Monitor API performance

---

**Read-only APIs with LightAPI provide secure, performant access to your data while maintaining complete data integrity.** Perfect for analytics, reporting, and public data access scenarios.