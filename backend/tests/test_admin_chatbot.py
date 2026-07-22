"""
Integration Tests for Admin Dashboard AI Business Assistant Chatbot (Atlas).
Verifies route protection, orchestrator integration, intent classification, and analytics telemetry.
"""

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from infrastructure.db import User, UserRole
from ai.orchestrator import MultiAgentOrchestrator, AgentIntent, classify_intent_rule_based
from ai.agents.bi_agent import BIAgent

def test_admin_chatbot_intent_classification():
    """Verify that rule-based intent classification routes analytical queries to BI agent."""
    assert classify_intent_rule_based("how much revenue did we earn?") == AgentIntent.BUSINESS_INTELLIGENCE
    assert classify_intent_rule_based("show staff performance dashboard") == AgentIntent.BUSINESS_INTELLIGENCE
    assert classify_intent_rule_based("compare with last 3 months performance") == AgentIntent.BUSINESS_INTELLIGENCE
    assert classify_intent_rule_based("forecast next month's expected revenue") == AgentIntent.BUSINESS_INTELLIGENCE


@pytest.mark.asyncio
async def test_admin_chatbot_agent_telemetry():
    """Verify that BIAgent tracks queries_processed and revenue_queries telemetry counters."""
    agent = BIAgent(name="Atlas")
    
    # Check initial metrics
    initial_analytics = agent.get_analytics()
    assert initial_analytics["metrics"]["queries_processed"] == 0
    assert initial_analytics["metrics"]["revenue_queries"] == 0

    # Process query
    from unittest.mock import AsyncMock, patch
    mock_result = AsyncMock()
    mock_msg = AsyncMock()
    mock_msg.content = "Total completed revenue is ₹6,20,000."
    mock_result.messages = [mock_msg]

    with patch.object(agent.assistant, "run", return_value=mock_result):
        response = await agent.process({
            "query": "Show me the revenue summary report",
            "session_id": "test-admin-session"
        })

        assert response["success"] is True
        assert response["agent_name"] == "Atlas"
        assert response["analytics"]["metrics"]["queries_processed"] == 1
        assert response["analytics"]["metrics"]["revenue_queries"] == 1


def test_admin_analytics_endpoints_auth(client: TestClient):
    """Verify that analytics endpoints enforce proper role-based access control (RBAC)."""
    # 1. Login as Admin
    login_admin = client.post("/api/v1/auth/login", json={
        "email": "owner@salonai.com",
        "password": "password123"
    })
    assert login_admin.status_code == status.HTTP_200_OK
    admin_token = login_admin.json()["access_token"]

    # 2. Login as Staff
    login_staff = client.post("/api/v1/auth/login", json={
        "email": "marcus@salonai.com",
        "password": "password123"
    })
    assert login_staff.status_code == status.HTTP_200_OK
    staff_token = login_staff.json()["access_token"]

    # 3. Request restricted /analytics/revenue endpoint
    # Admin (Owner) should be authorized
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    admin_resp = client.get("/api/v1/analytics/revenue", headers=admin_headers)
    assert admin_resp.status_code == status.HTTP_200_OK
    assert admin_resp.json()["success"] is True

    # Staff should be strictly forbidden
    staff_headers = {"Authorization": f"Bearer {staff_token}"}
    staff_resp = client.get("/api/v1/analytics/revenue", headers=staff_headers)
    assert staff_resp.status_code == status.HTTP_403_FORBIDDEN
    assert "Insufficient permissions" in staff_resp.json()["detail"]


@pytest.mark.asyncio
async def test_admin_agent_chat_routing(client: TestClient):
    """Verify that /api/v1/agent/chat correctly routes queries to orchestrator under BI intent override."""
    # Login as Admin
    login_admin = client.post("/api/v1/auth/login", json={
        "email": "owner@salonai.com",
        "password": "password123"
    })
    admin_token = login_admin.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Query with intent_override='business_intelligence'
    payload = {
        "message": "Compare this month's revenue with last month",
        "session id": "session-bi-123",
        "chat history": [],
        "intent override": "business_intelligence"
    }

    # Mock the orchestrator processing
    from unittest.mock import AsyncMock, patch
    mock_orch_response = {
        "success": True,
        "response": "Here is the comparison showing a 12% revenue growth.",
        "agent_name": "Atlas_BI",
        "intent": "business_intelligence"
    }

    with patch("api.routes.agent_routes._receptionist_agent", new=AsyncMock()):
        with patch("agents.orchestrator_v3.MultiAgentOrchestrator.process", return_value=mock_orch_response) as mock_orch:
            response = client.post("/api/v1/agent/chat", json=payload, headers=headers)
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is True
            assert data["agent_name"] == "Atlas_BI"
            assert data["response"] == "Here is the comparison showing a 12% revenue growth."
            
            # Verify orchestrator was called with correct parameters
            mock_orch.assert_called_once()
            args = mock_orch.call_args[0][0]
            assert args["query"] == "Compare this month's revenue with last month"
            assert args["intent_override"] == "business_intelligence"

