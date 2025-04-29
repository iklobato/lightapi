"""
This file contains pytest fixtures and configuration for testing.
"""
import pytest


# Configure pytest to ignore collection warnings for model classes that inherit from RestEndpoint
def pytest_configure(config):
    """
    Configure pytest to ignore specific collection warnings.
    """
    config.addinivalue_line(
        "filterwarnings", "ignore::pytest.PytestCollectionWarning"
    )


# Use the updated hook signature with pathlib.Path
def pytest_collect_file(parent, file_path):
    """
    Exclude model classes from test collection.
    
    Args:
        parent: The parent collector
        file_path: Path to the file (pathlib.Path)
    """
    return None
