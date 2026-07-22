"""
Staff Assistant AI Agent for SalonAI Workforce Platform.
Built using Microsoft AutoGen (agentchat v0.4+ / v0.10+).

Provides staff dashboard operations, schedule lookups, performance summaries,
and policy RAG context matching to salon employees.
"""

import os
import time
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

# AutoGen modern imports
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

# Import staff specific database tools and RAG tools
from application.services.staff_service import (
    get_schedule,
    get_today_schedule,
    get_next_customer,
    get_customer_history,
    get_customer_preferences,
    get_staff_revenue,
    get_staff_performance,
    get_pending_appointments,
    create_leave_request,
    send_customer_reminders,
    recommend_services,
    search_salon_knowledge,
    search_customer_interactions,
    search_all_context
)
from infrastructure.rag.retriever import search_staff_memory, search_customer_memory
from ai.tools.mcp_tool import mcp_execute

logger = logging.getLogger(__name__)
settings = get_settings()

STAFF_SYSTEM_PROMPT = """You are Atlas, the helpful AI Staff Productivity Assistant at SalonAI Workforce Platform.

Your job is to support salon staff members in managing their daily operations, schedules, appointments, customer histories, performance analytics, and leave requests.

Always retrieve information using the database tools provided before answering.
Never guess or hallucinate appointments, customer details, leaves, or ratings.

PRIMARY DATA TOOL (use this for all database reads):
- mcp_read(resource, operation, filters, agent_name, user_context, limit) — Use MCP for all schedule, performance, and appointment lookups. Always pass agent_name='Atlas'.
  Examples:
    mcp_read(resource='schedule', filters={'staff_id': '<your_staff_id>', 'date': '2026-06-10'})
    mcp_read(resource='today_schedule', filters={'staff_id': '<your_staff_id>'})
    mcp_read(resource='staff_revenue', filters={'staff_id': '<your_staff_id>'})
    mcp_read(resource='staff_performance', filters={'staff_id': '<your_staff_id>'})
    mcp_read(resource='customer_preferences', filters={'customer_name': '<name>'})
    mcp_read(resource='pending_appointments', filters={'staff_id': '<your_staff_id>'})

TRANSACTIONAL WORKFLOWS:
- execute_transaction(action='create_leave_request'|'send_customer_reminders', parameters={...})

SEMANTIC MEMORY & POLICY RAG:
- search_knowledge_base(domain='policies'|'interactions'|'staff_memory'|'customer_styling', query=...)

Always respond professionally. Format data in clean readable tables or bullet points using Markdown. CRITICAL: NEVER output raw JSON or python dicts directly. Present all information in plain text or formatted tables.
"""


class StaffAssistantAgent(Agent):
    """
    Staff Assistant AI Agent powered by Microsoft AutoGen v0.4+.
    Enables staff members to query schedules, customer preferences, log leaves,
    and track personal performance metrics.
    """
    CURRENT_QUERY_CONTEXT: str = ""

    def __init__(self, name: str = "Atlas", role: str = "Staff Productivity Assistant"):
        super().__init__(name=name, role=role)
        logger.info(f"Initializing Staff Assistant Agent '{name}'...")

        self._conversation_memory: Dict[str, List[Dict[str, str]]] = {}
        self._analytics: Dict[str, int] = {
            "queries_processed": 0,
            "schedule_queries": 0,
            "performance_queries": 0,
            "leave_requests": 0,
            "rag_lookups": 0,
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

        from ai.tools.mcp_tool import mcp_read
        from infrastructure.rag.rag_unified import search_knowledge_base
        from ai.tools.transaction_dispatcher import execute_transaction

        # 3. Build AutoGen AssistantAgent with consolidated tool suite
        self.assistant = AssistantAgent(
            name=name,
            model_client=self.model_client,
            system_message=STAFF_SYSTEM_PROMPT,
            tools=[
                mcp_read,
                search_knowledge_base,
                execute_transaction,
            ],
        )

        logger.info(f"Staff Assistant Agent '{name}' initialized with 15 tools.")

    def _get_memory_context(self, session_id: str) -> str:
        """Build conversation context string from memory for a given session."""
        history = self._conversation_memory.get(session_id, [])
        if not history:
            return ""

        context_lines = ["Here is the conversation history so far for context:"]
        for entry in history[-5:]:  # Keep context bounded
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
            logger.info(f"[StaffAssistantAgent] Cleared memory for session: {session_id}")

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
        Standardized entrypoint to process staff productivity and schedule queries.
        """
        query = input_data.get("query")
        if not query:
            return {"success": False, "error": "Input data must contain a 'query' key."}

        StaffAssistantAgent.CURRENT_QUERY_CONTEXT = query
        try:
            from core.query_context import set_query_context
            set_query_context(query)
        except Exception as qe:
            logger.warning(f"Failed to set query context: {qe}")
        session_id = input_data.get("session_id", "default")
        chat_history = input_data.get("chat_history", [])

        logger.info(f"[StaffAssistantAgent] Processing query (session={session_id}): '{query[:100]}'")
        self._track_analytics("queries_processed")

        # Telemetry updates based on keywords
        query_lower = query.lower()
        if any(kw in query_lower for kw in ["schedule", "appointment", "calendar", "today"]):
            self._track_analytics("schedule_queries")
        if any(kw in query_lower for kw in ["performance", "rating", "revenue", "completed"]):
            self._track_analytics("performance_queries")
        if any(kw in query_lower for kw in ["leave", "holiday", "off"]):
            self._track_analytics("leave_requests")
        if any(kw in query_lower for kw in ["policy", "refund", "pricing", "sop", "rag"]):
            self._track_analytics("rag_lookups")

        try:
            full_query = ""

            # Prepend sliced chat history
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

            # Extract response text using robust reverse search
            response_text = ""
            for msg in reversed(result.messages):
                msg_type = type(msg).__name__
                source = getattr(msg, "source", getattr(msg, "sender", ""))
                content = getattr(msg, "content", None)
                
                # Check if this is a conversational text message from the specialist agent
                if msg_type == "TextMessage" and source == self.name and content and isinstance(content, str) and len(content.strip()) > 0:
                    response_text = content.strip()
                    break
                    
            # Fallback 1: Any TextMessage from a non-user sender
            if not response_text:
                for msg in reversed(result.messages):
                    msg_type = type(msg).__name__
                    source = getattr(msg, "source", getattr(msg, "sender", ""))
                    content = getattr(msg, "content", None)
                    if msg_type == "TextMessage" and source != "user" and content and isinstance(content, str) and len(content.strip()) > 0:
                        response_text = content.strip()
                        break
                        
            # Fallback 2: Any last non-empty string message content in the history
            if not response_text:
                for msg in reversed(result.messages):
                    content = getattr(msg, "content", None)
                    if content and isinstance(content, str) and len(content.strip()) > 0:
                        response_text = content.strip()
                        break

            if not response_text:
                response_text = "I've processed your request. Is there anything else I can help with?"

            # Store assistant response in memory
            self._store_memory(session_id, "assistant", response_text)

            logger.info(f"[StaffAssistantAgent] Query processed successfully (session={session_id})")

            return {
                "success": True,
                "agent_name": self.name,
                "response": response_text,
                "session_id": session_id,
                "analytics": self.get_analytics(),
            }

        except Exception as e:
            logger.error(f"[StaffAssistantAgent] Error processing query: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": f"Staff Assistant Agent processing failed: {str(e)}",
            }

