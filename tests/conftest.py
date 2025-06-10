import os

import pytest

from lightapi.config import config

# Test configuration
TEST_JWT_SECRET = "test_secret_key_for_testing"
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(autouse=True)
def setup_test_env():
    """Set up test environment variables and configuration."""
    # Store original values
    original_env = {
        "LIGHTAPI_JWT_SECRET": os.environ.get("LIGHTAPI_JWT_SECRET"),
        "LIGHTAPI_ENV": os.environ.get("LIGHTAPI_ENV"),
        "LIGHTAPI_DATABASE_URL": os.environ.get("LIGHTAPI_DATABASE_URL"),
    }

    # Set test values
    os.environ["LIGHTAPI_JWT_SECRET"] = TEST_JWT_SECRET
    os.environ["LIGHTAPI_ENV"] = "test"
    os.environ["LIGHTAPI_DATABASE_URL"] = TEST_DATABASE_URL

    # Update config directly
    config.update(jwt_secret=TEST_JWT_SECRET, database_url=TEST_DATABASE_URL)

    yield

    # Restore original values
    for key, value in original_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def pytest_configure(config):
    """
    Configure pytest settings before test collection begins.

    This function adds configuration to ignore pytest collection warnings
    related to test classes that have similar names to actual test fixtures
    but aren't intended to be collected, such as model classes in test files.

    Args:
        config: The pytest config object.
    """
    config.addinivalue_line("filterwarnings", "ignore::pytest.PytestCollectionWarning")


def pytest_collect_file(parent, file_path):
    """
    Control how pytest collects test files.

    This hook can be used to skip certain files or implement custom
    collection logic. In this implementation, we return None for files
    that shouldn't be collected as test files, preventing test collection
    conflicts with model classes.

    Args:
        parent: The parent collector node.
        file_path: Path to the file (pathlib.Path).

    Returns:
        None: To indicate the file should not be collected.
    """
    return None
