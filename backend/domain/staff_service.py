"""
domain/staff_service.py
========================
Domain service layer for staff schedule, performance, revenue, leave,
and customer-facing operations.

Responsibilities
----------------
* Wrap staff_tools with a clean, logged, exception-safe API.
* Validate date inputs before forwarding to underlying tools.
* Expose a consistent Dict-response contract to routers and agents.

Author: SalonAI Platform Team
Phase:  2 – Enterprise Architecture
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Internal imports – staff tools
# ---------------------------------------------------------------------------
from backend.tools.staff_tools import (
    get_schedule,
    get_today_schedule,
    get_staff_performance,
    get_staff_revenue,
    create_leave_request,
    send_customer_reminders,
    get_next_customer,
)  # type: ignore

# ---------------------------------------------------------------------------
# Internal imports – date utilities
# ---------------------------------------------------------------------------
from backend.services.entity_resolver_service import resolve_relative_date  # type: ignore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton holder
# ---------------------------------------------------------------------------
_staff_service_instance: Optional["StaffService"] = None


class StaffService:
    """Domain service for staff operational queries.

    All public methods return a uniform ``Dict``::

        {"success": bool, "data": Any}   # success
        {"success": False, "error": str} # failure

    Use :func:`get_staff_service` to obtain the singleton.
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        logger.info("StaffService initialised.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_schedule(
        self,
        staff_id: str,
        date_str: Optional[str] = None,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Retrieve the appointment schedule for a staff member on a given date.

        Parameters
        ----------
        staff_id:
            Target staff member identifier.
        date_str:
            Optional date in ``YYYY-MM-DD`` format; defaults to today when
            omitted.
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            ``{"success": True, "data": <schedule>}``
        """
        logger.info(
            "StaffService.get_schedule | staff_id=%s date=%s tenant_id=%s",
            staff_id,
            date_str,
            tenant_id,
        )
        try:
            result = get_schedule(
                staff_id=staff_id,
                date_str=date_str,
                tenant_id=tenant_id,
            )
            return {"success": True, "data": result}

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "StaffService.get_schedule | error | staff_id=%s | %s",
                staff_id,
                exc,
            )
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------

    def get_today_schedule(
        self,
        staff_id: str,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Return today's appointments for a staff member.

        Parameters
        ----------
        staff_id:
            Target staff member identifier.
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            ``{"success": True, "data": <today_schedule>}``
        """
        logger.info(
            "StaffService.get_today_schedule | staff_id=%s tenant_id=%s",
            staff_id,
            tenant_id,
        )
        try:
            result = get_today_schedule(staff_id=staff_id, tenant_id=tenant_id)
            return {"success": True, "data": result}

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "StaffService.get_today_schedule | error | staff_id=%s | %s",
                staff_id,
                exc,
            )
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------

    def get_performance(
        self,
        staff_id: str,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Retrieve performance metrics for a staff member.

        Metrics typically include appointment count, average rating,
        no-show rate, and upsell conversion.

        Parameters
        ----------
        staff_id:
            Target staff member identifier.
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            ``{"success": True, "data": <performance_metrics>}``
        """
        logger.info(
            "StaffService.get_performance | staff_id=%s tenant_id=%s",
            staff_id,
            tenant_id,
        )
        try:
            result = get_staff_performance(staff_id=staff_id, tenant_id=tenant_id)
            return {"success": True, "data": result}

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "StaffService.get_performance | error | staff_id=%s | %s",
                staff_id,
                exc,
            )
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------

    def get_revenue(
        self,
        staff_id: str,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Retrieve revenue figures attributed to a staff member.

        Parameters
        ----------
        staff_id:
            Target staff member identifier.
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            ``{"success": True, "data": <revenue_summary>}``
        """
        logger.info(
            "StaffService.get_revenue | staff_id=%s tenant_id=%s",
            staff_id,
            tenant_id,
        )
        try:
            result = get_staff_revenue(staff_id=staff_id, tenant_id=tenant_id)
            return {"success": True, "data": result}

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "StaffService.get_revenue | error | staff_id=%s | %s",
                staff_id,
                exc,
            )
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------

    def request_leave(
        self,
        staff_id: str,
        leave_date: str,
        reason: Optional[str] = None,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Submit a leave request on behalf of a staff member.

        ``leave_date`` is first normalised through
        :func:`~backend.utils.date_utils.resolve_relative_date` so that
        relative expressions such as ``"tomorrow"`` or ``"next Monday"``
        are resolved before forwarding to the underlying tool.

        Parameters
        ----------
        staff_id:
            Staff member requesting leave.
        leave_date:
            Absolute (``YYYY-MM-DD``) or relative date expression.
        reason:
            Optional leave reason / description.
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            ``{"success": True, "data": <leave_record>}``
        """
        logger.info(
            "StaffService.request_leave | staff_id=%s leave_date=%r reason=%r tenant_id=%s",
            staff_id,
            leave_date,
            reason,
            tenant_id,
        )
        try:
            resolved_date = resolve_relative_date(leave_date)
            logger.debug(
                "StaffService.request_leave | resolved leave_date=%s -> %s",
                leave_date,
                resolved_date,
            )

            result = create_leave_request(
                staff_id=staff_id,
                leave_date=resolved_date,
                reason=reason,
                tenant_id=tenant_id,
            )
            logger.info(
                "StaffService.request_leave | leave request created | staff_id=%s date=%s",
                staff_id,
                resolved_date,
            )
            return {"success": True, "data": result}

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "StaffService.request_leave | error | staff_id=%s | %s",
                staff_id,
                exc,
            )
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------

    def send_reminders(
        self,
        staff_id: str,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Trigger customer reminders for upcoming appointments owned by a staff member.

        Parameters
        ----------
        staff_id:
            Staff member whose upcoming appointments will trigger reminders.
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            ``{"success": True, "data": <reminder_dispatch_result>}``
        """
        logger.info(
            "StaffService.send_reminders | staff_id=%s tenant_id=%s",
            staff_id,
            tenant_id,
        )
        try:
            result = send_customer_reminders(staff_id=staff_id, tenant_id=tenant_id)
            logger.info(
                "StaffService.send_reminders | reminders sent | staff_id=%s",
                staff_id,
            )
            return {"success": True, "data": result}

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "StaffService.send_reminders | error | staff_id=%s | %s",
                staff_id,
                exc,
            )
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------

    def get_next_customer(
        self,
        staff_id: str,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Return the next scheduled customer for a staff member.

        Parameters
        ----------
        staff_id:
            Staff member identifier.
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            ``{"success": True, "data": <next_customer_appointment>}``
        """
        logger.info(
            "StaffService.get_next_customer | staff_id=%s tenant_id=%s",
            staff_id,
            tenant_id,
        )
        try:
            result = get_next_customer(staff_id=staff_id, tenant_id=tenant_id)
            return {"success": True, "data": result}

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "StaffService.get_next_customer | error | staff_id=%s | %s",
                staff_id,
                exc,
            )
            return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------


def get_staff_service() -> StaffService:
    """Return the process-level singleton :class:`StaffService`."""
    global _staff_service_instance  # pylint: disable=global-statement
    if _staff_service_instance is None:
        _staff_service_instance = StaffService()
    return _staff_service_instance
