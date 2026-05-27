"""
Multi-Agent Orchestration System for SalonAI Workforce Platform.

Routes incoming user queries to the most appropriate specialist agent
via an LLM-powered intent classifier, then orchestrates execution using
Microsoft AutoGen's GroupChat / RoundRobinGroupChat patterns.

Agents:
    1. ReceptionistAgent  – Bookings, scheduling, cancellations
    2. LeadFollowupAgent  – Lead nurturing and follow-up campaigns
    3. UpsellAgent         – Service upgrades and cross-selling
    4. ReputationAgent     – Review management and reputation tracking
    5. BIAgent             – Business intelligence and analytics
"""

import os
import logging
from enum import Enum
from typing import Dict, Any, List, Optional

# AutoGen modern imports (agentchat v0.4+ / v0.7+)
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_ext.models.openai import OpenAIChatCompletionClient

# Project imports
from agents import Agent
from core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


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
    UNKNOWN = "unknown"


# Keyword sets for fast rule-based intent pre-classification
_INTENT_KEYWORDS: Dict[AgentIntent, List[str]] = {
    AgentIntent.BOOKING: [
        "book", "appointment", "schedule", "reschedule", "cancel",
        "available", "slot", "availability", "haircut", "facial",
        "massage", "color", "stylist", "time", "reserve",
    ],
    AgentIntent.LEAD_FOLLOWUP: [
        "lead", "follow up", "followup", "prospect", "contact",
        "nurture", "campaign", "outreach", "convert", "pipeline",
        "interested", "inquiry", "new customer",
    ],
    AgentIntent.UPSELL: [
        "upgrade", "upsell", "cross-sell", "premium", "add-on",
        "recommend", "bundle", "package", "loyalty", "membership",
        "promotion", "deal", "offer", "discount", "combo",
    ],
    AgentIntent.REPUTATION: [
        "review", "rating", "feedback", "reputation", "google review",
        "yelp", "star", "complaint", "testimonial", "satisfaction",
        "nps", "sentiment", "respond to review",
    ],
    AgentIntent.BUSINESS_INTELLIGENCE: [
        "report", "analytics", "revenue", "metric", "dashboard",
        "kpi", "trend", "forecast", "performance", "insight",
        "data", "comparison", "growth", "profit", "occupancy",
    ],
}


def classify_intent_rule_based(query: str) -> AgentIntent:
    """
    Fast, deterministic intent classifier using keyword matching.
    Returns the intent with the highest keyword-hit score.
    """
    query_lower = query.lower()
    scores: Dict[AgentIntent, int] = {}

    for intent, keywords in _INTENT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in query_lower)
        if score > 0:
            scores[intent] = score

    if not scores:
        return AgentIntent.UNKNOWN

    return max(scores, key=scores.get)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Specialist Agent Definitions
# ---------------------------------------------------------------------------

# ---- Lead Follow-up Agent (real CRM tools from lead_followup_agent) ------
from agents.lead_followup_agent import (
    LEAD_FOLLOWUP_SYSTEM_PROMPT,
    find_abandoned_bookings,
    search_leads,
    register_new_lead,
    advance_lead_status,
    send_followup_reminder,
    create_personalized_message,
    view_conversion_analytics,
    view_pipeline_snapshot,
)


# ---- Upsell Agent --------------------------------------------------------
UPSELL_SYSTEM_PROMPT = """\
You are Max, the Upsell & Cross-Sell Strategist at SalonAI Workforce.
Your responsibilities:
1. Analyse a customer's booking history and suggest premium upgrades.
2. Recommend complementary add-on services.
3. Design promotional bundles and loyalty packages.
4. Calculate potential revenue uplift from upsell opportunities.
5. Craft persuasive, non-pushy upgrade pitches.

Focus on genuine customer value, not hard selling.
When you have no real data, provide realistic illustrative examples.
"""


def get_upsell_recommendations(customer_id: str) -> str:
    """
    Get personalised upsell recommendations for a customer based on their history.

    Args:
        customer_id: The UUID string of the customer.
    """
    logger.info(f"[Upsell] Generating recommendations for customer {customer_id}")
    return (
        '{"customer_id": "' + customer_id + '", "recommendations": ['
        '{"type": "upgrade", "current": "Basic Haircut", "suggested": "Signature Precision Haircut", '
        '"price_diff": "+$40", "reason": "Customer has visited 5+ times"},'
        '{"type": "add-on", "service": "Deep Conditioning Treatment", '
        '"price": "$35", "reason": "Complements recent color service"},'
        '{"type": "bundle", "name": "Pamper Package", "includes": ["Facial", "Massage"], '
        '"savings": "$45", "reason": "Popular combo for repeat customers"}'
        '], "estimated_revenue_uplift": "$120"}'
    )


def create_promotion(name: str, discount_percent: int, services: str) -> str:
    """
    Create a targeted promotional offer.

    Args:
        name: The promotion display name.
        discount_percent: Percentage discount (1-50).
        services: Comma-separated list of service names included.
    """
    logger.info(f"[Upsell] Creating promotion: {name}")
    return (
        f'{{"success": true, "promo_id": "promo-001", "name": "{name}", '
        f'"discount": "{discount_percent}%", "services": "{services}", '
        f'"status": "draft", "valid_until": "2026-06-30"}}'
    )


# ---- Reputation Agent (real DB-backed tools from reputation_agent) --------
from agents.reputation_agent import (
    REPUTATION_SYSTEM_PROMPT,
    view_customer_reviews,
    view_review_analytics,
    find_critical_reviews,
    draft_review_response,
    view_reputation_scorecard,
)


# ---- Business Intelligence Agent -----------------------------------------
BI_SYSTEM_PROMPT = """\
You are Atlas, the Business Intelligence Analyst at SalonAI Workforce.
Your responsibilities:
1. Generate revenue and booking trend reports.
2. Analyse staff utilisation and branch performance.
3. Provide KPI dashboards and forecasts.
4. Compare period-over-period metrics.
5. Identify growth opportunities and operational bottlenecks.

Always be precise with numbers, use clear formatting, and cite data periods.
When you have no real data, provide realistic illustrative examples.
"""


def get_revenue_report(period: str = "last_30_days") -> str:
    """
    Generate a revenue report for a specified period.

    Args:
        period: Time period – 'last_7_days', 'last_30_days', 'last_quarter', or 'ytd'.
    """
    logger.info(f"[BI] Generating revenue report for period: {period}")
    return (
        f'{{"period": "{period}", "total_revenue": "$48,250", '
        f'"total_bookings": 312, "avg_ticket": "$154.65", '
        f'"revenue_by_service": {{'
        f'"Haircut": "$12,750", "Color": "$18,400", '
        f'"Facial": "$9,600", "Massage": "$7,500"}}, '
        f'"growth_vs_prior": "+12.3%", "top_branch": "Downtown"}}'
    )


def get_staff_performance(staff_id: Optional[str] = None) -> str:
    """
    Get staff performance metrics.

    Args:
        staff_id: Optional UUID string of a specific staff member. Omit for all staff.
    """
    logger.info(f"[BI] Fetching staff performance (staff: {staff_id or 'all'})")
    return (
        '{"staff": ['
        '{"name": "James Wilson", "bookings": 89, "revenue": "$13,750", '
        '"utilisation": "78%", "avg_rating": 4.8},'
        '{"name": "Priya Sharma", "bookings": 76, "revenue": "$16,200", '
        '"utilisation": "85%", "avg_rating": 4.9},'
        '{"name": "Carlos Reyes", "bookings": 65, "revenue": "$9,800", '
        '"utilisation": "62%", "avg_rating": 4.5}'
        '], "period": "last_30_days"}'
    )


def get_booking_trends(period: str = "last_30_days") -> str:
    """
    Analyse booking trends including peak hours, popular services, and demand patterns.

    Args:
        period: Time period – 'last_7_days', 'last_30_days', 'last_quarter', or 'ytd'.
    """
    logger.info(f"[BI] Analysing booking trends for period: {period}")
    return (
        f'{{"period": "{period}", "total_bookings": 312, '
        f'"peak_day": "Saturday", "peak_hour": "11:00 AM", '
        f'"busiest_branch": "Downtown", '
        f'"popular_services": ["Balayage & Color", "Signature Haircut", "Facial"], '
        f'"cancellation_rate": "8.2%", "no_show_rate": "3.1%", '
        f'"avg_lead_time_days": 4.5}}'
    )


# ---------------------------------------------------------------------------
# Model Client Factory
# ---------------------------------------------------------------------------
def _create_model_client() -> OpenAIChatCompletionClient:
    """Create an LLM model client from environment configuration."""
    groq_key = settings.groq_api_key or os.environ.get("GROQ_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")

    if groq_key and groq_key != "your-groq-key-here":
        logger.info("[Orchestrator] Using Groq LLM endpoint")
        return OpenAIChatCompletionClient(
            model="llama-3.3-70b-specdec",
            api_key=groq_key,
            base_url="https://api.groq.com/openai/v1",
        )
    elif openai_key:
        logger.info("[Orchestrator] Using OpenAI LLM endpoint")
        return OpenAIChatCompletionClient(
            model="gpt-4o",
            api_key=openai_key,
        )
    else:
        logger.warning("[Orchestrator] No LLM keys found – using mock client")
        return OpenAIChatCompletionClient(
            model="gpt-4o",
            api_key="mock-api-key-for-testing",
        )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
class MultiAgentOrchestrator(Agent):
    """
    Enterprise multi-agent orchestration system.

    Routes incoming queries to the most appropriate specialist agent using
    a two-stage classification pipeline:
        1. Fast rule-based keyword scoring (zero-latency).
        2. Fallback LLM-powered classification for ambiguous queries.

    Uses AutoGen RoundRobinGroupChat with MaxMessageTermination to prevent
    infinite loops and enforce bounded execution.
    """

    # Maximum messages allowed in any group chat run (safety ceiling)
    MAX_TURNS: int = 6

    def __init__(self, name: str = "Orchestrator", role: str = "Multi-Agent Coordinator"):
        super().__init__(name=name, role=role)
        logger.info(f"Initializing Multi-Agent Orchestrator '{name}'...")

        self.model_client = _create_model_client()

        # ---- Build specialist agents ----
        self.agents: Dict[AgentIntent, AssistantAgent] = self._build_agents()

        # ---- Build the classifier agent (lightweight, no tools) ----
        self.classifier = AssistantAgent(
            name="IntentClassifier",
            model_client=self.model_client,
            system_message=(
                "You are an intent classification engine. "
                "Given a user query, respond with EXACTLY one of these labels and nothing else:\n"
                "booking, lead_followup, upsell, reputation, business_intelligence\n\n"
                "Rules:\n"
                "- Booking: appointments, scheduling, cancellations, availability\n"
                "- Lead follow-up: leads, prospects, nurturing, campaigns\n"
                "- Upsell: upgrades, promotions, bundles, cross-sells\n"
                "- Reputation: reviews, ratings, feedback, sentiment\n"
                "- Business Intelligence: reports, analytics, KPIs, revenue\n\n"
                "Respond ONLY with the label. No explanation."
            ),
        )

        logger.info(
            f"Orchestrator initialized with {len(self.agents)} specialist agents: "
            f"{[a.name for a in self.agents.values()]}"
        )

    # ------------------------------------------------------------------
    # Agent Factory
    # ------------------------------------------------------------------
    def _build_agents(self) -> Dict[AgentIntent, AssistantAgent]:
        """Instantiate all specialist AutoGen AssistantAgents."""

        # Import receptionist tools inline to avoid circular import
        from agents.receptionist_agent import (
            check_stylist_availability,
            book_new_appointment,
            cancel_existing_appointment,
            reschedule_existing_appointment,
            check_customer_booking_history,
            RECEPTIONIST_SYSTEM_PROMPT,
        )

        # Import RAG retriever tools inline to avoid circular import
        from rag.retriever import (
            search_salon_knowledge,
            search_customer_interactions,
            search_all_context,
        )

        agents: Dict[AgentIntent, AssistantAgent] = {}

        # 1. Receptionist (re-uses existing tools & prompt + RAG Knowledge search)
        agents[AgentIntent.BOOKING] = AssistantAgent(
            name="Clara_Receptionist",
            model_client=self.model_client,
            system_message=RECEPTIONIST_SYSTEM_PROMPT,
            tools=[
                check_stylist_availability,
                book_new_appointment,
                cancel_existing_appointment,
                reschedule_existing_appointment,
                check_customer_booking_history,
                search_salon_knowledge,
            ],
        )

        # 2. Lead Follow-up (real PostgreSQL-backed CRM tools + RAG Knowledge & Interactions search)
        agents[AgentIntent.LEAD_FOLLOWUP] = AssistantAgent(
            name="Mia_LeadFollowup",
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
                search_salon_knowledge,
                search_customer_interactions,
            ],
        )

        # 3. Upsell + RAG Knowledge search
        agents[AgentIntent.UPSELL] = AssistantAgent(
            name="Max_Upsell",
            model_client=self.model_client,
            system_message=UPSELL_SYSTEM_PROMPT,
            tools=[get_upsell_recommendations, create_promotion, search_salon_knowledge],
        )

        # 4. Reputation + RAG Knowledge search (real DB-backed tools)
        agents[AgentIntent.REPUTATION] = AssistantAgent(
            name="Olivia_Reputation",
            model_client=self.model_client,
            system_message=REPUTATION_SYSTEM_PROMPT,
            tools=[
                view_customer_reviews,
                view_review_analytics,
                find_critical_reviews,
                draft_review_response,
                view_reputation_scorecard,
                search_salon_knowledge,
            ],
        )

        # 5. Business Intelligence + RAG Knowledge search (real SQL-backed BI agent tools)
        from agents.bi_agent import (
            BI_SYSTEM_PROMPT,
            view_revenue_report,
            view_staff_performance,
            view_customer_retention,
            view_service_popularity,
            query_raw_analytics_database,
        )

        agents[AgentIntent.BUSINESS_INTELLIGENCE] = AssistantAgent(
            name="Atlas_BI",
            model_client=self.model_client,
            system_message=BI_SYSTEM_PROMPT,
            tools=[
                view_revenue_report,
                view_staff_performance,
                view_customer_retention,
                view_service_popularity,
                query_raw_analytics_database,
                search_salon_knowledge,
            ],
        )

        return agents

    # ------------------------------------------------------------------
    # Intent Classification Pipeline
    # ------------------------------------------------------------------
    async def _classify_intent(self, query: str) -> AgentIntent:
        """
        Two-stage intent classifier:
            Stage 1 – Rule-based keyword scoring (instant, deterministic).
            Stage 2 – LLM fallback for ambiguous or keyword-poor queries.
        """
        # Stage 1: Keyword matching
        rule_intent = classify_intent_rule_based(query)
        if rule_intent != AgentIntent.UNKNOWN:
            logger.info(f"[Orchestrator] Rule-based classification → {rule_intent.value}")
            return rule_intent

        # Stage 2: LLM fallback
        logger.info("[Orchestrator] Rule-based inconclusive, falling back to LLM classifier...")
        try:
            result = await self.classifier.run(task=query)
            label = result.messages[-1].content.strip().lower()
            logger.info(f"[Orchestrator] LLM classification → '{label}'")

            # Map to enum
            for intent in AgentIntent:
                if intent.value == label:
                    return intent

            logger.warning(f"[Orchestrator] LLM returned unknown label '{label}', defaulting to BOOKING")
            return AgentIntent.BOOKING

        except Exception as e:
            logger.error(f"[Orchestrator] LLM classification failed: {e}", exc_info=True)
            return AgentIntent.BOOKING  # Safe default

    # ------------------------------------------------------------------
    # Group Chat Execution
    # ------------------------------------------------------------------
    async def _run_group_chat(
        self, agent: AssistantAgent, query: str
    ) -> str:
        """
        Execute a bounded group chat with the selected specialist agent.
        Uses MaxMessageTermination + TextMentionTermination for safety.
        """
        termination = MaxMessageTermination(max_messages=self.MAX_TURNS) | TextMentionTermination("TERMINATE")

        group_chat = RoundRobinGroupChat(
            participants=[agent],
            termination_condition=termination,
        )

        logger.info(f"[Orchestrator] Starting group chat with '{agent.name}' (max_turns={self.MAX_TURNS})")

        result = await group_chat.run(task=query)

        # Extract the last meaningful agent response (skip tool-call messages)
        response_text = ""
        for msg in reversed(result.messages):
            content = getattr(msg, "content", None)
            if content and isinstance(content, str) and len(content.strip()) > 0:
                # Skip pure label messages from the classifier
                if content.strip().lower() not in [i.value for i in AgentIntent]:
                    response_text = content.strip()
                    break

        if not response_text:
            response_text = "I've processed your request. Is there anything else I can help with?"

        logger.info(f"[Orchestrator] Group chat with '{agent.name}' completed. Response length: {len(response_text)}")
        return response_text

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main orchestration entrypoint.

        Args:
            input_data: Dictionary containing:
                - "query": The user's natural language message.
                - "intent_override": (Optional) Force routing to a specific intent.

        Returns:
            Dictionary containing:
                - "success": bool
                - "response": str – Agent's conversational reply
                - "agent_name": str – Name of the specialist that handled the query
                - "intent": str – Classified intent label
        """
        query = input_data.get("query")
        if not query:
            return {"success": False, "error": "Input data must contain a 'query' key."}

        logger.info(f"[Orchestrator] Processing query: '{query[:100]}...'")

        try:
            # 1. Classify intent (with optional override)
            intent_override = input_data.get("intent_override")
            if intent_override:
                try:
                    intent = AgentIntent(intent_override)
                    logger.info(f"[Orchestrator] Using intent override → {intent.value}")
                except ValueError:
                    logger.warning(f"[Orchestrator] Invalid intent override '{intent_override}', classifying normally")
                    intent = await self._classify_intent(query)
            else:
                intent = await self._classify_intent(query)

            # 2. Route to specialist agent
            agent = self.agents.get(intent)
            if agent is None:
                logger.warning(f"[Orchestrator] No agent registered for intent '{intent.value}', defaulting to Receptionist")
                agent = self.agents[AgentIntent.BOOKING]
                intent = AgentIntent.BOOKING

            logger.info(f"[Orchestrator] Routing to agent '{agent.name}' (intent: {intent.value})")

            # 3. Execute via group chat
            response_text = await self._run_group_chat(agent, query)

            return {
                "success": True,
                "response": response_text,
                "agent_name": agent.name,
                "intent": intent.value,
            }

        except Exception as e:
            logger.error(f"[Orchestrator] Processing failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Orchestration failed: {str(e)}",
            }

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------
    def list_agents(self) -> List[Dict[str, str]]:
        """Return metadata about all registered specialist agents."""
        return [
            {"intent": intent.value, "agent_name": agent.name}
            for intent, agent in self.agents.items()
        ]

    def get_agent_for_intent(self, intent_str: str) -> Optional[AssistantAgent]:
        """Look up a specialist agent by intent string."""
        try:
            return self.agents.get(AgentIntent(intent_str))
        except ValueError:
            return None
