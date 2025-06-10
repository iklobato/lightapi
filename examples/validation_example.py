from sqlalchemy import Column, Integer, String

from lightapi.core import LightApi, Response
from lightapi.models import Base, register_model_class
from lightapi.rest import RestEndpoint, Validator


# Define a custom validator with field-specific validation methods
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
            # If it's our own ValueError, re-raise it
            if isinstance(e, ValueError) and "must be greater than zero" in str(e):
                raise e
            # Otherwise, raise the generic message
            raise ValueError("Price must be a valid number")

    def validate_sku(self, value):
        if not value or not isinstance(value, str) or len(value) != 8:
            raise ValueError("SKU must be an 8-character string")
        return value.upper()


# Define a model that uses the validator
@register_model_class
class Product(RestEndpoint):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    name = Column(String(100))
    price = Column(Integer)  # Stored as cents
    sku = Column(String(8), unique=True)

    class Configuration:
        validator_class = ProductValidator

    # Override POST to handle validation errors gracefully
    def post(self, request):
        try:
            data = getattr(request, "data", {})

            # The validator will raise exceptions if validation fails
            validated_data = self.validator.validate(data)

            # Convert price to cents for storage
            if "price" in validated_data:
                validated_data["price"] = int(validated_data["price"] * 100)

            instance = self.__class__(**validated_data)
            self.session.add(instance)
            self.session.commit()

            # Return the created instance
            return {
                "id": instance.id,
                "name": instance.name,
                "price": instance.price / 100,  # Convert back to dollars
                "sku": instance.sku,
            }, 201

        except ValueError as e:
            # Return validation errors with 400 status
            return Response({"error": str(e)}, status_code=400)
        except Exception as e:
            self.session.rollback()
            return Response({"error": str(e)}, status_code=500)


if __name__ == "__main__":
    app = LightApi(
        database_url="sqlite:///validation_example.db",
        swagger_title="Validation Example",
        swagger_version="1.0.0",
        swagger_description="Example showing data validation with LightAPI",
    )

    app.register({"/products": Product})

    print("Server running at http://localhost:8000")
    print("API documentation available at http://localhost:8000/docs")
    print("Try creating products with:")
    print(
        'curl -X POST http://localhost:8000/products -H \'Content-Type: application/json\' -d \'{"name": "Widget", "price": 19.99, "sku": "WDG12345"}\''
    )

    app.run(host="localhost", port=8000, debug=True)
