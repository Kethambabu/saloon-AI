"""
Analytics Handlers — Phase 2.
Each handler processes one BI analytics query.
"""

from __future__ import annotations
from typing import Any, Dict, Optional
from handlers.base import BaseHandler, HandlerContext


class DashboardHandler(BaseHandler):
    name = "DashboardHandler"
    permission_action = "analytics_dashboard"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from agents.bi_agent import get_dashboard_summary
        return {"success": True, "result": get_dashboard_summary()}


class RevenueHandler(BaseHandler):
    name = "RevenueHandler"
    permission_action = "analytics_revenue"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from agents.bi_agent import get_revenue_summary
        return {"success": True, "result": get_revenue_summary()}


class CustomerMetricsHandler(BaseHandler):
    name = "CustomerMetricsHandler"
    permission_action = "analytics_customers"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from agents.bi_agent import get_customer_summary
        return {"success": True, "result": get_customer_summary()}


class StaffPerformanceHandler(BaseHandler):
    name = "StaffPerformanceHandler"
    permission_action = "analytics_staff"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from agents.bi_agent import get_staff_summary
        return {"success": True, "result": get_staff_summary()}


class LeadAnalyticsHandler(BaseHandler):
    name = "LeadAnalyticsHandler"
    permission_action = "analytics_leads"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from agents.bi_agent import get_lead_summary
        return {"success": True, "result": get_lead_summary()}


class ReviewAnalyticsHandler(BaseHandler):
    name = "ReviewAnalyticsHandler"
    permission_action = "analytics_reviews"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from agents.bi_agent import get_review_summary
        return {"success": True, "result": get_review_summary()}


class UpsellAnalyticsHandler(BaseHandler):
    name = "UpsellAnalyticsHandler"
    permission_action = "analytics_upsell"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from agents.bi_agent import get_upsell_summary
        return {"success": True, "result": get_upsell_summary()}


class ForecastHandler(BaseHandler):
    name = "ForecastHandler"
    permission_action = "analytics_forecast"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from agents.bi_agent import forecast_revenue
        return {"success": True, "result": forecast_revenue()}


class AIInsightsHandler(BaseHandler):
    name = "AIInsightsHandler"
    permission_action = "analytics_insights"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from agents.bi_agent import generate_ai_insights
        return {"success": True, "result": generate_ai_insights()}


class BusinessContextHandler(BaseHandler):
    name = "BusinessContextHandler"
    permission_action = "analytics_context"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from agents.bi_agent import retrieve_business_context
        days = int(ctx.get("days") or 90)
        return {"success": True, "result": retrieve_business_context(days=days)}


class RawSQLHandler(BaseHandler):
    name = "RawSQLHandler"
    permission_action = "analytics_raw_sql"

    def validate(self, ctx: HandlerContext) -> Optional[str]:
        sql = ctx.get("sql") or ctx.get("query", "")
        if not sql:
            return "'sql' parameter is required for raw SQL queries."
        sql_upper = sql.strip().upper()
        if not sql_upper.startswith("SELECT"):
            return "Only SELECT statements are allowed."
        return None

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from agents.bi_agent import query_raw_analytics_database
        sql = ctx.get("sql") or ctx.get("query", "")
        return {"success": True, "result": query_raw_analytics_database(sql_select_query=sql)}


class CohortRemindersHandler(BaseHandler):
    name = "CohortRemindersHandler"
    permission_action = "analytics_cohort_reminders"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from agents.bi_agent import trigger_returning_cohort_reminders
        return {"success": True, "result": trigger_returning_cohort_reminders()}
