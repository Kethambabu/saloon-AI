"""
Business Intelligence (BI) AI Agent for SalonAI Workforce Platform.
Built using Microsoft AutoGen (agentchat v0.4+ / v0.10+).

Exposes professional analytics summaries, SQL querying, forecasting, 
and Business Metrics RAG context matching to corporate dashboard assistants.
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
from agents import Agent
from core.config import get_settings
from core.llm_config import get_llm_config
from db.database import SessionLocal
from services.analytics_service import AnalyticsService
from services.insights_service import InsightsService
from services.forecast_service import ForecastService
from services.rag_service import RAGService
from tools.bi_tools import execute_bi_sql_query

logger = logging.getLogger(__name__)
settings = get_settings()


# ---------------------------------------------------------------------------
# Decoupled Wrapper Tools (exposes clean function schemas to LLM)
# ---------------------------------------------------------------------------
def get_dashboard_summary() -> str:
    """
    Retrieve today's core business performance indicators: revenue, completed bookings, 
    new customers, lead conversion rate, average rating, and upsell revenue.
    """
    logger.info("[BIAgent] Tool call: get_dashboard_summary()")
    db = SessionLocal()
    try:
        res = AnalyticsService.get_dashboard_summary(db)
        return str(res)
    finally:
        db.close()


def get_revenue_summary() -> str:
    """
    Retrieve detailed revenue intelligence aggregates: total/weekly/monthly/yearly revenue, 
    revenue by service, branch, staff, and daily line chart data.
    """
    logger.info("[BIAgent] Tool call: get_revenue_summary()")
    db = SessionLocal()
    try:
        res = AnalyticsService.get_revenue_summary(db)
        return str(res)
    finally:
        db.close()


def get_customer_summary() -> str:
    """
    Retrieve customer intelligence aggregates: total customers count, returning clients, 
    VIP transactors, lifetime values (LTV), and inactive clients in the last 90 days.
    """
    logger.info("[BIAgent] Tool call: get_customer_summary()")
    db = SessionLocal()
    try:
        res = AnalyticsService.get_customer_summary(db)
        return str(res)
    finally:
        db.close()


def get_staff_summary() -> str:
    """
    Retrieve stylist performance benchmarks: rankings, completed appointments count, 
    revenues generated, average stylist ratings, and upsell revenues sold.
    """
    logger.info("[BIAgent] Tool call: get_staff_summary()")
    db = SessionLocal()
    try:
        res = AnalyticsService.get_staff_summary(db)
        return str(res)
    finally:
        db.close()


def get_lead_summary() -> str:
    """
    Retrieve CRM lead pipeline conversion aggregates: new, contacted, converted, and lost 
    leads volume counts, alongside average conversion rate.
    """
    logger.info("[BIAgent] Tool call: get_lead_summary()")
    db = SessionLocal()
    try:
        res = AnalyticsService.get_lead_summary(db)
        return str(res)
    finally:
        db.close()


def get_review_summary() -> str:
    """
    Retrieve reputation intelligence aggregates: average rating (out of 5.0), positive vs 
    negative reviews volume counts, and primary customer complaints (e.g. Waiting Time).
    """
    logger.info("[BIAgent] Tool call: get_review_summary()")
    db = SessionLocal()
    try:
        res = AnalyticsService.get_review_summary(db)
        return str(res)
    finally:
        db.close()


def get_upsell_summary() -> str:
    """
    Retrieve automated upsell performance aggregates: upsell revenue generated, acceptances 
    count, acceptance rate, and top accepted service combination.
    """
    logger.info("[BIAgent] Tool call: get_upsell_summary()")
    db = SessionLocal()
    try:
        res = AnalyticsService.get_upsell_summary(db)
        return str(res)
    finally:
        db.close()


def generate_ai_insights() -> str:
    """
    Exposes real-time natural language business telemetry insights (e.g. revenue increases, 
    top service segments, or bottle-necks) dynamically analyzed from database patterns.
    """
    logger.info("[BIAgent] Tool call: generate_ai_insights()")
    db = SessionLocal()
    try:
        res = InsightsService.generate_ai_insights(db)
        return str(res)
    finally:
        db.close()


def forecast_revenue() -> str:
    """
    Retrieve expected next month parameters for expected revenue, appointments completed, 
    leads generated, and average growth forecasts (+8% model).
    """
    logger.info("[BIAgent] Tool call: forecast_revenue()")
    db = SessionLocal()
    try:
        res = ForecastService.get_forecast_metrics(db)
        return str(res)
    finally:
        db.close()


def retrieve_business_context(days: int = 90) -> str:
    """
    Retrieve historical context logs from daily snapshots (metric_date, revenue, conversions, 
    ratings) to perform multi-dimensional Business Metrics RAG reasoning.

    Args:
        days: Optional number of days of history to fetch (default: 90).
    """
    logger.info(f"[BIAgent] Tool call: retrieve_business_context(days={days})")
    db = SessionLocal()
    try:
        res = RAGService.retrieve_business_context(db, days)
        return str(res)
    finally:
        db.close()


def query_raw_analytics_database(sql_select_query: str) -> str:
    """
    Executes a secure read-only SQL SELECT query against the analytics database to search for 
    any other complex metrics (e.g., SELECT count(*) FROM staff WHERE role = 'Senior Stylist').
    Appends a LIMIT of 50 automatically and protects against SQL injection write operations.

    Args:
        sql_select_query: The SQL SELECT query string to execute.
    """
    logger.info(f"[BIAgent] Tool call: query_raw_analytics_database(sql='{sql_select_query[:100]}...')")
    result = execute_bi_sql_query(sql_select_query)
    return str(result)


# ---------------------------------------------------------------------------
# Conversational Prompt
# ---------------------------------------------------------------------------
BI_SYSTEM_PROMPT = """\
You are Atlas, the brilliant and analytical Business Intelligence Analyst at SalonAI Workforce Platform.

🎯 CORE MISSION:
You act as an elite corporate consultant, operations advisor, and financial analyst for salon owners (Admins).
Synthesize complex aggregates across branches, staff performance, customer retention cohorts, reviews, 
CRM leads, and upsells into beautiful data-driven suggestions.

📋 YOUR ANALYTICAL TOOLKIT:
Always try to use standard metric tools before writing custom database queries:
1. `get_dashboard_summary` - Core aggregates (revenue, conversions, active bookings, ratings).
2. `get_revenue_summary` - Revenue line-chart labels and distributions (service, branch, staff).
3. `get_customer_summary` - Customer LTV ranks and VIP returning client aggregates.
4. `get_staff_summary` - StylistCompleted bookings, ratings, utilization, and upsell commissions.
5. `get_lead_summary` - Lead conversions pipeline.
6. `get_review_summary` - Customer ratings counts and complaints highlights (e.g., Waiting Time).
7. `get_upsell_summary` - Accepted upgrades earnings and acceptance conversion ratios.
8. `generate_ai_insights` - Auto-compiled real-time corporate bullet points.
9. `forecast_revenue` - Next month expected forecasting (+8% model).
10. `retrieve_business_context` - Multi-dimensional **Business Metrics RAG** context retrieval (pulls daily snapshots).
11. `query_raw_analytics_database` - Run raw SELECT queries on database schemas.

🧠 THE POWER OF BUSINESS METRICS RAG:
When asked comparative business questions (e.g. "Why is revenue decreasing?" or "How does this compare to last month?"),
you MUST call `retrieve_business_context` first. 
Instead of giving static single metric points, leverage RAG history to deliver multi-layered comparisons:
- Contrast current rates to the last 3 months.
- Compare drops in lead conversions, ratings shifts, and upsell acceptances.
- Identify which specific branch or staff member contributed most to the change.

📂 SALON DATABASE TABLE SCHEMAS FOR SQL GENERATION:
Use the following schemas to generate SELECT SQL queries when standard tools do not cover the requested metrics:
- **branches** (id UUID, name VARCHAR, code VARCHAR, address VARCHAR, city VARCHAR, phone VARCHAR, email VARCHAR, is_active BOOLEAN)
- **staff** (id UUID, branch_id UUID, first_name VARCHAR, last_name VARCHAR, email VARCHAR, phone VARCHAR, role VARCHAR, is_active BOOLEAN)
- **customers** (id UUID, first_name VARCHAR, last_name VARCHAR, email VARCHAR, phone VARCHAR, is_active BOOLEAN)
- **services** (id UUID, name VARCHAR, description VARCHAR, price DECIMAL, duration_minutes INTEGER, is_active BOOLEAN)
- **appointments** (id UUID, customer_id UUID, branch_id UUID, staff_id UUID, service_id UUID, start_time TIMESTAMP, end_time TIMESTAMP, status VARCHAR, notes VARCHAR)
  - *Appointment Status values*: 'PENDING', 'CONFIRMED', 'COMPLETED', 'CANCELLED', 'NO_SHOW'
- **leads** (id UUID, branch_id UUID, customer_name VARCHAR, customer_email VARCHAR, customer_phone VARCHAR, service_name VARCHAR, preferred_date DATE, status VARCHAR)
  - *Lead Status values*: 'NEW', 'CONTACTED', 'INTERESTED', 'CONVERTED', 'LOST'
- **reviews** (id UUID, customer_id UUID, branch_id UUID, appointment_id UUID, rating INTEGER, comment VARCHAR, sentiment VARCHAR, ai_response VARCHAR, status VARCHAR)
  - *Review Status values*: 'PENDING', 'APPROVED', 'REJECTED'

📏 STRICT SQL SAFETY RULES:
- You MUST only write SELECT queries. Never attempt INSERT, UPDATE, DELETE, CREATE, DROP, ALTER, TRUNCATE, or ";" statements.
- Never query tables outside the whitelisted schemas (e.g., system catalogs).

🎨 FORMATTING STYLE:
- Act like a McKinsey consultant: objective, precise, structured, and action-oriented.
- Always present data in clean, standard Markdown tables and clear bullet points.
"""


# ---------------------------------------------------------------------------
# Agent Class
# ---------------------------------------------------------------------------
class BIAgent(Agent):
    """
    Business Intelligence AI Agent powered by Microsoft AutoGen v0.4+.
    Provides comprehensive aggregates compiler, sql querying, forecasting, 
    and Business Metrics RAG context retrieval.
    """

    def __init__(self, name: str = "Atlas", role: str = "Business Intelligence Analyst"):
        super().__init__(name=name, role=role)
        logger.info(f"Initializing Business Intelligence Agent '{name}'...")

        self._conversation_memory: Dict[str, List[Dict[str, str]]] = {}
        self._analytics: Dict[str, int] = {
            "queries_processed": 0,
            "insights_generated": 0,
            "rag_lookups": 0,
            "forecast_queries": 0,
            "raw_sql_queries": 0,
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

        # 3. Build AutoGen AssistantAgent with full Zenoti-style tool suite
        self.assistant = AssistantAgent(
            name=name,
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
            ],
        )

        logger.info(f"Business Intelligence Agent '{name}' initialized with 11 tools.")

    def _get_memory_context(self, session_id: str) -> str:
        """Build conversation context string from memory for a given session."""
        history = self._conversation_memory.get(session_id, [])
        if not history:
            return ""

        context_lines = ["Here is the conversation history so far for context:"]
        for entry in history[-5:]:  # Bounded memory context
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
            logger.info(f"[BIAgent] Cleared memory for session: {session_id}")

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
        Standardized entrypoint to process business intelligence and raw SQL queries.
        """
        query = input_data.get("query")
        if not query:
            return {"success": False, "error": "Input data must contain a 'query' key."}

        session_id = input_data.get("session_id", "default")
        chat_history = input_data.get("chat_history", [])

        logger.info(f"[BIAgent] Processing query (session={session_id}): '{query[:100]}'")
        self._track_analytics("queries_processed")

        # Telemetry updates
        query_lower = query.lower()
        if any(kw in query_lower for kw in ["insight", "suggest", "compare", "why"]):
            self._track_analytics("insights_generated")
        if any(kw in query_lower for kw in ["history", "rag", "past", "last", "context"]):
            self._track_analytics("rag_lookups")
        if any(kw in query_lower for kw in ["forecast", "predict", "expected", "next month"]):
            self._track_analytics("forecast_queries")
        if any(kw in query_lower for kw in ["sql", "select", "query", "database"]):
            self._track_analytics("raw_sql_queries")

        try:
            full_query = ""

            # Sliced chat history
            if chat_history:
                full_query += "Here is the conversation history so far for context:\n"
                for msg in chat_history[-5:]:
                    role = msg.get("role", "user").capitalize()
                    content = msg.get("content", "")
                    full_query += f"- {role}: {content}\n"
                full_query += "\n"

            # Session memory
            memory_context = self._get_memory_context(session_id)
            if memory_context and not chat_history:
                full_query += memory_context + "\n"

            full_query += f"Latest User Message: {query}"

            # Store user query
            self._store_memory(session_id, "user", query)

            # AutoGen run
            result = await self.assistant.run(task=full_query)
            response_text = result.messages[-1].content

            # Store assistant response
            self._store_memory(session_id, "assistant", response_text)

            logger.info(f"[BIAgent] Query processed successfully (session={session_id})")

            return {
                "success": True,
                "agent_name": self.name,
                "response": response_text,
                "session_id": session_id,
                "analytics": self.get_analytics(),
            }

        except Exception as e:
            logger.error(f"[BIAgent] Error processing query: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": f"Business Intelligence Agent processing failed: {str(e)}",
            }
