"""
CRMWorkflow — Phase 1 Capability Workflow for Mia (Lead Follow-up).

Agents call crm_workflow() instead of building raw mcp_read/execute_transaction calls.

Covers:
  - search leads
  - create lead
  - advance lead status
  - send follow-up reminder
  - generate personalized message
  - detect abandoned bookings
  - view conversion analytics
  - view pipeline snapshot
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CRMWorkflow:
    """
    Phase 1 workflow encapsulating all CRM / lead management operations for Mia.
    """

    @staticmethod
    def search_leads(
        status_filter: Optional[str] = None,
        branch_id: Optional[str] = None,
        source_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Search and filter CRM leads."""
        logger.info(
            "[CRMWorkflow] search_leads: status=%s branch=%s source=%s",
            status_filter, branch_id, source_filter
        )
        try:
            from ai.tools.mcp_tool import mcp_execute
            filters: Dict[str, Any] = {}
            if status_filter:
                filters["status"] = status_filter.upper()
            if branch_id:
                filters["branch_id"] = branch_id
            if source_filter:
                filters["source"] = source_filter
            return mcp_execute(
                resource="leads",
                operation="select",
                filters=filters,
                agent_name="Mia_LeadFollowup",
            )
        except Exception as exc:
            logger.error("[CRMWorkflow] search_leads failed: %s", exc)
            return {"success": False, "error": str(exc)}

    @staticmethod
    def create_lead(
        first_name: str,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        last_name: Optional[str] = None,
        source: Optional[str] = None,
        branch_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Register a new prospect lead in the CRM pipeline."""
        logger.info("[CRMWorkflow] create_lead: name=%s %s", first_name, last_name)
        try:
            from ai.workflows.lead_workflow import create_lead_workflow
            return create_lead_workflow(
                first_name=first_name,
                email=email,
                phone=phone,
                last_name=last_name,
                source=source,
                branch_id=branch_id,
                notes=notes,
            )
        except Exception as exc:
            logger.error("[CRMWorkflow] create_lead failed: %s", exc)
            return {"success": False, "error": str(exc)}

    @staticmethod
    def advance_lead_status(
        lead_id: str,
        new_status: str,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Move a lead to the next pipeline stage."""
        logger.info("[CRMWorkflow] advance_lead_status: lead=%s → %s", lead_id, new_status)
        try:
            from ai.workflows.lead_workflow import advance_lead_status_workflow
            return advance_lead_status_workflow(
                lead_id=lead_id,
                new_status=new_status,
                notes=notes,
            )
        except Exception as exc:
            logger.error("[CRMWorkflow] advance_lead_status failed: %s", exc)
            return {"success": False, "error": str(exc)}

    @staticmethod
    def send_followup_reminder(
        lead_id: str,
        channel: str = "email",
        message: str = "",
        scheduled_at: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Schedule and send a follow-up reminder to a lead."""
        logger.info(
            "[CRMWorkflow] send_followup_reminder: lead=%s channel=%s", lead_id, channel
        )
        try:
            from ai.workflows.lead_workflow import create_followup_reminder_workflow
            return create_followup_reminder_workflow(
                lead_id=lead_id,
                channel=channel,
                message=message,
                scheduled_at=scheduled_at,
            )
        except Exception as exc:
            logger.error("[CRMWorkflow] send_followup_reminder failed: %s", exc)
            return {"success": False, "error": str(exc)}

    @staticmethod
    def generate_personalized_message(
        customer_id: Optional[str] = None,
        lead_id: Optional[str] = None,
        channel: str = "email",
        tone: str = "warm",
    ) -> Dict[str, Any]:
        """Generate a personalized outreach message for a customer or lead."""
        logger.info(
            "[CRMWorkflow] generate_personalized_message: customer=%s lead=%s",
            customer_id, lead_id
        )
        try:
            from ai.workflows.lead_workflow import generate_followup_message_workflow
            return generate_followup_message_workflow(
                customer_id=customer_id,
                lead_id=lead_id,
                channel=channel,
                tone=tone,
            )
        except Exception as exc:
            logger.error("[CRMWorkflow] generate_personalized_message failed: %s", exc)
            return {"success": False, "error": str(exc)}

    @staticmethod
    def detect_abandoned_bookings(
        branch_id: Optional[str] = None,
        lookback_days: int = 30,
    ) -> Dict[str, Any]:
        """Detect customers who cancelled / no-showed and haven't rebooked."""
        logger.info(
            "[CRMWorkflow] detect_abandoned_bookings: branch=%s days=%d",
            branch_id, lookback_days
        )
        try:
            from ai.workflows.lead_workflow import detect_abandoned_bookings_workflow
            return detect_abandoned_bookings_workflow(
                branch_id=branch_id,
                lookback_days=lookback_days,
            )
        except Exception as exc:
            logger.error("[CRMWorkflow] detect_abandoned_bookings failed: %s", exc)
            return {"success": False, "error": str(exc)}

    @staticmethod
    def get_conversion_analytics(
        period_days: int = 30,
        branch_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get comprehensive lead conversion analytics."""
        logger.info("[CRMWorkflow] get_conversion_analytics: period=%dd", period_days)
        try:
            from ai.tools.mcp_tool import mcp_execute
            return mcp_execute(
                resource="leads",
                operation="aggregate",
                metric="group_by",
                group_by="status",
                agent_name="Mia_LeadFollowup",
            )
        except Exception as exc:
            logger.error("[CRMWorkflow] get_conversion_analytics failed: %s", exc)
            return {"success": False, "error": str(exc)}

    @staticmethod
    def get_pipeline_snapshot(branch_id: Optional[str] = None) -> Dict[str, Any]:
        """Get a quick snapshot of the current lead pipeline."""
        logger.info("[CRMWorkflow] get_pipeline_snapshot: branch=%s", branch_id)
        try:
            from ai.tools.mcp_tool import mcp_execute
            return mcp_execute(
                resource="leads",
                operation="aggregate",
                metric="count",
                group_by="status",
                agent_name="Mia_LeadFollowup",
            )
        except Exception as exc:
            logger.error("[CRMWorkflow] get_pipeline_snapshot failed: %s", exc)
            return {"success": False, "error": str(exc)}

