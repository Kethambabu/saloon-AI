"""
Multi-Agent Orchestration System for SalonAI Workforce Platform — Phase 1.

PHASE 1 CHANGES vs. Legacy:
  1. Agents now use Capability Tools (appointment_workflow, crm_workflow, etc.)
     instead of raw mcp_read() / execute_transaction().
  2. ConversationStateService provides multi-turn session context.
  3. EntityResolverService normalizes names/dates before agent execution.
  4. PermissionGuard validates role permissions before routing.
  5. Orchestrator uses dynamic state-aware agent selection instead of pure
     keyword/LLM classification — conversation state influences routing.
  6. All existing agents (Clara, Mia, Max, Olivia, Atlas Staff, Atlas BI)
     are preserved with their original names and roles.

BACKWARD COMPATIBILITY:
  - All existing public APIs are unchanged.
  - mcp_read() / execute_transaction() still work for agents that call them
    directly (they are not removed — only de-emphasized in system prompts).
  - No external API contracts are broken.

Agents:
    1. Clara_Receptionist    – Bookings, scheduling, cancellations
    2. Mia_LeadFollowup      – Lead nurturing and follow-up campaigns
    3. Max_Upsell            – Service upgrades and cross-selling
    4. Olivia_Reputation     – Review management and reputation tracking
    5. Atlas_Staff           – Staff schedules and productivity
    6. Atlas_BI              – Business intelligence and analytics
"""

import os
import logging
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple

# AutoGen modern imports
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import SelectorGroupChat
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from core.openai_client_adapter import OpenAIChatCompletionClient

# Project imports
from agents import Agent
from core.config import get_settings
from core.llm_config import get_llm_config

# Phase 1 services
from services.entity_resolver_service import resolve_entity_context
from services.conversation_state_service import get_state_service
from services.permission_guard import validate_workflow_permission, PermissionDeniedError

logger = logging.getLogger(__name__)
settings = get_settings()


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


# ---------------------------------------------------------------------------
# Intent Classification
# ---------------------------------------------------------------------------
class AgentIntent(str, Enum):
    """Enumeration of supported intent categories for routing."""
    BOOKING = "booking"
    LEAD_FOLLOWUP = "lead_followup"
    UPSELL = "upsell"
    REPUTATION = "reputation"
    BUSINESS_INTELLIGENCE = "business_intelligence"
    STAFF = "staff"
    UNKNOWN = "unknown"


def classify_intent_rule_based(query: str) -> AgentIntent:
    """Legacy keyword-based intent classifier preserved for compatibility and testing."""
    q = query.lower()
    if any(k in q for k in ["book", "appointment", "reschedule", "haircut", "cancel", "slot", "available"]):
        return AgentIntent.BOOKING
    if any(k in q for k in ["pipeline", "prospect", "lead", "crm", "nurture", "abandoned"]):
        return AgentIntent.LEAD_FOLLOWUP
    if any(k in q for k in ["upgrade", "promotion", "upsell", "recommend", "add-on", "bundle"]):
        return AgentIntent.UPSELL
    if any(k in q for k in ["review", "feedback", "rating", "reputation", "sentiment"]):
        return AgentIntent.REPUTATION
    if any(k in q for k in ["my schedule", "today's appointments", "my clients", "leave request", "my revenue"]):
        return AgentIntent.STAFF
    if any(k in q for k in ["revenue", "report", "metrics", "utilisation", "utilization", "performance", "dashboard", "forecast", "analytics", "kpi"]):
        return AgentIntent.BUSINESS_INTELLIGENCE
    return AgentIntent.UNKNOWN


# ---------------------------------------------------------------------------
# Role-based permission boundaries
# ---------------------------------------------------------------------------
_ROLE_ALLOWED_INTENTS: Dict[str, List[AgentIntent]] = {
    "CUSTOMER": [AgentIntent.BOOKING, AgentIntent.REPUTATION, AgentIntent.UPSELL],
    "STAFF":    [AgentIntent.BOOKING, AgentIntent.REPUTATION, AgentIntent.STAFF, AgentIntent.UPSELL],
    "MANAGER":  list(AgentIntent),
    "OWNER":    list(AgentIntent),
    "ADMIN":    list(AgentIntent),
}


def validate_role_intent(role: str, intent: AgentIntent) -> AgentIntent:
    """
    Enforce role-based access control over agent routing.

    If the requested intent is NOT allowed for the user's role, demote it
    to AgentIntent.BOOKING (Clara) — the safe default for all roles.
    """
    allowed = _ROLE_ALLOWED_INTENTS.get(role.upper(), [AgentIntent.BOOKING])
    if intent not in allowed:
        logger.warning(
            "[RoleValidator] Role '%s' attempted intent '%s' — blocked. Demoting to BOOKING.",
            role, intent.value
        )
        return AgentIntent.BOOKING
    return intent


# ---------------------------------------------------------------------------
# Fast-path: zero-token responses for greetings / thanks / yes-no
# ---------------------------------------------------------------------------
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


def _fast_path_response(query: str) -> Optional[str]:
    """
    Return a canned response string for trivial social phrases, or None
    if the query needs actual LLM/agent processing.
    Cost: zero LLM tokens, sub-millisecond latency.
    """
    import re
    q = query.lower().strip().rstrip("!?. ")

    # 1. Greetings: check if query starts with a greeting token or is exactly a greeting token
    for g in _GREETING_TOKENS:
        if q == g or q.startswith(g + " "):
            return (
                "Hello! 👋 I'm Clara, your AI Salon Receptionist. "
                "I can help you book, reschedule, or cancel appointments, "
                "check availability, and answer questions about our services and policies. "
                "How can I assist you today?"
            )

    # 2. Thanks: check if any token in _THANKS_TOKENS is present as a full word/phrase
    for g in _THANKS_TOKENS:
        pattern = r'\b' + re.escape(g) + r'\b'
        if re.search(pattern, q):
            return (
                "You're very welcome! 😊 Is there anything else I can help you with "
                "— bookings, availability, or salon information?"
            )

    # 3. Farewell: check if any token in _FAREWELL_TOKENS is present as a full word/phrase
    for g in _FAREWELL_TOKENS:
        pattern = r'\b' + re.escape(g) + r'\b'
        if re.search(pattern, q):
            return "Goodbye! 👋 We look forward to seeing you at the salon soon!"

    if q in _CONFIRM_TOKENS:
        return None  # pass through to LLM
    return None


# ---------------------------------------------------------------------------
# LLM Intent Classifier Prompt
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Updated System Prompts — Phase 1 (Capability Tool based)
# ---------------------------------------------------------------------------

# Clara — Receptionist
RECEPTIONIST_SYSTEM_PROMPT_V2 = """You are Clara, the professional AI Receptionist at SalonAI Workforce Platform.

CORE RESPONSIBILITIES:
- Book, reschedule, and cancel appointments
- Check stylist availability and open slots
- Answer questions about services, pricing, and salon policies
- Search for customers and their booking history

YOUR PRIMARY TOOL — Use this for ALL booking operations:
  appointment_workflow(action, parameters, user_role)

Actions available:
  - 'check_availability'   : Check open slots. Parameters: {branch_id, date, staff_id, service_id}
  - 'book'                 : Create appointment. Parameters: {customer_id, branch_id, service_id, start_time, staff_id, notes}
  - 'cancel'               : Cancel appointment. Parameters: {appointment_id, customer_id}
  - 'reschedule'           : Reschedule. Parameters: {appointment_id, new_start_time, new_staff_id, customer_id}
  - 'history'              : Customer's booking history. Parameters: {customer_id}
  - 'list_services'        : All available services. Parameters: {}
  - 'list_staff'           : Available stylists. Parameters: {date, time, branch_id}
  - 'search_customers'     : Find customer. Parameters: {query}

SECONDARY TOOL — For policy / FAQ / knowledge lookups:
  search_knowledge_base(domain='policies'|'faq'|'customer_styling', query='...')

RULES:
1. ALWAYS use appointment_workflow() for all booking operations.
2. Never construct raw resource/filter combinations.
3. Always confirm booking details before executing 'book' action.
4. If dates or service names are ambiguous, ask the user to clarify.
5. Be warm, professional, and concise.
"""

# Mia — Lead Follow-up
LEAD_FOLLOWUP_SYSTEM_PROMPT_V2 = """You are Mia, the SalonAI Lead Follow-up Specialist.

CORE RESPONSIBILITIES:
- Recover abandoned bookings and nurture leads into appointments
- Register new leads in the CRM pipeline
- Send follow-up reminders and personalized messages
- Track and analyze lead conversion pipeline

YOUR PRIMARY TOOL — Use this for ALL CRM operations:
  crm_workflow(action, parameters, user_role)

Actions available:
  - 'search_leads'         : Filter CRM leads. Parameters: {status_filter, branch_id, source_filter}
  - 'create_lead'          : Register prospect. Parameters: {first_name, last_name, email, phone, source, branch_id, notes}
  - 'advance_lead'         : Move lead forward. Parameters: {lead_id, new_status, notes}
  - 'send_followup'        : Schedule outreach. Parameters: {lead_id, channel, message, scheduled_at}
  - 'generate_message'     : Draft personalized message. Parameters: {customer_id, lead_id, channel, tone}
  - 'abandoned_bookings'   : Find lost customers. Parameters: {branch_id, lookback_days}
  - 'conversion_analytics' : Lead conversion analytics. Parameters: {period_days, branch_id}
  - 'pipeline_snapshot'    : Quick pipeline count. Parameters: {branch_id}

SECONDARY TOOL — For knowledge lookups:
  search_knowledge_base(domain='policies'|'lead_memory', query='...')

RULES:
1. ALWAYS use crm_workflow() for all CRM operations.
2. Never construct raw mcp_read/execute_transaction calls.
3. Always prioritize high-value leads for follow-up.
"""

# Max — Upsell
UPSELL_SYSTEM_PROMPT_V2 = """You are Max, the helpful AI Upsell & Cross-Sell Specialist at SalonAI Workforce Platform.

CORE RESPONSIBILITIES:
- Increase revenue per booking with targeted add-on recommendations
- Suggest premium service upgrades and promotional bundles
- Track upsell acceptance and rejection analytics

YOUR PRIMARY TOOL — Use this for ALL recommendation operations:
  recommendation_workflow(action, parameters, user_role)

Actions available:
  - 'get_recommendations'  : Fetch personalized recs. Parameters: {customer_id}
  - 'accept'               : Record accepted rec. Parameters: {customer_id, service_id, appointment_id}
  - 'reject'               : Record rejected rec. Parameters: {customer_id, service_id, appointment_id}
  - 'analytics'            : Upsell performance. Parameters: {}

SECONDARY TOOL — For customer history and knowledge:
  search_knowledge_base(domain='upsell_memory'|'customer_styling', query='...')

RULES:
1. ALWAYS use recommendation_workflow() for all upsell operations.
2. Never guess or hallucinate recommendations — use the tool.
3. Focus on genuine customer value.
"""

# Olivia — Reputation
REPUTATION_SYSTEM_PROMPT_V2 = """You are Olivia, the SalonAI Reputation & Review Manager.

CORE RESPONSIBILITIES:
- Monitor and respond to customer reviews
- Analyze review sentiment and generate reputation analytics
- Find and escalate critical reviews

YOUR PRIMARY TOOL — Use this for ALL reputation operations:
  reputation_workflow(action, parameters, user_role)

Actions available:
  - 'get_reviews'     : Fetch reviews. Parameters: {customer_id, staff_id, sentiment, rating}
  - 'analytics'       : Average rating analytics. Parameters: {}
  - 'critical'        : Get critical reviews. Parameters: {}
  - 'respond'         : Draft response to review. Parameters: {review_id, custom_response}
  - 'scorecard'       : Sentiment distribution. Parameters: {}
  - 'escalate'        : Escalate critical review. Parameters: {review_id}

SECONDARY TOOL — For policy knowledge:
  search_knowledge_base(domain='policies'|'reputation_memory', query='...')

RULES:
1. ALWAYS use reputation_workflow() for all review operations.
2. Never construct raw database reads — use the tool.
3. Escalate 1-star and highly negative reviews immediately.
"""

# Atlas Staff
STAFF_SYSTEM_PROMPT_V2 = """You are Atlas, the helpful AI Staff Productivity Assistant at SalonAI Workforce Platform.

CORE RESPONSIBILITIES:
- Help staff members manage schedules, appointments, and customer interactions
- Provide performance analytics and revenue summaries
- Handle leave requests and customer reminders

YOUR PRIMARY TOOL — Use this for ALL staff operations:
  staff_workflow(action, parameters, user_role)

Actions available:
  - 'get_schedule'         : Schedule for a date. Parameters: {staff_id, date}
  - 'today_schedule'       : Today's appointments. Parameters: {staff_id}
  - 'next_customer'        : Next upcoming customer. Parameters: {staff_id}
  - 'customer_history'     : Customer booking history. Parameters: {customer_name}
  - 'customer_preferences' : Customer styling preferences. Parameters: {customer_name}
  - 'staff_revenue'        : Revenue generated. Parameters: {staff_id}
  - 'staff_performance'    : KPI benchmarks. Parameters: {staff_id}
  - 'pending_appointments' : Unconfirmed bookings. Parameters: {staff_id}
  - 'create_leave'         : Log leave request. Parameters: {staff_id, leave_date, reason}
  - 'send_reminders'       : Send appointment reminders. Parameters: {staff_id}

SECONDARY TOOL — For policy lookups:
  search_knowledge_base(domain='policies'|'staff_memory', query='...')

RULES:
1. ALWAYS use staff_workflow() for all staff operations.
2. Never construct raw database reads.
3. Format all responses in clean Markdown tables or bullet points.
4. NEVER output raw JSON or Python dicts.
"""

# Atlas BI
BI_SYSTEM_PROMPT_V2 = """\
You are Atlas, the brilliant Business Intelligence Analyst at SalonAI Workforce Platform.

CORE RESPONSIBILITIES:
- Generate revenue and booking trend reports
- Analyze staff utilization and branch performance
- Provide KPI dashboards and forecasts
- Compare period-over-period metrics
- Identify growth opportunities and operational bottlenecks

YOUR PRIMARY TOOL — Use this for ALL analytics operations:
  analytics_workflow(action, parameters, user_role)

Actions available:
  - 'dashboard'          : Core KPI dashboard. Parameters: {}
  - 'revenue'            : Revenue intelligence. Parameters: {}
  - 'customers'          : Customer retention & LTV. Parameters: {}
  - 'staff'              : Stylist performance. Parameters: {}
  - 'leads'              : CRM funnel conversion. Parameters: {}
  - 'reviews'            : Reputation aggregates. Parameters: {}
  - 'upsell'             : Cross-sell performance. Parameters: {}
  - 'insights'           : AI-generated insights. Parameters: {}
  - 'forecast'           : Next-month forecasts. Parameters: {}
  - 'business_context'   : Historical RAG context. Parameters: {days}
  - 'raw_sql'            : Custom SELECT query. Parameters: {sql}
  - 'cohort_reminders'   : Trigger cohort reminders. Parameters: {}

SECONDARY TOOL — For policy and BI knowledge:
  search_knowledge_base(domain='bi_memory'|'policies', query='...')

SQL SAFETY RULES:
- Write ONLY SELECT queries. NEVER INSERT, UPDATE, DELETE, DROP, ALTER.

FORMATTING:
- Act like a McKinsey consultant: objective, precise, structured.
- Use clean Markdown tables and bullet points.
"""


# ---------------------------------------------------------------------------
# Model Client Factory
# ---------------------------------------------------------------------------
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
# Phase 1 Orchestrator
# ---------------------------------------------------------------------------
class MultiAgentOrchestrator(Agent):
    """
    Enterprise multi-agent orchestration system — Phase 1 Architecture.

    Changes from legacy:
    1. Agents use Capability Tools (appointment_workflow etc.) not raw mcp_read.
    2. ConversationStateService tracks multi-turn session context.
    3. State-aware routing: pending_booking context influences agent selection.
    4. PermissionGuard validates intents before agent dispatch.
    5. EntityResolver normalizes dates/names before context injection.
    """

    MAX_TURNS: int = 12
    AGENT_TIMEOUT: int = 60

    def __init__(self, name: str = "Orchestrator", role: str = "Multi-Agent Coordinator"):
        super().__init__(name=name, role=role)
        logger.info(f"Initializing Multi-Agent Orchestrator (Phase 1) '{name}'...")

        self.model_client = _create_model_client()
        self.state_service = get_state_service()

        # Build specialist agents
        self.agents: Dict[AgentIntent, AssistantAgent] = self._build_agents()

        # Lightweight LLM classifier (no tools)
        self.classifier = AssistantAgent(
            name="IntentClassifier",
            model_client=self.model_client,
            system_message=_CLASSIFIER_SYSTEM_PROMPT,
        )

        logger.info(
            f"Orchestrator (Phase 1) initialized with {len(self.agents)} specialist agents: "
            f"{[a.name for a in self.agents.values()]}"
        )

    # ------------------------------------------------------------------
    # Agent Factory
    # ------------------------------------------------------------------
    def _build_agents(self) -> Dict[AgentIntent, AssistantAgent]:
        """Instantiate all specialist AutoGen AssistantAgents with Capability Tools."""

        # Import Capability Tools
        from tools.capability_tools import (
            appointment_workflow,
            crm_workflow,
            recommendation_workflow,
            reputation_workflow,
            staff_workflow,
            analytics_workflow,
        )
        from tools.rag_unified import search_knowledge_base

        # Import RAG tools for enrichment
        try:
            from rag.retriever import search_salon_knowledge
        except Exception:
            search_salon_knowledge = None

        agents: Dict[AgentIntent, AssistantAgent] = {}

        # 1. Clara — Receptionist
        clara_tools = [appointment_workflow, search_knowledge_base]
        agents[AgentIntent.BOOKING] = AssistantAgent(
            name="Clara_Receptionist",
            model_client=self.model_client,
            system_message=RECEPTIONIST_SYSTEM_PROMPT_V2,
            description=(
                "Handles all customer bookings, appointments, scheduling, cancellations, "
                "rescheduling, availability checks, salon FAQ, hours, services, and policies."
            ),
            tools=clara_tools,
        )

        # 2. Mia — Lead Follow-up
        mia_tools = [crm_workflow, search_knowledge_base]
        agents[AgentIntent.LEAD_FOLLOWUP] = AssistantAgent(
            name="Mia_LeadFollowup",
            model_client=self.model_client,
            system_message=LEAD_FOLLOWUP_SYSTEM_PROMPT_V2,
            description=(
                "Handles lead management, CRM pipelines, follow-up messages, campaigns, "
                "and customer nurturing."
            ),
            tools=mia_tools,
        )

        # 3. Max — Upsell
        max_tools = [recommendation_workflow, search_knowledge_base]
        agents[AgentIntent.UPSELL] = AssistantAgent(
            name="Max_Upsell",
            model_client=self.model_client,
            system_message=UPSELL_SYSTEM_PROMPT_V2,
            description=(
                "Handles service upgrades, promotional offers, discounts, bundles, "
                "and upsell suggestions."
            ),
            tools=max_tools,
        )

        # 4. Olivia — Reputation
        olivia_tools = [reputation_workflow, search_knowledge_base]
        agents[AgentIntent.REPUTATION] = AssistantAgent(
            name="Olivia_Reputation",
            model_client=self.model_client,
            system_message=REPUTATION_SYSTEM_PROMPT_V2,
            description=(
                "Handles customer reviews, rating analytics, feedback sentiment, "
                "reputation scores, and drafting review responses."
            ),
            tools=olivia_tools,
        )

        # 5. Atlas Staff
        atlas_staff_tools = [staff_workflow, search_knowledge_base]
        agents[AgentIntent.STAFF] = AssistantAgent(
            name="Atlas_Staff",
            model_client=self.model_client,
            system_message=STAFF_SYSTEM_PROMPT_V2,
            description=(
                "Helps salon staff with daily schedules, customer histories, performance "
                "analytics, leave requests, and appointment reminders."
            ),
            tools=atlas_staff_tools,
        )

        # 6. Atlas BI
        atlas_bi_tools = [analytics_workflow, search_knowledge_base]
        agents[AgentIntent.BUSINESS_INTELLIGENCE] = AssistantAgent(
            name="Atlas_BI",
            model_client=self.model_client,
            system_message=BI_SYSTEM_PROMPT_V2,
            description=(
                "Handles business intelligence, revenue metrics, dashboards, staff "
                "performance, utilization reports, and operational forecasts."
            ),
            tools=atlas_bi_tools,
        )

        return agents

    # ------------------------------------------------------------------
    # State-Aware Intent Resolution
    # ------------------------------------------------------------------
    def _resolve_intent_with_state(
        self,
        query: str,
        session_id: str,
        user_role: str,
    ) -> AgentIntent:
        """
        Determine agent intent considering conversation state.

        Priority:
          1. If there is active pending_booking context → continue with BOOKING
          2. Rule-based keyword classification
          3. Role validation
        """
        session = self.state_service.get_session(session_id)

        # Priority 1: Sticky BOOKING if pending booking context exists
        if session and session.pending_booking and len(session.pending_booking) > 0:
            logger.info(
                "[Orchestrator] Sticky BOOKING — session has pending_booking context: %s",
                list(session.pending_booking.keys())
            )
            return AgentIntent.BOOKING

        # Priority 2: Rule-based classification
        intent = classify_intent_rule_based(query)
        if intent == AgentIntent.UNKNOWN:
            intent = AgentIntent.BOOKING  # safe default

        # Priority 3: Role validation (demote if not allowed)
        intent = validate_role_intent(user_role, intent)
        return intent

    def _build_enriched_query(
        self,
        query: str,
        session_state,
        entity_context: Dict[str, Any],
        intent: AgentIntent,
    ) -> str:
        """Build enriched query with conversation context and system context."""
        context_str = session_state.build_context_string(n=6)
        pending = session_state.pending_booking
        user_role = session_state.user_role
        customer_id = session_state.metadata.get("customer_id")

        system_time_ctx = (
            f"[SYSTEM TIME CONTEXT: Current system time is "
            f"{__import__('datetime').datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} (UTC)]\n"
        )
        if customer_id or entity_context.get("customer_id"):
            cid = entity_context.get("customer_id") or customer_id
            system_time_ctx += f"[SYSTEM CUSTOMER CONTEXT: Logged-in customer ID: {cid}, Role: {user_role}]\n"

        # Staff context enrichment
        sid = entity_context.get("staff_id")
        if sid:
            try:
                from db.database import SessionLocal
                from db.models import Staff
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

        return system_time_ctx + pending_ctx + context_str + f"\nLatest User Message: {query}"

    # ------------------------------------------------------------------
    # Intent Classification (LLM fallback)
    # ------------------------------------------------------------------
    async def _classify_intent(self, query: str) -> AgentIntent:
        """
        Two-stage intent classifier:
          Stage 1 – Tiny LLM classifier with a stripped-down prompt.
          Stage 2 – Fallback to BOOKING on any error (safe default).
        """
        import asyncio as _asyncio
        logger.info("[Orchestrator] Running LLM intent classifier...")
        try:
            result = await _asyncio.wait_for(
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

    # ------------------------------------------------------------------
    # Group Chat Execution
    # ------------------------------------------------------------------
    async def _run_group_chat(self, agent: AssistantAgent, query: str) -> str:
        """Execute a bounded agent run with the selected specialist."""
        import asyncio
        logger.info(f"[Orchestrator] Executing agent run with '{agent.name}'")
        
        # Inject query context for resolvers and permission guards
        try:
            from core.query_context import set_query_context
            set_query_context(query)
        except Exception:
            pass
        try:
            from agents.receptionist_agent import ReceptionistAgent
            ReceptionistAgent.CURRENT_QUERY_CONTEXT = query
        except Exception:
            pass
        try:
            from agents.staff_assistant_agent import StaffAssistantAgent
            StaffAssistantAgent.CURRENT_QUERY_CONTEXT = query
        except Exception:
            pass

        try:
            result = await asyncio.wait_for(agent.run(task=query), timeout=self.AGENT_TIMEOUT)

            response_text = ""
            # First: TextMessage from the specific agent
            for msg in reversed(result.messages):
                msg_type = type(msg).__name__
                source = getattr(msg, "source", getattr(msg, "sender", ""))
                content = getattr(msg, "content", None)
                if (msg_type == "TextMessage" and source == agent.name
                        and content and isinstance(content, str) and len(content.strip()) > 0):
                    if content.strip().lower() not in [i.value for i in AgentIntent]:
                        response_text = content.strip()
                        break

            # Fallback 1: any TextMessage from non-user
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

            # Fallback 2: any non-empty content
            if not response_text:
                for msg in reversed(result.messages):
                    content = getattr(msg, "content", None)
                    if content and isinstance(content, str) and len(content.strip()) > 0:
                        if content.strip().lower() not in [i.value for i in AgentIntent]:
                            response_text = content.strip()
                            break

            if not response_text:
                response_text = "I've processed your request. Is there anything else I can help with?"

            # LLM formatter fallback for raw JSON responses
            response_stripped = response_text.strip()
            is_json = (
                (response_stripped.startswith("{") or response_stripped.startswith("["))
                or ("success" in response_stripped.lower()
                    and ("true" in response_stripped.lower() or "false" in response_stripped.lower())
                    and len(response_stripped) < 200)
            )

            if is_json:
                is_typed = False
                try:
                    import json
                    parsed = json.loads(response_stripped)
                    if isinstance(parsed, dict) and "response_type" in parsed:
                        is_typed = True
                except Exception:
                    pass

                if not is_typed:
                    try:
                        from autogen_core.models import SystemMessage, UserMessage
                        if "Clara" in agent.name:
                            persona = "Clara, the professional AI Salon Receptionist"
                            extra = "Ensure a friendly tone, confirming booking details clearly."
                        elif "Mia" in agent.name:
                            persona = "Mia, the professional AI Lead Follow-up Specialist"
                            extra = "Focus on CRM status updates, pipeline highlights, and next steps."
                        elif "Atlas_BI" in agent.name or (hasattr(agent, 'name') and "BI" in agent.name):
                            persona = "Atlas, the professional AI Business Intelligence Analyst"
                            extra = "Use tables, lists, and Markdown headers for professional analytics."
                        elif "Olivia" in agent.name:
                            persona = "Olivia, the professional AI Reputation Manager"
                            extra = "Summarize review insights clearly and professionally."
                        else:
                            persona = f"{agent.name}, a professional AI Salon Assistant"
                            extra = ""

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
        if "atlas_staff" in name_lower or "staff" in name_lower:
            return AgentIntent.STAFF
        if "atlas_bi" in name_lower or "bi" in name_lower:
            return AgentIntent.BUSINESS_INTELLIGENCE
        return AgentIntent.BOOKING

    async def _run_team(self, query: str, user_role: str = "ADMIN") -> Tuple[str, str]:
        """
        Build a SelectorGroupChat with role-filtered agents and run it.
        Returns (response_text, agent_name).
        """
        import asyncio

        # Build role-filtered participant list
        allowed_intents = _ROLE_ALLOWED_INTENTS.get(user_role.upper(), [AgentIntent.BOOKING, AgentIntent.REPUTATION])
        participants = [self.agents[intent] for intent in allowed_intents if intent in self.agents]

        # Ensure at least 2 participants for SelectorGroupChat
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

        # Inject query context for resolvers and permission guards
        try:
            from core.query_context import set_query_context
            set_query_context(query)
        except Exception:
            pass
        try:
            from agents.receptionist_agent import ReceptionistAgent
            ReceptionistAgent.CURRENT_QUERY_CONTEXT = query
        except Exception:
            pass
        try:
            from agents.staff_assistant_agent import StaffAssistantAgent
            StaffAssistantAgent.CURRENT_QUERY_CONTEXT = query
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
                        and source not in ("user", "selector", "SelectorGroupChat",
                                           "SelectorGroupChatManager", "")
                        and len(content.strip()) > 5):
                    response_text = content.strip()
                    agent_name = source
                    break

            if not response_text:
                for msg in reversed(result.messages):
                    source = getattr(msg, "source", getattr(msg, "sender", ""))
                    content = getattr(msg, "content", None)
                    if content and isinstance(content, str) and len(content.strip()) > 5 and source != "user":
                        response_text = content.strip()
                        agent_name = source if source else "Clara_Receptionist"
                        break

            if not response_text:
                response_text = "I've processed your request. Is there anything else I can help with?"

            return response_text, agent_name

        except asyncio.TimeoutError:
            logger.error("[Orchestrator] Team run timed out.")
            return "I apologize, but processing timed out. Please try again.", "Clara_Receptionist"
        except Exception as e:
            logger.error(f"[Orchestrator] Team run failed: {e}", exc_info=True)
            raise

    # ------------------------------------------------------------------
    # Main Entry Point
    # ------------------------------------------------------------------
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Standardized entrypoint — Phase 1.

        Additional state management and entity resolution happen here
        before dispatching to specialist agents.

        Args:
            input_data: {
                "query":       str (required) — user message
                "session_id":  str — conversation session ID
                "user_id":     str — authenticated user ID
                "user_role":   str — CUSTOMER | STAFF | MANAGER | OWNER | ADMIN
                "customer_id": str — logged-in customer UUID (optional)
                "staff_id":    str — logged-in staff UUID (optional)
                "chat_history":list — prior messages (optional)
                "use_team":    bool — force team mode (optional)
            }

        Returns:
            {
                "success":    bool,
                "response":   str,
                "agent_name": str,
                "session_id": str,
                "intent":     str,
            }
        """
        query = input_data.get("query", "").strip()
        if not query:
            return {"success": False, "error": "Empty query."}

        session_id  = input_data.get("session_id", "default")
        user_id     = input_data.get("user_id", "anonymous")
        user_role   = input_data.get("user_role", "CUSTOMER")
        customer_id = input_data.get("customer_id")
        chat_history = input_data.get("chat_history", [])
        use_team    = input_data.get("use_team", False)

        logger.info(
            "[Orchestrator] Processing query (session=%s role=%s): '%s'",
            session_id, user_role, query[:100]
        )

        # --- Fast-path for trivial social phrases ---
        fast = _fast_path_response(query)
        if fast:
            return {
                "success": True,
                "response": fast,
                "agent_name": "Clara_Receptionist",
                "session_id": session_id,
                "intent": AgentIntent.BOOKING.value,
            }

        # --- Session state ---
        session = self.state_service.get_or_create(
            session_id=session_id,
            user_id=user_id,
            user_role=user_role,
        )
        session.add_turn("user", query)

        # --- Entity resolution for context enrichment ---
        resolved_context = resolve_entity_context(
            {
                "customer_id": customer_id or input_data.get("customer_id"),
                "staff_id":    input_data.get("staff_id"),
                "branch_id":   input_data.get("branch_id"),
            }
        )
        if resolved_context.get("customer_id"):
            session.metadata["customer_id"] = resolved_context["customer_id"]

        # --- State-aware intent resolution ---
        intent = self._resolve_intent_with_state(query, session_id, user_role)
        logger.info("[Orchestrator] Resolved intent: %s", intent.value)

        # --- Build enriched query with conversation context ---
        enriched_query = self._build_enriched_query(
            query=query,
            session_state=session,
            entity_context=resolved_context,
            intent=intent,
        )

        # --- Dispatch ---
        try:
            if use_team:
                response_text, agent_name = await self._run_team(enriched_query, user_role)
            else:
                agent = self.agents.get(intent, self.agents[AgentIntent.BOOKING])
                response_text = await self._run_group_chat(agent, enriched_query)
                agent_name = agent.name

            # --- Update session state ---
            session.add_turn("assistant", response_text, agent_name=agent_name)
            session.agent_name = agent_name

            return {
                "success": True,
                "response": response_text,
                "agent_name": agent_name,
                "session_id": session_id,
                "intent": intent.value,
            }

        except Exception as e:
            logger.error("[Orchestrator] Dispatch failed: %s", e, exc_info=True)
            return {
                "success": False,
                "error": f"Agent processing failed: {e}",
                "session_id": session_id,
                "intent": intent.value,
            }
