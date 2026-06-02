"""
Upsell & Recommendation Agent for SalonAI Workforce Platform.
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
from tools.recommendation_tools import (
    get_customer_recommendations_tool,
    accept_recommendation_tool,
    reject_recommendation_tool,
    get_upsell_analytics_tool,
)

logger = logging.getLogger(__name__)
settings = get_settings()


UPSELL_SYSTEM_PROMPT = """
You are SalonAI Upsell Agent.

Responsibilities:

- Increase revenue per booking
- Suggest add-on services
- Analyze customer purchase history
- Recommend premium upgrades
- Track recommendation performance

Always use available tools.
"""


class UpsellAgent(Agent):
    """
    Upsell & Recommendation Agent powered by Microsoft AutoGen.
    Suggests high-value service add-ons and benchmarks upsell conversion metrics.
    """

    def __init__(self, name: str = "Mia", role: str = "Upsell Specialist"):
        super().__init__(name=name, role=role)
        logger.info(f"Initializing Upsell & Recommendation Agent '{name}'...")

        self._conversation_memory: Dict[str, List[Dict[str, str]]] = {}
        self._analytics: Dict[str, int] = {
            "queries_processed": 0,
            "recommendations_served": 0,
            "recommendations_accepted": 0,
            "analytics_viewed": 0,
        }

        # 1. Get centralized LLM configuration
        llm_config = get_llm_config()
        config = llm_config.get_config()
        
        logger.info(f"Using model: {config['model']}")

        # 2. Instantiate AutoGen AssistantAgent with system prompt and tools
        self.model_client = OpenAIChatCompletionClient(
            model=config["model"],
            api_key=config["api_key"],
            base_url=config["base_url"],
            model_info=config["model_info"],
        )

        # 3. Build AutoGen AssistantAgent with full upsell tool suite
        self.assistant = AssistantAgent(
            name=name,
            model_client=self.model_client,
            system_message=UPSELL_SYSTEM_PROMPT,
            tools=[
                get_customer_recommendations_tool,
                accept_recommendation_tool,
                reject_recommendation_tool,
                get_upsell_analytics_tool,
            ],
        )

        logger.info(f"Upsell Agent '{name}' initialized with 4 recommendation tools.")

    def _get_memory_context(self, session_id: str) -> str:
        """Build conversation context string from memory for a given session."""
        history = self._conversation_memory.get(session_id, [])
        if not history:
            return ""

        context_lines = ["Here is the conversation history so far for context:"]
        for entry in history[-5:]:  # Kept bounded to manage prompt tokens
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
            logger.info(f"[UpsellAgent] Cleared memory for session: {session_id}")

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
        Standardized entrypoint to process natural language recommendation/upsell queries.
        """
        query = input_data.get("query")
        if not query:
            return {"success": False, "error": "Input data must contain a 'query' key."}

        session_id = input_data.get("session_id", "default")
        chat_history = input_data.get("chat_history", [])

        logger.info(f"[UpsellAgent] Processing query (session={session_id}): '{query[:100]}'")
        self._track_analytics("queries_processed")

        # Telemetry tracking based on query keywords
        query_lower = query.lower()
        if any(kw in query_lower for kw in ["recommend", "suggest", "offer"]):
            self._track_analytics("recommendations_served")
        if any(kw in query_lower for kw in ["accept", "add service", "yes"]):
            self._track_analytics("recommendations_accepted")
        if any(kw in query_lower for kw in ["analytics", "revenue", "acceptance"]):
            self._track_analytics("analytics_viewed")

        try:
            full_query = ""

            # Prepend chat history limited to last 5 messages to avoid token overflow
            if chat_history:
                full_query += "Here is the conversation history so far for context:\n"
                for msg in chat_history[-5:]:
                    role = msg.get("role", "user").capitalize()
                    content = msg.get("content", "")
                    full_query += f"- {role}: {content}\n"
                full_query += "\n"

            # Prepend session memory
            memory_context = self._get_memory_context(session_id)
            if memory_context and not chat_history:
                full_query += memory_context + "\n"

            full_query += f"Latest User Message: {query}"

            # Store user query in memory
            self._store_memory(session_id, "user", query)

            # Execute AutoGen run task
            result = await self.assistant.run(task=full_query)

            # Extract response text
            response_text = result.messages[-1].content

            # Store assistant response in memory
            self._store_memory(session_id, "assistant", response_text)

            logger.info(f"[UpsellAgent] Query processed successfully (session={session_id})")

            return {
                "success": True,
                "agent_name": self.name,
                "response": response_text,
                "session_id": session_id,
                "analytics": self.get_analytics(),
            }

        except Exception as e:
            logger.error(f"[UpsellAgent] Error processing query: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": f"Upsell Agent processing failed: {str(e)}",
            }
