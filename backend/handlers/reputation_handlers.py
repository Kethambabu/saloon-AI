"""
Reputation Handlers — Phase 2.
Each handler processes one review/reputation operation.
"""

from __future__ import annotations
from typing import Any, Dict, Optional
from handlers.base import BaseHandler, HandlerContext


class GetReviewsHandler(BaseHandler):
    name = "GetReviewsHandler"
    permission_action = "reputation_read"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from tools.mcp_tool import mcp_execute
        filters = {}
        if ctx.get("customer_id"):
            filters["customer_id"] = ctx.get("customer_id")
        if ctx.get("staff_id"):
            filters["staff_id"] = ctx.get("staff_id")
        if ctx.get("sentiment"):
            filters["sentiment"] = ctx.get("sentiment", "").upper()
        if ctx.get("rating"):
            filters["rating"] = ctx.get("rating")
        return mcp_execute(resource="reviews", operation="select", filters=filters, agent_name="ReputationWorkflow")


class ReviewAnalyticsHandler(BaseHandler):
    name = "ReviewAnalyticsHandler"
    permission_action = "reputation_analytics"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from tools.mcp_tool import mcp_execute
        return mcp_execute(resource="reviews", operation="aggregate", metric="avg", agent_name="ReputationWorkflow")


class CriticalReviewsHandler(BaseHandler):
    name = "CriticalReviewsHandler"
    permission_action = "reputation_critical"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from tools.mcp_tool import mcp_execute
        return mcp_execute(
            resource="reviews", operation="select",
            filters={"sentiment": "CRITICAL"}, agent_name="ReputationWorkflow"
        )


class DraftResponseHandler(BaseHandler):
    name = "DraftResponseHandler"
    permission_action = "reputation_respond"

    def validate(self, ctx: HandlerContext) -> Optional[str]:
        if not ctx.get("review_id"):
            return "review_id is required."
        return None

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from workflows.review_workflow import respond_to_review_workflow
        return respond_to_review_workflow(
            review_id=ctx.get("review_id"),
            custom_response=ctx.get("custom_response"),
        )


class ReputationScorecardHandler(BaseHandler):
    name = "ReputationScorecardHandler"
    permission_action = "reputation_scorecard"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from tools.mcp_tool import mcp_execute
        return mcp_execute(
            resource="reviews", operation="aggregate", metric="count",
            group_by="sentiment", agent_name="ReputationWorkflow"
        )


class EscalateReviewHandler(BaseHandler):
    name = "EscalateReviewHandler"
    permission_action = "reputation_escalate"

    def validate(self, ctx: HandlerContext) -> Optional[str]:
        if not ctx.get("review_id"):
            return "review_id is required."
        return None

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from workflows.review_workflow import escalate_review_workflow
        return escalate_review_workflow(review_id=ctx.get("review_id"))


# Alias for registry compatibility
ReputationAnalyticsHandler = ReviewAnalyticsHandler

