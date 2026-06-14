"""
Reputation Management Agent for SalonAI Workforce Platform.
Built using Microsoft AutoGen (agentchat v0.4+ / v0.10+).
"""

import os
import time
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

# AutoGen imports
from autogen_agentchat.agents import AssistantAgent
try:
    from core.openai_client_adapter import OpenAIChatCompletionClient
except ImportError:
    try:
        from autogen_ext.models.openai import OpenAIChatCompletionClient
    except ImportError:
        from openai import OpenAI as OpenAIChatCompletionClient

# Project imports
from agents import Agent
from core.config import get_settings
from core.llm_config import get_llm_config
# review_tools imports removed to use workflows and mcp

logger = logging.getLogger(__name__)
settings = get_settings()

from rag.retriever import (
    search_salon_knowledge,
    search_reputation_memory,
)
from tools.mcp_tool import mcp_execute


REPUTATION_SYSTEM_PROMPT = """
You are Olivia, the SalonAI Reputation & Review Manager.

Responsibilities:
- Monitor and respond to customer reviews
- Analyze review sentiment and analytics
- Find and escalate critical reviews

PRIMARY DATA TOOL (use for all review lookups):
- mcp_read(resource, operation, filters, agent_name, user_context, limit)
  Use MCP for reading reviews and reputation data. Always pass agent_name='Olivia'.
  Examples:
    mcp_read(resource='reviews', operation='select', filters={}, agent_name='Olivia')
    mcp_read(resource='reviews', operation='aggregate', metric='count', group_by='sentiment', agent_name='Olivia')

TRANSACTIONAL WORKFLOWS:
- execute_transaction(action='draft_review_response'|'escalate_review', parameters={...})

Always use tools. Prefer mcp_read for all review reads.
"""

# ---- Wrapper functions defined before class so they can be bound as tools ----
def view_customer_reviews(
    customer_id: Optional[str] = None,
    staff_id: Optional[str] = None,
    sentiment: Optional[str] = None,
    rating: Optional[int] = None,
) -> str:
    """Retrieve customer reviews matching filter parameters."""
    filters = {}
    if customer_id:
        filters["customer_id"] = customer_id
    if staff_id:
        filters["staff_id"] = staff_id
    if sentiment:
        filters["sentiment"] = sentiment.upper()
    if rating:
        filters["rating"] = rating
    return str(mcp_execute(resource="reviews", operation="select", filters=filters, agent_name="Olivia"))


def view_review_analytics() -> str:
    """Generate comprehensive reputation analytics."""
    return str(mcp_execute(
        resource="reviews",
        operation="aggregate",
        metric="avg",
        agent_name="Olivia"
    ))


def find_critical_reviews() -> str:
    """Retrieve all critical sentiment reviews requiring manager review."""
    return str(mcp_execute(resource="reviews", operation="select", filters={"sentiment": "CRITICAL"}, agent_name="Olivia"))


def draft_review_response(review_id: str, custom_response: Optional[str] = None) -> str:
    """Draft or register a salon response to a specific customer review using the review workflow."""
    from workflows.review_workflow import respond_to_review_workflow
    return str(respond_to_review_workflow(review_id=review_id, custom_response=custom_response))


def view_reputation_scorecard() -> str:
    """Generate the overall reputation metrics scorecard."""
    return str(mcp_execute(
        resource="reviews",
        operation="aggregate",
        metric="count",
        group_by="sentiment",
        agent_name="Olivia"
    ))


def escalate_customer_review(review_id: str) -> str:
    """Escalate a customer review to management using the review escalation workflow."""
    from workflows.review_workflow import escalate_review_workflow
    return str(escalate_review_workflow(review_id=review_id))


class ReputationAgent(Agent):
    """
    Reputation Management Agent powered by Microsoft AutoGen.
    Manages customer reviews, analyzes sentiment, drafts responses, and escalates complaints.
    """

    def __init__(self, name: str = "Olivia", role: str = "Reputation & Review Manager"):
        super().__init__(name=name, role=role)
        logger.info(f"Initializing Reputation Agent '{name}'...")

        self._conversation_memory: Dict[str, List[Dict[str, str]]] = {}
        self._analytics: Dict[str, int] = {
            "queries_processed": 0,
            "critical_detections": 0,
            "reviews_analyzed": 0,
            "responses_generated": 0,
            "escalations_logged": 0,
            "analytics_viewed": 0,
        }

        # 1. Get centralized LLM configuration
        llm_config = get_llm_config()
        config = llm_config.get_config()
        
        logger.info(f"Using model: {config['model']}")

        # 2. Instantiate AutoGen AssistantAgent with model client
        self.model_client = OpenAIChatCompletionClient(
            model=config["model"],
            api_key=config["api_key"],
            base_url=config["base_url"],
            model_info=config["model_info"],
        )

        from tools.mcp_tool import mcp_read
        from tools.rag_unified import search_knowledge_base
        from tools.transaction_unified import execute_transaction

        # 3. Build AutoGen AssistantAgent with consolidated tool suite
        self.assistant = AssistantAgent(
            name=name,
            model_client=self.model_client,
            system_message=REPUTATION_SYSTEM_PROMPT,
            tools=[
                mcp_read,
                search_knowledge_base,
                execute_transaction,
            ],
        )

        logger.info(f"Reputation Agent '{name}' initialized with 8 tools (6 Review CRUD, 2 RAG).")

    def _get_memory_context(self, session_id: str) -> str:
        """Build conversation context string from memory for a given session."""
        history = self._conversation_memory.get(session_id, [])
        if not history:
            return ""

        context_lines = ["Here is the conversation history so far for context:"]
        for entry in history[-5:]:  # Bounded to last 5 messages to avoid token overflow
            role = entry.get("role", "user").capitalize()
            content = entry.get("content", "")
            context_lines.append(f"- {role}: {content}")
        context_lines.append("")
        return "\n".join(context_lines)

    def _store_memory(self, session_id: str, role: str, content: str) -> None:
        """Store a message in session memory."""
        if session_id not in self._conversation_memory:
            self._conversation_memory[session_id] = []
        self._conversation_memory[session_id].append({
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def clear_memory(self, session_id: str) -> None:
        """Clear conversation memory for a specific session."""
        if session_id in self._conversation_memory:
            del self._conversation_memory[session_id]
            logger.info(f"[ReputationAgent] Cleared memory for session: {session_id}")

    def _track_analytics(self, category: str) -> None:
        """Increment an analytics counter."""
        if category in self._analytics:
            self._analytics[category] += 1

    def get_analytics(self) -> Dict[str, Any]:
        """Return current analytics counters."""
        return {
            "agent_name": self.name,
            "role": self.role,
            "metrics": dict(self._analytics),
            "active_sessions": len(self._conversation_memory),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Standardized entrypoint to process natural language reputation queries.
        """
        query = input_data.get("query")
        if not query:
            return {"success": False, "error": "Input data must contain a 'query' key."}

        session_id = input_data.get("session_id", "default")
        chat_history = input_data.get("chat_history", [])

        logger.info(f"[ReputationAgent] Processing query (session={session_id}): '{query[:100]}'")
        self._track_analytics("queries_processed")
        self._track_analytics("reviews_analyzed")

        # Telemetry tracking
        query_lower = query.lower()
        if any(kw in query_lower for kw in ["critical", "negative", "bad", "1-star", "1 star", "complaint", "worst", "terrible", "rude"]):
            self._track_analytics("critical_detections")
        if any(kw in query_lower for kw in ["respond", "reply", "answer"]):
            self._track_analytics("responses_generated")
        if any(kw in query_lower for kw in ["escalate", "flag", "manager"]):
            self._track_analytics("escalations_logged")
        if any(kw in query_lower for kw in ["analytics", "distribution", "scorecard", "stats"]):
            self._track_analytics("analytics_viewed")

        try:
            full_query = ""

            # Sliced chat history
            if chat_history:
                full_query += "Here is the conversation history so far for context:\n"
                for msg in chat_history[-5:]:
                    role = msg.get("role", "user").capitalize()
                    content = msg.get("content", "")
                    full_query += f"- {role}: {content}\n"
                full_query += "\n"

            # Session memory
            memory_context = self._get_memory_context(session_id)
            if memory_context and not chat_history:
                full_query += memory_context + "\n"

            full_query += f"Latest User Message: {query}"

            # Store query
            self._store_memory(session_id, "user", query)

            # AutoGen run
            result = await self.assistant.run(task=full_query)
            response_text = result.messages[-1].content

            # Store assistant response
            self._store_memory(session_id, "assistant", response_text)

            logger.info(f"[ReputationAgent] Query processed successfully (session={session_id})")

            return {
                "success": True,
                "agent_name": self.name,
                "response": response_text,
                "session_id": session_id,
                "analytics": self.get_analytics(),
            }

        except Exception as e:
            logger.error(f"[ReputationAgent] Error processing query: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": f"Reputation Agent processing failed: {str(e)}",
            }


# ---- Orchestrator Compatibility Aliases ----

def view_customer_reviews(
    customer_id: Optional[str] = None,
    staff_id: Optional[str] = None,
    sentiment: Optional[str] = None,
    rating: Optional[int] = None,
) -> str:
    """Retrieve customer reviews matching filter parameters."""
    return get_reviews_tool(customer_id=customer_id, staff_id=staff_id, sentiment=sentiment, rating=rating)


def view_review_analytics() -> str:
    """Generate comprehensive reputation analytics."""
    return get_review_analytics_tool()


def find_critical_reviews() -> str:
    """Retrieve all critical sentiment reviews requiring manager review."""
    return get_reviews_tool(sentiment="CRITICAL")


def draft_review_response(review_id: str, custom_response: Optional[str] = None) -> str:
    """Draft or register a salon response to a specific customer review."""
    return generate_response_tool(review_id=review_id, custom_response=custom_response)


def view_reputation_scorecard() -> str:
    """Generate the overall reputation metrics scorecard."""
    return get_review_analytics_tool()


def escalate_customer_review(review_id: str) -> str:
    """Escalate a customer review to management for urgent attention."""
    return escalate_review_tool(review_id=review_id)
