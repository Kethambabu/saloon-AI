"""
domain/lead_service.py
=======================
Domain service layer for CRM lead lifecycle management.

Responsibilities
----------------
* Orchestrate lead creation, status advancement, search, message
  generation, reminder scheduling, abandoned-booking detection, and
  pipeline reporting.
* Publish domain events (LeadCreatedEvent, LeadConvertedEvent) via the
  central event bus after mutating operations.

Author: SalonAI Platform Team
Phase:  2 – Enterprise Architecture
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Internal imports – lead workflows
# ---------------------------------------------------------------------------
from backend.workflows.lead_workflow import (
    create_lead_workflow,
    advance_lead_status_workflow,
    generate_followup_message_workflow,
    create_followup_reminder_workflow,
    detect_abandoned_bookings_workflow,
)  # type: ignore

# ---------------------------------------------------------------------------
# Internal imports – MCP execution helper
# ---------------------------------------------------------------------------
from backend.tools.mcp_tool import mcp_execute  # type: ignore

# ---------------------------------------------------------------------------
# Internal imports – event bus
# ---------------------------------------------------------------------------
from backend.core.event_bus import (
    get_event_bus,
    LeadCreatedEvent,
    LeadConvertedEvent,
)  # type: ignore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton holder
# ---------------------------------------------------------------------------
_lead_service_instance: Optional["LeadService"] = None


class LeadService:
    """Domain service for CRM lead operations.

    All public methods return a uniform ``Dict``::

        {"success": bool, "data": Any}   # success
        {"success": False, "error": str} # failure

    Use :func:`get_lead_service` to obtain the singleton.
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        self._event_bus = get_event_bus()
        logger.info("LeadService initialised.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create(
        self,
        first_name: str,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        last_name: Optional[str] = None,
        source: Optional[str] = None,
        branch_id: Optional[str] = None,
        notes: Optional[str] = None,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Create a new lead and publish a :class:`LeadCreatedEvent`.

        Parameters
        ----------
        first_name:
            Lead's first name (required).
        email:
            Optional email address.
        phone:
            Optional phone number.
        last_name:
            Optional last name.
        source:
            Acquisition channel (e.g., ``"INSTAGRAM"``, ``"WALK_IN"``).
        branch_id:
            Originating branch identifier.
        notes:
            Optional free-text notes.
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            ``{"success": True, "data": <lead>}``
        """
        logger.info(
            "LeadService.create | first_name=%r email=%s phone=%s source=%s "
            "branch_id=%s tenant_id=%s",
            first_name,
            email,
            phone,
            source,
            branch_id,
            tenant_id,
        )
        try:
            result = create_lead_workflow(
                first_name=first_name,
                email=email,
                phone=phone,
                last_name=last_name,
                source=source,
                branch_id=branch_id,
                notes=notes,
                tenant_id=tenant_id,
            )

            if not result.get("success"):
                logger.warning(
                    "LeadService.create | workflow failed | first_name=%r | error=%s",
                    first_name,
                    result.get("error"),
                )
                return result

            lead = result.get("data", {})
            lead_id = lead.get("id") or lead.get("lead_id")

            # Publish domain event
            event = LeadCreatedEvent(
                tenant_id=tenant_id,
                payload={
                    "lead_id": lead_id,
                    "first_name": first_name,
                    "email": email,
                    "phone": phone,
                    "source": source,
                    "branch_id": branch_id,
                    "tenant_id": tenant_id,
                    "created_at": datetime.utcnow().isoformat(),
                }
            )
            self._event_bus.publish(event)
            logger.info(
                "LeadService.create | LeadCreatedEvent published | lead_id=%s",
                lead_id,
            )

            return {"success": True, "data": lead}

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "LeadService.create | error | first_name=%r | %s",
                first_name,
                exc,
            )
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------

    def advance(
        self,
        lead_id: str,
        new_status: str,
        notes: Optional[str] = None,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Advance a lead's CRM status and optionally publish a conversion event.

        When ``new_status`` equals ``"CONVERTED"`` a :class:`LeadConvertedEvent`
        is published after the workflow completes successfully.

        Parameters
        ----------
        lead_id:
            The lead to advance.
        new_status:
            Target status string (e.g., ``"CONTACTED"``, ``"CONVERTED"``).
        notes:
            Optional notes associated with this status change.
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            ``{"success": True, "data": <updated_lead>}``
        """
        logger.info(
            "LeadService.advance | lead_id=%s new_status=%s tenant_id=%s",
            lead_id,
            new_status,
            tenant_id,
        )
        try:
            result = advance_lead_status_workflow(
                lead_id=lead_id,
                new_status=new_status,
                notes=notes,
                tenant_id=tenant_id,
            )

            if not result.get("success"):
                logger.warning(
                    "LeadService.advance | workflow failed | lead_id=%s | error=%s",
                    lead_id,
                    result.get("error"),
                )
                return result

            # Publish conversion event when applicable
            if new_status.upper() == "CONVERTED":
                event = LeadConvertedEvent(
                    tenant_id=tenant_id,
                    payload={
                        "lead_id": lead_id,
                        "tenant_id": tenant_id,
                        "converted_at": datetime.utcnow().isoformat(),
                        "notes": notes,
                    }
                )
                self._event_bus.publish(event)
                logger.info(
                    "LeadService.advance | LeadConvertedEvent published | lead_id=%s",
                    lead_id,
                )

            return {"success": True, "data": result.get("data", {})}

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "LeadService.advance | error | lead_id=%s | %s",
                lead_id,
                exc,
            )
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------

    def search(
        self,
        status_filter: Optional[str] = None,
        branch_id: Optional[str] = None,
        source_filter: Optional[str] = None,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Search leads with optional status, branch, and source filters.

        Parameters
        ----------
        status_filter:
            Optional CRM status to filter by (e.g., ``"NEW"``, ``"CONVERTED"``).
        branch_id:
            Optional branch to restrict results to.
        source_filter:
            Optional acquisition source to filter by.
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            ``{"success": True, "data": [<lead>, ...]}``
        """
        logger.info(
            "LeadService.search | status=%s branch_id=%s source=%s tenant_id=%s",
            status_filter,
            branch_id,
            source_filter,
            tenant_id,
        )
        try:
            filters: Dict[str, Any] = {"tenant_id": tenant_id}
            if status_filter:
                filters["status"] = status_filter
            if branch_id:
                filters["branch_id"] = branch_id
            if source_filter:
                filters["source"] = source_filter

            result = mcp_execute(
                resource="leads",
                action="list",
                filters=filters,
            )
            leads = result.get("data", [])
            logger.info(
                "LeadService.search | %d lead(s) found | filters=%s",
                len(leads) if isinstance(leads, list) else 0,
                filters,
            )
            return {"success": True, "data": leads}

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "LeadService.search | error | tenant_id=%s | %s",
                tenant_id,
                exc,
            )
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------

    def generate_message(
        self,
        customer_id: Optional[str] = None,
        lead_id: Optional[str] = None,
        channel: str = "email",
        tone: str = "warm",
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Generate a personalised follow-up message for a lead or customer.

        Parameters
        ----------
        customer_id:
            Optional converted customer identifier.
        lead_id:
            Optional lead identifier.
        channel:
            Delivery channel: ``"email"``, ``"sms"``, or ``"whatsapp"``.
        tone:
            Message tone: ``"warm"``, ``"professional"``, ``"urgent"``, etc.
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            ``{"success": True, "data": {"message": str, ...}}``
        """
        logger.info(
            "LeadService.generate_message | lead_id=%s customer_id=%s channel=%s "
            "tone=%s tenant_id=%s",
            lead_id,
            customer_id,
            channel,
            tone,
            tenant_id,
        )
        try:
            result = generate_followup_message_workflow(
                customer_id=customer_id,
                lead_id=lead_id,
                channel=channel,
                tone=tone,
                tenant_id=tenant_id,
            )
            return result if isinstance(result, dict) else {"success": True, "data": result}

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "LeadService.generate_message | error | lead_id=%s | %s",
                lead_id,
                exc,
            )
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------

    def send_reminder(
        self,
        lead_id: str,
        channel: str = "email",
        message: str = "",
        scheduled_at: Optional[str] = None,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Schedule a follow-up reminder for a lead.

        Parameters
        ----------
        lead_id:
            Target lead.
        channel:
            Delivery channel: ``"email"``, ``"sms"``, or ``"whatsapp"``.
        message:
            Message body to deliver.
        scheduled_at:
            Optional ISO-8601 datetime to schedule delivery; defaults to
            immediate dispatch when omitted.
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            ``{"success": True, "data": <reminder_record>}``
        """
        logger.info(
            "LeadService.send_reminder | lead_id=%s channel=%s scheduled_at=%s tenant_id=%s",
            lead_id,
            channel,
            scheduled_at,
            tenant_id,
        )
        try:
            result = create_followup_reminder_workflow(
                lead_id=lead_id,
                channel=channel,
                message=message,
                scheduled_at=scheduled_at,
                tenant_id=tenant_id,
            )
            logger.info(
                "LeadService.send_reminder | reminder created | lead_id=%s",
                lead_id,
            )
            return result if isinstance(result, dict) else {"success": True, "data": result}

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "LeadService.send_reminder | error | lead_id=%s | %s",
                lead_id,
                exc,
            )
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------

    def detect_abandoned(
        self,
        branch_id: Optional[str] = None,
        lookback_days: int = 30,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Identify customers who started but did not complete a booking.

        Parameters
        ----------
        branch_id:
            Optional branch to restrict detection to.
        lookback_days:
            Number of past days to scan (defaults to 30).
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            ``{"success": True, "data": [<abandoned_record>, ...]}``
        """
        logger.info(
            "LeadService.detect_abandoned | branch_id=%s lookback_days=%d tenant_id=%s",
            branch_id,
            lookback_days,
            tenant_id,
        )
        try:
            result = detect_abandoned_bookings_workflow(
                branch_id=branch_id,
                lookback_days=lookback_days,
                tenant_id=tenant_id,
            )
            return result if isinstance(result, dict) else {"success": True, "data": result}

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "LeadService.detect_abandoned | error | tenant_id=%s | %s",
                tenant_id,
                exc,
            )
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------

    def get_pipeline(
        self,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Return an aggregated CRM pipeline view grouped by status.

        Parameters
        ----------
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            ``{"success": True, "data": [{"status": str, "count": int}, ...]}``
        """
        logger.info("LeadService.get_pipeline | tenant_id=%s", tenant_id)
        try:
            result = mcp_execute(
                resource="leads",
                action="aggregate",
                filters={"tenant_id": tenant_id},
                aggregation={"group_by": "status", "count": True},
            )
            pipeline = result.get("data", [])
            logger.info(
                "LeadService.get_pipeline | %d status bucket(s) | tenant_id=%s",
                len(pipeline) if isinstance(pipeline, list) else 0,
                tenant_id,
            )
            return {"success": True, "data": pipeline}

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "LeadService.get_pipeline | error | tenant_id=%s | %s",
                tenant_id,
                exc,
            )
            return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------


def get_lead_service() -> LeadService:
    """Return the process-level singleton :class:`LeadService`."""
    global _lead_service_instance  # pylint: disable=global-statement
    if _lead_service_instance is None:
        _lead_service_instance = LeadService()
    return _lead_service_instance
