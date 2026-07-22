"""
Lead Follow-Up Agent for SalonAI Workforce Platform.

Built using Microsoft AutoGen (agentchat v0.4+ / v0.10+).
Provides autonomous lead nurturing, abandoned booking recovery, conversion tracking,
and personalised follow-up message generation.

Capabilities:
    1. Detect abandoned bookings (cancelled / no-show customers not rebooked)
    2. Send follow-up reminders via email, SMS, or phone
    3. Track lead conversion pipeline (NEW → CONTACTED → CONVERTED → LOST)
    4. Generate personalised follow-up messages based on customer history
    5. Provide lead conversion analytics and pipeline recommendations

Integrations:
    - PostgreSQL CRM via SQLAlchemy (backend/tools/lead_tools.py)
    - Notification dispatch payloads (email / SMS / phone)
    - Analytics tracking with actionable recommendations
"""

import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

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
# lead_tools imports removed to use workflows and mcp
from infrastructure.rag.retriever import (
    search_salon_knowledge,
    search_customer_interactions,
    search_lead_memory,
    search_customer_memory,
)
from ai.tools.mcp_tool import mcp_execute

logger = logging.getLogger(__name__)
settings = get_settings()


# ---------------------------------------------------------------------------
# Wrapper Tools (decouple DB session injection from LLM-visible parameters)
# ---------------------------------------------------------------------------

def find_abandoned_bookings(
    branch_id: Optional[str] = None,
    lookback_days: int = 30,
) -> str:
    """
    Detect customers who cancelled or no-showed and haven't rebooked since.
    """
    logger.info(f"[LeadFollowupAgent] Tool call: find_abandoned_bookings(branch={branch_id}, days={lookback_days})")
    from ai.workflows.lead_workflow import detect_abandoned_bookings_workflow
    result = detect_abandoned_bookings_workflow(branch_id=branch_id, lookback_days=lookback_days)
    return str(result)


def search_leads(
    status_filter: Optional[str] = None,
    branch_id: Optional[str] = None,
    source_filter: Optional[str] = None,
) -> str:
    """
    Search and filter leads in the CRM database by status, branch, or acquisition source.
    """
    logger.info(f"[LeadFollowupAgent] Tool call: search_leads(status={status_filter}, branch={branch_id})")
    filters = {}
    if status_filter:
        filters["status"] = status_filter.upper()
    if branch_id:
        filters["branch_id"] = branch_id
    if source_filter:
        filters["source"] = source_filter
    return str(mcp_execute(resource="leads", operation="select", filters=filters, agent_name="Mia"))


def register_new_lead(
    first_name: str,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    last_name: Optional[str] = None,
    source: Optional[str] = None,
    branch_id: Optional[str] = None,
    notes: Optional[str] = None,
) -> str:
    """
    Register a new prospect lead in the CRM pipeline.
    """
    logger.info(f"[LeadFollowupAgent] Tool call: register_new_lead(name={first_name} {last_name})")
    from ai.workflows.lead_workflow import create_lead_workflow
    result = create_lead_workflow(
        first_name=first_name,
        email=email,
        phone=phone,
        last_name=last_name,
        source=source,
        branch_id=branch_id,
        notes=notes,
    )
    return str(result)


def advance_lead_status(
    lead_id: str,
    new_status: str,
    notes: Optional[str] = None,
) -> str:
    """
    Move a lead to the next stage in the CRM pipeline.
    """
    logger.info(f"[LeadFollowupAgent] Tool call: advance_lead_status(lead={lead_id}, status={new_status})")
    from ai.workflows.lead_workflow import advance_lead_status_workflow
    result = advance_lead_status_workflow(lead_id=lead_id, new_status=new_status, notes=notes)
    return str(result)


def send_followup_reminder(
    lead_id: str,
    channel: str,
    message: str,
    scheduled_at: Optional[str] = None,
) -> str:
    """
    Schedule and send a follow-up reminder to a lead via email, SMS, or phone.
    """
    logger.info(f"[LeadFollowupAgent] Tool call: send_followup_reminder(lead={lead_id}, channel={channel})")
    from ai.workflows.lead_workflow import create_followup_reminder_workflow
    result = create_followup_reminder_workflow(
        lead_id=lead_id,
        channel=channel,
        message=message,
        scheduled_at=scheduled_at,
    )
    return str(result)


def create_personalized_message(
    customer_id: Optional[str] = None,
    lead_id: Optional[str] = None,
    channel: str = "email",
    tone: str = "warm",
) -> str:
    """
    Generate a personalised follow-up message based on customer/lead history.
    """
    logger.info(f"[LeadFollowupAgent] Tool call: create_personalized_message(customer={customer_id}, lead={lead_id})")
    from ai.workflows.lead_workflow import generate_followup_message_workflow
    result = generate_followup_message_workflow(
        customer_id=customer_id,
        lead_id=lead_id,
        channel=channel,
        tone=tone,
    )
    return str(result)


def view_conversion_analytics(
    period_days: int = 30,
    branch_id: Optional[str] = None,
) -> str:
    """
    Get comprehensive lead conversion analytics.
    """
    logger.info(f"[LeadFollowupAgent] Tool call: view_conversion_analytics(period={period_days}d)")
    return str(mcp_execute(
        resource="leads",
        operation="aggregate",
        metric="group_by",
        group_by="status",
        agent_name="Mia"
    ))


def view_pipeline_snapshot(
    branch_id: Optional[str] = None,
) -> str:
    """
    Get a quick snapshot of the current lead pipeline.
    """
    logger.info(f"[LeadFollowupAgent] Tool call: view_pipeline_snapshot(branch={branch_id})")
    return str(mcp_execute(
        resource="leads",
        operation="aggregate",
        metric="count",
        group_by="status",
        agent_name="Mia"
    ))


# ---------------------------------------------------------------------------
# System Prompt
# ---------------------------------------------------------------------------
LEAD_FOLLOWUP_SYSTEM_PROMPT = """
You are Mia, the SalonAI Lead Follow-up Specialist.

Responsibilities:
- Recover abandoned bookings and nurture leads into appointments
- Send follow-up reminders and personalized messages
- Track and analyze lead conversion pipeline
- Recommend best leads to prioritize

PRIMARY DATA TOOL (use for all lead/customer lookups):
- mcp_read(resource, operation, filters, agent_name, user_context, limit)
  Use MCP for reading leads, customers, branches, and summaries. Always pass agent_name='Mia'.
  Examples:
    mcp_read(resource='leads', operation='select', filters={'status': 'NEW'}, agent_name='Mia')
    mcp_read(resource='leads', operation='aggregate', metric='count', group_by='status', agent_name='Mia')

TRANSACTIONAL WORKFLOWS:
- execute_transaction(action='register_lead'|'advance_lead_status'|'send_followup'|'create_personalized_message', parameters={...})

Always use tools. Prefer mcp_read for database reads.
"""


# ---------------------------------------------------------------------------
# Agent Class
# ---------------------------------------------------------------------------
class LeadFollowupAgent(Agent):
    """
    Lead Follow-Up Agent powered by Microsoft AutoGen v0.4+ and OpenAI/Groq endpoints.
    Provides autonomous CRM lead management, abandoned booking recovery,
    personalised outreach, and conversion analytics.
    """

    def __init__(self, name: str = "Mia", role: str = "Lead Follow-Up Specialist"):
        super().__init__(name=name, role=role)
        logger.info(f"Initializing Lead Follow-Up Agent '{name}'...")

        # Conversation memory: stores interaction history per session
        self._conversation_memory: Dict[str, List[Dict[str, str]]] = {}

        # Analytics tracker: counts tool invocations for observability
        self._analytics: Dict[str, int] = {
            "queries_processed": 0,
            "abandoned_scans": 0,
            "leads_searched": 0,
            "leads_created": 0,
            "followups_sent": 0,
            "messages_generated": 0,
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
            system_message=LEAD_FOLLOWUP_SYSTEM_PROMPT,
            tools=[
                mcp_read,
                search_knowledge_base,
                execute_transaction,
            ],
        )

        logger.info(f"Lead Follow-Up Agent '{name}' initialized with 12 tools (8 CRM, 4 RAG/Memory).")

    # ------------------------------------------------------------------
    # Conversation Memory
    # ------------------------------------------------------------------
    def _get_memory_context(self, session_id: str) -> str:
        """Build conversation context string from memory for a given session."""
        history = self._conversation_memory.get(session_id, [])
        if not history:
            return ""

        context_lines = ["Here is the conversation history so far for context:"]
        for entry in history[-10:]:  # Last 10 exchanges to keep context window manageable
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
            logger.info(f"[LeadFollowupAgent] Cleared memory for session: {session_id}")

    # ------------------------------------------------------------------
    # Analytics Tracking
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Standardized entrypoint to process lead management queries.

        Args:
            input_data: Dictionary containing:
                - "query": The user's natural language message (required).
                - "session_id": Optional session identifier for conversation memory.
                - "chat_history": Optional list of prior messages for context.

        Returns:
            Dictionary containing:
                - "success": True/False
                - "response": Conversational response text from the agent
                - "agent_name": Name of this agent
                - "analytics": Current analytics counters
        """
        query = input_data.get("query")
        if not query:
            return {"success": False, "error": "Input data must contain a 'query' key."}

        session_id = input_data.get("session_id", "default")
        chat_history = input_data.get("chat_history", [])

        logger.info(f"[LeadFollowupAgent] Processing query (session={session_id}): '{query[:100]}'")
        self._track_analytics("queries_processed")

        # Track which tools are likely to be invoked (for observability)
        query_lower = query.lower()
        if any(kw in query_lower for kw in ["abandon", "cancel", "no-show", "no show", "churn"]):
            self._track_analytics("abandoned_scans")
        if any(kw in query_lower for kw in ["search", "find", "list", "show lead", "pipeline"]):
            self._track_analytics("leads_searched")
        if any(kw in query_lower for kw in ["create lead", "register", "new lead", "add lead"]):
            self._track_analytics("leads_created")
        if any(kw in query_lower for kw in ["follow up", "followup", "remind", "send", "reach out"]):
            self._track_analytics("followups_sent")
        if any(kw in query_lower for kw in ["message", "draft", "compose", "template", "write"]):
            self._track_analytics("messages_generated")
        if any(kw in query_lower for kw in ["analytic", "conversion", "metric", "report", "pipeline"]):
            self._track_analytics("analytics_viewed")

        try:
            # Build full query with conversation context
            full_query = ""

            # Prepend chat history if provided
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

            # Store user message in memory
            self._store_memory(session_id, "user", query)

            # Execute agent run
            result = await self.assistant.run(task=full_query)

            # Extract final response
            response_text = result.messages[-1].content

            # Store assistant response in memory
            self._store_memory(session_id, "assistant", response_text)

            logger.info(f"[LeadFollowupAgent] Query processed successfully (session={session_id})")

            return {
                "success": True,
                "agent_name": self.name,
                "response": response_text,
                "session_id": session_id,
                "analytics": self.get_analytics(),
            }

        except Exception as e:
            logger.error(f"[LeadFollowupAgent] Error processing query: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": f"Lead Follow-Up Agent processing failed: {str(e)}",
            }

