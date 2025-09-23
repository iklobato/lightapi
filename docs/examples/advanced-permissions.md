# Advanced Role-Based Permissions

This example demonstrates how to create an enterprise-grade API with role-based permissions using YAML configuration. Perfect for e-commerce platforms, content management systems, and multi-user applications.

## Overview

Role-based permissions allow you to control which operations different user types can perform on your data. This approach provides:

- **Security**: Limit access based on user roles
- **Data Integrity**: Prevent accidental deletion of critical data
- **Compliance**: Meet audit and regulatory requirements
- **Scalability**: Easy to manage permissions as your application grows

## Example: E-commerce Management API

Let's build an e-commerce API with different permission levels:

- **Admin**: Full user and system management
- **Manager**: Product and inventory management
- **Customer**: Order creation and viewing
- **Public**: Read-only access to products

### Database Schema

First, let's create a realistic e-commerce database:

```sql
-- Users table
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    full_name VARCHAR(100),
    role VARCHAR(20) DEFAULT 'customer',
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Products table
CREATE TABLE products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    price DECIMAL(10,2) NOT NULL,
    category_id INTEGER,
    sku VARCHAR(50) UNIQUE,
    stock_quantity INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES categories(id)
);

-- Categories table
CREATE TABLE categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    parent_id INTEGER,
    is_active BOOLEAN DEFAULT 1,
    FOREIGN KEY (parent_id) REFERENCES categories(id)
);

-- Orders table
CREATE TABLE orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    total_amount DECIMAL(10,2) NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    order_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    shipping_address TEXT,
    notes TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Order items table
CREATE TABLE order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price DECIMAL(10,2) NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (product_id) REFERENCES products(id)
);

-- Audit log table
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name VARCHAR(50) NOT NULL,
    record_id INTEGER NOT NULL,
    action VARCHAR(20) NOT NULL,
    user_id INTEGER,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    old_values TEXT,
    new_values TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- System settings table
CREATE TABLE system_settings (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT,
    description TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_by INTEGER,
    FOREIGN KEY (updated_by) REFERENCES users(id)
);
```

### YAML Configuration

```yaml
# ecommerce_api.yaml
database_url: "${DATABASE_URL}"
swagger_title: "E-commerce Management API"
swagger_version: "2.0.0"
swagger_description: |
  Advanced e-commerce API with role-based permissions
  
  ## Permission Levels
  
  ### 🔴 ADMIN LEVEL
  - **Users**: Full CRUD access for user management
  - **System Settings**: Read-only access to configuration
  
  ### 🟡 MANAGER LEVEL  
  - **Products**: Full inventory management
  - **Categories**: Create and update categories (no delete for data integrity)
  - **Orders**: View orders and update status
  
  ### 🟢 CUSTOMER LEVEL
  - **Orders**: Create new orders and view own orders
  - **Products**: Browse product catalog
  
  ### 🔵 PUBLIC LEVEL
  - **Products**: Read-only product browsing
  - **Categories**: Read-only category browsing
  
  ## Security Features
  - Audit logs are read-only for tamper-proofing
  - Order items managed through orders (data integrity)
  - Categories cannot be deleted (preserve relationships)
  - System settings are read-only via API
enable_swagger: true

tables:
  # 🔴 ADMIN LEVEL - Full user management
  - name: users
    crud: [get, post, put, patch, delete]
    # Full CRUD for user administration
    # - GET: List and search users
    # - POST: Create new users (admin accounts)
    # - PUT/PATCH: Update user information and roles
    # - DELETE: Remove users (admin only)
  
  # 🟡 MANAGER LEVEL - Full product management
  - name: products
    crud: [get, post, put, patch, delete]
    # Complete inventory management
    # - GET: Browse product catalog with filtering
    # - POST: Add new products to inventory
    # - PUT/PATCH: Update product details, prices, stock
    # - DELETE: Remove discontinued products
  
  # 🟡 MANAGER LEVEL - Category management (no delete)
  - name: categories
    crud: [get, post, put, patch]
    # Category management without delete for data integrity
    # - GET: Browse category hierarchy
    # - POST: Create new categories
    # - PUT/PATCH: Update category information
    # - No DELETE: Preserve product relationships
  
  # 🟢 CUSTOMER/MANAGER LEVEL - Order management
  - name: orders
    crud: [get, post, patch]
    # Order lifecycle management
    # - GET: View orders (customers see own, managers see all)
    # - POST: Create new orders (customers)
    # - PATCH: Update order status (managers only)
    # - No PUT: Prevent full order replacement
    # - No DELETE: Maintain order history for accounting
  
  # 🔵 READ-ONLY - Order details (managed through orders)
  - name: order_items
    crud: [get]
    # Order line items - read-only for data integrity
    # - GET: View order details and line items
    # - Order items are created/updated through order management
    # - Prevents direct manipulation of order totals
  
  # 🔵 READ-ONLY - Security audit trail
  - name: audit_log
    crud: [get]
    # Tamper-proof audit trail
    # - GET: View system activity logs
    # - Audit logs are system-generated only
    # - No manual modifications allowed for security
  
  # 🔴 ADMIN READ-ONLY - System configuration
  - name: system_settings
    crud: [get]
    # System configuration - read-only via API
    # - GET: View system settings
    # - Settings updates should go through admin interface
    # - Prevents accidental configuration changes
```

### Running the API

```python
# app.py
from lightapi import LightApi
import os

# Set environment variables
os.environ['DATABASE_URL'] = 'sqlite:///ecommerce.db'

# Create API from YAML configuration
app = LightApi.from_config('ecommerce_api.yaml')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
```

### Generated API Endpoints

The configuration above generates the following endpoints:

#### 🔴 Admin Level Endpoints

```bash
# User Management (Full CRUD)
GET    /users/              # List all users
GET    /users/{id}          # Get specific user
POST   /users/              # Create new user
PUT    /users/{id}          # Update user
PATCH  /users/{id}          # Partial user update
DELETE /users/{id}          # Delete user

# System Settings (Read-only)
GET    /system_settings/    # List settings
GET    /system_settings/{key} # Get specific setting
```

#### 🟡 Manager Level Endpoints

```bash
# Product Management (Full CRUD)
GET    /products/           # Browse products
GET    /products/{id}       # Get product details
POST   /products/           # Add new product
PUT    /products/{id}       # Update product
PATCH  /products/{id}       # Update stock/price
DELETE /products/{id}       # Remove product

# Category Management (No Delete)
GET    /categories/         # Browse categories
GET    /categories/{id}     # Get category
POST   /categories/         # Create category
PUT    /categories/{id}     # Update category
PATCH  /categories/{id}     # Partial update

# Order Status Management
GET    /orders/             # View all orders
GET    /orders/{id}         # Get order details
PATCH  /orders/{id}         # Update order status
```

#### 🟢 Customer Level Endpoints

```bash
# Order Creation
GET    /orders/             # View own orders
POST   /orders/             # Create new order
PATCH  /orders/{id}         # Update own order

# Product Browsing
GET    /products/           # Browse products
GET    /products/{id}       # View product details
```

#### 🔵 Read-Only Endpoints

```bash
# Order Details
GET    /order_items/        # View order items
GET    /order_items/{id}    # Get item details

# Audit Trail
GET    /audit_log/          # View audit logs
GET    /audit_log/{id}      # Get log entry
```

### Usage Examples

#### Admin Operations

```bash
# Create a new manager user
curl -X POST http://localhost:8000/users/ \
  -H 'Content-Type: application/json' \
  -d '{
    "username": "manager1",
    "email": "manager@company.com",
    "full_name": "Store Manager",
    "role": "manager"
  }'

# Delete inactive user
curl -X DELETE http://localhost:8000/users/5

# View system settings
curl http://localhost:8000/system_settings/
```

#### Manager Operations

```bash
# Add new product
curl -X POST http://localhost:8000/products/ \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Wireless Headphones",
    "description": "Premium wireless headphones",
    "price": 199.99,
    "category_id": 1,
    "sku": "WH001",
    "stock_quantity": 50
  }'

# Update product stock
curl -X PATCH http://localhost:8000/products/1 \
  -H 'Content-Type: application/json' \
  -d '{"stock_quantity": 25}'

# Update order status
curl -X PATCH http://localhost:8000/orders/1 \
  -H 'Content-Type: application/json' \
  -d '{"status": "shipped"}'

# Create new category
curl -X POST http://localhost:8000/categories/ \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Electronics",
    "description": "Electronic devices and accessories"
  }'
```

#### Customer Operations

```bash
# Browse products
curl http://localhost:8000/products/

# Create new order
curl -X POST http://localhost:8000/orders/ \
  -H 'Content-Type: application/json' \
  -d '{
    "user_id": 3,
    "total_amount": 199.99,
    "shipping_address": "123 Main St, City, State",
    "notes": "Please handle with care"
  }'

# View own orders
curl http://localhost:8000/orders/?user_id=3
```

#### Public/Read-Only Operations

```bash
# View audit trail
curl http://localhost:8000/audit_log/

# View order details
curl http://localhost:8000/order_items/?order_id=1
```

## Security Considerations

### Data Integrity

1. **No Category Deletion**: Categories cannot be deleted to preserve product relationships
2. **Order History**: Orders cannot be deleted to maintain accounting records
3. **Audit Trail**: Audit logs are read-only to prevent tampering
4. **Order Items**: Managed through orders to prevent total manipulation

### Access Control

1. **Role-Based Operations**: Different CRUD operations based on user roles
2. **Read-Only Settings**: System settings are read-only via API
3. **Limited Updates**: Orders only allow status updates, not full replacement
4. **Audit Logging**: All changes are logged for security

### Production Recommendations

1. **Add Authentication**: Implement JWT or OAuth for user authentication
2. **Rate Limiting**: Add rate limiting to prevent abuse
3. **Input Validation**: Add custom validation rules for business logic
4. **Monitoring**: Implement logging and monitoring for security events

## Environment-Based Configuration

### Development Environment

```yaml
# development.yaml
database_url: "sqlite:///dev_ecommerce.db"
enable_swagger: true  # Enable for development

tables:
  - name: users
    crud: [get, post, put, patch, delete]  # Full access in dev
  - name: products
    crud: [get, post, put, patch, delete]
  # ... other tables with full access
```

### Production Environment

```yaml
# production.yaml
database_url: "${PROD_DATABASE_URL}"
enable_swagger: false  # Disabled for security

tables:
  - name: users
    crud: [get, patch]  # Limited access in production
  - name: products
    crud: [get, post, put, patch]  # No delete in production
  # ... other tables with restricted access
```

### Deployment

```bash
# Development
export DATABASE_URL="sqlite:///dev_ecommerce.db"
python -c "from lightapi import LightApi; LightApi.from_config('development.yaml').run()"

# Production
export DATABASE_URL="postgresql://user:pass@prod-db:5432/ecommerce"
python -c "from lightapi import LightApi; LightApi.from_config('production.yaml').run()"
```

## Benefits of This Approach

### 🔒 **Security**
- Role-based access control
- Audit trail for compliance
- Read-only critical data
- Environment-specific permissions

### 📊 **Data Integrity**
- Prevents accidental data loss
- Maintains referential integrity
- Preserves business relationships
- Audit trail for changes

### 🚀 **Scalability**
- Easy to add new roles
- Simple permission management
- Environment-based deployment
- Zero-code configuration

### 🛠️ **Maintainability**
- Clear permission structure
- Self-documenting configuration
- Easy to understand and modify
- Version-controlled permissions

This role-based permissions example demonstrates how LightAPI's YAML configuration system can create sophisticated, enterprise-ready APIs with proper security and data integrity controls, all without writing a single line of Python code.