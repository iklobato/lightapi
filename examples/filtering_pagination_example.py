from sqlalchemy import Column, Float, Integer, String, create_engine
from sqlalchemy.orm import sessionmaker

from lightapi.core import LightApi
from lightapi.filters import ParameterFilter
from lightapi.models import Base, register_model_class
from lightapi.pagination import Paginator
from lightapi.rest import RestEndpoint


# Custom filter implementation
class ProductFilter(ParameterFilter):
    def filter_queryset(self, queryset, request):
        # Apply base filtering from parent class
        queryset = super().filter_queryset(queryset, request)

        # Get query parameters
        params = request.query_params

        # Filter by price range
        min_price = params.get("min_price")
        if min_price and min_price.isdigit():
            queryset = queryset.filter(Product.price >= float(min_price) * 100)

        max_price = params.get("max_price")
        if max_price and max_price.isdigit():
            queryset = queryset.filter(Product.price <= float(max_price) * 100)

        # Filter by category
        category = params.get("category")
        if category:
            queryset = queryset.filter(Product.category == category)

        # Search by name (case-insensitive partial match)
        search = params.get("search")
        if search:
            queryset = queryset.filter(Product.name.ilike(f"%{search}%"))

        return queryset


# Custom paginator with configurable options
class ProductPaginator(Paginator):
    # Default page size
    limit = 10

    # Default maximum page size
    max_limit = 100

    # Enable sorting
    sort = True

    # Default sort field
    default_sort_field = "name"

    # Valid sort fields
    valid_sort_fields = ["name", "price", "category"]

    def paginate(self, queryset):
        """Paginate the results from the queryset.

        Args:
            queryset: The SQLAlchemy query to paginate.

        Returns:
            A page object with pagination metadata and results.
        """
        # Get pagination parameters
        limit = self.limit
        if hasattr(self, "request"):
            params = getattr(self.request, "query_params", {})
            limit_param = params.get("limit")
            if limit_param and limit_param.isdigit():
                limit = min(int(limit_param), self.max_limit)

            page_param = params.get("page")
            if page_param and page_param.isdigit():
                page = int(page_param)
            else:
                page = 1

            # Apply sorting if enabled
            if self.sort:
                sort_param = params.get("sort", "")
                if sort_param:
                    # Check if it's descending (prefixed with '-')
                    descending = sort_param.startswith("-")
                    if descending:
                        sort_field = sort_param[1:]
                    else:
                        sort_field = sort_param

                    # Validate the sort field
                    if sort_field in self.valid_sort_fields:
                        column = getattr(
                            queryset.column_descriptions[0]["type"], sort_field
                        )
                        if descending:
                            queryset = queryset.order_by(column.desc())
                        else:
                            queryset = queryset.order_by(column.asc())
        else:
            page = 1

        self.paginator_limit = limit  # Store the limit for use in get() method

        # Calculate offset
        offset = (page - 1) * limit

        # Get total count
        total = queryset.count()

        # Get paginated results
        items = queryset.offset(offset).limit(limit).all()

        # Create a page object
        class Page:
            def __init__(self, items, page, limit, total):
                self.items = items
                self.page = page
                self.limit = limit
                self.total = total
                self.pages = (total + limit - 1) // limit  # Ceiling division

                # Calculate next and previous page numbers
                self.next_page = page + 1 if page < self.pages else None
                self.prev_page = page - 1 if page > 1 else None

        return Page(items, page, limit, total)


# Product model with filtering and pagination
@register_model_class
class Product(RestEndpoint):
    __tablename__ = "pagination_products"

    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    price = Column(Integer)  # Stored as cents
    category = Column(String(50))
    description = Column(String(500))

    class Configuration:
        filter_class = ProductFilter
        pagination_class = ProductPaginator

    # Override GET to transform price from cents to dollars in response
    def get(self, request):
        # Save the request for the paginator to access
        if hasattr(self, "paginator"):
            self.paginator.request = request

        query = self.session.query(self.__class__)

        # Apply filtering
        if hasattr(self, "filter"):
            query = self.filter.filter_queryset(query, request)

        # Apply pagination
        if hasattr(self, "paginator"):
            page = self.paginator.paginate(query)
            results = page.items

            # Prepare response with pagination metadata
            response = {
                "count": page.total,
                "next": page.next_page,
                "previous": page.prev_page,
                "page": page.page,
                "pages": page.pages,
                "results": [],
            }
        else:
            results = query.all()
            response = {"results": []}

        # Format results
        for obj in results:
            response["results"].append(
                {
                    "id": obj.id,
                    "name": obj.name,
                    "price": obj.price / 100,  # Convert to dollars
                    "category": obj.category,
                    "description": obj.description,
                }
            )

        return response, 200


# Populate the database with sample data
def init_database():
    # Create the database engine
    engine = create_engine("sqlite:///pagination_example.db")

    # Create tables
    Base.metadata.create_all(engine)

    # Create a session
    Session = sessionmaker(bind=engine)
    session = Session()

    # Check if we already have data
    if session.query(Product).count() == 0:
        # Create sample products
        products = [
            Product(
                name="Laptop",
                price=125000,
                category="Electronics",
                description="High-performance laptop",
            ),
            Product(
                name="Smartphone",
                price=85000,
                category="Electronics",
                description="Latest smartphone model",
            ),
            Product(
                name="Headphones",
                price=12500,
                category="Electronics",
                description="Noise-cancelling headphones",
            ),
            Product(
                name="Coffee Maker",
                price=7500,
                category="Appliances",
                description="Automatic coffee maker",
            ),
            Product(
                name="Blender",
                price=5000,
                category="Appliances",
                description="High-speed blender",
            ),
            Product(
                name="T-shirt",
                price=2500,
                category="Clothing",
                description="Cotton t-shirt",
            ),
            Product(
                name="Jeans", price=6000, category="Clothing", description="Denim jeans"
            ),
            Product(
                name="Sneakers",
                price=8000,
                category="Footwear",
                description="Running sneakers",
            ),
            Product(
                name="Boots",
                price=10000,
                category="Footwear",
                description="Leather boots",
            ),
            Product(
                name="Watch",
                price=15000,
                category="Accessories",
                description="Analog watch",
            ),
            Product(
                name="Backpack",
                price=7000,
                category="Accessories",
                description="Waterproof backpack",
            ),
            Product(
                name="Book",
                price=2000,
                category="Books",
                description="Bestselling novel",
            ),
            Product(
                name="Notebook",
                price=1500,
                category="Stationery",
                description="Spiral notebook",
            ),
            Product(
                name="Pen Set",
                price=1200,
                category="Stationery",
                description="Premium pen set",
            ),
            Product(
                name="Mouse",
                price=4000,
                category="Electronics",
                description="Wireless mouse",
            ),
            Product(
                name="Keyboard",
                price=6000,
                category="Electronics",
                description="Mechanical keyboard",
            ),
            Product(
                name="Monitor",
                price=20000,
                category="Electronics",
                description="4K monitor",
            ),
            Product(
                name="Desk",
                price=30000,
                category="Furniture",
                description="Office desk",
            ),
            Product(
                name="Chair",
                price=15000,
                category="Furniture",
                description="Ergonomic chair",
            ),
            Product(
                name="Desk Lamp",
                price=5000,
                category="Lighting",
                description="LED desk lamp",
            ),
        ]

        session.add_all(products)
        session.commit()

    session.close()


if __name__ == "__main__":
    # Initialize database with sample data
    init_database()

    app = LightApi(
        database_url="sqlite:///pagination_example.db",
        swagger_title="Filtering and Pagination Example",
        swagger_version="1.0.0",
        swagger_description="Example showing filtering and pagination with LightAPI",
    )

    app.register(
        {
            "/products": Product,
        }
    )

    print("Server running at http://localhost:8000")
    print("API documentation available at http://localhost:8000/docs")
    print("\nTry these example queries:")
    print("1. Paginated list of all products:")
    print("   curl http://localhost:8000/products")
    print("2. Go to page 2 with 5 items per page:")
    print("   curl http://localhost:8000/products?page=2&limit=5")
    print("3. Filter by category:")
    print("   curl http://localhost:8000/products?category=Electronics")
    print("4. Filter by price range:")
    print("   curl http://localhost:8000/products?min_price=50&max_price=100")
    print("5. Search by name:")
    print("   curl http://localhost:8000/products?search=phone")
    print("6. Sort by price descending:")
    print("   curl http://localhost:8000/products?sort=-price")

    app.run(host="localhost", port=8000, debug=True)
