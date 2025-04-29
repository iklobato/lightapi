import pytest


def pytest_configure(config):
    """
    Configure pytest settings before test collection begins.
    
    This function adds configuration to ignore pytest collection warnings
    related to test classes that have similar names to actual test fixtures
    but aren't intended to be collected, such as model classes in test files.
    
    Args:
        config: The pytest config object.
    """
    config.addinivalue_line(
        "filterwarnings", "ignore::pytest.PytestCollectionWarning"
    )


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
