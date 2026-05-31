"""
Unit and Integration Tests for AI Receptionist Agent.
Verifies agent class properties, prompt bounds, and tool binding configuration.
"""

import os
import sys
import pytest

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.receptionist_agent import ReceptionistAgent
from autogen_agentchat.agents import AssistantAgent


def test_receptionist_agent_initialization():
    """Verifies that Clara the AI Receptionist Agent initializes with the correct prompt and tools."""
    # Initialize the agent
    receptionist = ReceptionistAgent(name="Clara")

    # 1. Verify inheritance and naming
    assert receptionist.name == "Clara"
    assert receptionist.role == "AI Salon Receptionist"
    assert isinstance(receptionist.assistant, AssistantAgent)

    # 2. Verify model client is successfully attached
    assert receptionist.model_client is not None

    # 3. Verify system message contains the core Receptionist prompt guidelines
    sys_msg = receptionist.assistant._system_messages[0].content
    assert "Clara" in sys_msg
    assert "receptionist" in sys_msg.lower()
    assert "never invent data" in sys_msg.lower()
    assert "tool execution is mandatory" in sys_msg.lower()

    # 4. Verify that the 5 custom booking tools wrapper functions are bound to the agent
    bound_tools = receptionist.assistant._tools
    assert len(bound_tools) == 9

    tool_names = [tool.name for tool in bound_tools]
    assert "check_stylist_availability" in tool_names
    assert "book_new_appointment" in tool_names
    assert "cancel_existing_appointment" in tool_names
    assert "reschedule_existing_appointment" in tool_names
    assert "check_customer_booking_history" in tool_names

    print("AI Receptionist Agent initialized and configured perfectly!")
