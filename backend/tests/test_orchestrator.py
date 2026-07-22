"""
Unit and Integration Tests for Multi-Agent Orchestrator.
Verifies intent classification, agent building factory, and conversational routing.
"""

import os
import sys
import pytest
from unittest.mock import AsyncMock, patch

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ai.orchestrator import MultiAgentOrchestrator, AgentIntent, classify_intent_rule_based
from autogen_agentchat.agents import AssistantAgent


def test_classify_intent_rule_based():
    """Verifies that the rule-based intent classifier correctly matches keywords."""
    # Bookings keywords
    assert classify_intent_rule_based("I want to book an appointment") == AgentIntent.BOOKING
    assert classify_intent_rule_based("reschedule my haircut please") == AgentIntent.BOOKING

    # Lead follow-up keywords
    assert classify_intent_rule_based("show me the lead pipeline") == AgentIntent.LEAD_FOLLOWUP
    assert classify_intent_rule_based("contact prospect and follow up") == AgentIntent.LEAD_FOLLOWUP

    # Upsell keywords
    assert classify_intent_rule_based("recommend an upgrade for Alice") == AgentIntent.UPSELL
    assert classify_intent_rule_based("create promotion discount combo") == AgentIntent.UPSELL

    # Reputation keywords
    assert classify_intent_rule_based("get the review summary for Downtown") == AgentIntent.REPUTATION
    assert classify_intent_rule_based("respond to Google review") == AgentIntent.REPUTATION

    # BI keywords
    assert classify_intent_rule_based("what is our revenue report?") == AgentIntent.BUSINESS_INTELLIGENCE
    assert classify_intent_rule_based("staff utilisation metrics") == AgentIntent.BUSINESS_INTELLIGENCE

    # Ambiguous keyword
    assert classify_intent_rule_based("hello how are you?") == AgentIntent.UNKNOWN


def test_orchestrator_agent_initialization():
    """Verifies that the Multi-Agent Orchestrator instantiates all 5 specialist agents correctly."""
    orchestrator = MultiAgentOrchestrator(name="Orchestrator")

    assert orchestrator.name == "Orchestrator"
    assert orchestrator.role == "Multi-Agent Coordinator"
    assert isinstance(orchestrator.classifier, AssistantAgent)

    # Verify that all 5 specialist agents are created and registered in the orchestrator
    assert len(orchestrator.agents) == 5
    assert AgentIntent.BOOKING in orchestrator.agents
    assert AgentIntent.LEAD_FOLLOWUP in orchestrator.agents
    assert AgentIntent.UPSELL in orchestrator.agents
    assert AgentIntent.REPUTATION in orchestrator.agents
    assert AgentIntent.BUSINESS_INTELLIGENCE in orchestrator.agents

    # Verify name tags of some agents
    assert orchestrator.agents[AgentIntent.BOOKING].name == "Clara_Receptionist"
    assert orchestrator.agents[AgentIntent.LEAD_FOLLOWUP].name == "Mia_LeadFollowup"
    assert orchestrator.agents[AgentIntent.BUSINESS_INTELLIGENCE].name == "Atlas_BI"

    # Verify list_agents metadata
    agent_list = orchestrator.list_agents()
    assert len(agent_list) == 5
    intents = [item["intent"] for item in agent_list]
    assert "booking" in intents
    assert "business_intelligence" in intents


@pytest.mark.asyncio
async def test_orchestrator_classify_intent_fallback():
    """Verifies that the orchestrator falls back to LLM intent classification if keywords are inconclusive."""
    orchestrator = MultiAgentOrchestrator(name="Orchestrator")

    # Mock the intent classifier assistant agent run response
    mock_classifier_result = AsyncMock()
    mock_msg = AsyncMock()
    mock_msg.content = "business_intelligence"
    mock_classifier_result.messages = [mock_msg]

    with patch.object(orchestrator.classifier, "run", return_value=mock_classifier_result) as mock_run:
        # A query with no keywords
        intent = await orchestrator._classify_intent("Calculate something completely custom for me please.")
        
        # Verify it falls back to the LLM classifier and parses output correctly
        mock_run.assert_called_once()
        assert intent == AgentIntent.BUSINESS_INTELLIGENCE


@pytest.mark.asyncio
async def test_orchestrator_process_routing():
    """Verifies that process() routes queries based on intent and returns formatted execution results."""
    orchestrator = MultiAgentOrchestrator(name="Orchestrator")

    # Mock receptionist group chat execution
    with patch.object(orchestrator, "_run_group_chat", return_value="Booking completed successfully.") as mock_chat:
        # Process a booking query (determines booking intent via rule-based keyword)
        response = await orchestrator.process({"query": "Book an appointment for tomorrow"})

        assert response["success"] is True
        assert response["agent_name"] == "Clara_Receptionist"
        assert response["intent"] == "booking"
        assert response["response"] == "Booking completed successfully."

        # Verify correct agent object was passed to group chat runner
        mock_chat.assert_called_once_with(orchestrator.agents[AgentIntent.BOOKING], "Book an appointment for tomorrow")


@pytest.mark.asyncio
async def test_orchestrator_process_intent_override():
    """Verifies that process() respects manual intent overrides to force specific routing."""
    orchestrator = MultiAgentOrchestrator(name="Orchestrator")

    with patch.object(orchestrator, "_run_group_chat", return_value="Here are your upsell offers.") as mock_chat:
        # User query is booking-oriented but we force it to UPSELL
        response = await orchestrator.process({
            "query": "Book an appointment",
            "intent_override": "upsell"
        })

        assert response["success"] is True
        assert response["agent_name"] == "Max_Upsell"
        assert response["intent"] == "upsell"
        assert response["response"] == "Here are your upsell offers."

        mock_chat.assert_called_once_with(orchestrator.agents[AgentIntent.UPSELL], "Book an appointment")


@pytest.mark.asyncio
async def test_orchestrator_intent_override_blocked_for_disallowed_role():
    """A CUSTOMER-role caller must NOT be able to use the client-supplied
    intent_override field to self-elevate into a restricted agent
    (e.g. BUSINESS_INTELLIGENCE) — it should be demoted to BOOKING exactly
    like any other role-disallowed intent resolution."""
    orchestrator = MultiAgentOrchestrator(name="Orchestrator")

    with patch.object(orchestrator, "_run_group_chat", return_value="Sure, let's get you booked.") as mock_chat:
        response = await orchestrator.process({
            "query": "Book an appointment",
            "intent_override": "business_intelligence",
            "user_role": "CUSTOMER",
        })

        assert response["success"] is True
        assert response["agent_name"] == "Clara_Receptionist"
        assert response["intent"] == "booking"

        mock_chat.assert_called_once_with(orchestrator.agents[AgentIntent.BOOKING], "Book an appointment")


@pytest.mark.asyncio
async def test_orchestrator_intent_override_allowed_for_privileged_role():
    """Sanity check: the same override still works for a role that IS
    permitted to reach BUSINESS_INTELLIGENCE, so the fix only tightens the
    disallowed case rather than breaking the override feature outright."""
    orchestrator = MultiAgentOrchestrator(name="Orchestrator")

    with patch.object(orchestrator, "_run_group_chat", return_value="Here is the dashboard.") as mock_chat:
        response = await orchestrator.process({
            "query": "Book an appointment",
            "intent_override": "business_intelligence",
            "user_role": "OWNER",
        })

        assert response["success"] is True
        assert response["agent_name"] == "Atlas_BI"
        assert response["intent"] == "business_intelligence"

        mock_chat.assert_called_once_with(orchestrator.agents[AgentIntent.BUSINESS_INTELLIGENCE], "Book an appointment")

