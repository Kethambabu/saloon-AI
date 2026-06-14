"""
CRM Handlers — Phase 2.
Each handler processes exactly one CRM lead management operation.
"""

from __future__ import annotations
from typing import Any, Dict, Optional
from handlers.base import BaseHandler, HandlerContext


class SearchLeadsHandler(BaseHandler):
    name = "SearchLeadsHandler"
    permission_action = "crm_search"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from tools.mcp_tool import mcp_execute
        filters = {}
        if ctx.get("status") or ctx.get("status_filter"):
            filters["status"] = (ctx.get("status") or ctx.get("status_filter", "")).upper()
        if ctx.get("branch_id"):
            filters["branch_id"] = ctx.get("branch_id")
        return mcp_execute(resource="leads", operation="select", filters=filters, agent_name="CRMWorkflow")


class CreateLeadHandler(BaseHandler):
    name = "CreateLeadHandler"
    permission_action = "crm_create_lead"

    def validate(self, ctx: HandlerContext) -> Optional[str]:
        if not ctx.get("first_name"):
            return "first_name is required to create a lead."
        return None

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from workflows.lead_workflow import create_lead_workflow
        return create_lead_workflow(
            first_name=ctx.get("first_name", ""),
            email=ctx.get("email"),
            phone=ctx.get("phone"),
            last_name=ctx.get("last_name"),
            source=ctx.get("source"),
            branch_id=ctx.get("branch_id"),
            notes=ctx.get("notes"),
        )


class AdvanceLeadHandler(BaseHandler):
    name = "AdvanceLeadHandler"
    permission_action = "crm_advance_lead"

    def validate(self, ctx: HandlerContext) -> Optional[str]:
        if not ctx.get("lead_id"):
            return "lead_id is required."
        if not ctx.get("new_status"):
            return "new_status is required."
        return None

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from workflows.lead_workflow import advance_lead_status_workflow
        return advance_lead_status_workflow(
            lead_id=ctx.get("lead_id"),
            new_status=ctx.get("new_status"),
            notes=ctx.get("notes"),
        )


class SendFollowupHandler(BaseHandler):
    name = "SendFollowupHandler"
    permission_action = "crm_send_followup"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from workflows.lead_workflow import create_followup_reminder_workflow
        return create_followup_reminder_workflow(
            lead_id=ctx.get("lead_id", ""),
            channel=ctx.get("channel", "email"),
            message=ctx.get("message", ""),
            scheduled_at=ctx.get("scheduled_at"),
        )


class GenerateMessageHandler(BaseHandler):
    name = "GenerateMessageHandler"
    permission_action = "crm_message"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from workflows.lead_workflow import generate_followup_message_workflow
        return generate_followup_message_workflow(
            customer_id=ctx.get("customer_id"),
            lead_id=ctx.get("lead_id"),
            channel=ctx.get("channel", "email"),
            tone=ctx.get("tone", "warm"),
        )


class DetectAbandonedHandler(BaseHandler):
    name = "DetectAbandonedHandler"
    permission_action = "crm_abandoned"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from workflows.lead_workflow import detect_abandoned_bookings_workflow
        return detect_abandoned_bookings_workflow(
            branch_id=ctx.get("branch_id"),
            lookback_days=int(ctx.get("lookback_days") or 30),
        )


class ConversionAnalyticsHandler(BaseHandler):
    name = "ConversionAnalyticsHandler"
    permission_action = "crm_analytics"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from tools.mcp_tool import mcp_execute
        return mcp_execute(
            resource="leads", operation="aggregate", metric="group_by",
            group_by="status", agent_name="CRMWorkflow"
        )


class PipelineSnapshotHandler(BaseHandler):
    name = "PipelineSnapshotHandler"
    permission_action = "crm_pipeline"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from tools.mcp_tool import mcp_execute
        return mcp_execute(
            resource="leads", operation="aggregate", metric="count",
            group_by="status", agent_name="CRMWorkflow"
        )
