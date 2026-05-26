"""Test configuration and fixtures"""

import pytest
from fastapi.testclient import TestClient

from main import create_app
from core.config import Settings


@pytest.fixture(scope="session")
def test_settings():
    """Create test settings"""
    return Settings(
        environment="testing",
        database_url="sqlite:///./test.db",
        debug=True,
    )


@pytest.fixture(scope="session")
def app(test_settings):
    """Create test app"""
    return create_app(settings=test_settings)


@pytest.fixture(scope="session")
def client(app):
    """Create test client"""
    return TestClient(app)


__all__ = ["test_settings", "app", "client"]
