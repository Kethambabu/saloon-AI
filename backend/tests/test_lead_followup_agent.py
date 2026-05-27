"""
Unit and Integration Tests for AI Lead Follow-Up Agent.
Verifies agent class properties, system prompts, conversation memory tracking,
CRM tools configuration, and processing pipelines.
"""

import os
import sys
import pytest
from unittest.mock import AsyncMock, patch

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.lead_followup_agent import LeadFollowupAgent
from autogen_agentchat.agents import AssistantAgent


def test_lead_followup_agent_initialization():
    """Verifies that Mia the AI Lead Follow-Up Agent initializes with correct prompts and tools."""
    # Initialize the agent
    agent = LeadFollowupAgent(name="Mia")

    # 1. Verify basic properties and role
    assert agent.name == "Mia"
    assert agent.role == "Lead Follow-Up Specialist"
    assert isinstance(agent.assistant, AssistantAgent)
    assert agent.model_client is not None

    # 2. Verify system message contains core CRM prompt guidelines
    sys_msg = agent.assistant._system_messages[0].content
    assert "Mia" in sys_msg
    assert "lead" in sys_msg.lower()
    assert "crm" in sys_msg.lower()
    assert "cadence" in sys_msg.lower()

    # 3. Verify that the 8 custom CRM tools wrapper functions are bound to the agent
    bound_tools = agent.assistant._tools
    assert len(bound_tools) == 8

    tool_names = [tool.name for tool in bound_tools]
    assert "find_abandoned_bookings" in tool_names
    assert "search_leads" in tool_names
    assert "register_new_lead" in tool_names
    assert "advance_lead_status" in tool_names
    assert "send_followup_reminder" in tool_names
    assert "create_personalized_message" in tool_names
    assert "view_conversion_analytics" in tool_names
    assert "view_pipeline_snapshot" in tool_names


def test_lead_followup_agent_conversation_memory():
    """Verifies that conversation memory records queries and responses accurately per session."""
    agent = LeadFollowupAgent(name="Mia")
    session_id = "test-session-123"

    # Initially empty context
    assert agent._get_memory_context(session_id) == ""

    # Store user query
    agent._store_memory(session_id, "user", "How many leads were added yesterday?")
    
    context = agent._get_memory_context(session_id)
    assert "User: How many leads were added yesterday?" in context

    # Store assistant response
    agent._store_memory(session_id, "assistant", "We added 4 new leads yesterday from Instagram.")
    
    context = agent._get_memory_context(session_id)
    assert "Assistant: We added 4 new leads yesterday from Instagram." in context

    # Clear memory
    agent.clear_memory(session_id)
    assert agent._get_memory_context(session_id) == ""


def test_lead_followup_agent_analytics():
    """Verifies that internal analytics counter tracks process interactions correctly."""
    agent = LeadFollowupAgent(name="Mia")
    
    # Verify initial stats
    analytics = agent.get_analytics()
    assert analytics["metrics"]["queries_processed"] == 0
    assert analytics["metrics"]["abandoned_scans"] == 0

    # Track some category triggers
    agent._track_analytics("queries_processed")
    agent._track_analytics("abandoned_scans")
    agent._track_analytics("abandoned_scans")

    analytics = agent.get_analytics()
    assert analytics["metrics"]["queries_processed"] == 1
    assert analytics["metrics"]["abandoned_scans"] == 2


@pytest.mark.asyncio
async def test_lead_followup_agent_process_pipeline():
    """Verifies the async process method pipelines messages and updates session memory."""
    agent = LeadFollowupAgent(name="Mia")
    session_id = "session-abc"

    # Mock the internal AutoGen AssistantAgent's run method
    mock_run_result = AsyncMock()
    mock_msg = AsyncMock()
    mock_msg.content = "I found 3 abandoned bookings for Downtown branch."
    mock_run_result.messages = [mock_msg]

    with patch.object(agent.assistant, "run", return_value=mock_run_result) as mock_run:
        response = await agent.process({
            "query": "Find abandoned bookings",
            "session_id": session_id
        })

        assert response["success"] is True
        assert response["agent_name"] == "Mia"
        assert response["response"] == "I found 3 abandoned bookings for Downtown branch."
        assert response["session_id"] == session_id
        
        # Verify that prompt got formatted and sent to agent
        mock_run.assert_called_once()
        
        # Check memory was updated
        context = agent._get_memory_context(session_id)
        assert "User: Find abandoned bookings" in context
        assert "Assistant: I found 3 abandoned bookings" in context
