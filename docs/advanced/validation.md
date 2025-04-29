---
title: Request Validation
---

LightAPI supports request data validation by plugging in a `validator_class` in your endpoint's `Configuration`. Validators inherit from the base `Validator` and define `validate_<field>` methods.

## 1. Creating a Validator

```python
# app/validators.py
from lightapi.rest import Validator

class UserValidator(Validator):
    def validate_username(self, value: str) -> str:
        if not value:
            raise ValueError("Username cannot be empty")
        return value.strip()

    def validate_email(self, value: str) -> str:
        if "@" not in value:
            raise ValueError("Invalid email address")
        return value.lower()
```

## 2. Enabling Validation

Configure your endpoint to use the validator:

```python
from lightapi.rest import RestEndpoint
from app.validators import UserValidator

class UserEndpoint(RestEndpoint):
    class Configuration:
        validator_class = UserValidator

    async def post(self, request):
        # Data is automatically validated before creating the instance
        data = request.data
        # If validation fails, returns a 400 error with the exception message
        return super().post(request)
```

## 3. Error Handling

- If a `validate_<field>` method raises `ValueError`, LightAPI catches it, rolls back the transaction, and returns a 400 Bad Request with the error message.
- Unrecognized fields are passed through unchanged.

## 4. Custom Validation Patterns

- You can also override the `validate(self, data: dict)` method directly for full-body validation.
- Combine with filtering and pagination for robust endpoint logic.
