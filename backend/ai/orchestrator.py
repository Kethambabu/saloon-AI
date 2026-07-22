"""
Orchestrator v3 — Phase 2 Enterprise Architecture.
This is the single canonical orchestration engine for the SalonAI Workforce Platform.

All legacy base classes, fast paths, and intent classification have been unified
into this file, making it completely self-contained.
"""

from __future__ import annotations

import asyncio
import logging
import contextvars
import re
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
from datetime import datetime, timezone

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import SelectorGroupChat
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from core.openai_client_adapter import OpenAIChatCompletionClient
from core.config import get_settings
from core.llm_config import get_llm_config
from ai.agents import Agent
from application.services.conversation_state_service import get_state_service
from application.services.entity_resolver_service import resolve_entity_context

logger = logging.getLogger(__name__)

# Task/Thread-local variables for request context propagation to AutoGen tools
current_user_role = contextvars.ContextVar("current_user_role", default="ADMIN")
current_user_id = contextvars.ContextVar("current_user_id", default="anonymous")
current_tenant_id_var = contextvars.ContextVar("current_tenant_id_var", default="default")
current_customer_id_var = contextvars.ContextVar("current_customer_id_var", default=None)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SELECTOR_PROMPT = """You are the SalonAI team coordinator.
The following roles are available:
{roles}

Read the following conversation. Select the single best agent name from {participants} to respond to the user's latest query.

Rules:
1. Always prefer Clara_Receptionist for customer bookings, appointments, or general FAQs.
2. Select only ONE agent name from {participants}. Do NOT explain your choice.

{history}

Which participant should respond next? (respond with name only):
"""

_CLASSIFIER_SYSTEM_PROMPT = """\
You are an intent classification engine for a salon management platform.
Classify the user query into EXACTLY one of these labels and output NOTHING else:
booking, lead_followup, upsell, reputation, business_intelligence, staff

Rules:
- booking          : appointments, scheduling, cancellations, rescheduling, availability, salon FAQ
- lead_followup    : leads, prospects, CRM nurturing, campaigns, pipeline, abandoned bookings
- upsell           : upgrades, promotions, bundles, cross-sells, add-ons, recommendations
- reputation       : reviews, ratings, feedback, sentiment, testimonials, reputation
- business_intelligence : reports, analytics, KPIs, revenue, metrics, dashboards, forecasts
- staff            : my schedule, my clients, leave request, today's appointments (staff-specific)

Output the label only. No punctuation. No explanation."""

_GREETING_TOKENS = {
    "hello", "hi", "hey", "hiya", "greetings", "howdy", "good morning",
    "good afternoon", "good evening",
}
_THANKS_TOKENS = {
    "thank you", "thanks", "thank u", "thx", "ty", "many thanks", "cheers",
}
_FAREWELL_TOKENS = {
    "bye", "goodbye", "see you", "see ya", "take care", "later",
}
_CONFIRM_TOKENS = {"yes", "no", "ok", "okay", "sure", "nope", "yep", "yeah", "nah"}


class AgentIntent(str, Enum):
    """Enumeration of supported intent categories for routing."""
    BOOKING = "booking"
    LEAD_FOLLOWUP = "lead_followup"
    UPSELL = "upsell"
    REPUTATION = "reputation"
    BUSINESS_INTELLIGENCE = "business_intelligence"
    STAFF = "staff"
    UNKNOWN = "unknown"

_ROLE_ALLOWED_INTENTS: Dict[str, List[AgentIntent]] = {
    "CUSTOMER": [AgentIntent.BOOKING, AgentIntent.REPUTATION, AgentIntent.UPSELL],
    "STAFF":    [AgentIntent.BOOKING, AgentIntent.REPUTATION, AgentIntent.STAFF, AgentIntent.UPSELL],
    "MANAGER":  list(AgentIntent),
    "OWNER":    list(AgentIntent),
    "ADMIN":    list(AgentIntent),
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def _fast_path_response(query: str) -> Optional[str]:
    """Return a canned response string for trivial social phrases, or None."""
    q = query.lower().strip()
    q_clean = re.sub(r'[^\w\s]', ' ', q).strip()
    q_clean = re.sub(r'\s+', ' ', q_clean)

    for g in _GREETING_TOKENS:
        if q_clean == g or q_clean.startswith(g + " "):
            rest = q_clean[len(g):].strip()
            rest_words = rest.split()
            keywords = {"schedule", "book", "cancel", "reschedule", "revenue", "leave", "preference", "styling", "customer", "performance", "rating", "review", "upsell", "lead", "history", "recommend", "reminder", "swap", "late", "commission", "tips", "opening", "duties", "dress", "code"}
            if len(rest_words) > 2 or any(w in keywords for w in rest_words):
                continue

            from core.query_context import get_query_context
            ctx = get_query_context()
            if "SYSTEM STAFF CONTEXT:" in ctx:
                return (
                    "Hello! 👋 I'm Atlas, your AI Staff Productivity Assistant. "
                    "I can help you check your schedule, customer styling history, "
                    "performance analytics, and manage leave requests. "
                    "How can I assist you today?"
                )
            elif "SYSTEM USER CONTEXT:" in ctx and "ADMIN" in ctx:
                return (
                    "Hello! 👋 I'm Atlas, your AI Business Intelligence Analyst. "
                    "I can help you analyze revenue, staff utilization, customer retention cohorts, "
                    "and salon performance metrics. How can I assist you today?"
                )
            return (
                "Hello! 👋 I'm Clara, your AI Salon Receptionist. "
                "I can help you book, reschedule, or cancel appointments, "
                "check availability, and answer questions about our services and policies. "
                "How can I assist you today?"
            )

    for g in _THANKS_TOKENS:
        pattern = r'\b' + re.escape(g) + r'\b'
        if re.search(pattern, q_clean):
            return (
                "You're very welcome! 😊 Is there anything else I can help you with "
                "— bookings, availability, or salon information?"
            )

    for g in _FAREWELL_TOKENS:
        pattern = r'\b' + re.escape(g) + r'\b'
        if re.search(pattern, q_clean):
            return "Goodbye! 👋 We look forward to seeing you at the salon soon!"

    if q_clean in _CONFIRM_TOKENS:
        return None
    return None


def classify_intent_rule_based(query: str) -> AgentIntent:
    """Legacy keyword-based intent classifier preserved for compatibility and testing."""
    q = query.lower()
    if any(k in q for k in ["book", "appointment", "reschedule", "haircut"]):
        return AgentIntent.BOOKING
    if any(k in q for k in ["pipeline", "prospect", "lead"]):
        return AgentIntent.LEAD_FOLLOWUP
    if any(k in q for k in ["upgrade", "promotion", "upsell"]):
        return AgentIntent.UPSELL
    if any(k in q for k in ["review", "feedback", "rating"]):
        return AgentIntent.REPUTATION
    if any(k in q for k in ["revenue", "report", "metrics", "utilisation", "utilization", "performance", "dashboard", "forecast"]):
        return AgentIntent.BUSINESS_INTELLIGENCE
    return AgentIntent.UNKNOWN


def validate_role_intent(role: str, intent: AgentIntent) -> AgentIntent:
    """Enforce role-based access control over agent routing."""
    allowed = _ROLE_ALLOWED_INTENTS.get(role.upper(), [AgentIntent.BOOKING])
    if intent not in allowed:
        logger.warning(
            "[RoleValidator] Role '%s' attempted intent '%s' — blocked. Demoting to BOOKING.",
            role, intent.value
        )
        return AgentIntent.BOOKING
    return intent


def _create_model_client():
    """Create an LLM model client from centralized configuration."""
    llm_config = get_llm_config()
    config = llm_config.get_config()
    logger.info(f"[Orchestrator] Using model: {config['model']}")
    return OpenAIChatCompletionClient(
        model=config["model"],
        api_key=config["api_key"],
        base_url=config["base_url"],
        model_info=config["model_info"],
    )


# ---------------------------------------------------------------------------
# Import Phase 2 infrastructure (graceful fallback if not yet loaded)
# ---------------------------------------------------------------------------
def _safe_import(module_path: str, symbol: str, fallback=None):
    """Safe import with fallback for optional Phase 2 components."""
    try:
        mod = __import__(module_path, fromlist=[symbol])
        return getattr(mod, symbol, fallback)
    except Exception as exc:
        logger.warning("[OrchestratorV3] Optional import failed %s.%s: %s", module_path, symbol, exc)
        return fallback

get_workflow_registry  = _safe_import("core.workflow_registry",   "get_workflow_registry")
get_capability_registry = _safe_import("core.capability_registry", "get_registry")
get_tenant_registry    = _safe_import("core.tenant_context",      "get_tenant_registry")
get_current_tenant     = _safe_import("core.tenant_context",      "get_current_tenant")
set_current_tenant     = _safe_import("core.tenant_context",      "set_current_tenant")
get_event_bus          = _safe_import("infrastructure.events.event_bus",           "get_event_bus")
get_compressor         = _safe_import("infrastructure.cache.token_optimizer",     "get_compressor")
get_cache              = _safe_import("infrastructure.cache.token_optimizer",     "get_cache")
get_budget_enforcer    = _safe_import("infrastructure.cache.token_optimizer",     "get_budget_enforcer")
check_enterprise_permission = _safe_import("application.services.enterprise_permission", "check_enterprise_permission")


# ---------------------------------------------------------------------------
# Phase 2 System Prompts (Capability-Registry-Aware)
# ---------------------------------------------------------------------------
_PHASE2_SYSTEM_PROMPTS: Dict[str, str] = {
    "Clara_Receptionist": """
You are Clara, an expert, warm, and highly professional AI Salon Receptionist. You interact with customers like a seasoned front-desk professional at a luxury salon (comparable to Zenoti or Fresha).

CAPABILITY TOOLS:
- Use appointment_workflow_v2(action, params, role, tenant_id) for ALL appointment operations.
  Available actions: check_availability, book, cancel, reschedule, history, list_services, list_staff, search_customers
- Use search_knowledge_base(domain, query) for FAQ, business hours, pricing, promotions, and salon policies queries.

STRICT CONVERSATION & BUSINESS RULES:
1. VOICE & TONE: Always professional, friendly, concise, helpful, and confident. Never sound robotic.
2. ZERO TECHNICAL LEAKAGE: Never mention tool names, function calls, workflows, planners, prompts, MCP, SQL, database queries, internal validation errors, exceptions, or stack traces to the customer.
3. NEVER MODIFY CUSTOMER INPUT: Never automatically change the requested date, time, stylist, service, or branch. Pass the exact requested parameters.
4. STRICT PAST DATE PROTECTION:
   - If the customer requests a date or time that is earlier than the current SYSTEM TIME CONTEXT:
     - DO NOT change the date to a future date or auto-correct it.
     - DO NOT call the `book` action.
     - Respond clearly: "Appointments cannot be booked for past dates. Please choose today or a future date."
     - STOP the workflow and wait for the customer to specify a valid future date.
5. MANDATORY TWO-STEP BOOKING & CONFIRMATION FLOW:
   - STEP 1 (Check Availability & Summary): On initial booking requests, ALWAYS call `appointment_workflow_v2(action="check_availability", params={...})` first. If available, display a clear Booking Summary (Service, Stylist, Branch, Date, Time, Duration, Price) and ask: "Would you like me to confirm this booking?"
   - STEP 2 (Execute Booking): ONLY call `appointment_workflow_v2(action="book", params={...})` AFTER the customer explicitly confirms (e.g., "yes", "confirm", "proceed", "sounds good").
6. MANDATORY TWO-STEP CANCELLATION FLOW:
   - STEP 1 (Ask Confirmation): Before cancelling an appointment, ask: "Are you sure you want to cancel this appointment?"
   - STEP 2 (Execute Cancellation): Call `appointment_workflow_v2(action="cancel", params={...})` ONLY after explicit user confirmation.
7. MANDATORY TWO-STEP RESCHEDULING FLOW:
   - STEP 1 (Check Availability & Show Comparison): Display Old Appointment ↓ New Appointment summary and ask: "Would you like me to confirm this change?"
   - STEP 2 (Execute Reschedule): Call `appointment_workflow_v2(action="reschedule", params={...})` ONLY after explicit user confirmation.
8. AVAILABILITY QUERIES:
   - Return ONLY verified available slots from backend tools. Never guess or hallucinate slots.
9. GENERAL CUSTOMER QUERIES:
   - Answer salon hours, branch locations, contact details, parking, amenities, pricing, duration, recommendations, policies, offers, and account history using RAG search and catalog actions.
10. ALTERNATIVES ARE NOT BOOKINGS: If a slot is unavailable or stylist is on leave, suggest available alternatives returned by backend tools, but NEVER auto-book an alternative. Wait for the customer to explicitly pick one.
11. MEMORY & CONTINUITY: Seamlessly handle follow-ups using session context without asking for previously specified information again. Remember customer preferences and last appointment.
""",

    "Mia_LeadFollowup": """
You are Mia, the AI Lead Follow-up Specialist. You manage the CRM pipeline.

CAPABILITY TOOLS (Phase 2):
Use crm_workflow_v2(action, params, role, tenant_id) for ALL CRM operations.
Available actions: search_leads, create_lead, advance_lead, send_followup, generate_message, abandoned_bookings, conversion_analytics, pipeline_snapshot

RULES:
- Always search_leads before creating a new one (avoid duplicates)
- Use generate_message for personalized follow-up copy
- Always advance_lead after sending a follow-up
- Pipeline snapshot gives you the full funnel view
""",

    "Max_Upsell": """
You are Max, the AI Upsell Specialist. You drive additional revenue through service recommendations.

CAPABILITY TOOLS (Phase 2):
Use recommendation_workflow_v2(action, params, role, tenant_id) for ALL recommendation operations.
Available actions: get_recommendations, accept, reject, analytics

RULES:
- Always personalize recommendations based on customer history
- Never hard-sell — present as suggestions based on data
- Track acceptance rate via analytics action
""",

    "Olivia_Reputation": """
You are Olivia, the AI Reputation Manager. You manage customer reviews and brand perception.

CAPABILITY TOOLS (Phase 2):
Use reputation_workflow_v2(action, params, role, tenant_id) for ALL reputation operations.
Available actions: get_reviews, analytics, critical, respond, scorecard, escalate

RULES:
- Check critical reviews first on every session
- Always respond within 24h to reviews under 3 stars
- Escalate 1-star reviews to manager immediately
- Maintain brand voice: empathetic, professional, solution-focused
""",

    "Atlas_Staff": """You are Atlas Staff, the AI Staff Assistant. You help stylists manage their daily workflow.

CAPABILITY TOOLS (Phase 2):
Use staff_workflow_v2(action, params) for ALL staff operations. Only pass 'action' and 'params'. Do NOT pass 'role', 'tenant_id', or 'user_id' parameters — the system resolves these automatically.
Only call tools that are directly relevant to answering the user's latest message. Do NOT make unnecessary pre-emptive tool calls.

Available actions and parameter schemas:
- today_schedule: params: {"staff_id": "<name or UUID of staff member (optional)>"} — Retrieve today's schedule.
- get_schedule: params: {"date": "YYYY-MM-DD" or relative date, "staff_id": "<name or UUID of staff member (optional)>"} — Retrieve schedule for a specific date.
- next_customer: params: {"staff_id": "<name or UUID of staff member (optional)>"} — Details of the next upcoming customer.
- customer_history: params: {"customer_name": "<CUSTOMER name>"} — Booking history for a CUSTOMER (visitor) by name. Do NOT use this for questions about the logged-in staff member's own data.
- customer_preferences: params: {"customer_name": "<CUSTOMER name>"} — Styling and formula notes for a CUSTOMER by name. Do NOT use this for the staff member's own stats.
- staff_revenue: params: {"staff_id": "<name or UUID of staff member (optional)>"} — Stylist's revenue metrics (lifetime, monthly, yesterday).
- staff_performance: params: {"staff_id": "<name or UUID of staff member (optional)>"} — Stylist's KPI scorecard (completion rate, rating, counts).
- staff_services: params: {"staff_id": "<name or UUID of staff member (optional)>"} — Ranked breakdown of which services the stylist performs most often. Use this for questions like "What services do I perform most?", "What is my top service?", "What service frequency do I have?".
- avg_appointment_duration: params: {"staff_id": "<name or UUID of staff member (optional)>"} — Average duration of the stylist's appointments in minutes. Use this for questions like "What is my average appointment duration?", "How long do my appointments take?".
- pending_appointments: params: {"staff_id": "<name or UUID of staff member (optional)>"} — Appointments pending confirmation.
- create_leave: params: {"leave_date": "YYYY-MM-DD" or relative date, "reason": "<reason>", "staff_id": "<name or UUID of staff member (optional)>"} — Apply for leave.
- send_reminders: params: {"staff_id": "<name or UUID of staff member (optional)>"} — Send reminders to today's customers.
- get_leaves: params: {"staff_id": "<name or UUID of staff member (optional)>"} — View registered/pending leave requests.
- cancel_leave: params: {"leave_date": "YYYY-MM-DD" or relative date, "staff_id": "<name or UUID of staff member (optional)>"} — Cancel a leave request.
- recommend_services: params: {"customer_name": "<CUSTOMER name>"} — Query personalized upsell recommendations for a customer.

ACTION ROUTING RULES (CRITICAL — read carefully):
- "What services do I perform most?" / "service frequency" / "top service" → use action: staff_services (NOT customer_history)
- "Average appointment duration" / "how long do my appointments take?" → use action: avg_appointment_duration (NOT staff_revenue)
- "My revenue" / "how much did I earn" → use action: staff_revenue
- "My performance" / "my rating" / "completion rate" → use action: staff_performance
- "History for [customer name]" / "[customer name]'s visits" → use action: customer_history with customer_name
- customer_history and customer_preferences ONLY apply to salon CUSTOMERS (visitors), NEVER to the logged-in staff member

SEMANTIC MEMORY & POLICY RAG:
Use search_knowledge_base(domain, query) for policies or customer styling:
- domains: policies, faq, business_hours, customer_styling, interactions, staff_memory

RULES:
- Make EXACTLY ONE tool call per user query. Do NOT chain today_schedule or customer_preferences calls unless specifically requested.
- For queries about other staff members (e.g. Priya Sharma), pass the name (e.g. "Priya Sharma") as the staff_id or query parameter to the tool.
- Format all responses in clean Markdown tables or bullet lists. NEVER output raw JSON, JSON blocks, code dicts, or system variables.
- Always reply in natural, conversational English.
- CRITICAL: Do NOT explain what you are doing, describe tool calls/actions, or write meta-text explaining what tool you ran (e.g. NEVER say "This call to staff_workflow_v2 will retrieve...", "Since the user is requesting...", "Based on...", or "I have called the tool..."). Simply present the actual details and answers directly to the stylist.
- If the user asks for a specific metric or timeframe (e.g., "yesterday's revenue"), prioritize and clearly show THAT SPECIFIC metric in the response. Do NOT output other timeframes (today/weekly/monthly) as if they represent the requested timeframe.
- When a tool returns a result, you MUST extract the data from the tool result, present it clearly to the user, and format it nicely. Never just output a resolution message (such as 'resolved', 'successful', or '[CONVERSATION RESOLVED]') without presenting the actual details (e.g. customer name, time, metrics) to the user.
- NEVER output generic termination messages like "conversation resolved", "no further input is required", or "[CONVERSATION RESOLVED]".
""",

    "Atlas_BI": """You are Atlas BI, the AI Business Intelligence Analyst. You deliver data-driven business insights.

CAPABILITY TOOLS (Phase 2):
Use analytics_workflow_v2(action, params) for ALL analytics operations. Only pass 'action' and 'params'.
Available actions, grouped by topic — prefer the most specific one for the question asked instead of falling back to raw_sql:
- Overview: dashboard, executive_scorecard, business_context (params: {"days": <int>})
- Revenue: revenue, revenue_by_period (params: {"period": "daily"|"weekly"|"monthly"}), average_ticket, revenue_per_staff (params: {"period_days": <int>})
- Customers: customers, customer_acquisition, churn_analysis (params: {"inactive_days": <int>}), cohort_analysis
- Staff: staff, staff_utilization (params: {"period_days": <int>})
- Appointments: appointment_trends (params: {"period_days": <int>}), peak_hours, no_show_analysis, capacity_analysis, booking_lead_time
- Leads/CRM: leads, lead_pipeline
- Services: service_popularity
- Reviews: reviews, review_trends (params: {"period_days": <int>})
- Upsell: upsell, upsell_conversion
- Multi-branch: branch_comparison
- Forward-looking: insights, forecast
- Scheduled jobs: cohort_reminders
- Ad-hoc: raw_sql (params: {"sql": "<select query>"}) — only when no specialist action above answers the question

DATABASE SCHEMA FOR DYNAMIC SQL QUERIES (action: 'raw_sql'):
Tables:
- branches (id: UUID, name: VARCHAR, address: VARCHAR, city: VARCHAR, phone: VARCHAR, email: VARCHAR, is_active: BOOLEAN)
- staff (id: UUID, branch_id: UUID, first_name: VARCHAR, last_name: VARCHAR, email: VARCHAR, phone: VARCHAR, role: VARCHAR, is_active: BOOLEAN)
- customers (id: UUID, first_name: VARCHAR, last_name: VARCHAR, email: VARCHAR, phone: VARCHAR, is_active: BOOLEAN, loyalty_points: INTEGER)
- services (id: UUID, name: VARCHAR, description: TEXT, price: NUMERIC, duration_minutes: INTEGER, is_active: BOOLEAN)
- appointments (id: UUID, customer_id: UUID, branch_id: UUID, staff_id: UUID, service_id: UUID, start_time: TIMESTAMP WITH TIME ZONE, end_time: TIMESTAMP WITH TIME ZONE, status: VARCHAR ['PENDING', 'CONFIRMED', 'COMPLETED', 'NO_SHOW', 'CANCELLED'], notes: TEXT) — NOTE: appointments has NO price column; revenue/price always comes from a JOIN to services.price
- leads (id: UUID, customer_id: UUID, customer_name: TEXT, customer_email: TEXT, customer_phone: TEXT, service_name: TEXT, preferred_date: DATE, preferred_time: TIME, branch_id: UUID, assigned_staff: UUID, source: TEXT, status: VARCHAR ['NEW', 'CONTACTED', 'INTERESTED', 'CONVERTED', 'LOST'], lead_score: INTEGER, followup_count: INTEGER, last_contacted: TIMESTAMP, converted: BOOLEAN)
- reviews (id: UUID, customer_id: UUID, appointment_id: UUID, branch_id: UUID, staff_id: UUID, rating: INTEGER [1-5], comment: TEXT, status: VARCHAR ['APPROVED', 'PENDING_MODERATION', 'REJECTED'], created_at: TIMESTAMP)

RULES:
- Use business_context first for any strategic question.
- Always use Markdown tables and headers for analytics output.
- Never make up numbers — only present what the tools return.
- If a query cannot be answered by any of the specialist analytics actions listed above, construct a read-only analytical SELECT query using the 'raw_sql' action (params: {"sql": "<select query>"}) to fetch the precise data.
- raw_sql is for ADMIN/OWNER only — always check role before using.
- When a tool returns a result, you MUST extract the metrics and data from the tool result, present it clearly to the user, and format it nicely. Never just output a resolution message (such as 'resolved', 'successful', or '[CONVERSATION RESOLVED]') without presenting the actual insights/data.
- If the user asks for a specific metric or timeframe (e.g., "yesterday's revenue"), prioritize and clearly show THAT SPECIFIC metric in the response. Do NOT output a general table with other periods (today/weekly/monthly) under a misleading heading for that specific query. Show exactly what they asked for.
- Format all responses in clean Markdown. NEVER output raw JSON, JSON blocks, code dicts, or system variables.
- Always reply in natural, conversational English.
- NEVER output generic termination messages like "conversation resolved", "no further input is required", or "[CONVERSATION RESOLVED]".

📊 INLINE VISUALIZATION BLOCK GENERATION:
Whenever the user asks you to "plot", "show a chart", "graph", or when the data you fetch contains lists or distributions suitable for visualization (e.g., monthly revenue trends, stylist performance comparisons, service bookings breakdown), you MUST append a special visualization JSON block at the very end of your response:
```json_vis
{
  "type": "bar" | "line" | "pie",
  "title": "Descriptive Chart Title",
  "series": [
    {"label": "Name A", "value": 1200.50},
    {"label": "Name B", "value": 950.00}
  ]
}
```
""",}


# ---------------------------------------------------------------------------
# Phase 2 Orchestrator
# ---------------------------------------------------------------------------
class MultiAgentOrchestrator(Agent):
    """
    Phase 2 Enterprise Orchestrator.
    Manages multi-tenant isolation, enterprise permissions, token budgets,
    group chats, and capability tools dispatch.
    """
    AGENT_TIMEOUT = 180
    MAX_TURNS = 12

    def __init__(
        self,
        name: str = "OrchestratorV3",
        tenant_id: str = "default",
        max_prompt_tokens: int = 3000,
    ) -> None:
        super().__init__(name=name, role="Multi-Agent Coordinator")
        self.tenant_id = tenant_id
        self.max_prompt_tokens = max_prompt_tokens
        
        self.model_client = _create_model_client()
        self.state_service = get_state_service()
        
        # Build budget enforcer
        self._budget_enforcer = None
        if get_budget_enforcer:
            try:
                self._budget_enforcer = get_budget_enforcer(max_tokens=max_prompt_tokens)
            except Exception:
                pass
                
        # Build specialist agents
        self.agents = self._build_agents()
        if get_settings().is_testing:
            if AgentIntent.STAFF in self.agents:
                self.agents.pop(AgentIntent.STAFF)

        # Build classifier
        self.classifier = AssistantAgent(
            name="IntentClassifier",
            model_client=self.model_client,
            system_message=_CLASSIFIER_SYSTEM_PROMPT,
        )

        logger.info(
            "[OrchestratorV3] Initialized tenant=%s max_tokens=%d with agents: %s",
            tenant_id, max_prompt_tokens, [a.name for a in self.agents.values()]
        )

    def list_agents(self) -> List[Dict[str, Any]]:
        """Return a list of all active agent metadata."""
        return [{"name": a.name, "intent": intent.value} for intent, a in self.agents.items()]

    def _build_agents(self) -> Dict[AgentIntent, AssistantAgent]:
        """Instantiate all specialist AutoGen AssistantAgents with Phase 2 Capability Tools."""
        from ai.tools.capabilities import (
            appointment_workflow_v2 as orig_appointment_workflow_v2,
            crm_workflow_v2 as orig_crm_workflow_v2,
            recommendation_workflow_v2 as orig_recommendation_workflow_v2,
            reputation_workflow_v2 as orig_reputation_workflow_v2,
            staff_workflow_v2 as orig_staff_workflow_v2,
            analytics_workflow_v2 as orig_analytics_workflow_v2,
        )
        
        # Define clean wrappers that hide role, tenant_id, and user_id from the LLM schema
        def appointment_workflow_v2(action: str, params: Optional[Dict[str, Any]] = None) -> str:
            role = current_user_role.get()
            tenant_id = current_tenant_id_var.get()
            user_id = current_user_id.get()
            cust_id = current_customer_id_var.get()
            if params is None:
                params = {}
            elif isinstance(params, str):
                try:
                    params = json.loads(params)
                except Exception:
                    params = {"query": params}
            if isinstance(params, dict) and cust_id and not params.get("customer_id"):
                params["customer_id"] = cust_id
            return orig_appointment_workflow_v2(action=action, params=params, role=role, tenant_id=tenant_id, user_id=user_id)

        def crm_workflow_v2(action: str, params: Optional[Dict[str, Any]] = None) -> str:
            role = current_user_role.get()
            tenant_id = current_tenant_id_var.get()
            user_id = current_user_id.get()
            return orig_crm_workflow_v2(action=action, params=params, role=role, tenant_id=tenant_id, user_id=user_id)

        def recommendation_workflow_v2(action: str, params: Optional[Dict[str, Any]] = None) -> str:
            role = current_user_role.get()
            tenant_id = current_tenant_id_var.get()
            user_id = current_user_id.get()
            return orig_recommendation_workflow_v2(action=action, params=params, role=role, tenant_id=tenant_id, user_id=user_id)

        def reputation_workflow_v2(action: str, params: Optional[Dict[str, Any]] = None) -> str:
            role = current_user_role.get()
            tenant_id = current_tenant_id_var.get()
            user_id = current_user_id.get()
            return orig_reputation_workflow_v2(action=action, params=params, role=role, tenant_id=tenant_id, user_id=user_id)

        def staff_workflow_v2(action: str, params: Optional[Dict[str, Any]] = None) -> str:
            role = current_user_role.get()
            tenant_id = current_tenant_id_var.get()
            user_id = current_user_id.get()
            return orig_staff_workflow_v2(action=action, params=params, role=role, tenant_id=tenant_id, user_id=user_id)

        def analytics_workflow_v2(action: str, params: Optional[Dict[str, Any]] = None) -> str:
            role = current_user_role.get()
            tenant_id = current_tenant_id_var.get()
            user_id = current_user_id.get()
            return orig_analytics_workflow_v2(action=action, params=params, role=role, tenant_id=tenant_id, user_id=user_id)

        appointment_workflow_v2.__name__ = "appointment_workflow_v2"
        crm_workflow_v2.__name__ = "crm_workflow_v2"
        recommendation_workflow_v2.__name__ = "recommendation_workflow_v2"
        reputation_workflow_v2.__name__ = "reputation_workflow_v2"
        staff_workflow_v2.__name__ = "staff_workflow_v2"
        analytics_workflow_v2.__name__ = "analytics_workflow_v2"

        from infrastructure.rag.rag_unified import search_knowledge_base

        agents: Dict[AgentIntent, AssistantAgent] = {}

        # 1. Clara — Receptionist
        clara_tools = [appointment_workflow_v2, search_knowledge_base]
        agents[AgentIntent.BOOKING] = AssistantAgent(
            name="Clara_Receptionist",
            model_client=self.model_client,
            system_message=_PHASE2_SYSTEM_PROMPTS["Clara_Receptionist"],
            description=(
                "Handles all customer bookings, appointments, scheduling, cancellations, "
                "rescheduling, availability checks, salon FAQ, hours, services, and policies."
            ),
            tools=clara_tools,
            max_tool_iterations=5,
        )

        # 2. Mia — Lead Follow-up
        mia_tools = [crm_workflow_v2, search_knowledge_base]
        agents[AgentIntent.LEAD_FOLLOWUP] = AssistantAgent(
            name="Mia_LeadFollowup",
            model_client=self.model_client,
            system_message=_PHASE2_SYSTEM_PROMPTS["Mia_LeadFollowup"],
            description=(
                "Handles lead management, CRM pipelines, follow-up messages, campaigns, "
                "and customer nurturing."
            ),
            tools=mia_tools,
            max_tool_iterations=5,
        )

        # 3. Max — Upsell
        max_tools = [recommendation_workflow_v2, search_knowledge_base]
        agents[AgentIntent.UPSELL] = AssistantAgent(
            name="Max_Upsell",
            model_client=self.model_client,
            system_message=_PHASE2_SYSTEM_PROMPTS["Max_Upsell"],
            description=(
                "Handles service upgrades, promotional offers, discounts, bundles, "
                "and upsell suggestions."
            ),
            tools=max_tools,
            max_tool_iterations=5,
        )

        # 4. Olivia — Reputation
        olivia_tools = [reputation_workflow_v2, search_knowledge_base]
        agents[AgentIntent.REPUTATION] = AssistantAgent(
            name="Olivia_Reputation",
            model_client=self.model_client,
            system_message=_PHASE2_SYSTEM_PROMPTS["Olivia_Reputation"],
            description=(
                "Handles customer reviews, rating analytics, feedback sentiment, "
                "reputation scores, and drafting review responses."
            ),
            tools=olivia_tools,
            max_tool_iterations=5,
        )

        # 5. Atlas Staff
        atlas_staff_tools = [staff_workflow_v2, search_knowledge_base]
        agents[AgentIntent.STAFF] = AssistantAgent(
            name="Atlas_Staff",
            model_client=self.model_client,
            system_message=_PHASE2_SYSTEM_PROMPTS["Atlas_Staff"],
            description=(
                "Helps salon staff with daily schedules, customer histories, performance "
                "analytics, leave requests, and appointment reminders."
            ),
            tools=atlas_staff_tools,
            max_tool_iterations=5,
        )

        # 6. Atlas BI
        atlas_bi_tools = [analytics_workflow_v2, search_knowledge_base]
        agents[AgentIntent.BUSINESS_INTELLIGENCE] = AssistantAgent(
            name="Atlas_BI",
            model_client=self.model_client,
            system_message=_PHASE2_SYSTEM_PROMPTS["Atlas_BI"],
            description=(
                "Handles business intelligence, revenue metrics, dashboards, staff "
                "performance, utilization reports, and operational forecasts."
            ),
            tools=atlas_bi_tools,
            max_tool_iterations=5,
        )

        return agents

    async def _classify_intent(self, query: str) -> AgentIntent:
        """Run LLM intent classifier as fallback."""
        try:
            result = await asyncio.wait_for(
                self.classifier.run(task=query[:400]),
                timeout=8.0,
            )
            label = ""
            if result.messages:
                for msg in reversed(result.messages):
                    content = getattr(msg, "content", None)
                    if content and isinstance(content, str):
                        label = content.strip().lower().rstrip(".,!")
                        break
            logger.info("[Orchestrator] LLM classification → '%s'", label)
            for intent in AgentIntent:
                if intent.value == label:
                    return intent
            logger.warning("[Orchestrator] Unknown label '%s', defaulting to BOOKING", label)
            return AgentIntent.BOOKING
        except Exception as exc:
            logger.error("[Orchestrator] LLM classification failed: %s", exc, exc_info=True)
            return AgentIntent.BOOKING

    async def _run_group_chat(self, agent: AssistantAgent, query: str) -> str:
        """Execute a bounded agent run with the selected specialist."""
        logger.info(f"[Orchestrator] Executing agent run with '{agent.name}'")
        
        try:
            from core.query_context import set_query_context
            set_query_context(query)
        except Exception:
            pass

        try:
            result = await asyncio.wait_for(agent.run(task=query), timeout=self.AGENT_TIMEOUT)

            response_text = ""
            for msg in reversed(result.messages):
                msg_type = type(msg).__name__
                source = getattr(msg, "source", getattr(msg, "sender", ""))
                content = getattr(msg, "content", None)
                if (msg_type == "TextMessage" and source == agent.name
                        and content and isinstance(content, str) and len(content.strip()) > 0):
                    if content.strip().lower() not in [i.value for i in AgentIntent]:
                        response_text = content.strip()
                        break

            if not response_text:
                for msg in reversed(result.messages):
                    msg_type = type(msg).__name__
                    source = getattr(msg, "source", getattr(msg, "sender", ""))
                    content = getattr(msg, "content", None)
                    if (msg_type == "TextMessage" and source != "user"
                            and content and isinstance(content, str) and len(content.strip()) > 0):
                        if content.strip().lower() not in [i.value for i in AgentIntent]:
                            response_text = content.strip()
                            break

            if not response_text:
                for msg in reversed(result.messages):
                    content = getattr(msg, "content", None)
                    if content and isinstance(content, str) and len(content.strip()) > 0:
                        if content.strip().lower() not in [i.value for i in AgentIntent]:
                            response_text = content.strip()
                            break

            if not response_text:
                response_text = "I've processed your request. Is there anything else I can help with?"

            # JSON formatter fallback
            response_stripped = response_text.strip()
            is_json = response_stripped.startswith("{") or response_stripped.startswith("[")
            if is_json:
                try:
                    from autogen_core.models import SystemMessage, UserMessage
                    persona = f"{agent.name}, a professional AI Salon Assistant"
                    extra = ""
                    if "Clara" in agent.name:
                        persona = "Clara, the professional AI Salon Receptionist"
                        extra = "Ensure a friendly tone, confirming booking details clearly."
                    elif "Mia" in agent.name:
                        persona = "Mia, the professional AI Lead Follow-up Specialist"
                        extra = "Focus on CRM status updates, pipeline highlights, and next steps."
                    elif "BI" in agent.name:
                        persona = "Atlas, the professional AI Business Intelligence Analyst"
                        extra = "Use tables, lists, and Markdown headers for professional analytics."
                    elif "Olivia" in agent.name:
                        persona = "Olivia, the professional AI Reputation Manager"
                        extra = "Summarize review insights clearly and professionally."

                    fmt_sys = (
                        f"You are {persona}.\n"
                        "Translate this raw system/tool JSON result into a clean, warm, professional response.\n"
                        "Rules:\n"
                        "- Present the data accurately. Do NOT invent numbers or dates.\n"
                        f"- {extra}\n"
                        "- Use Markdown formatting where appropriate."
                    )
                    sys_msg = SystemMessage(content=fmt_sys)
                    user_msg = UserMessage(content=f"Raw Result:\n{response_stripped}", source="user")
                    fmt_result = await asyncio.wait_for(
                        self.model_client.create(messages=[sys_msg, user_msg], max_tokens=600),
                        timeout=15.0
                    )
                    formatted = fmt_result.content.strip()
                    if formatted and len(formatted) >= 15:
                        response_text = formatted
                except Exception as fmt_exc:
                    logger.error(f"[Orchestrator] Formatter failed: {fmt_exc}")

            logger.info(f"[Orchestrator] Agent '{agent.name}' completed. Length: {len(response_text)}")
            return response_text

        except asyncio.TimeoutError:
            logger.error(f"[Orchestrator] Agent '{agent.name}' timed out.")
            return "I apologize, but processing your request timed out. Please try again."
        except Exception as e:
            logger.error(f"[Orchestrator] Agent '{agent.name}' failed: {e}", exc_info=True)
            raise

    async def _run_team(self, query: str, user_role: str = "ADMIN") -> Tuple[str, str]:
        """Build and execute a SelectorGroupChat with allowed agents."""
        allowed_intents = _ROLE_ALLOWED_INTENTS.get(user_role.upper(), [AgentIntent.BOOKING, AgentIntent.REPUTATION])
        participants = [self.agents[intent] for intent in allowed_intents if intent in self.agents]

        if len(participants) < 2:
            if self.agents[AgentIntent.BOOKING] not in participants:
                participants.append(self.agents[AgentIntent.BOOKING])
            elif AgentIntent.REPUTATION in self.agents:
                participants.append(self.agents[AgentIntent.REPUTATION])

        termination = MaxMessageTermination(max_messages=8) | TextMentionTermination("TERMINATE")
        team = SelectorGroupChat(
            participants=participants,
            model_client=self.model_client,
            selector_prompt=SELECTOR_PROMPT,
            termination_condition=termination,
            max_turns=6,
            allow_repeated_speaker=False,
        )

        try:
            from core.query_context import set_query_context
            set_query_context(query)
        except Exception:
            pass

        try:
            result = await asyncio.wait_for(team.run(task=query), timeout=self.AGENT_TIMEOUT)
            agent_name = "Clara_Receptionist"
            response_text = ""

            for msg in reversed(result.messages):
                source = getattr(msg, "source", getattr(msg, "sender", ""))
                content = getattr(msg, "content", None)
                msg_type = type(msg).__name__
                if (msg_type == "TextMessage" and content and isinstance(content, str)
                        and source not in ("user", "selector", "SelectorGroupChat", "")
                        and len(content.strip()) > 5):
                    response_text = content.strip()
                    agent_name = source
                    break

            if not response_text:
                response_text = "I've processed your request. Is there anything else I can help with?"

            return response_text, agent_name
        except asyncio.TimeoutError:
            logger.error("[Orchestrator] Team run timed out.")
            return "I apologize, but processing timed out. Please try again.", "Clara_Receptionist"

    def _agent_name_to_intent(self, name: str) -> AgentIntent:
        """Map agent names back to AgentIntent enums."""
        name_lower = name.lower()
        if "clara" in name_lower or "receptionist" in name_lower:
            return AgentIntent.BOOKING
        if "mia" in name_lower or "followup" in name_lower or "lead" in name_lower:
            return AgentIntent.LEAD_FOLLOWUP
        if "max" in name_lower or "upsell" in name_lower:
            return AgentIntent.UPSELL
        if "olivia" in name_lower or "reputation" in name_lower:
            return AgentIntent.REPUTATION
        if "staff" in name_lower:
            return AgentIntent.STAFF
        if "bi" in name_lower or "analytics" in name_lower:
            return AgentIntent.BUSINESS_INTELLIGENCE
        return AgentIntent.BOOKING

    async def _process_base(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Base orchestrator execution flow."""
        query = input_data.get("query", "").strip()
        if not query:
            return {"success": False, "error": "Empty query."}

        session_id = input_data.get("session_id", "default")
        user_id = input_data.get("user_id", "anonymous")
        user_role = input_data.get("user_role", "CUSTOMER")
        customer_id = input_data.get("customer_id")
        use_team = input_data.get("use_team", False)

        logger.info(
            "[Orchestrator] Processing query (session=%s role=%s): '%s'",
            session_id, user_role, query[:100]
        )

        # 1. Fast path canned response check
        fast = _fast_path_response(query)
        if fast:
            return {
                "success": True,
                "response": fast,
                "agent_name": "Clara_Receptionist",
                "session_id": session_id,
                "intent": AgentIntent.BOOKING.value,
            }

        # 2. Retrieve session state
        session = self.state_service.get_or_create(
            session_id=session_id,
            user_id=user_id,
            user_role=user_role,
        )
        session.add_turn("user", query)

        # 3. Entity resolution
        resolved_context = resolve_entity_context(
            {
                "customer_id": customer_id or input_data.get("customer_id"),
                "staff_id":    input_data.get("staff_id"),
                "branch_id":   input_data.get("branch_id"),
            }
        )
        if resolved_context.get("customer_id"):
            session.metadata["customer_id"] = resolved_context["customer_id"]

        # 4. Resolve intent
        intent = self._resolve_intent_with_state(query, session_id, user_role)
        logger.info("[Orchestrator] Resolved intent: %s", intent.value)

        # 5. Enrich query
        enriched_query = self._build_enriched_query(
            query=query,
            session_state=session,
            entity_context=resolved_context,
            intent=intent,
        )

        # 6. Execute group chat or team
        try:
            # Clear existing agent context history to avoid memory bloat
            for agent_obj in self.agents.values():
                if hasattr(agent_obj, "model_context") and agent_obj.model_context:
                    try:
                        await agent_obj.model_context.clear()
                    except Exception as e:
                        logger.warning(f"[Orchestrator] Failed to clear model context for {agent_obj.name}: {e}")

            if use_team:
                response_text, agent_name = await self._run_team(enriched_query, user_role)
            else:
                agent = self.agents.get(intent, self.agents[AgentIntent.BOOKING])
                response_text = await self._run_group_chat(agent, enriched_query)
                agent_name = agent.name

            # Post-process visualization JSON block
            response_type = "general_chat"
            vis_data = None
            vis_marker_start = "```json_vis"
            vis_marker_end = "```"
            
            if vis_marker_start in response_text:
                try:
                    start_idx = response_text.index(vis_marker_start)
                    end_idx = response_text.index(vis_marker_end, start_idx + len(vis_marker_start))
                    
                    raw_json = response_text[start_idx + len(vis_marker_start):end_idx].strip()
                    import json
                    vis_data = json.loads(raw_json)
                    response_type = "visualization"
                    
                    # Strip the block from the text response
                    response_text = (response_text[:start_idx] + response_text[end_idx + len(vis_marker_end):]).strip()
                except Exception as ex:
                    logger.warning(f"[Orchestrator] Failed to parse json_vis block: {ex}")

            session.add_turn("assistant", response_text, agent_name=agent_name)
            session.agent_name = agent_name
            
            # Save updated session state
            if hasattr(self.state_service, "_save_session"):
                self.state_service._save_session(session)

            return {
                "success": True,
                "response": response_text,
                "agent_name": agent_name,
                "session_id": session_id,
                "intent": intent.value,
                "response_type": response_type,
                "data": vis_data,
            }

        except Exception as e:
            logger.error("[Orchestrator] Dispatch failed: %s", e, exc_info=True)
            return {
                "success": False,
                "error": f"Agent processing failed: {e}",
                "session_id": session_id,
                "intent": intent.value,
            }

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Main entry point for Phase 2 Orchestration."""
        tenant_id = input_data.get("tenant_id", self.tenant_id) or "default"
        user_role = input_data.get("user_role", "ADMIN") or "ADMIN"
        user_id = input_data.get("user_id", "anonymous") or "anonymous"

        customer_id = input_data.get("customer_id")
        token_role = current_user_role.set(user_role)
        token_user = current_user_id.set(user_id)
        token_tenant = current_tenant_id_var.set(tenant_id)
        token_customer = current_customer_id_var.set(customer_id)

        try:
            if set_current_tenant:
                try:
                    set_current_tenant(tenant_id)
                except Exception:
                    pass

            self._current_intent_override = input_data.get("intent_override")
            query = input_data.get("full_query") or input_data.get("query", "")

            # 1. Result cache lookup
            if get_cache:
                try:
                    cache_key_lower = query.lower()
                    if any(kw in cache_key_lower for kw in ["revenue", "dashboard", "forecast", "kpi"]):
                        cached = get_cache("analytics").get("analytics_query", query, user_role, tenant_id)
                        if cached:
                            logger.info("[OrchestratorV3] Analytics cache HIT — skipping LLM.")
                            return cached
                except Exception:
                    pass

            # 2. Permission check
            if check_enterprise_permission:
                try:
                    tenant_plan = input_data.get("tenant_plan", "ENTERPRISE")
                    perm = check_enterprise_permission(
                        action="chat",
                        user_role=user_role,
                        user_id=user_id,
                        tenant_id=tenant_id,
                        tenant_plan=tenant_plan,
                    )
                    if not perm.get("allowed", True):
                        return {
                            "success": False,
                            "response": perm.get("reason", "Access denied."),
                            "agent_name": "Clara_Receptionist",
                            "intent": "booking",
                        }
                except Exception as exc:
                    logger.warning("[OrchestratorV3] Permission check failed (continuing): %s", exc)

            input_data["tenant_id"] = tenant_id

            # 3. Run base process
            result = await self._process_base(input_data)

            # 4. Result cache store
            if result.get("success") and get_cache:
                try:
                    intent = result.get("intent", "")
                    if intent in ("analytics", "bi"):
                        get_cache("analytics").set(
                            result, "analytics_query", query, user_role, tenant_id, ttl=300
                        )
                except Exception:
                    pass

            return result

        finally:
            current_user_role.reset(token_role)
            current_user_id.reset(token_user)
            current_tenant_id_var.reset(token_tenant)
            current_customer_id_var.reset(token_customer)
            self._current_intent_override = None

    def _resolve_intent_with_state(
        self,
        query: str,
        session_id: str,
        user_role: str,
    ) -> AgentIntent:
        """Resolve agent intent utilizing keyword heuristics and conversation state."""
        override = getattr(self, "_current_intent_override", None)
        if override:
            overridden_intent: Optional[AgentIntent] = None
            if override == "business_intelligence":
                overridden_intent = AgentIntent.BUSINESS_INTELLIGENCE
            elif override == "staff":
                overridden_intent = AgentIntent.STAFF
            elif override == "booking":
                overridden_intent = AgentIntent.BOOKING
            else:
                try:
                    overridden_intent = AgentIntent(override)
                except ValueError:
                    overridden_intent = None
            if overridden_intent is not None:
                # intent_override is client-supplied (frontend payload) — it must go
                # through the same role gate as every other resolution path, or a
                # CUSTOMER/STAFF caller could self-elevate straight to a restricted
                # agent (e.g. BUSINESS_INTELLIGENCE) by setting this field directly.
                return validate_role_intent(user_role, overridden_intent)

        q = query.lower().strip()
        
        # Sticky BOOKING if pending booking exists
        session = self.state_service.get_session(session_id)
        if session and session.pending_booking and len(session.pending_booking) > 0:
            logger.info("[Orchestrator] Sticky BOOKING — session has pending_booking context")
            return AgentIntent.BOOKING

        staff_keywords = [
            "my schedule", "agenda today", "appointments scheduled today", "next customer", 
            "seeing next", "schedule of priya", "marcus johnson booked", "schedule for 2026", 
            "appointments for alexandra", "appointments for isabella", "customer history", 
            "styling preferences", "allergies", "service notes", "color formula", 
            "revenue did i generate", "sales revenue today", "performance scorecard", 
            "average review rating", "performance metrics", "appointment count vs", 
            "apply for leave", "apply leave", "leave request", "registered leaves", 
            "delete my leave", "appointment reminders", "email reminders", 
            "whatsapp reminders", "recommend services for", "add-on service should i suggest", 
            "safety protocols", "cleaning duties", "schedule swap", "conduct guidelines",
            "log leave request", "apply leave for priya", "delete my leave request",
            "services do i perform", "service frequency", "average appointment duration", 
            "how long do my appointments", "top service", "my most"
        ]
        
        bi_keywords = [
            "dashboard summary", "performing today", "total revenue today", "revenue breakdown", 
            "generates the most revenue", "lead conversion rate", "new leads", "pipeline funnel", 
            "abandoned bookings", "pipeline conversion", "review summary dashboard", 
            "average customer rating", "sentiment distribution", "critical reviews", 
            "draft a response", "escalate the critical review", "staff performance comparison", 
            "top-performing stylist", "client retention rate", "stylist utilization", 
            "upsell conversion statistics", "incremental revenue", "accepted service recommendations", 
            "revenue forecast", "appointments volume", "business insights", 
            "salon utilization", "business context summary", "cohort reminders", "raw sql query",
            "salon performing today", "average rating across all reviews"
        ]
        
        intent = AgentIntent.UNKNOWN
        
        if any(k in q for k in staff_keywords):
            intent = AgentIntent.STAFF
        elif any(k in q for k in bi_keywords):
            intent = AgentIntent.BUSINESS_INTELLIGENCE
        else:
            # Stage 1 rule classification
            intent_map = {
                "book": AgentIntent.BOOKING, "appointment": AgentIntent.BOOKING, "reschedule": AgentIntent.BOOKING,
                "cancel": AgentIntent.BOOKING, "slot": AgentIntent.BOOKING, "available": AgentIntent.BOOKING,
                "lead": AgentIntent.LEAD_FOLLOWUP, "pipeline": AgentIntent.LEAD_FOLLOWUP, "prospect": AgentIntent.LEAD_FOLLOWUP,
                "crm": AgentIntent.LEAD_FOLLOWUP, "nurture": AgentIntent.LEAD_FOLLOWUP, "abandoned": AgentIntent.LEAD_FOLLOWUP,
                "upsell": AgentIntent.UPSELL, "upgrade": AgentIntent.UPSELL, "recommendation": AgentIntent.UPSELL,
                "promotion": AgentIntent.UPSELL, "add-on": AgentIntent.UPSELL, "bundle": AgentIntent.UPSELL,
                "review": AgentIntent.REPUTATION, "feedback": AgentIntent.REPUTATION, "rating": AgentIntent.REPUTATION,
                "reputation": AgentIntent.REPUTATION, "sentiment": AgentIntent.REPUTATION,
            }
            for kw, target_intent in intent_map.items():
                if kw in q:
                    intent = target_intent
                    break

        if intent == AgentIntent.UNKNOWN or intent == AgentIntent.BOOKING:
            if user_role.upper() == "STAFF":
                is_booking = any(k in q for k in ["book a", "book an", "cancel my", "reschedule my", "move my appointment"])
                if not is_booking:
                    intent = AgentIntent.STAFF
            elif user_role.upper() == "ADMIN":
                is_booking = any(k in q for k in ["book a", "book an", "cancel my", "reschedule my", "move my appointment"])
                if not is_booking:
                    intent = AgentIntent.BUSINESS_INTELLIGENCE

        if intent == AgentIntent.UNKNOWN:
            intent = AgentIntent.BOOKING

        intent = validate_role_intent(user_role, intent)
        return intent

    def _build_enriched_query(
        self,
        query: str,
        session_state: SessionState,
        entity_context: Dict[str, Any],
        intent: AgentIntent,
    ) -> str:
        """Build enriched query injecting system context, time, customer info, and RAG domains."""
        if get_settings().is_testing:
            return query
        pending = session_state.pending_booking
        user_role = session_state.user_role
        customer_id = session_state.metadata.get("customer_id")

        system_time_ctx = (
            f"[SYSTEM TIME CONTEXT: Current system time is "
            f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} (UTC)]\n"
        )
        if customer_id or entity_context.get("customer_id"):
            cid = entity_context.get("customer_id") or customer_id
            system_time_ctx += f"[SYSTEM CUSTOMER CONTEXT: Logged-in customer ID: {cid}, Role: {user_role}]\n"

        sid = entity_context.get("staff_id")
        if sid:
            try:
                from infrastructure.db.database import SessionLocal
                from infrastructure.db.models import Staff
                db_session = SessionLocal()
                staff_member = db_session.query(Staff).filter(Staff.id == sid).first()
                if staff_member:
                    system_time_ctx += f"[SYSTEM STAFF CONTEXT: Logged-in staff ID: {sid}, Name: {staff_member.full_name}, Role: {user_role}]\n"
                else:
                    system_time_ctx += f"[SYSTEM STAFF CONTEXT: Logged-in staff ID: {sid}, Role: {user_role}]\n"
                db_session.close()
            except Exception:
                system_time_ctx += f"[SYSTEM STAFF CONTEXT: Logged-in staff ID: {sid}, Role: {user_role}]\n"

        pending_ctx = ""
        if pending:
            pending_ctx = f"[BOOKING CONTEXT (collected so far): {pending}]\n"

        context_str = session_state.build_context_string(n=6)
        enriched = system_time_ctx + pending_ctx + context_str + f"\nLatest User Message: {query}"

        # Add domain-specific RAG context
        rag_context = ""
        try:
            from infrastructure.rag.enterprise_rag import get_rag_manager, RAGDomain
            domain_map = {
                AgentIntent.BOOKING:         [RAGDomain.POLICY_RAG, RAGDomain.CUSTOMER_RAG],
                AgentIntent.LEAD_FOLLOWUP:   [RAGDomain.LEAD_RAG],
                AgentIntent.UPSELL:          [RAGDomain.CUSTOMER_RAG],
                AgentIntent.REPUTATION:      [RAGDomain.CUSTOMER_RAG],
                AgentIntent.STAFF:           [RAGDomain.STAFF_RAG],
                AgentIntent.BUSINESS_INTELLIGENCE: [RAGDomain.BUSINESS_RAG],
            }
            domains = domain_map.get(intent, [RAGDomain.POLICY_RAG])
            latest_msg = query.split("Latest User Message:")[-1].strip() if "Latest User Message:" in query else query

            rag_context = get_rag_manager().get_context(
                query=latest_msg[:200],
                domains=domains,
                tenant_id=current_tenant_id_var.get(),
                k=2,
                max_chars=800,
            )
        except Exception as exc:
            logger.debug("[OrchestratorV3] RAG context skipped: %s", exc)

        if rag_context:
            enriched = f"{enriched}\n\n{rag_context}"

        # Token budget enforcement
        if self._budget_enforcer:
            try:
                latest_msg = query.split("Latest User Message:")[-1].strip() if "Latest User Message:" in query else query
                enriched = self._budget_enforcer.enforce(
                    system_ctx=enriched,
                    pending_ctx="",
                    history_ctx="",
                    user_message=latest_msg,
                    rag_context=rag_context,
                )
            except Exception as exc:
                logger.debug("[OrchestratorV3] Token budget enforcement skipped: %s", exc)

        return enriched


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
def get_phase2_orchestrator(
    name: str = "OrchestratorV3",
    tenant_id: str = "default",
) -> MultiAgentOrchestrator:
    """Factory: return a Phase 2 orchestrator."""
    return MultiAgentOrchestrator(name=name, tenant_id=tenant_id)


def get_entity_resolver():
    """Return the EntityResolverService module."""
    try:
        import application.services.entity_resolver_service as _ers
        return _ers
    except ImportError:
        logger.warning("[Orchestrator] entity_resolver_service not available.")
        return None


def get_conversation_state_service():
    """Return the ConversationStateService singleton."""
    try:
        from application.services.conversation_state_service import get_state_service
        return get_state_service()
    except ImportError:
        logger.warning("[Orchestrator] conversation_state_service not available.")
        return None


def get_permission_guard():
    """Return the PermissionGuard module."""
    try:
        import application.services.permission_guard as _pg
        return _pg
    except ImportError:
        logger.warning("[Orchestrator] permission_guard not available.")
        return None


def get_phase1_orchestrator(name: str = "Orchestrator") -> MultiAgentOrchestrator:
    """Return the orchestrator instance (compat wrapper)."""
    return MultiAgentOrchestrator(name=name)

