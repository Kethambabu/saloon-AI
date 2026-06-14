"""
AnalyticsWorkflow — Phase 1 Capability Workflow for Atlas BI.

Agents call analytics_workflow() instead of raw mcp_read calls.

Covers:
  - dashboard summary
  - revenue summary
  - customer summary
  - staff summary
  - lead summary
  - review summary
  - upsell summary
  - AI insights
  - forecast revenue
  - retrieve business context
  - raw SQL query
  - trigger cohort reminders
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class AnalyticsWorkflow:
    """
    Phase 1 workflow encapsulating all BI analytics operations for Atlas BI.
    """

    @staticmethod
    def get_dashboard() -> Dict[str, Any]:
        """Retrieve today's core business performance indicators."""
        logger.info("[AnalyticsWorkflow] get_dashboard")
        try:
            from agents.bi_agent import get_dashboard_summary
            return {"success": True, "result": get_dashboard_summary()}
        except Exception as exc:
            logger.error("[AnalyticsWorkflow] get_dashboard failed: %s", exc)
            return {"success": False, "error": str(exc)}

    @staticmethod
    def get_revenue() -> Dict[str, Any]:
        """Retrieve detailed revenue intelligence aggregates."""
        logger.info("[AnalyticsWorkflow] get_revenue")
        try:
            from agents.bi_agent import get_revenue_summary
            return {"success": True, "result": get_revenue_summary()}
        except Exception as exc:
            logger.error("[AnalyticsWorkflow] get_revenue failed: %s", exc)
            return {"success": False, "error": str(exc)}

    @staticmethod
    def get_customers() -> Dict[str, Any]:
        """Retrieve customer intelligence aggregates (LTV, retention cohorts)."""
        logger.info("[AnalyticsWorkflow] get_customers")
        try:
            from agents.bi_agent import get_customer_summary
            return {"success": True, "result": get_customer_summary()}
        except Exception as exc:
            logger.error("[AnalyticsWorkflow] get_customers failed: %s", exc)
            return {"success": False, "error": str(exc)}

    @staticmethod
    def get_staff() -> Dict[str, Any]:
        """Retrieve stylist performance benchmarks."""
        logger.info("[AnalyticsWorkflow] get_staff")
        try:
            from agents.bi_agent import get_staff_summary
            return {"success": True, "result": get_staff_summary()}
        except Exception as exc:
            logger.error("[AnalyticsWorkflow] get_staff failed: %s", exc)
            return {"success": False, "error": str(exc)}

    @staticmethod
    def get_leads() -> Dict[str, Any]:
        """Retrieve CRM lead pipeline conversion aggregates."""
        logger.info("[AnalyticsWorkflow] get_leads")
        try:
            from agents.bi_agent import get_lead_summary
            return {"success": True, "result": get_lead_summary()}
        except Exception as exc:
            logger.error("[AnalyticsWorkflow] get_leads failed: %s", exc)
            return {"success": False, "error": str(exc)}

    @staticmethod
    def get_reviews() -> Dict[str, Any]:
        """Retrieve reputation intelligence aggregates."""
        logger.info("[AnalyticsWorkflow] get_reviews")
        try:
            from agents.bi_agent import get_review_summary
            return {"success": True, "result": get_review_summary()}
        except Exception as exc:
            logger.error("[AnalyticsWorkflow] get_reviews failed: %s", exc)
            return {"success": False, "error": str(exc)}

    @staticmethod
    def get_upsell() -> Dict[str, Any]:
        """Retrieve automated upsell performance aggregates."""
        logger.info("[AnalyticsWorkflow] get_upsell")
        try:
            from agents.bi_agent import get_upsell_summary
            return {"success": True, "result": get_upsell_summary()}
        except Exception as exc:
            logger.error("[AnalyticsWorkflow] get_upsell failed: %s", exc)
            return {"success": False, "error": str(exc)}

    @staticmethod
    def get_ai_insights() -> Dict[str, Any]:
        """Generate real-time AI business telemetry insights."""
        logger.info("[AnalyticsWorkflow] get_ai_insights")
        try:
            from agents.bi_agent import generate_ai_insights
            return {"success": True, "result": generate_ai_insights()}
        except Exception as exc:
            logger.error("[AnalyticsWorkflow] get_ai_insights failed: %s", exc)
            return {"success": False, "error": str(exc)}

    @staticmethod
    def get_forecast() -> Dict[str, Any]:
        """Get revenue and appointment forecast for next month."""
        logger.info("[AnalyticsWorkflow] get_forecast")
        try:
            from agents.bi_agent import forecast_revenue
            return {"success": True, "result": forecast_revenue()}
        except Exception as exc:
            logger.error("[AnalyticsWorkflow] get_forecast failed: %s", exc)
            return {"success": False, "error": str(exc)}

    @staticmethod
    def get_business_context(days: int = 90) -> Dict[str, Any]:
        """Retrieve historical business context snapshots for RAG reasoning."""
        logger.info("[AnalyticsWorkflow] get_business_context: days=%d", days)
        try:
            from agents.bi_agent import retrieve_business_context
            return {"success": True, "result": retrieve_business_context(days=days)}
        except Exception as exc:
            logger.error("[AnalyticsWorkflow] get_business_context failed: %s", exc)
            return {"success": False, "error": str(exc)}

    @staticmethod
    def run_raw_sql(sql_query: str) -> Dict[str, Any]:
        """Execute a secure read-only SELECT query against the analytics database."""
        logger.info("[AnalyticsWorkflow] run_raw_sql: query=%s…", sql_query[:80])
        try:
            from agents.bi_agent import query_raw_analytics_database
            return {"success": True, "result": query_raw_analytics_database(sql_select_query=sql_query)}
        except Exception as exc:
            logger.error("[AnalyticsWorkflow] run_raw_sql failed: %s", exc)
            return {"success": False, "error": str(exc)}

    @staticmethod
    def trigger_cohort_reminders() -> Dict[str, Any]:
        """Manually trigger daily reminder dispatch to returning cohort customers."""
        logger.info("[AnalyticsWorkflow] trigger_cohort_reminders")
        try:
            from agents.bi_agent import trigger_returning_cohort_reminders
            return {"success": True, "result": trigger_returning_cohort_reminders()}
        except Exception as exc:
            logger.error("[AnalyticsWorkflow] trigger_cohort_reminders failed: %s", exc)
            return {"success": False, "error": str(exc)}
