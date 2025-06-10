import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from examples.validation_example import Product, ProductValidator


class TestProductValidator:
    """Test suite for the ProductValidator class from validation_example.py.

    This class tests the validation methods used to validate product data
    before persistence. It verifies the validator handles valid inputs properly
    and raises appropriate errors for invalid inputs.
    """

    @pytest.fixture
    def validator(self):
        """Create and return a ProductValidator instance for testing.

        Returns:
            ProductValidator: A fresh instance of the ProductValidator class.
        """
        return ProductValidator()

    def test_validate_name_valid(self, validator):
        """Test that validate_name accepts valid product names.

        Args:
            validator: The ProductValidator fixture.
        """
        # Test valid names with different formats
        assert validator.validate_name("Product") == "Product"
        assert (
            validator.validate_name("  Product with spaces  ") == "Product with spaces"
        )
        assert validator.validate_name("X-123") == "X-123"

    def test_validate_name_invalid(self, validator):
        """Test that validate_name rejects invalid product names.

        Args:
            validator: The ProductValidator fixture.
        """
        # Test empty name
        with pytest.raises(ValueError, match="must be at least 3 characters"):
            validator.validate_name("")

        # Test too short name
        with pytest.raises(ValueError, match="must be at least 3 characters"):
            validator.validate_name("AB")

    def test_validate_price_valid(self, validator):
        """Test that validate_price accepts valid price values.

        Args:
            validator: The ProductValidator fixture.
        """
        # Test integer price
        assert validator.validate_price(10) == 10.0

        # Test float price
        assert validator.validate_price(19.99) == 19.99

        # Test string price (should convert to float)
        assert validator.validate_price("29.99") == 29.99

    def test_validate_price_invalid(self, validator):
        """Test that validate_price rejects invalid price values.

        Args:
            validator: The ProductValidator fixture.
        """
        # Test zero price
        with pytest.raises(ValueError, match="must be greater than zero"):
            validator.validate_price(0)

        # Test negative price
        with pytest.raises(ValueError, match="must be greater than zero"):
            validator.validate_price(-10)

        # Test non-numeric price
        with pytest.raises(ValueError, match="must be a valid number"):
            validator.validate_price("not-a-price")

    def test_validate_sku_valid(self, validator):
        """Test that validate_sku accepts valid SKU values.

        Args:
            validator: The ProductValidator fixture.
        """
        # Test valid SKU (exactly 8 characters)
        assert validator.validate_sku("PROD1234") == "PROD1234"

        # Test lowercase SKU (should be converted to uppercase)
        assert validator.validate_sku("prod1234") == "PROD1234"

    def test_validate_sku_invalid(self, validator):
        """Test that validate_sku rejects invalid SKU values.

        Args:
            validator: The ProductValidator fixture.
        """
        # Test empty SKU
        with pytest.raises(ValueError, match="must be an 8-character string"):
            validator.validate_sku("")

        # Test too short SKU
        with pytest.raises(ValueError, match="must be an 8-character string"):
            validator.validate_sku("PROD123")

        # Test too long SKU
        with pytest.raises(ValueError, match="must be an 8-character string"):
            validator.validate_sku("PROD12345")

        # Test non-string value
        with pytest.raises(ValueError, match="must be an 8-character string"):
            validator.validate_sku(12345678)


class TestProductModel:
    """Test suite for the Product model from validation_example.py.

    This class tests the Product model's configuration and REST endpoint functionality,
    focusing on the happy path of POST operation with validation.
    """

    @pytest.fixture
    def db_session(self):
        """Create an in-memory SQLite database session for testing.

        Returns:
            Session: A SQLAlchemy session connected to an in-memory database.
        """
        engine = create_engine("sqlite:///:memory:")
        Product.metadata.create_all(engine)
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        yield session
        session.close()

    def test_product_post_valid_data(self, db_session, monkeypatch):
        """Test that Product.post successfully creates a product with valid data.

        Args:
            db_session: The SQLAlchemy session fixture.
            monkeypatch: Pytest's monkeypatch fixture for mocking.
        """

        # Create a mock request with valid data
        class MockRequest:
            data = {"name": "Test Product", "price": 29.99, "sku": "TESTPROD"}

        # Create a product instance and set up its environment
        product = Product()
        product.session = db_session

        # Mock the validator
        validator = ProductValidator()
        product.validator = validator

        # Call the post method with our mock request
        response, status_code = product.post(MockRequest())

        # Assert the response contains the expected data
        assert status_code == 201
        assert response["id"] is not None
        assert response["name"] == "Test Product"
        assert response["price"] == 29.99
        assert response["sku"] == "TESTPROD"

        # Verify the product was actually saved to the database
        saved_product = db_session.query(Product).first()
        assert saved_product is not None
        assert saved_product.name == "Test Product"
        assert saved_product.price == 2999  # Stored as cents
        assert saved_product.sku == "TESTPROD"

    def test_product_post_invalid_data(self, db_session):
        """Test that Product.post returns an error response for invalid data.

        Args:
            db_session: The SQLAlchemy session fixture.
        """

        # Create a mock request with invalid data
        class MockRequest:
            data = {
                "name": "",  # Invalid: empty name
                "price": -10,  # Invalid: negative price
                "sku": "SHORT",  # Invalid: not 8 characters
            }

        # Create a product instance and set up its environment
        product = Product()
        product.session = db_session

        # Set up the validator
        product.validator = ProductValidator()

        # Call the post method with our mock request
        response = product.post(MockRequest())

        # Assert the response is an error response
        assert response.status_code == 400
        assert "error" in response.body
        assert "name must be at least 3 characters" in response.body["error"]

        # Verify no product was saved to the database
        product_count = db_session.query(Product).count()
        assert product_count == 0
