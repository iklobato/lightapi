import datetime
import os
import random
import time
import uuid

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    create_engine,
)
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.sql import func

from lightapi.auth import JWTAuthentication
from lightapi.cache import RedisCache
from lightapi.core import (
    AuthenticationMiddleware,
    CORSMiddleware,
    LightApi,
    Middleware,
    Response,
)
from lightapi.filters import ParameterFilter
from lightapi.models import Base, register_model_class
from lightapi.pagination import Paginator
from lightapi.rest import RestEndpoint, Validator
from lightapi.swagger import SwaggerGenerator

# --- Association Table for Product-Category ---
product_category_association = Table(
    "product_category",
    Base.metadata,
    Column("product_id", Integer, ForeignKey("products.id")),
    Column("category_id", Integer, ForeignKey("categories.id")),
)


# --- Validators ---
class ProductValidator(Validator):
    def validate_name(self, value):
        if not value or len(value) < 3:
            raise ValueError("Product name must be at least 3 characters")
        return value.strip()

    def validate_price(self, value):
        try:
            price = float(value)
            if price <= 0:
                raise ValueError("Price must be greater than zero")
            return price
        except (TypeError, ValueError) as e:
            if isinstance(e, ValueError) and "must be greater than zero" in str(e):
                raise e
            raise ValueError("Price must be a valid number")

    def validate_sku(self, value):
        if not value or not isinstance(value, str) or len(value) != 8:
            raise ValueError("SKU must be an 8-character string")
        return value.upper()


class CustomEndpointValidator(Validator):
    def validate_name(self, value):
        return value

    def validate_email(self, value):
        return value

    def validate_website(self, value):
        return value


# --- Models & Endpoints ---
@register_model_class
class User(RestEndpoint):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    email = Column(String(100))
    role = Column(String(50))


class Category(Base, RestEndpoint):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True)
    name = Column(String(50), unique=True, nullable=False)
    description = Column(String(200))
    products = relationship("Product", secondary=product_category_association, back_populates="categories")

    def get(self, request):
        category_id = request.path_params.get("id")
        if category_id:
            category = self.session.query(self.__class__).filter_by(id=category_id).first()
            if not category:
                return {"error": "Category not found"}, 404
            result = {"id": category.id, "name": category.name, "description": category.description, "products": []}
            for product in category.products:
                result["products"].append({"id": product.id, "name": product.name, "price": product.price, "sku": product.sku})
            return {"result": result}, 200
        else:
            categories = self.session.query(self.__class__).all()
            results = []
            for category in categories:
                results.append(
                    {"id": category.id, "name": category.name, "description": category.description, "product_count": len(category.products)}
                )
            return {"results": results}, 200


class Supplier(Base, RestEndpoint):
    __tablename__ = "suppliers"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    contact_name = Column(String(100))
    email = Column(String(100))
    phone = Column(String(20))
    products = relationship("Product", back_populates="supplier")


class Product(Base, RestEndpoint):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    price = Column(Float, nullable=False)
    sku = Column(String(20), unique=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())
    supplier_id = Column(Integer, ForeignKey("suppliers.id"))
    supplier = relationship("Supplier", back_populates="products")
    categories = relationship("Category", secondary=product_category_association, back_populates="products")
    order_items = relationship("OrderItem", back_populates="product")

    def get(self, request):
        product_id = request.path_params.get("id")
        if product_id:
            product = self.session.query(self.__class__).filter_by(id=product_id).first()
            if not product:
                return {"error": "Product not found"}, 404
            result = {
                "id": product.id,
                "name": product.name,
                "price": product.price,
                "sku": product.sku,
                "created_at": product.created_at.isoformat() if product.created_at else None,
                "updated_at": product.updated_at.isoformat() if product.updated_at else None,
                "supplier": None,
                "categories": [],
            }
            if product.supplier:
                result["supplier"] = {"id": product.supplier.id, "name": product.supplier.name}
            for category in product.categories:
                result["categories"].append({"id": category.id, "name": category.name})
            return {"result": result}, 200
        else:
            products = self.session.query(self.__class__).all()
            results = []
            for product in products:
                results.append(
                    {
                        "id": product.id,
                        "name": product.name,
                        "price": product.price,
                        "sku": product.sku,
                        "supplier": product.supplier.name if product.supplier else None,
                        "category_count": len(product.categories),
                    }
                )
            return {"results": results}, 200

    def post(self, request):
        try:
            data = getattr(request, "data", {})
            categories_data = data.pop("categories", [])
            supplier_id = data.pop("supplier_id", None)
            product = self.__class__(**data)
            if supplier_id:
                supplier = self.session.query(Supplier).filter_by(id=supplier_id).first()
                if supplier:
                    product.supplier = supplier
            if categories_data:
                for category_id in categories_data:
                    category = self.session.query(Category).filter_by(id=category_id).first()
                    if category:
                        product.categories.append(category)
            self.session.add(product)
            self.session.commit()
            return {"id": product.id, "name": product.name, "price": product.price, "sku": product.sku}, 201
        except Exception as e:
            self.session.rollback()
            return Response({"error": str(e)}, status_code=500)


class Customer(Base, RestEndpoint):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True)
    phone = Column(String(20))
    orders = relationship("Order", back_populates="customer")


class Order(Base, RestEndpoint):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    order_date = Column(DateTime, default=func.now())
    status = Column(String(20), default="pending")
    customer_id = Column(Integer, ForeignKey("customers.id"))
    customer = relationship("Customer", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")

    def get(self, request):
        order_id = request.path_params.get("id")
        if order_id:
            order = self.session.query(self.__class__).filter_by(id=order_id).first()
            if not order:
                return {"error": "Order not found"}, 404
            result = {
                "id": order.id,
                "order_date": order.order_date.isoformat() if order.order_date else None,
                "status": order.status,
                "customer": {"id": order.customer.id, "name": order.customer.name, "email": order.customer.email}
                if order.customer
                else None,
                "items": [],
                "total": 0.0,
            }
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
            orders = self.session.query(self.__class__).all()
            results = []
            for order in orders:
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
    id = Column(Integer, primary_key=True)
    quantity = Column(Integer, default=1)
    price = Column(Float, nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")


# --- Blog Example ---
class BlogPost(Base, RestEndpoint):
    __tablename__ = "posts"
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")


class Comment(Base, RestEndpoint):
    __tablename__ = "comments"
    id = Column(Integer, primary_key=True)
    content = Column(String(1000), nullable=False)
    author = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    post = relationship("BlogPost", back_populates="comments")


# --- JWT Auth Example ---
class CustomJWTAuth(JWTAuthentication):
    def __init__(self):
        super().__init__()
        from lightapi.config import config

        self.secret_key = config.jwt_secret

    def authenticate(self, request):
        return super().authenticate(request)


class AuthEndpoint(RestEndpoint):
    __abstract__ = True

    def post(self, request):
        import jwt

        from lightapi.config import config

        data = getattr(request, "data", {})
        username = data.get("username")
        password = data.get("password")
        if username == "admin" and password == "password":
            payload = {
                "sub": "user_1",
                "username": username,
                "role": "admin",
                "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1),
            }
            token = jwt.encode(payload, config.jwt_secret, algorithm="HS256")
            return {"token": token}, 200
        else:
            return Response({"error": "Invalid credentials"}, status_code=401)


class SecretResource(RestEndpoint):
    __abstract__ = True

    class Configuration:
        authentication_class = CustomJWTAuth

    def get(self, request):
        username = request.state.user.get("username")
        role = request.state.user.get("role")
        return {"message": f"Hello, {username}! You have {role} access.", "secret_data": "This is protected information"}, 200


class PublicResource(RestEndpoint):
    __abstract__ = True

    def get(self, request):
        return {"message": "This is public information"}, 200


@register_model_class
class UserProfile(RestEndpoint):
    __tablename__ = "user_profiles"
    id = Column(Integer, primary_key=True)
    user_id = Column(String(50))
    full_name = Column(String(100))
    email = Column(String(100))

    class Configuration:
        authentication_class = CustomJWTAuth

    def get(self, request):
        user_id = request.state.user.get("sub")
        profile = self.session.query(self.__class__).filter_by(user_id=user_id).first()
        if profile:
            return {"id": profile.id, "user_id": profile.user_id, "full_name": profile.full_name, "email": profile.email}, 200
        else:
            return Response({"error": "Profile not found"}, status_code=404)


# --- Caching Example ---
class CustomCache(RedisCache):
    prefix = "custom_cache:"
    expiration = 60

    def __init__(self):
        self.cache_data = {}

    def get(self, key):
        cache_key = f"{self.prefix}{key}"
        if cache_key in self.cache_data:
            entry = self.cache_data[cache_key]
            if entry["expires_at"] > time.time():
                return entry["value"]
            else:
                del self.cache_data[cache_key]
        return None

    def set(self, key, value, expiration=None):
        cache_key = f"{self.prefix}{key}"
        expires_at = time.time() + (expiration or self.expiration)
        self.cache_data[cache_key] = {"value": value, "expires_at": expires_at}

    def delete(self, key):
        cache_key = f"{self.prefix}{key}"
        if cache_key in self.cache_data:
            del self.cache_data[cache_key]

    def flush(self):
        self.cache_data = {}


class WeatherEndpoint(RestEndpoint):
    __abstract__ = True

    class Configuration:
        caching_class = CustomCache
        caching_method_names = ["GET"]

    def get(self, request):
        city = None
        if hasattr(request, "path_params"):
            city = request.path_params.get("city")
        if not city and hasattr(request, "query_params"):
            city = request.query_params.get("city")
        if not city:
            city = "default"
        cache_key = f"weather:{city}"
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return Response(cached_data, headers={"X-Cache": "HIT"})
        time.sleep(0.1)
        data = {
            "city": city,
            "temperature": random.randint(-10, 40),
            "condition": random.choice(["Sunny", "Cloudy", "Rainy", "Snowy"]),
            "humidity": random.randint(0, 100),
            "wind_speed": random.randint(0, 50),
            "timestamp": time.time(),
        }
        self.cache.set(cache_key, data, 30)
        return Response(data, headers={"X-Cache": "MISS"})


class ConfigurableCacheEndpoint(RestEndpoint):
    __abstract__ = True

    class Configuration:
        caching_class = CustomCache
        caching_method_names = ["GET"]

    def get(self, request):
        cache_ttl = request.query_params.get("ttl")
        resource_id = request.query_params.get("id", "default")
        cache_key = f"resource:{resource_id}"
        cached_data = self.cache.get(cache_key)
        if cached_data:
            return Response(cached_data, headers={"X-Cache": "HIT"})
        time.sleep(1)
        data = {"id": resource_id, "value": random.randint(1, 1000), "generated_at": time.time()}
        if cache_ttl and cache_ttl.isdigit():
            self.cache.set(cache_key, data, int(cache_ttl))
        else:
            self.cache.set(cache_key, data)
        return Response(data, headers={"X-Cache": "MISS"})


# --- Filtering/Pagination Example ---
class ProductFilter(ParameterFilter):
    def filter_queryset(self, query, request):
        params = request.query_params
        if "category" in params:
            query = query.filter(Product.category == params["category"])
        if "min_price" in params:
            query = query.filter(Product.price >= int(float(params["min_price"]) * 100))
        if "max_price" in params:
            query = query.filter(Product.price <= int(float(params["max_price"]) * 100))
        if "search" in params:
            query = query.filter(Product.name.ilike(f"%{params['search']}%"))
        if "sort" in params:
            sort = params["sort"]
            if sort.startswith("-"):
                query = query.order_by(getattr(Product, sort[1:]).desc())
            else:
                query = query.order_by(getattr(Product, sort).asc())
        return query


class ProductPaginator(Paginator):
    def paginate(self, query):
        page = int(self.request.query_params.get("page", 1))
        limit = int(self.request.query_params.get("limit", 10))
        total = query.count()
        items = query.offset((page - 1) * limit).limit(limit).all()
        return type(
            "Page",
            (),
            {
                "items": items,
                "total": total,
                "page": page,
                "pages": (total + limit - 1) // limit,
                "next_page": page + 1 if (page * limit) < total else None,
                "prev_page": page - 1 if page > 1 else None,
            },
        )()


# --- Middleware ---
class LoggingMiddleware(Middleware):
    def process(self, request, response=None):
        if response is None:
            request_id = str(uuid.uuid4())
            request.id = request_id
            print(f"[{request_id}] Request: {request.method} {getattr(request, 'url', type('U', (), {'path': ''})) .path}")
            return super().process(request, response)
        else:
            print(f"[{getattr(request, 'id', 'unknown')}] Response: {getattr(response, 'status_code', 'unknown')}")
            if not hasattr(response, "headers"):
                response.headers = {}
            response.headers["X-Request-ID"] = getattr(request, "id", "unknown")
            return response


class RateLimitMiddleware(Middleware):
    def __init__(self):
        self.clients = {}
        self.requests_per_minute = 2
        self.window = 60

    def process(self, request, response=None):
        if response:
            return response
        client_ip = getattr(request.client, "host", "127.0.0.1")
        current_time = time.time()
        if client_ip not in self.clients:
            self.clients[client_ip] = []
        recent_requests = [req_time for req_time in self.clients[client_ip] if req_time >= current_time - self.window]
        self.clients[client_ip] = recent_requests
        if len(self.clients[client_ip]) >= self.requests_per_minute:
            return Response({"error": "Rate limit exceeded. Try again later."}, status_code=429, headers={"Retry-After": str(self.window)})
        self.clients[client_ip].append(current_time)
        return super().process(request, response)


# --- Hello World Endpoint for Middleware Test ---
class HelloWorldEndpoint(RestEndpoint):
    __abstract__ = True

    def get(self, request):
        request_id = getattr(request, "id", "unknown")
        return {"message": "Hello, World!", "request_id": request_id, "timestamp": time.time()}, 200

    def post(self, request):
        data = getattr(request, "data", {})
        name = data.get("name", "World")
        return {"message": f"Hello, {name}!", "timestamp": time.time()}, 201


# --- Main App ---
def init_database():
    engine = create_engine("sqlite:///mega_example.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    if session.query(Product).count() == 0:
        electronics = Category(name="Electronics", description="Electronic devices and accessories")
        clothing = Category(name="Clothing", description="Apparel and fashion items")
        books = Category(name="Books", description="Books and publications")
        session.add_all([electronics, clothing, books])
        supplier1 = Supplier(name="TechSupplies Inc.", contact_name="John Tech", email="john@techsupplies.com")
        supplier2 = Supplier(name="Fashion Wholesale", contact_name="Mary Style", email="mary@fashionwholesale.com")
        session.add_all([supplier1, supplier2])
        laptop = Product(name="Laptop", price=999.99, sku="TECH001", supplier=supplier1)
        laptop.categories.append(electronics)
        phone = Product(name="Smartphone", price=499.99, sku="TECH002", supplier=supplier1)
        phone.categories.append(electronics)
        tshirt = Product(name="T-Shirt", price=19.99, sku="CLOTH001", supplier=supplier2)
        tshirt.categories.append(clothing)
        novel = Product(name="Novel", price=14.99, sku="BOOK001")
        novel.categories.append(books)
        session.add_all([laptop, phone, tshirt, novel])
        customer = Customer(name="Alice Johnson", email="alice@example.com", phone="555-1234")
        session.add(customer)
        order = Order(customer=customer, status="completed", order_date=datetime.datetime.now())
        order_item1 = OrderItem(order=order, product=laptop, quantity=1, price=laptop.price)
        order_item2 = OrderItem(order=order, product=tshirt, quantity=2, price=tshirt.price)
        session.add_all([order, order_item1, order_item2])
        session.commit()
    session.close()


if __name__ == "__main__":
    os.environ["LIGHTAPI_JWT_SECRET"] = "test-secret-key-123"
    init_database()
    app = LightApi(
        database_url="sqlite:///mega_example.db",
        swagger_title="Mega Example API",
        swagger_version="1.0.0",
        swagger_description="A comprehensive API merging all LightAPI features.",
    )
    # Register all endpoints
    app.register(User)
    app.register(Category)
    app.register(Supplier)
    app.register(Product)
    app.register(Customer)
    app.register(Order)
    app.register(OrderItem)
    app.register(BlogPost)
    app.register(Comment)

    # Register concrete endpoints for abstract resources
    class AuthEndpointCustom(AuthEndpoint):
        route_patterns = ["/auth/login"]

    class PublicResourceCustom(PublicResource):
        route_patterns = ["/public"]

    class SecretResourceCustom(SecretResource):
        route_patterns = ["/secret"]

    class UserProfileCustom(UserProfile):
        route_patterns = ["/user_profiles", "/user_profiles/{id}"]

    class WeatherEndpointCustom(WeatherEndpoint):
        route_patterns = ["/weather/{city}"]

    class ConfigurableCacheEndpointCustom(ConfigurableCacheEndpoint):
        route_patterns = ["/configurable_cache", "/configurable_cache/{id}"]

    class HelloWorldEndpointCustom(HelloWorldEndpoint):
        route_patterns = ["/hello"]

    app.register(AuthEndpointCustom)
    app.register(PublicResourceCustom)
    app.register(SecretResourceCustom)
    app.register(UserProfileCustom)
    app.register(WeatherEndpointCustom)
    app.register(ConfigurableCacheEndpointCustom)
    app.register(HelloWorldEndpointCustom)
    # Add middleware
    app.add_middleware([LoggingMiddleware, CORSMiddleware, RateLimitMiddleware, AuthenticationMiddleware])
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
    print("6. Get weather:")
    print("   curl http://localhost:8000/weather/London")
    print("7. Hello world endpoint:")
    print("   curl http://localhost:8000/hello")
    print("8. JWT login:")
    print(
        '   curl -X POST http://localhost:8000/auth/login -H \'Content-Type: application/json\' -d \'{"username": "admin", "password": "password"}\''
    )
    print("9. Access protected resource:")
    print("   curl -X GET http://localhost:8000/secret -H 'Authorization: Bearer YOUR_TOKEN'")
    app.run(host="localhost", port=8000, debug=True)
