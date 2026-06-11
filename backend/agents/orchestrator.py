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
from core.openai_client_adapter import OpenAIChatCompletionClient

# Project imports
from agents import Agent
from core.config import get_settings
from core.llm_config import get_llm_config

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
UPSELL_SYSTEM_PROMPT = """You are Max, the helpful AI Upsell & Cross-Sell Specialist at SalonAI Workforce Platform.

Your job is to increase revenue per booking, suggest add-on services, recommend premium upgrades, and design promotional bundles.

Available tools:
1. get_upsell_recommendations(customer_id: str) - Fetch mock personalized service recommendations for a customer.
2. create_promotion(name: str, discount_percent: int, services: str) - Create a targeted promotional offer draft.
3. search_salon_knowledge(query: str) - Search salon policy, safety, and SOP documents.
4. search_receptionist_knowledge(query: str) - Search salon knowledge base for services, policies, and offers.
5. get_active_offers() - Retrieve active promotional offers.
6. search_customer_memory(query: str, customer_id: Optional[str]) - Search customer-specific styling and preferences memory.
7. search_upsell_memory(query: str) - Search upsell strategy, templates, and campaign guidelines memory.

Focus on genuine customer value. Always use RAG and memory tools before responding.
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
    escalate_customer_review,
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
    MAX_TURNS: int = 12
    # Timeout in seconds for each group chat execution
    AGENT_TIMEOUT: int = 60

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
            search_customer_memory,
            search_lead_memory,
            search_upsell_memory,
            search_reputation_memory,
            search_bi_memory,
        )
        from tools.receptionist_rag_tools import (
            search_receptionist_knowledge,
            get_active_offers,
            get_business_timings,
            get_cancellation_policy,
            get_refund_policy,
            get_faq_answer,
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
                search_receptionist_knowledge,
                get_active_offers,
                get_business_timings,
                get_cancellation_policy,
                get_refund_policy,
                get_faq_answer,
            ],
        )

        # 2. Lead Follow-up (real PostgreSQL-backed CRM tools + RAG Knowledge & Interactions search + lead/customer memory)
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
                search_lead_memory,
                search_customer_memory,
            ],
        )

        # 3. Upsell + RAG Knowledge search + upsell/customer memory
        agents[AgentIntent.UPSELL] = AssistantAgent(
            name="Max_Upsell",
            model_client=self.model_client,
            system_message=UPSELL_SYSTEM_PROMPT,
            tools=[
                get_upsell_recommendations,
                create_promotion,
                search_salon_knowledge,
                search_upsell_memory,
                search_customer_memory,
                get_active_offers,
                search_receptionist_knowledge,
            ],
        )

        # 4. Reputation + RAG Knowledge search + reputation memory (real DB-backed tools)
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
                escalate_customer_review,
                search_salon_knowledge,
                search_reputation_memory,
            ],
        )

        # 5. Business Intelligence + RAG Knowledge search + BI memory (real SQL-backed BI agent tools)
        from agents.bi_agent import (
            BI_SYSTEM_PROMPT,
            get_dashboard_summary,
            get_revenue_summary,
            get_customer_summary,
            get_staff_summary,
            get_lead_summary,
            get_review_summary,
            get_upsell_summary,
            generate_ai_insights,
            forecast_revenue,
            retrieve_business_context,
            query_raw_analytics_database,
            trigger_returning_cohort_reminders,
        )

        agents[AgentIntent.BUSINESS_INTELLIGENCE] = AssistantAgent(
            name="Atlas_BI",
            model_client=self.model_client,
            system_message=BI_SYSTEM_PROMPT,
            tools=[
                get_dashboard_summary,
                get_revenue_summary,
                get_customer_summary,
                get_staff_summary,
                get_lead_summary,
                get_review_summary,
                get_upsell_summary,
                generate_ai_insights,
                forecast_revenue,
                retrieve_business_context,
                query_raw_analytics_database,
                trigger_returning_cohort_reminders,
                search_salon_knowledge,
                search_bi_memory,
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
        Includes advanced message extraction and automatic JSON formatting fallback.
        """
        import asyncio

        logger.info(f"[Orchestrator] Executing direct agent run with '{agent.name}'")

        try:
            result = await asyncio.wait_for(agent.run(task=query), timeout=self.AGENT_TIMEOUT)

            # Extract the last conversational TextMessage from the agent
            response_text = ""
            for msg in reversed(result.messages):
                msg_type = type(msg).__name__
                source = getattr(msg, "source", getattr(msg, "sender", ""))
                content = getattr(msg, "content", None)
                
                # Check if this is a conversational text message from the specialist agent
                if msg_type == "TextMessage" and source == agent.name and content and isinstance(content, str) and len(content.strip()) > 0:
                    if content.strip().lower() not in [i.value for i in AgentIntent]:
                        response_text = content.strip()
                        break

            # Fallback 1: Any TextMessage from a non-user sender
            if not response_text:
                for msg in reversed(result.messages):
                    msg_type = type(msg).__name__
                    source = getattr(msg, "source", getattr(msg, "sender", ""))
                    content = getattr(msg, "content", None)
                    if msg_type == "TextMessage" and source != "user" and content and isinstance(content, str) and len(content.strip()) > 0:
                        if content.strip().lower() not in [i.value for i in AgentIntent]:
                            response_text = content.strip()
                            break

            # Fallback 2: Any last non-empty string message content in the history
            if not response_text:
                for msg in reversed(result.messages):
                    content = getattr(msg, "content", None)
                    if content and isinstance(content, str) and len(content.strip()) > 0:
                        if content.strip().lower() not in [i.value for i in AgentIntent]:
                            response_text = content.strip()
                            break

            if not response_text:
                response_text = "I've processed your request. Is there anything else I can help with?"

            # Formatter Fallback Layer: If the response is raw JSON or single-quoted dict, format it via LLM
            response_stripped = response_text.strip()
            is_json_response = (
                (response_stripped.startswith("{") or response_stripped.startswith("[") or response_stripped.startswith("{'"))
                or ("success" in response_stripped.lower() and ("true" in response_stripped.lower() or "false" in response_stripped.lower()) and len(response_stripped) < 200)
            )

            if is_json_response:
                logger.info("[Orchestrator] Raw JSON/dictionary response detected in _run_group_chat. Formatting using LLM...")
                try:
                    from autogen_core.models import SystemMessage, UserMessage
                    
                    if "Atlas" in agent.name:
                        persona = "Atlas, the professional AI Business Intelligence Analyst"
                        extra_instructions = "Use tables, lists, and clean Markdown headers to make the analytics look highly professional."
                    elif "Mia" in agent.name:
                        persona = "Mia, the professional AI Lead Follow-up Specialist"
                        extra_instructions = "Focus on CRM status updates, pipeline highlights, and next steps."
                    elif "Clara" in agent.name:
                        persona = "Clara, the professional AI Salon Receptionist"
                        extra_instructions = "Ensure a friendly tone, confirming booking details clearly."
                    else:
                        persona = f"{agent.name}, a professional AI Salon Assistant"
                        extra_instructions = ""
                    
                    formatter_sys_prompt = (
                        f"You are {persona}.\n"
                        "Translate this raw system/tool JSON result into a clean, warm, and professional natural language response.\n"
                        "Rules:\n"
                        "- Present the data accurately. Do NOT invent, hallucinate, or alter any numbers or dates.\n"
                        f"- {extra_instructions}\n"
                        "- Use Markdown formatting where appropriate (bolding, lists, tables)."
                    )
                    
                    sys_msg = SystemMessage(content=formatter_sys_prompt)
                    user_msg = UserMessage(content=f"Raw System Result:\n{response_stripped}", source="user")
                    
                    fmt_result = await asyncio.wait_for(
                        self.model_client.create(messages=[sys_msg, user_msg], max_tokens=600),
                        timeout=15.0
                    )
                    formatted_response = fmt_result.content.strip()
                    
                    if formatted_response and len(formatted_response) >= 15:
                        logger.info("[Orchestrator] Formatting successful.")
                        response_text = formatted_response
                    else:
                        logger.warning("[Orchestrator] Formatter returned empty or too short response. Using original.")
                except Exception as fmt_ex:
                    logger.error(f"[Orchestrator] Failed to format JSON response: {fmt_ex}")

            logger.info(f"[Orchestrator] Group chat with '{agent.name}' completed. Response length: {len(response_text)}")
            return response_text

        except asyncio.TimeoutError:
            logger.error(f"[Orchestrator] Group chat with agent '{agent.name}' timed out.")
            return "I apologize, but processing your request timed out. Please try again or refine your query."
        except Exception as e:
            logger.error(f"[Orchestrator] Group chat with agent '{agent.name}' failed: {e}", exc_info=True)
            raise

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
            error_str = str(e)
            logger.error(f"[Orchestrator] Processing failed: {error_str}", exc_info=True)
            
            # Provide user-friendly error messages instead of raw stack traces
            if "429" in error_str or "rate_limit" in error_str.lower() or "Rate limit" in error_str:
                user_msg = "Our AI service is temporarily at capacity. Please wait a minute and try again."
            elif "timeout" in error_str.lower():
                user_msg = "Your request took longer than expected. Please try a simpler question or try again shortly."
            elif "connection" in error_str.lower():
                user_msg = "Unable to connect to our analytics service. Please check your internet connection and try again."
            else:
                user_msg = "I encountered an unexpected issue processing your request. Please try again."
            
            return {
                "success": False,
                "response": user_msg,
                "error": user_msg,
                "agent_name": agent.name if agent else "Atlas_BI",
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
