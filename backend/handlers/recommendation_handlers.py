"""
Recommendation Handlers — Phase 2.
"""

from __future__ import annotations
from typing import Any, Dict, Optional
from handlers.base import BaseHandler, HandlerContext


class GetRecommendationsHandler(BaseHandler):
    name = "GetRecommendationsHandler"
    permission_action = "recommendation_fetch"

    def validate(self, ctx: HandlerContext) -> Optional[str]:
        if not ctx.get("customer_id"):
            return "customer_id is required."
        return None

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from workflows.upsell_workflow import get_customer_recommendations_workflow
        return get_customer_recommendations_workflow(customer_id=ctx.get("customer_id"))


class AcceptRecommendationHandler(BaseHandler):
    name = "AcceptRecommendationHandler"
    permission_action = "recommendation_accept"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from workflows.upsell_workflow import accept_recommendation_workflow
        return accept_recommendation_workflow(
            customer_id=ctx.get("customer_id", ""),
            service_id=ctx.get("service_id", ""),
            appointment_id=ctx.get("appointment_id"),
        )


class RejectRecommendationHandler(BaseHandler):
    name = "RejectRecommendationHandler"
    permission_action = "recommendation_reject"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from workflows.upsell_workflow import reject_recommendation_workflow
        return reject_recommendation_workflow(
            customer_id=ctx.get("customer_id", ""),
            service_id=ctx.get("service_id", ""),
            appointment_id=ctx.get("appointment_id"),
        )


class UpsellAnalyticsHandler(BaseHandler):
    name = "UpsellAnalyticsHandler"
    permission_action = "recommendation_analytics"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from workflows.upsell_workflow import get_upsell_analytics_workflow
        return get_upsell_analytics_workflow()


# Alias for registry compatibility
RecommendationAnalyticsHandler = UpsellAnalyticsHandler

