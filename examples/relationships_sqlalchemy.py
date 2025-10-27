from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    create_engine,
)
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.sql import func

from lightapi.core import LightApi, Response
from lightapi.models import Base
from lightapi.rest import RestEndpoint

# Association table for many-to-many relationship
product_category_association = Table(
    "product_category",
    Base.metadata,
    Column("product_id", Integer, ForeignKey("products.id")),
    Column("category_id", Integer, ForeignKey("rel_categories.id")),
    extend_existing=True
)


# Define models with relationships
class Category(Base, RestEndpoint):
    __tablename__ = "rel_categories"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(String(200))

    # Many-to-many relationship with products
    products = relationship("Product", secondary=product_category_association, back_populates="categories")

    # Override GET to include related products
    def get(self, request):
        # Check if we're looking for a specific category
        category_id = request.path_params.get("id")

        if category_id:
            # Get a specific category with its products
            category = self.session.query(self.__class__).filter_by(id=category_id).first()

            if not category:
                return {"error": "Category not found"}, 404

            # Format category with products
            result = {
                "id": category.id,
                "name": category.name,
                "description": category.description,
                "products": [],
            }

            # Add related products
            for product in category.products:
                result["products"].append(
                    {
                        "id": product.id,
                        "name": product.name,
                        "price": product.price,
                        "sku": product.sku,
                    }
                )

            return {"result": result}, 200
        else:
            # Get all categories (without products for brevity)
            categories = self.session.query(self.__class__).all()
            results = []

            for category in categories:
                results.append(
                    {
                        "id": category.id,
                        "name": category.name,
                        "description": category.description,
                        "product_count": len(category.products),
                    }
                )

            return {"results": results}, 200


class Supplier(Base, RestEndpoint):
    __tablename__ = "suppliers"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    contact_name = Column(String(100))
    email = Column(String(100))
    phone = Column(String(20))

    # One-to-many relationship with products
    products = relationship("Product", back_populates="supplier")


class Product(Base, RestEndpoint):
    __tablename__ = "products"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    price = Column(Float, nullable=False)
    sku = Column(String(20), unique=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    supplier_id = Column(Integer, ForeignKey("suppliers.id"))

    # Many-to-one relationship with supplier
    supplier = relationship("Supplier", back_populates="products")

    # Many-to-many relationship with categories
    categories = relationship("Category", secondary=product_category_association, back_populates="products")

    # One-to-many relationship with order items
    order_items = relationship("OrderItem", back_populates="product")

    def _serialize_product(self, product, include_relationships=True):
        """Serialize product with optional relationships."""
        result = {c.name: getattr(product, c.name) for c in product.__table__.columns}
        
        # Convert datetime fields to ISO format
        if result.get('created_at'):
            result['created_at'] = result['created_at'].isoformat()
        if result.get('updated_at'):
            result['updated_at'] = result['updated_at'].isoformat()
            
        if include_relationships:
            result["supplier"] = {"id": product.supplier.id, "name": product.supplier.name} if product.supplier else None
            result["categories"] = [{"id": c.id, "name": c.name} for c in product.categories]
        else:
            result["supplier"] = product.supplier.name if product.supplier else None
            result["category_count"] = len(product.categories)
        return result

    def get(self, request):
        """Get product(s) with relationships."""
        product_id = request.path_params.get("id")
        
        if product_id:
            product = self.session.query(self.__class__).filter_by(id=product_id).first()
            if not product:
                return {"error": "Product not found"}, 404
            return {"result": self._serialize_product(product)}, 200
        
        products = self.session.query(self.__class__).all()
        return {"results": [self._serialize_product(p, include_relationships=False) for p in products]}, 200

    # Override POST to handle relationships
    def post(self, request):
        try:
            data = getattr(request, "data", {})

            # Extract relationship data
            categories_data = data.pop("categories", [])
            supplier_id = data.pop("supplier_id", None)

            # Create the product
            product = self.__class__(**data)

            # Set supplier relationship
            if supplier_id:
                supplier = self.session.query(Supplier).filter_by(id=supplier_id).first()
                if supplier:
                    product.supplier = supplier

            # Set category relationships
            if categories_data:
                for category_id in categories_data:
                    category = self.session.query(Category).filter_by(id=category_id).first()
                    if category:
                        product.categories.append(category)

            self.session.add(product)
            self.session.commit()

            # Format the response
            result = {
                "id": product.id,
                "name": product.name,
                "price": product.price,
                "sku": product.sku,
                "supplier_id": product.supplier_id,
                "categories": [c.id for c in product.categories],
            }

            return {"result": result}, 201
        except Exception as e:
            self.session.rollback()
            return {"error": str(e)}, 400


class Customer(Base, RestEndpoint):
    __tablename__ = "customers"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True)
    phone = Column(String(20))

    # One-to-many relationship with orders
    orders = relationship("Order", back_populates="customer")


class Order(Base, RestEndpoint):
    __tablename__ = "orders"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)
    order_date = Column(DateTime, default=func.now())
    status = Column(String(20), default="pending")
    customer_id = Column(Integer, ForeignKey("customers.id"))

    # Many-to-one relationship with customer
    customer = relationship("Customer", back_populates="orders")

    # One-to-many relationship with order items
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

    # Override GET to include relationships
    def get(self, request):
        # Check if we're looking for a specific order
        order_id = request.path_params.get("id")

        if order_id:
            # Get a specific order with relationships
            order = self.session.query(self.__class__).filter_by(id=order_id).first()

            if not order:
                return {"error": "Order not found"}, 404

            # Format order with relationships
            result = {
                "id": order.id,
                "order_date": order.order_date.isoformat() if order.order_date else None,
                "status": order.status,
                "customer": {
                    "id": order.customer.id,
                    "name": order.customer.name,
                    "email": order.customer.email,
                }
                if order.customer
                else None,
                "items": [],
                "total": 0.0,
            }

            # Add order items
            total = 0.0
            for item in order.items:
                item_total = item.quantity * item.price
                total += item_total

                result["items"].append(
                    {
                        "id": item.id,
                        "product_id": item.product_id,
                        "product_name": item.product.name if item.product else "Unknown",
                        "quantity": item.quantity,
                        "price": item.price,
                        "total": item_total,
                    }
                )

            result["total"] = total

            return {"result": result}, 200
        else:
            # List orders with minimal info
            orders = self.session.query(self.__class__).all()
            results = []

            for order in orders:
                # Calculate order total
                total = sum(item.quantity * item.price for item in order.items)

                results.append(
                    {
                        "id": order.id,
                        "order_date": order.order_date.isoformat() if order.order_date else None,
                        "status": order.status,
                        "customer_name": order.customer.name if order.customer else "Unknown",
                        "item_count": len(order.items),
                        "total": total,
                    }
                )

            return {"results": results}, 200


class OrderItem(Base, RestEndpoint):
    __tablename__ = "order_items"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)
    quantity = Column(Integer, default=1)
    price = Column(Float, nullable=False)  # Price at time of order
    order_id = Column(Integer, ForeignKey("orders.id"))
    product_id = Column(Integer, ForeignKey("products.id"))

    # Relationships
    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")


# Initialize the database with sample data
def _create_sample_categories(session):
    """Create sample categories."""
    categories = [
        Category(name="Electronics", description="Electronic devices and accessories"),
        Category(name="Clothing", description="Apparel and fashion items"),
        Category(name="Books", description="Books and publications")
    ]
    session.add_all(categories)
    return categories

def _create_sample_suppliers(session):
    """Create sample suppliers."""
    suppliers = [
        Supplier(name="TechSupplies Inc.", contact_name="John Tech", email="john@techsupplies.com"),
        Supplier(name="Fashion Wholesale", contact_name="Mary Style", email="mary@fashionwholesale.com")
    ]
    session.add_all(suppliers)
    return suppliers

def _create_sample_products(session, categories, suppliers):
    """Create sample products with relationships."""
    products = [
        Product(name="Laptop", price=999.99, sku="TECH001", supplier=suppliers[0]),
        Product(name="Smartphone", price=499.99, sku="TECH002", supplier=suppliers[0]),
        Product(name="T-Shirt", price=19.99, sku="CLOTH001", supplier=suppliers[1]),
        Product(name="Novel", price=14.99, sku="BOOK001")
    ]
    
    # Add category relationships
    products[0].categories.append(categories[0])  # Laptop -> Electronics
    products[1].categories.append(categories[0])  # Smartphone -> Electronics
    products[2].categories.append(categories[1])  # T-Shirt -> Clothing
    products[3].categories.append(categories[2])  # Novel -> Books
    
    session.add_all(products)
    return products

def _create_sample_customer(session):
    """Create sample customer."""
    customer = Customer(name="Alice Johnson", email="alice@example.com", phone="555-1234")
    session.add(customer)
    return customer

def _create_sample_order(session, customer, products):
    """Create sample order with order items."""
    order = Order(customer=customer, status="completed", order_date=datetime.datetime.now())
    order_items = [
        OrderItem(order=order, product=products[0], quantity=1, price=products[0].price),
        OrderItem(order=order, product=products[2], quantity=2, price=products[2].price)
    ]
    session.add_all([order] + order_items)
    return order

def init_database():
    """Initialize database with sample data."""
    engine = create_engine("sqlite:///relationships_example.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    if session.query(Product).count() == 0:
        categories = _create_sample_categories(session)
        suppliers = _create_sample_suppliers(session)
        products = _create_sample_products(session, categories, suppliers)
        customer = _create_sample_customer(session)
        _create_sample_order(session, customer, products)
        session.commit()
    
    session.close()


def _print_usage():
    """Print usage instructions."""
    print("🚀 Relationships API Started")
    print("Server running at http://localhost:8000")
    print("API documentation available at http://localhost:8000/docs")
    print("\nTry these example queries:")
    print("1. Get all products:")
    print("   curl http://localhost:8000/products")
    print("2. Get a specific product with relationships:")
    print("   curl http://localhost:8000/products/1")
    print("3. Get all categories:")
    print("   curl http://localhost:8000/categories")
    print("4. Get a specific category with its products:")
    print("   curl http://localhost:8000/categories/1")
    print("5. Get an order with its items:")
    print("   curl http://localhost:8000/orders/1")


if __name__ == "__main__":
    # Initialize database with sample data
    init_database()

    app = LightApi(
        database_url="sqlite:///relationships_example.db",
        swagger_title="E-Commerce API with Relationships",
        swagger_version="1.0.0",
        swagger_description="Example showing SQLAlchemy relationships with LightAPI",
    )

    app.register(Category)
    app.register(Supplier)
    app.register(Product)
    app.register(Customer)
    app.register(Order)
    app.register(OrderItem)

    _print_usage()

    app.run(host="localhost", port=8000, debug=True)
