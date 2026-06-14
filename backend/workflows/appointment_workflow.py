"""
AppointmentWorkflow — Phase 1 Capability Workflow for Clara (Receptionist).

Internally delegates all operations to existing MCP functions and booking tools.
Agents call appointment_workflow() instead of constructing raw mcp_read/execute_transaction calls.

Covers:
  - check availability
  - book appointment
  - cancel appointment
  - reschedule appointment
  - check history
  - list services
  - list staff
  - search customers
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from services.entity_resolver_service import resolve_entity_context

logger = logging.getLogger(__name__)


class AppointmentWorkflow:
    """
    Phase 1 workflow encapsulating all appointment-related operations for Clara.

    All methods are synchronous (agents call them as regular Python functions).
    They return plain dicts that Clara formats into natural language.
    """

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    @staticmethod
    def check_availability(
        branch_id: Optional[str] = None,
        date: Optional[str] = None,
        staff_id: Optional[str] = None,
        service_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Check available booking slots for a given date / staff / service."""
        logger.info(
            "[AppointmentWorkflow] check_availability: branch=%s date=%s staff=%s service=%s",
            branch_id, date, staff_id, service_id
        )

        # Resolve entities
        ctx = resolve_entity_context({
            "branch_id": branch_id,
            "date": date,
            "staff_id": staff_id,
            "service_id": service_id,
        })

        try:
            from workflows.booking_workflow import check_availability_workflow
            return check_availability_workflow(
                branch_id=ctx.get("branch_id"),
                date_str=ctx.get("date") or date or "",
                staff_id=ctx.get("staff_id"),
                service_id=ctx.get("service_id"),
            )
        except Exception as exc:
            logger.error("[AppointmentWorkflow] check_availability failed: %s", exc)
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # Booking
    # ------------------------------------------------------------------

    @staticmethod
    def book_appointment(
        customer_id: Optional[str] = None,
        branch_id: Optional[str] = None,
        service_id: Optional[str] = None,
        start_time: Optional[str] = None,
        staff_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new salon appointment."""
        logger.info(
            "[AppointmentWorkflow] book_appointment: customer=%s service=%s start=%s",
            customer_id, service_id, start_time
        )

        ctx = resolve_entity_context({
            "customer_id": customer_id,
            "branch_id": branch_id,
            "service_id": service_id,
            "start_time": start_time,
            "staff_id": staff_id,
        })

        try:
            from workflows.booking_workflow import book_appointment_workflow
            return book_appointment_workflow(
                customer_id=ctx.get("customer_id"),
                branch_id=ctx.get("branch_id"),
                service_id=ctx.get("service_id"),
                start_time=ctx.get("start_time"),
                staff_id=ctx.get("staff_id"),
                notes=notes,
            )
        except Exception as exc:
            logger.error("[AppointmentWorkflow] book_appointment failed: %s", exc)
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # Cancellation
    # ------------------------------------------------------------------

    @staticmethod
    def cancel_appointment(
        appointment_id: Optional[str] = None,
        customer_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Cancel an existing appointment."""
        logger.info(
            "[AppointmentWorkflow] cancel_appointment: appointment=%s customer=%s",
            appointment_id, customer_id
        )
        try:
            from workflows.booking_workflow import cancel_appointment_workflow
            return cancel_appointment_workflow(
                appointment_id=appointment_id,
                customer_id=customer_id,
            )
        except Exception as exc:
            logger.error("[AppointmentWorkflow] cancel_appointment failed: %s", exc)
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # Reschedule
    # ------------------------------------------------------------------

    @staticmethod
    def reschedule_appointment(
        appointment_id: Optional[str] = None,
        new_start_time: Optional[str] = None,
        new_staff_id: Optional[str] = None,
        customer_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Reschedule an existing appointment to a new time."""
        logger.info(
            "[AppointmentWorkflow] reschedule_appointment: appointment=%s new_time=%s",
            appointment_id, new_start_time
        )
        ctx = resolve_entity_context({
            "start_time": new_start_time,
            "staff_id": new_staff_id,
        })

        try:
            from workflows.booking_workflow import reschedule_appointment_workflow
            return reschedule_appointment_workflow(
                appointment_id=appointment_id,
                new_start_time=ctx.get("start_time") or new_start_time,
                new_staff_id=ctx.get("staff_id"),
                customer_id=customer_id,
            )
        except Exception as exc:
            logger.error("[AppointmentWorkflow] reschedule_appointment failed: %s", exc)
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    @staticmethod
    def get_customer_history(customer_id: str) -> Dict[str, Any]:
        """Retrieve booking history for a customer."""
        logger.info("[AppointmentWorkflow] get_customer_history: customer=%s", customer_id)
        resolved_cust_id = customer_id
        try:
            from services.entity_resolver_service import resolve_customer_name
            resolved = resolve_customer_name(customer_id)
            if resolved:
                resolved_cust_id = resolved
        except Exception as exc:
            logger.warning("[AppointmentWorkflow] Customer resolution failed in get_customer_history: %s", exc)

        try:
            from tools.mcp_tool import mcp_execute
            result = mcp_execute(
                resource="appointments",
                operation="select",
                filters={"customer_id": resolved_cust_id},
                agent_name="Clara_Receptionist",
            )
            return result
        except Exception as exc:
            logger.error("[AppointmentWorkflow] get_customer_history failed: %s", exc)
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    @staticmethod
    def list_services() -> Dict[str, Any]:
        """List all active services at the salon."""
        logger.info("[AppointmentWorkflow] list_services")
        try:
            from tools.discovery_tools import list_available_services
            return {"success": True, "result": list_available_services()}
        except Exception as exc:
            logger.error("[AppointmentWorkflow] list_services failed: %s", exc)
            return {"success": False, "error": str(exc)}

    @staticmethod
    def list_staff(
        date: Optional[str] = None,
        time: Optional[str] = None,
        branch_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List available stylists for a date / time."""
        logger.info("[AppointmentWorkflow] list_staff: date=%s time=%s", date, time)
        try:
            from tools.discovery_tools import list_available_staff
            return {"success": True, "result": list_available_staff(
                date=date, time=time, branch_id=branch_id
            )}
        except Exception as exc:
            logger.error("[AppointmentWorkflow] list_staff failed: %s", exc)
            return {"success": False, "error": str(exc)}

    @staticmethod
    def search_customers(query: str) -> Dict[str, Any]:
        """Search for a customer by name, email, or phone."""
        logger.info("[AppointmentWorkflow] search_customers: query=%s", query)
        try:
            from tools.discovery_tools import search_for_customers
            return {"success": True, "result": search_for_customers(customer_query=query)}
        except Exception as exc:
            logger.error("[AppointmentWorkflow] search_customers failed: %s", exc)
            return {"success": False, "error": str(exc)}
