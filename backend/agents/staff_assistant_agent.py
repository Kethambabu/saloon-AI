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
from agents import Agent
from core.config import get_settings
from core.llm_config import get_llm_config

# Import staff specific database tools and RAG tools
from tools.staff_tools import (
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

logger = logging.getLogger(__name__)
settings = get_settings()

STAFF_SYSTEM_PROMPT = """You are Atlas, the helpful AI Staff Productivity Assistant at SalonAI Workforce Platform.

Your job is to support salon staff members in managing their daily operations, schedules, appointments, customer histories, performance analytics, and leave requests.

Always retrieve information using the database tools provided before answering.
Never guess or hallucinate appointments, customer details, leaves, or ratings.
Provide personalized service recommendations using customer history or active upsell rule tools.

Available tools:
1. get_today_schedule(staff_id: str) - Retrieve list of appointments for today.
2. get_next_customer(staff_id: str) - Find details of the next customer scheduled.
3. get_customer_history(customer_name: str) - Find historical appointments, spend, and ratings for a customer.
4. get_customer_preferences(customer_name: str) - View formula styling details or notes from past appointments.
5. get_staff_revenue(staff_id: str) - Calculate total career and monthly revenue generated.
6. get_staff_performance(staff_id: str) - Review completions, cancellations, ratings, and stats.
7. get_pending_appointments(staff_id: str) - List appointments waiting for confirmation.
8. create_leave_request(staff_id: str, leave_date: str, reason: Optional[str]) - Submit a leave request on YYYY-MM-DD.
9. send_customer_reminders(staff_id: str) - Send WhatsApp/SMS notifications to today's appointments.
10. recommend_services(customer_id: str) - Retrieve matching service upsells for a customer.
11. search_salon_knowledge(query: str, category: Optional[str]) - Search salon policy, safety, and SOP documents.
12. search_customer_interactions(query: str, doc_type: Optional[str], customer_name: Optional[str]) - Search customer interactions RAG base.
13. search_all_context(query: str) - General RAG search across knowledge and interactions.

Always respond professionally, clearly, and constructively. When displaying customer history, schedule, or performance data, format it in clean, readable tables or bullet points using Markdown.
"""


class StaffAssistantAgent(Agent):
    """
    Staff Assistant AI Agent powered by Microsoft AutoGen v0.4+.
    Enables staff members to query schedules, customer preferences, log leaves,
    and track personal performance metrics.
    """

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

        # 3. Build AutoGen AssistantAgent with full staff tool suite
        self.assistant = AssistantAgent(
            name=name,
            model_client=self.model_client,
            system_message=STAFF_SYSTEM_PROMPT,
            tools=[
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
            ],
        )

        logger.info(f"Staff Assistant Agent '{name}' initialized with 13 tools.")

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

            # Extract response text
            response_text = result.messages[-1].content

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
