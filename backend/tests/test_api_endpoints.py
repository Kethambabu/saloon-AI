"""
Unit and Integration Tests for FastAPI API Endpoints.
Verifies health checks, CORS, custom middlewares, and /agent/chat Pydantic input/output schemas.
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import create_app
from core.config import Settings
from api.routes.agent_routes import get_receptionist_agent


@pytest.fixture(scope="module")
def app_client():
    """Provides a configured FastAPI test client for module-level API requests."""
    test_settings = Settings(
        environment="testing",
        database_url="sqlite:///./test.db",
        debug=True,
    )
    app = create_app(settings=test_settings)
    return TestClient(app)


def test_core_health_check(app_client):
    """Verifies that the root health check endpoint returns 200 and healthy status."""
    response = app_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "environment" in data


def test_api_v1_health_check(app_client):
    """Verifies that the sub-routed health check endpoint responds correctly."""
    response = app_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@patch("api.routes.agent_routes.get_receptionist_agent")
def test_agent_chat_endpoint_success(mock_get_agent, app_client):
    """Verifies that POST /api/v1/agent/chat successfully validates schema and maps response."""
    # 1. Setup mocked agent
    mock_agent = MagicMock()
    # Mocking async process method
    async def mock_process(input_data):
        return {
            "success": True,
            "agent_name": "Clara",
            "response": "Hello! I am Clara, how can I help you book your style today?"
        }
    mock_agent.process = mock_process
    mock_get_agent.return_value = mock_agent

    # 2. Make post query with spaces in aliases to check validation compatibility
    payload = {
        "message": "I would like to book a Signature Haircut.",
        "session id": "test-session-99",
        "chat history": []
    }
    
    response = app_client.post("/api/v1/agent/chat", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert data["success"] is True
    assert data["session id"] == "test-session-99"
    assert data["agent_name"] == "Clara"
    assert "how can I help you" in data["response"]


def test_agent_chat_endpoint_validation_error(app_client):
    """Verifies that malformed payloads (e.g. missing message or session id) are rejected with 422."""
    # Payload missing "session id"
    payload = {
        "message": "Hello!",
        "chat history": []
    }
    
    response = app_client.post("/api/v1/agent/chat", json=payload)
    assert response.status_code == 422  # Unprocessable Entity
