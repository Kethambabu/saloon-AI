"""
domain/availability_service.py
================================
Domain service layer for slot and staff availability queries.

Responsibilities
----------------
* Wrap the lower-level availability workflow and discovery tools with a
  clean, logged, exception-safe API.
* Expose slot availability, staff discovery, service discovery, and
  per-staff availability checks.

Author: SalonAI Platform Team
Phase:  2 – Enterprise Architecture
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Internal imports – workflows
# ---------------------------------------------------------------------------
from backend.workflows.booking_workflow import (
    check_availability_workflow,
)  # type: ignore

# ---------------------------------------------------------------------------
# Internal imports – discovery tools
# ---------------------------------------------------------------------------
from backend.tools.discovery_tools import (
    list_available_staff,
    list_available_services,
)  # type: ignore

# ---------------------------------------------------------------------------
# Internal imports – MCP execution helper (used for booking collision checks)
# ---------------------------------------------------------------------------
from backend.tools.mcp_tool import mcp_execute  # type: ignore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton holder
# ---------------------------------------------------------------------------
_availability_service_instance: Optional["AvailabilityService"] = None


class AvailabilityService:
    """Domain service for availability and scheduling queries.

    All public methods return a uniform ``Dict``::

        {"success": bool, "data": Any}   # success
        {"success": False, "error": str} # failure

    Use :func:`get_availability_service` to obtain the singleton.
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        logger.info("AvailabilityService initialised.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_slots(
        self,
        branch_id: str,
        date_str: str,
        staff_id: Optional[str] = None,
        service_id: Optional[str] = None,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Return available booking slots for a branch on a given date.

        Parameters
        ----------
        branch_id:
            Salon branch to query.
        date_str:
            Date string in ``YYYY-MM-DD`` format.
        staff_id:
            Optional filter – only return slots for this staff member.
        service_id:
            Optional filter – only return slots long enough for this service.
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            ``{"success": True, "data": {"date": date_str, "slots": [...]}}``
            where each slot contains at minimum ``start_time`` and
            ``end_time`` keys formatted as ``HH:MM``.
        """
        logger.info(
            "AvailabilityService.check_slots | branch_id=%s date=%s "
            "staff_id=%s service_id=%s tenant_id=%s",
            branch_id,
            date_str,
            staff_id,
            service_id,
            tenant_id,
        )
        try:
            result = check_availability_workflow(
                branch_id=branch_id,
                date_str=date_str,
                staff_id=staff_id,
                service_id=service_id,
                tenant_id=tenant_id,
            )

            if not result.get("success"):
                logger.warning(
                    "AvailabilityService.check_slots | workflow failed | branch_id=%s | error=%s",
                    branch_id,
                    result.get("error"),
                )
                return result

            raw_slots: List[Dict[str, Any]] = result.get("data", {}).get("slots", [])

            # Normalise and format times for consistent consumer output
            formatted_slots: List[Dict[str, Any]] = []
            for slot in raw_slots:
                formatted_slots.append(
                    {
                        **slot,
                        "date": date_str,
                        "start_time_fmt": _fmt_time(slot.get("start_time", "")),
                        "end_time_fmt": _fmt_time(slot.get("end_time", "")),
                    }
                )

            logger.info(
                "AvailabilityService.check_slots | %d slot(s) found | branch_id=%s date=%s",
                len(formatted_slots),
                branch_id,
                date_str,
            )
            return {
                "success": True,
                "data": {
                    "date": date_str,
                    "branch_id": branch_id,
                    "slots": formatted_slots,
                },
            }

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "AvailabilityService.check_slots | unexpected error | branch_id=%s | %s",
                branch_id,
                exc,
            )
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------

    def get_staff_for_date(
        self,
        branch_id: str,
        date_str: str,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """List staff members available to work on a given date.

        Parameters
        ----------
        branch_id:
            Salon branch to query.
        date_str:
            Date string in ``YYYY-MM-DD`` format.
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            ``{"success": True, "data": [<staff_member>, ...]}``
        """
        logger.info(
            "AvailabilityService.get_staff_for_date | branch_id=%s date=%s tenant_id=%s",
            branch_id,
            date_str,
            tenant_id,
        )
        try:
            staff_list = list_available_staff(
                branch_id=branch_id,
                date_str=date_str,
                tenant_id=tenant_id,
            )
            logger.info(
                "AvailabilityService.get_staff_for_date | %d staff found | branch_id=%s",
                len(staff_list) if isinstance(staff_list, list) else 0,
                branch_id,
            )
            return {"success": True, "data": staff_list}

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "AvailabilityService.get_staff_for_date | error | branch_id=%s | %s",
                branch_id,
                exc,
            )
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------

    def get_available_services(
        self,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Return the catalogue of services offered by the salon.

        Parameters
        ----------
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            ``{"success": True, "data": [<service>, ...]}``
        """
        logger.info(
            "AvailabilityService.get_available_services | tenant_id=%s",
            tenant_id,
        )
        try:
            services = list_available_services(tenant_id=tenant_id)
            logger.info(
                "AvailabilityService.get_available_services | %d service(s) returned",
                len(services) if isinstance(services, list) else 0,
            )
            return {"success": True, "data": services}

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "AvailabilityService.get_available_services | error | tenant_id=%s | %s",
                tenant_id,
                exc,
            )
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------

    def is_staff_available(
        self,
        staff_id: str,
        date_str: str,
        time_str: str,
        tenant_id: str = "default",
    ) -> bool:
        """Check whether a staff member has no conflicting booking at a given time.

        The method queries the ``appointments`` MCP resource for active
        bookings assigned to ``staff_id`` on ``date_str`` and returns
        ``True`` only when no overlap exists at ``time_str``.

        Parameters
        ----------
        staff_id:
            Staff member to check.
        date_str:
            Date string in ``YYYY-MM-DD`` format.
        time_str:
            Time string in ``HH:MM`` (24-hour) format.
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        bool
            ``True`` if the staff member is free; ``False`` otherwise or
            if an error occurs (fail-safe: treat errors as unavailable).
        """
        logger.info(
            "AvailabilityService.is_staff_available | staff_id=%s date=%s time=%s tenant_id=%s",
            staff_id,
            date_str,
            time_str,
            tenant_id,
        )
        try:
            result = mcp_execute(
                resource="appointments",
                action="list",
                filters={
                    "staff_id": staff_id,
                    "date": date_str,
                    "tenant_id": tenant_id,
                    "status__in": ["CONFIRMED", "PENDING"],
                },
            )
            bookings: List[Dict[str, Any]] = result.get("data", [])
            for booking in bookings:
                b_start = booking.get("start_time", "")
                b_end = booking.get("end_time", "")
                if _time_overlaps(time_str, b_start, b_end):
                    logger.info(
                        "AvailabilityService.is_staff_available | BUSY | staff_id=%s "
                        "date=%s time=%s",
                        staff_id,
                        date_str,
                        time_str,
                    )
                    return False

            logger.info(
                "AvailabilityService.is_staff_available | AVAILABLE | staff_id=%s "
                "date=%s time=%s",
                staff_id,
                date_str,
                time_str,
            )
            return True

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "AvailabilityService.is_staff_available | error | staff_id=%s | %s",
                staff_id,
                exc,
            )
            return False  # Fail-safe: treat errors as unavailable


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _fmt_time(raw: str) -> str:
    """Normalise a time string to ``HH:MM`` format.

    Accepts ISO-8601 datetimes, ``HH:MM:SS``, and ``HH:MM``.
    Returns the original string unchanged when parsing fails.
    """
    if not raw:
        return raw
    try:
        # Handle ISO-8601 datetime strings
        if "T" in raw:
            raw = raw.split("T")[1]
        parts = raw.split(":")
        return f"{int(parts[0]):02d}:{int(parts[1]):02d}"
    except Exception:  # pylint: disable=broad-except
        return raw


def _time_overlaps(time_str: str, b_start: str, b_end: str) -> bool:
    """Return True if ``time_str`` falls within [b_start, b_end).

    All three strings are expected in ``HH:MM`` (or ``HH:MM:SS``) format.
    """
    try:
        t = _to_minutes(time_str)
        s = _to_minutes(b_start)
        e = _to_minutes(b_end)
        return s <= t < e
    except Exception:  # pylint: disable=broad-except
        return False


def _to_minutes(time_str: str) -> int:
    """Convert a ``HH:MM`` or ISO datetime string to minutes since midnight."""
    if "T" in time_str:
        time_str = time_str.split("T")[1]
    parts = time_str.split(":")
    return int(parts[0]) * 60 + int(parts[1])


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------


def get_availability_service() -> AvailabilityService:
    """Return the process-level singleton :class:`AvailabilityService`."""
    global _availability_service_instance  # pylint: disable=global-statement
    if _availability_service_instance is None:
        _availability_service_instance = AvailabilityService()
    return _availability_service_instance
