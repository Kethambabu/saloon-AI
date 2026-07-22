"""
Unit and Integration Tests for AI Receptionist Agent.
Verifies agent class properties, prompt bounds, and tool binding configuration.
"""

import os
import sys
import pytest

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ai.agents.receptionist_agent import ReceptionistAgent
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

    # 4. Verify that the consolidated tools are bound to the agent
    bound_tools = receptionist.assistant._tools
    assert len(bound_tools) == 3

    tool_names = [tool.name for tool in bound_tools]
    assert "mcp_read" in tool_names
    assert "search_knowledge_base" in tool_names
    assert "execute_transaction" in tool_names

    print("AI Receptionist Agent initialized and configured perfectly!")


def test_model_tier_priority():
    """Verifies that Hugging Face is primary, Groq is fallback 1, and Gemini is next fallback."""
    from ai.agents.receptionist_agent import sort_queue_cheap_first

    unordered_queue = [
        {"provider": "gemini", "model": "gemini-2.0-flash-lite"},
        {"provider": "groq", "model": "llama-3.1-8b-instant"},
        {"provider": "huggingface", "model": "Qwen/Qwen2.5-72B-Instruct"},
        {"provider": "gemini", "model": "gemini-2.0-flash"},
        {"provider": "groq", "model": "llama-3.3-70b-versatile"},
    ]

    sorted_queue = sort_queue_cheap_first(unordered_queue)

    providers = [item["provider"] for item in sorted_queue]
    # Primary: Hugging Face first
    assert providers[0] == "huggingface"
    # Fallback 1: Groq second and third
    assert providers[1] == "groq"
    assert providers[2] == "groq"
    # Fallback 2: Gemini fourth and fifth
    assert providers[3] == "gemini"
    assert providers[4] == "gemini"


def test_print_supabase_status():
    """Verifies that print_supabase_status runs without error and returns status dictionary."""
    from ai.agents.receptionist_agent import print_supabase_status

    status = print_supabase_status()
    assert isinstance(status, dict)
    assert "db_configured" in status or "error" in status


