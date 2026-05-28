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
from autogen_ext.models.openai import OpenAIChatCompletionClient

# Project imports
from agents import Agent
from core.config import get_settings
from tools.lead_tools import (
    detect_abandoned_bookings,
    get_all_leads,
    create_lead,
    update_lead_status,
    create_followup_reminder,
    generate_followup_message,
    get_lead_conversion_analytics,
    get_lead_pipeline_summary,
)

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
    These represent high-value re-engagement opportunities.

    Args:
        branch_id: Optional UUID string of a specific branch. Omit for all branches.
        lookback_days: How many days back to scan for abandoned bookings (default 30).
    """
    logger.info(f"[LeadFollowupAgent] Tool call: find_abandoned_bookings(branch={branch_id}, days={lookback_days})")
    result = detect_abandoned_bookings(branch_id=branch_id, lookback_days=lookback_days)
    return str(result)


def search_leads(
    status_filter: Optional[str] = None,
    branch_id: Optional[str] = None,
    source_filter: Optional[str] = None,
) -> str:
    """
    Search and filter leads in the CRM database by status, branch, or acquisition source.

    Args:
        status_filter: Filter by lead status: 'NEW', 'CONTACTED', 'CONVERTED', or 'LOST'. Omit for all.
        branch_id: Optional UUID string of a branch to filter by.
        source_filter: Filter by lead source (e.g. 'Instagram Ad', 'Website Form', 'Referral').
    """
    logger.info(f"[LeadFollowupAgent] Tool call: search_leads(status={status_filter}, branch={branch_id}, source={source_filter})")
    result = get_all_leads(status_filter=status_filter, branch_id=branch_id, source_filter=source_filter)
    return str(result)


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

    Args:
        first_name: Lead's first name (required).
        email: Email address for follow-up.
        phone: Phone number for SMS/call follow-up.
        last_name: Last name (optional).
        source: How they found us (e.g. 'Instagram Ad', 'Walk-in', 'Referral', 'Website Form').
        branch_id: UUID string of the interested salon branch.
        notes: Additional notes about the inquiry or interest.
    """
    logger.info(f"[LeadFollowupAgent] Tool call: register_new_lead(name={first_name} {last_name})")
    result = create_lead(
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

    Args:
        lead_id: UUID string of the lead to update.
        new_status: Target status: 'NEW', 'CONTACTED', 'CONVERTED', or 'LOST'.
        notes: Optional reason or context for the status change.
    """
    logger.info(f"[LeadFollowupAgent] Tool call: advance_lead_status(lead={lead_id}, status={new_status})")
    result = update_lead_status(lead_id=lead_id, new_status=new_status, notes=notes)
    return str(result)


def send_followup_reminder(
    lead_id: str,
    channel: str,
    message: str,
    scheduled_at: Optional[str] = None,
) -> str:
    """
    Schedule and send a follow-up reminder to a lead via email, SMS, or phone.
    Automatically advances NEW leads to CONTACTED status.

    Args:
        lead_id: UUID string of the target lead.
        channel: Communication channel – 'email', 'sms', or 'phone'.
        message: Personalised message content for the follow-up.
        scheduled_at: Optional ISO datetime for scheduled send (e.g. '2026-06-01T10:00:00Z'). Omit for immediate.
    """
    logger.info(f"[LeadFollowupAgent] Tool call: send_followup_reminder(lead={lead_id}, channel={channel})")
    result = create_followup_reminder(
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
    Generate a personalised follow-up message based on customer/lead history,
    preferences, and engagement data. The message is tailored per channel format.

    Args:
        customer_id: UUID string of an existing customer (provide this OR lead_id).
        lead_id: UUID string of a lead (provide this OR customer_id).
        channel: Target channel – 'email' (full letter), 'sms' (≤160 chars), or 'phone' (call script).
        tone: Message tone – 'warm', 'professional', 'urgent', or 'casual'.
    """
    logger.info(f"[LeadFollowupAgent] Tool call: create_personalized_message(customer={customer_id}, lead={lead_id})")
    result = generate_followup_message(
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
    Get comprehensive lead conversion analytics including pipeline distribution,
    conversion rates, source effectiveness, and actionable recommendations.

    Args:
        period_days: Analysis window in days (default 30).
        branch_id: Optional UUID string of a branch to scope the analytics.
    """
    logger.info(f"[LeadFollowupAgent] Tool call: view_conversion_analytics(period={period_days}d)")
    result = get_lead_conversion_analytics(period_days=period_days, branch_id=branch_id)
    return str(result)


def view_pipeline_snapshot(
    branch_id: Optional[str] = None,
) -> str:
    """
    Get a quick snapshot of the current lead pipeline showing counts per stage
    and overall conversion rate.

    Args:
        branch_id: Optional UUID string of a branch. Omit for organisation-wide snapshot.
    """
    logger.info(f"[LeadFollowupAgent] Tool call: view_pipeline_snapshot(branch={branch_id})")
    result = get_lead_pipeline_summary(branch_id=branch_id)
    return str(result)


# ---------------------------------------------------------------------------
# System Prompt
# ---------------------------------------------------------------------------
LEAD_FOLLOWUP_SYSTEM_PROMPT = """\
You are Mia, the Lead Follow-Up Specialist and CRM Manager at SalonAI Workforce Platform.

🎯 CORE MISSION:
Convert prospects into loyal salon customers through intelligent, data-driven follow-up strategies.

📋 YOUR CAPABILITIES:
1. **Abandoned Booking Detection** — Find customers who cancelled/no-showed and haven't returned.
   Use `find_abandoned_bookings` to identify re-engagement opportunities.

2. **Lead Pipeline Management** — Search, register, and advance leads through the pipeline.
   Pipeline stages: NEW → CONTACTED → CONVERTED (or LOST).
   Use `search_leads`, `register_new_lead`, `advance_lead_status`.

3. **Follow-Up Reminders** — Schedule and dispatch personalised follow-up messages.
   Channels: email, SMS, phone.
   Use `send_followup_reminder` to create follow-ups (auto-advances NEW → CONTACTED).

4. **Personalised Messaging** — Generate contextual follow-up messages using customer history.
   Adapts tone (warm/professional/urgent/casual) and format (email/SMS/phone script).
   Use `create_personalized_message` for data-driven templates.

5. **Conversion Analytics** — Track pipeline health, conversion rates, and source effectiveness.
   Use `view_conversion_analytics` for deep analysis, `view_pipeline_snapshot` for quick status.

📏 BUSINESS RULES:
- Always use tools to retrieve real data before making claims or recommendations.
- When a user asks about "leads" or "prospects", search the CRM first.
- When drafting follow-ups, always personalise based on available data.
- Follow-up cadence recommendation: Day 1 (email), Day 3 (SMS), Day 7 (phone call).
- Mark leads as LOST only if they explicitly decline or after 3+ unanswered follow-ups.
- For abandoned bookings, always offer a re-engagement incentive (10-20% discount).

🎨 COMMUNICATION STYLE:
- Be data-driven and action-oriented — always cite specific numbers.
- Present analytics in clean, formatted summaries with key takeaways.
- When suggesting follow-ups, provide the drafted message ready to send.
- Be proactive — if you see pipeline issues, flag them with recommendations.
- Keep responses concise but thorough. Use bullet points and headers for clarity.
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

        # 1. Configure model client - Groq (free, open-source alternative to OpenAI)
        groq_key = settings.groq_api_key or os.environ.get("GROQ_API_KEY")

        if groq_key and groq_key != "your-groq-key-here":
            logger.info("Configuring LeadFollowupAgent with Groq endpoint...")
            self.model_client = OpenAIChatCompletionClient(
                model="llama-3.3-70b-specdec",
                api_key=groq_key,
                base_url="https://api.groq.com/openai/v1",
            )
        else:
            logger.warning("No Groq API key found – LeadFollowupAgent using mock client for testing.")
            self.model_client = OpenAIChatCompletionClient(
                model="llama-3.3-70b-specdec",
                api_key="mock-groq-key-for-testing",
                base_url="https://api.groq.com/openai/v1",
            )

        # 2. Build AutoGen AssistantAgent with full tool suite
        self.assistant = AssistantAgent(
            name=name,
            model_client=self.model_client,
            system_message=LEAD_FOLLOWUP_SYSTEM_PROMPT,
            tools=[
                find_abandoned_bookings,
                search_leads,
                register_new_lead,
                advance_lead_status,
                send_followup_reminder,
                create_personalized_message,
                view_conversion_analytics,
                view_pipeline_snapshot,
            ],
        )

        logger.info(f"Lead Follow-Up Agent '{name}' initialized with 8 CRM tools.")

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
                for msg in chat_history:
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
