"""
domain/appointment_service.py
=============================
Domain service layer for appointment lifecycle management.

Responsibilities
----------------
* Orchestrate appointment workflows (book / cancel / reschedule).
* Publish domain events to the central event bus after every mutating operation.
* Provide a clean, singleton-based API consumed by routers and agents.

Author: SalonAI Platform Team
Phase:  2 – Enterprise Architecture
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Internal imports – workflows
# ---------------------------------------------------------------------------
from backend.workflows.booking_workflow import (
    book_appointment_workflow,
    cancel_appointment_workflow,
    reschedule_appointment_workflow,
)

# ---------------------------------------------------------------------------
# Internal imports – MCP execution helper
# ---------------------------------------------------------------------------
from backend.tools.mcp_tool import mcp_execute  # type: ignore

# ---------------------------------------------------------------------------
# Internal imports – event bus
# ---------------------------------------------------------------------------
from backend.core.event_bus import (
    get_event_bus,
    AppointmentBookedEvent,
    AppointmentCancelledEvent,
    AppointmentRescheduledEvent,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton holder
# ---------------------------------------------------------------------------
_appointment_service_instance: Optional["AppointmentService"] = None


class AppointmentService:
    """High-level domain service for appointment operations.

    All public methods return a uniform ``Dict`` shaped as::

        {
            "success": bool,
            "data":    Any,   # present on success
            "error":   str,   # present on failure
        }

    The class is intended to be used as a singleton via
    :func:`get_appointment_service`.
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        self._event_bus = get_event_bus()
        logger.info("AppointmentService initialised.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def book(
        self,
        customer_id: str,
        branch_id: str,
        service_id: str,
        start_time: str,
        staff_id: Optional[str] = None,
        notes: Optional[str] = None,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Book a new appointment and publish an :class:`AppointmentBookedEvent`.

        Parameters
        ----------
        customer_id:
            Unique identifier of the customer making the booking.
        branch_id:
            Target salon branch identifier.
        service_id:
            Service to be performed (e.g., haircut, colouring).
        start_time:
            ISO-8601 formatted start datetime string.
        staff_id:
            Optional preferred staff member.
        notes:
            Optional free-text notes for the appointment.
        tenant_id:
            Multi-tenant discriminator (defaults to ``"default"``).

        Returns
        -------
        Dict
            ``{"success": True, "data": <appointment_dict>}`` on success or
            ``{"success": False, "error": <message>}`` on failure.
        """
        logger.info(
            "AppointmentService.book | customer_id=%s branch_id=%s service_id=%s "
            "start_time=%s staff_id=%s tenant_id=%s",
            customer_id,
            branch_id,
            service_id,
            start_time,
            staff_id,
            tenant_id,
        )
        try:
            result = book_appointment_workflow(
                customer_id=customer_id,
                branch_id=branch_id,
                service_id=service_id,
                start_time=start_time,
                staff_id=staff_id,
                notes=notes,
                tenant_id=tenant_id,
            )

            if not result.get("success"):
                logger.warning(
                    "AppointmentService.book | workflow failed | customer_id=%s | error=%s",
                    customer_id,
                    result.get("error"),
                )
                return result

            appointment = result.get("data", {})
            appointment_id = appointment.get("id") or appointment.get("appointment_id")

            # Publish domain event
            event = AppointmentBookedEvent(
                tenant_id=tenant_id,
                payload={
                    "appointment_id": appointment_id,
                    "customer_id": customer_id,
                    "branch_id": branch_id,
                    "service_id": service_id,
                    "start_time": start_time,
                    "staff_id": staff_id,
                    "tenant_id": tenant_id,
                    "booked_at": datetime.utcnow().isoformat(),
                }
            )
            self._event_bus.publish(event)
            logger.info(
                "AppointmentService.book | AppointmentBookedEvent published | "
                "appointment_id=%s customer_id=%s",
                appointment_id,
                customer_id,
            )

            return {"success": True, "data": appointment}

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "AppointmentService.book | unexpected error | customer_id=%s | %s",
                customer_id,
                exc,
            )
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------

    def cancel(
        self,
        appointment_id: str,
        customer_id: Optional[str] = None,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Cancel an existing appointment and publish an :class:`AppointmentCancelledEvent`.

        Parameters
        ----------
        appointment_id:
            The appointment to cancel.
        customer_id:
            Optional customer identifier for authorisation checks.
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            Uniform success / error envelope.
        """
        logger.info(
            "AppointmentService.cancel | appointment_id=%s customer_id=%s tenant_id=%s",
            appointment_id,
            customer_id,
            tenant_id,
        )
        try:
            result = cancel_appointment_workflow(
                appointment_id=appointment_id,
                customer_id=customer_id,
                tenant_id=tenant_id,
            )

            if not result.get("success"):
                logger.warning(
                    "AppointmentService.cancel | workflow failed | appointment_id=%s | error=%s",
                    appointment_id,
                    result.get("error"),
                )
                return result

            # Publish domain event
            event = AppointmentCancelledEvent(
                tenant_id=tenant_id,
                payload={
                    "appointment_id": appointment_id,
                    "customer_id": customer_id,
                    "tenant_id": tenant_id,
                    "cancelled_at": datetime.utcnow().isoformat(),
                }
            )
            self._event_bus.publish(event)
            logger.info(
                "AppointmentService.cancel | AppointmentCancelledEvent published | "
                "appointment_id=%s",
                appointment_id,
            )

            return {"success": True, "data": result.get("data", {})}

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "AppointmentService.cancel | unexpected error | appointment_id=%s | %s",
                appointment_id,
                exc,
            )
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------

    def reschedule(
        self,
        appointment_id: str,
        new_start_time: str,
        new_staff_id: Optional[str] = None,
        customer_id: Optional[str] = None,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Reschedule an appointment and publish an :class:`AppointmentRescheduledEvent`.

        Parameters
        ----------
        appointment_id:
            The appointment to reschedule.
        new_start_time:
            ISO-8601 formatted new start datetime.
        new_staff_id:
            Optional replacement staff member.
        customer_id:
            Optional customer identifier for authorisation.
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            Uniform success / error envelope.
        """
        logger.info(
            "AppointmentService.reschedule | appointment_id=%s new_start_time=%s "
            "new_staff_id=%s customer_id=%s tenant_id=%s",
            appointment_id,
            new_start_time,
            new_staff_id,
            customer_id,
            tenant_id,
        )
        try:
            result = reschedule_appointment_workflow(
                appointment_id=appointment_id,
                new_start_time=new_start_time,
                new_staff_id=new_staff_id,
                customer_id=customer_id,
                tenant_id=tenant_id,
            )

            if not result.get("success"):
                logger.warning(
                    "AppointmentService.reschedule | workflow failed | appointment_id=%s | error=%s",
                    appointment_id,
                    result.get("error"),
                )
                return result

            # Publish domain event
            event = AppointmentRescheduledEvent(
                tenant_id=tenant_id,
                payload={
                    "appointment_id": appointment_id,
                    "customer_id": customer_id,
                    "new_start_time": new_start_time,
                    "new_staff_id": new_staff_id,
                    "tenant_id": tenant_id,
                    "rescheduled_at": datetime.utcnow().isoformat(),
                }
            )
            self._event_bus.publish(event)
            logger.info(
                "AppointmentService.reschedule | AppointmentRescheduledEvent published | "
                "appointment_id=%s",
                appointment_id,
            )

            return {"success": True, "data": result.get("data", {})}

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "AppointmentService.reschedule | unexpected error | appointment_id=%s | %s",
                appointment_id,
                exc,
            )
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------

    def get_history(
        self,
        customer_id: str,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Retrieve the complete appointment history for a customer.

        Parameters
        ----------
        customer_id:
            Customer whose history is requested.
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            ``{"success": True, "data": [<appointment>, ...]}`` or error envelope.
        """
        logger.info(
            "AppointmentService.get_history | customer_id=%s tenant_id=%s",
            customer_id,
            tenant_id,
        )
        try:
            result = mcp_execute(
                resource="appointments",
                action="list",
                filters={"customer_id": customer_id, "tenant_id": tenant_id},
            )
            logger.debug(
                "AppointmentService.get_history | fetched %d records | customer_id=%s",
                len(result.get("data", [])),
                customer_id,
            )
            return {"success": True, "data": result.get("data", [])}

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "AppointmentService.get_history | unexpected error | customer_id=%s | %s",
                customer_id,
                exc,
            )
            return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------


def get_appointment_service() -> AppointmentService:
    """Return the process-level singleton :class:`AppointmentService` instance.

    Thread-safety note: module-level singletons are safe for the GIL-protected
    CPython interpreter under normal I/O-bound async workloads.
    """
    global _appointment_service_instance  # pylint: disable=global-statement
    if _appointment_service_instance is None:
        _appointment_service_instance = AppointmentService()
    return _appointment_service_instance
