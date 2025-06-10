import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from examples.filtering_pagination_example import (
    Product,
    ProductFilter,
    ProductPaginator,
    init_database,
)


class TestProductFilter:
    """Test suite for the ProductFilter class from filtering_pagination_example.py.

    This class tests the filtering functionality for product queries, including
    price range filtering, category filtering, and search functionality.
    """

    @pytest.fixture
    def filter(self):
        """Create a ProductFilter instance for testing.

        Returns:
            ProductFilter: A fresh instance of the ProductFilter class.
        """
        return ProductFilter()

    @pytest.fixture
    def db_session(self):
        """Create an in-memory SQLite database session with test data.

        Returns:
            Session: A SQLAlchemy session connected to an in-memory database.
        """
        engine = create_engine("sqlite:///:memory:")
        Product.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()

        # Add test products
        session.add_all(
            [
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
                    name="T-shirt",
                    price=2500,
                    category="Clothing",
                    description="Cotton t-shirt",
                ),
                Product(
                    name="Book",
                    price=2000,
                    category="Books",
                    description="Bestselling novel",
                ),
            ]
        )
        session.commit()

        yield session
        session.close()

    def test_filter_by_price_range(self, filter, db_session):
        """Test that filter_queryset filters products by price range.

        Args:
            filter: The ProductFilter fixture.
            db_session: The database session fixture.
        """
        # Create a basic query
        query = db_session.query(Product)

        # Create a mock request with price range
        class MockRequest:
            query_params = {"min_price": "20", "max_price": "100"}

        # Apply filtering
        filtered_query = filter.filter_queryset(query, MockRequest())

        # Execute the query and get results
        results = filtered_query.all()

        # Verify filtering is correct
        assert len(results) == 2
        assert {product.name for product in results} == {"T-shirt", "Book"}

    def test_filter_by_category(self, filter, db_session):
        """Test that filter_queryset filters products by category.

        Args:
            filter: The ProductFilter fixture.
            db_session: The database session fixture.
        """
        # Create a basic query
        query = db_session.query(Product)

        # Create a mock request with category
        class MockRequest:
            query_params = {"category": "Electronics"}

        # Apply filtering
        filtered_query = filter.filter_queryset(query, MockRequest())

        # Execute the query and get results
        results = filtered_query.all()

        # Verify filtering is correct
        assert len(results) == 2
        assert {product.name for product in results} == {"Laptop", "Smartphone"}

    def test_search_by_name(self, filter, db_session):
        """Test that filter_queryset searches products by name.

        Args:
            filter: The ProductFilter fixture.
            db_session: The database session fixture.
        """
        # Create a basic query
        query = db_session.query(Product)

        # Create a mock request with search term
        class MockRequest:
            query_params = {"search": "phone"}

        # Apply filtering
        filtered_query = filter.filter_queryset(query, MockRequest())

        # Execute the query and get results
        results = filtered_query.all()

        # Verify filtering is correct
        assert len(results) == 1
        assert results[0].name == "Smartphone"

    def test_combined_filters(self, filter, db_session):
        """Test that filter_queryset combines multiple filter criteria.

        Args:
            filter: The ProductFilter fixture.
            db_session: The database session fixture.
        """
        # Create a basic query
        query = db_session.query(Product)

        # Create a mock request with multiple filters
        class MockRequest:
            query_params = {"category": "Electronics", "min_price": "1000"}

        # Apply filtering
        filtered_query = filter.filter_queryset(query, MockRequest())

        # Execute the query and get results
        results = filtered_query.all()

        # Verify filtering is correct - we expect at least one product
        assert len(results) > 0
        # All results should be Electronics with price >= 1000
        for product in results:
            assert product.category == "Electronics"
            assert product.price >= 100000  # 1000 dollars in cents


class TestProductPaginator:
    """Test suite for the ProductPaginator class from filtering_pagination_example.py.

    This class tests the pagination functionality, including page size limits,
    page navigation, and sorting.
    """

    @pytest.fixture
    def paginator(self):
        """Create a ProductPaginator instance for testing.

        Returns:
            ProductPaginator: A fresh instance of the ProductPaginator class.
        """
        return ProductPaginator()

    @pytest.fixture
    def db_session(self):
        """Create an in-memory SQLite database session with test data.

        Returns:
            Session: A SQLAlchemy session connected to an in-memory database.
        """
        engine = create_engine("sqlite:///:memory:")
        Product.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()

        # Add test products with ascending price order
        products = [
            Product(name="Book", price=2000, category="Books"),
            Product(name="T-shirt", price=2500, category="Clothing"),
            Product(name="Headphones", price=5000, category="Electronics"),
            Product(name="Smartphone", price=85000, category="Electronics"),
            Product(name="Laptop", price=125000, category="Electronics"),
        ]
        session.add_all(products)
        session.commit()

        yield session
        session.close()

    def test_default_pagination(self, paginator, db_session):
        """Test that paginate returns the default page size.

        Args:
            paginator: The ProductPaginator fixture.
            db_session: The database session fixture.
        """
        # Create a basic query
        query = db_session.query(Product)

        # Mock the request context
        paginator.request = type("obj", (object,), {"query_params": {}})

        # Paginate the query
        page = paginator.paginate(query)

        # Verify pagination is correct
        assert page.total == 5
        assert page.page == 1
        assert page.pages == 1
        assert len(page.items) == 5  # Default page size is 10, so we get all 5
        assert page.next_page is None
        assert page.prev_page is None

    def test_custom_page_size(self, paginator, db_session):
        """Test that paginate respects the limit parameter.

        Args:
            paginator: The ProductPaginator fixture.
            db_session: The database session fixture.
        """
        # Create a basic query
        query = db_session.query(Product)

        # Mock the request context with limit parameter
        paginator.request = type("obj", (object,), {"query_params": {"limit": "2"}})

        # Paginate the query
        page = paginator.paginate(query)

        # Verify pagination is correct
        assert page.total == 5
        assert page.page == 1
        assert page.pages == 3  # 5 items with 2 per page = 3 pages
        assert len(page.items) == 2
        assert page.next_page is not None
        assert page.prev_page is None

    def test_page_navigation(self, paginator, db_session):
        """Test that paginate handles page navigation correctly.

        Args:
            paginator: The ProductPaginator fixture.
            db_session: The database session fixture.
        """
        # Create a basic query
        query = db_session.query(Product)

        # Mock the request context with page and limit parameters
        paginator.request = type(
            "obj", (object,), {"query_params": {"page": "2", "limit": "2"}}
        )

        # Paginate the query
        page = paginator.paginate(query)

        # Verify pagination is correct
        assert page.total == 5
        assert page.page == 2
        assert page.pages == 3
        assert len(page.items) == 2
        assert page.next_page is not None
        assert page.prev_page is not None

    def test_sorting(self, paginator, db_session):
        """Test that paginate sorts the results correctly.

        Args:
            paginator: The ProductPaginator fixture.
            db_session: The database session fixture.
        """
        # Create a basic query
        query = db_session.query(Product)

        # Mock the request context with sort parameter (descending price)
        paginator.request = type("obj", (object,), {"query_params": {"sort": "-price"}})

        # Paginate the query
        page = paginator.paginate(query)

        # Verify sorting is correct (descending price)
        assert len(page.items) == 5
        assert page.items[0].price == 125000  # Laptop
        assert page.items[1].price == 85000  # Smartphone
        assert page.items[2].price == 5000  # Headphones
        assert page.items[3].price == 2500  # T-shirt
        assert page.items[4].price == 2000  # Book


class TestProductModel:
    """Test suite for the Product model and its GET method from filtering_pagination_example.py.

    This class tests the integration of filtering and pagination in the GET method
    of the Product endpoint.
    """

    @pytest.fixture
    def db_session(self):
        """Create an in-memory SQLite database session with test data.

        Returns:
            Session: A SQLAlchemy session connected to an in-memory database.
        """
        engine = create_engine("sqlite:///:memory:")
        Product.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()

        # Add test products
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
                name="T-shirt",
                price=2500,
                category="Clothing",
                description="Cotton t-shirt",
            ),
            Product(
                name="Book",
                price=2000,
                category="Books",
                description="Bestselling novel",
            ),
        ]
        session.add_all(products)
        session.commit()

        yield session
        session.close()

    def test_get_with_filtering_and_pagination(self, db_session):
        """Test that GET applies both filtering and pagination.

        Args:
            db_session: The database session fixture.
        """
        # Create a Product instance
        product = Product()
        product.session = db_session

        # Set up filter and paginator
        product.filter = ProductFilter()
        product.paginator = ProductPaginator()

        # Create a mock request with filtering and pagination params
        class MockRequest:
            query_params = {
                "category": "Electronics",
                "limit": "2",
                "page": "1",
                "sort": "-price",
            }

        # Call the get method
        response, status_code = product.get(MockRequest())

        # Verify response status
        assert status_code == 200

        # Verify pagination metadata exists
        assert "count" in response
        assert "page" in response
        assert "pages" in response

        # Verify results are present
        assert "results" in response
        assert len(response["results"]) > 0

        # Verify filtering worked
        for item in response["results"]:
            assert item["category"] == "Electronics"

        # Verify sorting worked (descending price)
        if len(response["results"]) > 1:
            assert response["results"][0]["price"] >= response["results"][1]["price"]

    def test_get_with_search(self, db_session):
        """Test that GET applies search filtering.

        Args:
            db_session: The database session fixture.
        """
        # Create a Product instance
        product = Product()
        product.session = db_session

        # Set up filter and paginator
        product.filter = ProductFilter()
        product.paginator = ProductPaginator()

        # Create a mock request with search parameter
        class MockRequest:
            query_params = {"search": "head"}

        # Call the get method
        response, status_code = product.get(MockRequest())

        # Verify response
        assert status_code == 200
        assert response["count"] == 1

        # Verify search results
        results = response["results"]
        assert len(results) == 1
        assert results[0]["name"] == "Headphones"

    def test_init_database(self):
        """Test that init_database creates all required tables and sample data."""
        # Create an in-memory database
        engine = create_engine("sqlite:///:memory:")

        # Call the init_database function with a custom engine
        from unittest.mock import patch

        with patch(
            "examples.filtering_pagination_example.create_engine", return_value=engine
        ):
            init_database()

        # Create a session to verify the data
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()

        # Verify products were created
        products = session.query(Product).all()
        assert len(products) == 20  # There should be 20 sample products

        # Verify categories
        categories = {p.category for p in products}
        assert len(categories) >= 5  # There should be at least 5 distinct categories

        # Close the session
        session.close()
