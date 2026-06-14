"""
domain/notification_service.py
================================
Domain service layer for dispatching notifications across all channels.

Responsibilities
----------------
* Provide a unified API for sending typed notifications (confirmations,
  alerts, reminders).
* Subscribe to domain events emitted by other services and fan-out the
  appropriate notifications.
* Delegate actual dispatch to ``create_notification_workflow``.

Author: SalonAI Platform Team
Phase:  2 – Enterprise Architecture
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Internal imports – notification workflow
# ---------------------------------------------------------------------------
from backend.workflows.notification_workflow import (
    create_notification_workflow,
)  # type: ignore

# ---------------------------------------------------------------------------
# Internal imports – event bus
# ---------------------------------------------------------------------------
from backend.core.event_bus import (
    get_event_bus,
    AppointmentBookedEvent,
    LeadConvertedEvent,
    ReviewSubmittedEvent,
)  # type: ignore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton holder
# ---------------------------------------------------------------------------
_notification_service_instance: Optional["NotificationService"] = None


class NotificationService:
    """Domain service for cross-channel notification dispatch.

    All public methods return a uniform ``Dict``::

        {"success": bool, "data": Any}   # success
        {"success": False, "error": str} # failure

    Event handler methods (``handle_*``) are designed to be called by the
    event bus and do **not** return values.

    Use :func:`get_notification_service` to obtain the singleton and call
    :func:`register_event_subscribers` to activate event-driven dispatch.
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        self._event_bus = get_event_bus()
        logger.info("NotificationService initialised.")

    # ------------------------------------------------------------------
    # Core send method
    # ------------------------------------------------------------------

    def send(
        self,
        user_id: str,
        title: str,
        message: str,
        notification_type: str = "INFO",
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Dispatch a notification to a user.

        Parameters
        ----------
        user_id:
            Recipient identifier (customer or staff).
        title:
            Short notification title / subject.
        message:
            Full notification body.
        notification_type:
            Severity / category label: ``"INFO"``, ``"ALERT"``,
            ``"REMINDER"``, ``"URGENT"``.
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            ``{"success": True, "data": <notification_record>}``
        """
        logger.info(
            "NotificationService.send | user_id=%s type=%s title=%r tenant_id=%s",
            user_id,
            notification_type,
            title,
            tenant_id,
        )
        try:
            result = create_notification_workflow(
                user_id=user_id,
                title=title,
                message=message,
                notification_type=notification_type,
                tenant_id=tenant_id,
            )
            logger.info(
                "NotificationService.send | dispatched | user_id=%s type=%s",
                user_id,
                notification_type,
            )
            return result if isinstance(result, dict) else {"success": True, "data": result}

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "NotificationService.send | error | user_id=%s | %s",
                user_id,
                exc,
            )
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # Typed notification helpers
    # ------------------------------------------------------------------

    def send_appointment_confirmation(
        self,
        customer_id: str,
        appointment_details: Dict[str, Any],
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Send an appointment confirmation notification to a customer.

        Parameters
        ----------
        customer_id:
            Customer to notify.
        appointment_details:
            Dict containing at minimum ``start_time``, ``service_name``,
            and optionally ``staff_name``, ``branch_name``.
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            Uniform success / error envelope.
        """
        logger.info(
            "NotificationService.send_appointment_confirmation | customer_id=%s tenant_id=%s",
            customer_id,
            tenant_id,
        )
        start_time = appointment_details.get("start_time", "your scheduled time")
        service_name = appointment_details.get("service_name", "your service")
        staff_name = appointment_details.get("staff_name", "our team")
        branch_name = appointment_details.get("branch_name", "our salon")

        title = "Appointment Confirmed ✅"
        message = (
            f"Hi! Your appointment for {service_name} with {staff_name} "
            f"at {branch_name} is confirmed for {start_time}. "
            f"We look forward to seeing you!"
        )
        return self.send(
            user_id=customer_id,
            title=title,
            message=message,
            notification_type="INFO",
            tenant_id=tenant_id,
        )

    # ------------------------------------------------------------------

    def send_lead_converted_alert(
        self,
        lead_id: str,
        staff_id: Optional[str] = None,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Send an alert notification when a lead has been converted.

        Parameters
        ----------
        lead_id:
            The converted lead identifier.
        staff_id:
            Optional staff member to notify about the conversion.
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            Uniform success / error envelope.
        """
        logger.info(
            "NotificationService.send_lead_converted_alert | lead_id=%s staff_id=%s tenant_id=%s",
            lead_id,
            staff_id,
            tenant_id,
        )
        recipient = staff_id or "management"
        title = "🎉 Lead Converted!"
        message = (
            f"Great news! Lead {lead_id} has been successfully converted to a customer. "
            f"Please follow up to schedule their first appointment."
        )
        return self.send(
            user_id=recipient,
            title=title,
            message=message,
            notification_type="ALERT",
            tenant_id=tenant_id,
        )

    # ------------------------------------------------------------------

    def send_review_escalation_alert(
        self,
        review_id: str,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Send an urgent escalation alert for a critical review.

        Parameters
        ----------
        review_id:
            The critical review requiring immediate attention.
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            Uniform success / error envelope.
        """
        logger.info(
            "NotificationService.send_review_escalation_alert | review_id=%s tenant_id=%s",
            review_id,
            tenant_id,
        )
        title = "🚨 Critical Review Escalation"
        message = (
            f"A critical review (ID: {review_id}) requires your immediate attention. "
            f"Please review, respond, and take remedial action as soon as possible."
        )
        return self.send(
            user_id="management",
            title=title,
            message=message,
            notification_type="URGENT",
            tenant_id=tenant_id,
        )

    # ------------------------------------------------------------------

    def send_cohort_reminder(
        self,
        customer_id: str,
        service_name: str,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Send a rebooking reminder to a returning cohort customer.

        Parameters
        ----------
        customer_id:
            Customer to remind.
        service_name:
            Name of the service they last booked (personalises the message).
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            Uniform success / error envelope.
        """
        logger.info(
            "NotificationService.send_cohort_reminder | customer_id=%s service=%s tenant_id=%s",
            customer_id,
            service_name,
            tenant_id,
        )
        title = "We Miss You! 💇 Time to Rebook"
        message = (
            f"It's been a while since your last {service_name}. "
            f"Book your next appointment today and keep looking your best!"
        )
        return self.send(
            user_id=customer_id,
            title=title,
            message=message,
            notification_type="REMINDER",
            tenant_id=tenant_id,
        )

    # ------------------------------------------------------------------
    # Event bus subscriber handlers
    # ------------------------------------------------------------------

    def handle_appointment_booked_event(self, event: AppointmentBookedEvent) -> None:
        """Event bus subscriber for :class:`AppointmentBookedEvent`.

        Extracts customer and appointment details from the event payload
        and triggers :meth:`send_appointment_confirmation`.

        Parameters
        ----------
        event:
            The fired ``AppointmentBookedEvent`` instance.
        """
        logger.info(
            "NotificationService.handle_appointment_booked_event | event_id=%s",
            getattr(event, "event_id", "?"),
        )
        try:
            payload: Dict[str, Any] = event.payload or {}
            customer_id = payload.get("customer_id")
            if not customer_id:
                logger.warning(
                    "NotificationService.handle_appointment_booked_event | "
                    "missing customer_id in payload"
                )
                return
            self.send_appointment_confirmation(
                customer_id=customer_id,
                appointment_details=payload,
                tenant_id=payload.get("tenant_id", "default"),
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "NotificationService.handle_appointment_booked_event | error | %s",
                exc,
            )

    # ------------------------------------------------------------------

    def handle_lead_converted_event(self, event: LeadConvertedEvent) -> None:
        """Event bus subscriber for :class:`LeadConvertedEvent`.

        Parameters
        ----------
        event:
            The fired ``LeadConvertedEvent`` instance.
        """
        logger.info(
            "NotificationService.handle_lead_converted_event | event_id=%s",
            getattr(event, "event_id", "?"),
        )
        try:
            payload: Dict[str, Any] = event.payload or {}
            lead_id = payload.get("lead_id")
            if not lead_id:
                logger.warning(
                    "NotificationService.handle_lead_converted_event | "
                    "missing lead_id in payload"
                )
                return
            self.send_lead_converted_alert(
                lead_id=lead_id,
                staff_id=payload.get("staff_id"),
                tenant_id=payload.get("tenant_id", "default"),
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "NotificationService.handle_lead_converted_event | error | %s",
                exc,
            )

    # ------------------------------------------------------------------

    def handle_review_submitted_event(self, event: ReviewSubmittedEvent) -> None:
        """Event bus subscriber for :class:`ReviewSubmittedEvent`.

        Sends an escalation alert when the review is flagged as critical.

        Parameters
        ----------
        event:
            The fired ``ReviewSubmittedEvent`` instance.
        """
        logger.info(
            "NotificationService.handle_review_submitted_event | event_id=%s",
            getattr(event, "event_id", "?"),
        )
        try:
            payload: Dict[str, Any] = event.payload or {}
            if payload.get("critical"):
                review_id = payload.get("review_id")
                if review_id:
                    self.send_review_escalation_alert(
                        review_id=review_id,
                        tenant_id=payload.get("tenant_id", "default"),
                    )
                else:
                    logger.warning(
                        "NotificationService.handle_review_submitted_event | "
                        "critical=True but missing review_id"
                    )
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "NotificationService.handle_review_submitted_event | error | %s",
                exc,
            )


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------


def get_notification_service() -> NotificationService:
    """Return the process-level singleton :class:`NotificationService`."""
    global _notification_service_instance  # pylint: disable=global-statement
    if _notification_service_instance is None:
        _notification_service_instance = NotificationService()
    return _notification_service_instance


# ---------------------------------------------------------------------------
# Event subscriber registration
# ---------------------------------------------------------------------------


def register_event_subscribers() -> None:
    """Subscribe :class:`NotificationService` handlers to the event bus.

    Call this function once during application start-up (e.g., in the
    FastAPI ``lifespan`` context) to wire event-driven notifications.

    Subscribed events
    -----------------
    * :class:`~backend.core.event_bus.AppointmentBookedEvent`
    * :class:`~backend.core.event_bus.LeadConvertedEvent`
    * :class:`~backend.core.event_bus.ReviewSubmittedEvent`
    """
    svc = get_notification_service()
    bus = get_event_bus()

    bus.subscribe(AppointmentBookedEvent, svc.handle_appointment_booked_event)
    bus.subscribe(LeadConvertedEvent, svc.handle_lead_converted_event)
    bus.subscribe(ReviewSubmittedEvent, svc.handle_review_submitted_event)

    logger.info(
        "NotificationService | registered subscribers for AppointmentBookedEvent, "
        "LeadConvertedEvent, ReviewSubmittedEvent"
    )
