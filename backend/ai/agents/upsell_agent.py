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
from ai.agents import Agent
from core.config import get_settings
from core.llm_config import get_llm_config
# recommendation_tools imports removed to use workflows and mcp
from infrastructure.rag.receptionist_rag_tools import (
    get_active_offers,
    search_receptionist_knowledge,
)
from infrastructure.rag.retriever import (
    search_customer_memory,
    search_upsell_memory,
)
from ai.tools.mcp_tool import mcp_execute

logger = logging.getLogger(__name__)
settings = get_settings()


UPSELL_SYSTEM_PROMPT = """You are Mia, the helpful AI Upsell & Cross-Sell Specialist at SalonAI Workforce Platform.

Your job is to increase revenue per booking, suggest add-on services, analyze customer purchase history, recommend premium upgrades, and track recommendation performance.

PRIMARY DATA TOOL (use for all customer/service/appointment lookups):
- mcp_read(resource, operation, filters, agent_name, user_context, limit)
  Use MCP for reading customer history, services, and appointments. Always pass agent_name='Mia'.
  Examples:
    mcp_read(resource='recommendations', filters={'customer_id': '<id>'})
    mcp_read(resource='upsell_analytics')

TRANSACTIONAL WORKFLOWS:
- execute_transaction(action='accept_upsell_recommendation'|'reject_upsell_recommendation', parameters={...})

SEMANTIC MEMORY & POLICY RAG:
- search_knowledge_base(domain='policies'|'customer_styling'|'upsell_memory', query=...)

Always use available RAG and memory tools before responding. Prefer mcp_read for all database reads. Never guess or hallucinate recommendations or offers.
"""

# ---- Wrapper functions defined before class so they can be bound as tools ----
def get_customer_recommendations(customer_id: str) -> str:
    """Fetch personalized service recommendations for a customer."""
    from ai.workflows.upsell_workflow import get_customer_recommendations_workflow
    return str(get_customer_recommendations_workflow(customer_id))

def accept_recommendation(customer_id: str, service_id: str, appointment_id: Optional[str] = None) -> str:
    """Accept an upsell recommendation."""
    from ai.workflows.upsell_workflow import accept_recommendation_workflow
    return str(accept_recommendation_workflow(customer_id, service_id, appointment_id))

def reject_recommendation(customer_id: str, service_id: str, appointment_id: Optional[str] = None) -> str:
    """Reject/dismiss an upsell recommendation."""
    from ai.workflows.upsell_workflow import reject_recommendation_workflow
    return str(reject_recommendation_workflow(customer_id, service_id, appointment_id))

def get_upsell_analytics() -> str:
    """Retrieve upsell analytics scorecard."""
    from ai.workflows.upsell_workflow import get_upsell_analytics_workflow
    return str(get_upsell_analytics_workflow())



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

        from ai.tools.mcp_tool import mcp_read
        from infrastructure.rag.rag_unified import search_knowledge_base
        from ai.tools.transaction_dispatcher import execute_transaction

        # 3. Build AutoGen AssistantAgent with consolidated tool suite
        self.assistant = AssistantAgent(
            name=name,
            model_client=self.model_client,
            system_message=UPSELL_SYSTEM_PROMPT,
            tools=[
                mcp_read,
                search_knowledge_base,
                execute_transaction,
            ],
        )

        logger.info(f"Upsell Agent '{name}' initialized with 8 recommendation tools.")

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

