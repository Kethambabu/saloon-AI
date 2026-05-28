"""
Business Intelligence (BI) AI Agent for SalonAI Workforce Platform.
Built using Microsoft AutoGen (agentchat v0.4+ / v0.10+).

Exposes analytical dashboard aggregates, staff metrics, retention reports,
and natural language secure SQL query translation to AutoGen conversational pipelines.
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
from tools.bi_tools import (
    get_revenue_analytics,
    get_staff_performance_analytics,
    get_retention_analytics,
    get_service_popularity_analytics,
    execute_bi_sql_query,
)

logger = logging.getLogger(__name__)
settings = get_settings()


# ---------------------------------------------------------------------------
# Decoupled Wrapper Tools (exposes clean function schemas to LLM)
# ---------------------------------------------------------------------------
def view_revenue_report(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    branch_id: Optional[str] = None,
) -> str:
    """
    Generate revenue summaries and daily transaction data for line charts.

    Args:
        start_date: Optional filter start date (YYYY-MM-DD).
        end_date: Optional filter end date (YYYY-MM-DD).
        branch_id: Optional UUID string of a specific branch to filter records.
    """
    logger.info(f"[BIAgent] Tool call: view_revenue_report(start={start_date}, end={end_date}, branch={branch_id})")
    result = get_revenue_analytics(start_date=start_date, end_date=end_date, branch_id=branch_id)
    return str(result)


def view_staff_performance(
    branch_id: Optional[str] = None
) -> str:
    """
    Benchmark stylists' completed bookings, revenue, ratings, and utilization ratios.

    Args:
        branch_id: Optional UUID string of a physical branch location to filter.
    """
    logger.info(f"[BIAgent] Tool call: view_staff_performance(branch={branch_id})")
    result = get_staff_performance_analytics(branch_id=branch_id)
    return str(result)


def view_customer_retention() -> str:
    """
    Computes cohort statistics for repeat vs first-time customers and customer lifetime values (LTV).
    """
    logger.info("[BIAgent] Tool call: view_customer_retention()")
    result = get_retention_analytics()
    return str(result)


def view_service_popularity() -> str:
    """
    Analyzes booking volume shares and total revenue percentages across services.
    """
    logger.info("[BIAgent] Tool call: view_service_popularity()")
    result = get_service_popularity_analytics()
    return str(result)


def query_raw_analytics_database(
    sql_select_query: str
) -> str:
    """
    Executes a secure read-only SQL SELECT query against the analytics database.
    Appends a LIMIT of 50 automatically and protects against SQL injection write operations.

    Args:
        sql_select_query: The SQL SELECT query string to execute (e.g. 'SELECT count(*) FROM staff').
    """
    logger.info(f"[BIAgent] Tool call: query_raw_analytics_database(sql='{sql_select_query[:100]}...')")
    result = execute_bi_sql_query(sql_select_query)
    return str(result)


# ---------------------------------------------------------------------------
# Conversational Prompt
# ---------------------------------------------------------------------------
BI_SYSTEM_PROMPT = """\
You are Atlas, the brilliant and analytical Business Intelligence Agent at SalonAI Workforce Platform.

🎯 CORE MISSION:
Expose critical business insights, revenue distributions, stylist performance scores, and user behavior trends. 
Translate natural language queries into highly descriptive, structure-oriented business intelligence reports.

📋 YOUR CAPABILITIES:
1. **Revenue Report Analysis** — Get revenue totals, averages, and chart datasets.
   Use `view_revenue_report` (supports branch & date range filtering).
2. **Staff Benchmarks** — Benchmark booking counts, revenues, utilization, and ratings.
   Use `view_staff_performance`.
3. **Retention & Loyalty Cohorts** — Review repeat bookers, loyal metrics, and LTV charts.
   Use `view_customer_retention`.
4. **Service Popularity Metrics** — Track total bookings and revenue shares by service item.
   Use `view_service_popularity`.
5. **Secure Natural Language SQL Querying** — Run raw SELECT queries on the salon database securely.
   Use `query_raw_analytics_database` (must only contain read-only SELECT statements).

📂 SALON DATABASE TABLE SCHEMAS FOR SQL GENERATION:
Use the following schemas to generate SQL queries when standard tools do not cover the requested metrics:
- **branches** (id UUID, name VARCHAR, code VARCHAR, address VARCHAR, city VARCHAR, phone VARCHAR, email VARCHAR, is_active BOOLEAN)
- **staff** (id UUID, branch_id UUID, first_name VARCHAR, last_name VARCHAR, email VARCHAR, phone VARCHAR, role VARCHAR, is_active BOOLEAN)
- **customers** (id UUID, first_name VARCHAR, last_name VARCHAR, email VARCHAR, phone VARCHAR, is_active BOOLEAN)
- **services** (id UUID, name VARCHAR, description VARCHAR, price DECIMAL, duration_minutes INTEGER, is_active BOOLEAN)
- **appointments** (id UUID, customer_id UUID, branch_id UUID, staff_id UUID, service_id UUID, start_time TIMESTAMP, end_time TIMESTAMP, status VARCHAR, notes VARCHAR)
  - *Appointment Status values*: 'pending', 'confirmed', 'completed', 'cancelled', 'no_show'
- **leads** (id UUID, branch_id UUID, first_name VARCHAR, last_name VARCHAR, email VARCHAR, phone VARCHAR, source VARCHAR, status VARCHAR, notes VARCHAR)
  - *Lead Status values*: 'new', 'contacted', 'converted', 'lost'
- **reviews** (id UUID, customer_id UUID, branch_id UUID, appointment_id UUID, rating INTEGER, comment VARCHAR, status VARCHAR)
  - *Review Status values*: 'pending', 'approved', 'rejected'

📏 STRICT SQL SAFETY RULES:
- You MUST only write SELECT queries. Never attempt INSERT, UPDATE, DELETE, CREATE, DROP, ALTER, TRUNCATE, or ";" statements.
- Never query tables outside the whitelisted schemas (e.g., system catalogs).
- Keep SQL simple and efficient. Always filter using JOINs where appropriate.

🎨 COMMUNICATION & FORMATTING STYLE:
- Be highly professional, data-driven, and objective. Never make up numbers.
- Present reports with beautiful Markdown structures:
  - Use clear headings and lists.
  - Render tabulated results in standard Markdown tables.
  - Present chart data explicitly so frontends can easily render them (state the labels and values).
  - Summarize key actionable insights (e.g. highlight top-performing services or low-utilization staff).
"""


# ---------------------------------------------------------------------------
# Agent Class
# ---------------------------------------------------------------------------
class BIAgent(Agent):
    """
    Business Intelligence AI Agent powered by Microsoft AutoGen v0.4+ and OpenAI/Groq endpoints.
    Provides complete revenue analysis, staff benchmarking, retention tracking,
    and natural language SQL generation.
    """

    def __init__(self, name: str = "Atlas", role: str = "Business Intelligence Analyst"):
        super().__init__(name=name, role=role)
        logger.info(f"Initializing Business Intelligence Agent '{name}'...")

        self._conversation_memory: Dict[str, List[Dict[str, str]]] = {}
        self._analytics: Dict[str, int] = {
            "queries_processed": 0,
            "revenue_queries": 0,
            "staff_queries": 0,
            "retention_queries": 0,
            "popularity_queries": 0,
            "raw_sql_queries": 0,
        }

        # 1. Configure model client - Groq (free, open-source alternative to OpenAI)
        groq_key = settings.groq_api_key or os.environ.get("GROQ_API_KEY")

        if groq_key and groq_key != "your-groq-key-here":
            logger.info("Configuring BIAgent with Groq endpoint...")
            self.model_client = OpenAIChatCompletionClient(
                model="llama-3.3-70b-specdec",
                api_key=groq_key,
                base_url="https://api.groq.com/openai/v1",
            )
        else:
            logger.warning("No Groq API key found – BIAgent using mock client for testing.")
            self.model_client = OpenAIChatCompletionClient(
                model="llama-3.3-70b-specdec",
                api_key="mock-groq-key-for-testing",
                base_url="https://api.groq.com/openai/v1",
            )

        # 2. Build AutoGen AssistantAgent with full tool suite
        self.assistant = AssistantAgent(
            name=name,
            model_client=self.model_client,
            system_message=BI_SYSTEM_PROMPT,
            tools=[
                view_revenue_report,
                view_staff_performance,
                view_customer_retention,
                view_service_popularity,
                query_raw_analytics_database,
            ],
        )

        logger.info(f"Business Intelligence Agent '{name}' initialized with 5 analytics tools.")

    def _get_memory_context(self, session_id: str) -> str:
        """Build conversation context string from memory for a given session."""
        history = self._conversation_memory.get(session_id, [])
        if not history:
            return ""

        context_lines = ["Here is the conversation history so far for context:"]
        for entry in history[-10:]:
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

        Args:
            input_data: Dictionary containing:
                - "query": The user's natural language analytical query (required).
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

        logger.info(f"[BIAgent] Processing query (session={session_id}): '{query[:100]}'")
        self._track_analytics("queries_processed")

        # Track category keywords for analytics telemetry
        query_lower = query.lower()
        if any(kw in query_lower for kw in ["revenue", "sales", "ticket", "earnings"]):
            self._track_analytics("revenue_queries")
        if any(kw in query_lower for kw in ["staff", "stylist", "utilization", "performance", "bench"]):
            self._track_analytics("staff_queries")
        if any(kw in query_lower for kw in ["retention", "cohort", "repeat", "visitor", "ltv"]):
            self._track_analytics("retention_queries")
        if any(kw in query_lower for kw in ["service", "popular", "market share", "treatment"]):
            self._track_analytics("popularity_queries")
        if any(kw in query_lower for kw in ["sql", "select", "query", "database", "table"]):
            self._track_analytics("raw_sql_queries")

        try:
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

            # Store user query in memory
            self._store_memory(session_id, "user", query)

            # Execute AutoGen AssistantAgent run task
            result = await self.assistant.run(task=full_query)

            # Extract response text
            response_text = result.messages[-1].content

            # Store assistant response in memory
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
