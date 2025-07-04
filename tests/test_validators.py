import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import pytest

from lightapi.rest import Validator


class TestValidators:
    def test_product_validator(self):
        class ProductValidator(Validator):
            def validate_name(self, value):
                if not value or len(value) < 3:
                    raise ValueError("Name too short")
                return value.upper()

        validator = ProductValidator()
        with pytest.raises(ValueError):
            validator.validate_name("ab")
        assert validator.validate_name("test") == "TEST"

    def test_email_validator(self):
        class EmailValidator(Validator):
            def validate_email(self, value):
                if "@" not in value:
                    raise ValueError("Invalid email")
                return value

        validator = EmailValidator()
        with pytest.raises(ValueError):
            validator.validate_email("notanemail")
        assert validator.validate_email("user@example.com") == "user@example.com"

    def test_validator_functionality(self):
        class CustomValidator(Validator):
            def validate_name(self, value):
                if len(value) < 3:
                    raise ValueError("too short")
                return value.upper()

        validator = CustomValidator()
        with pytest.raises(ValueError):
            validator.validate_name("ab")
        assert validator.validate_name("test") == "TEST"
