"""
Appointment Handlers — Phase 2.

Each handler processes exactly one appointment operation.
Workflows dispatch to these via the WorkflowRegistry.
"""

from __future__ import annotations

from typing import Any, Dict, Optional
from handlers.base import BaseHandler, HandlerContext


class CheckAvailabilityHandler(BaseHandler):
    """Check available booking slots for a given date/staff/service."""
    name = "CheckAvailabilityHandler"
    permission_action = "appointment_check"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from workflows.booking_workflow import check_availability_workflow
        from services.entity_resolver_service import resolve_entity_context
        resolved = resolve_entity_context(ctx.params)
        return check_availability_workflow(
            branch_id=resolved.get("branch_id"),
            date_str=resolved.get("date") or ctx.get("date", ""),
            staff_id=resolved.get("staff_id"),
            service_id=resolved.get("service_id"),
        )


class BookAppointmentHandler(BaseHandler):
    """Create a new salon appointment."""
    name = "BookAppointmentHandler"
    permission_action = "appointment_book"

    def validate(self, ctx: HandlerContext) -> Optional[str]:
        if not ctx.get("service_id") and not ctx.get("service") and not ctx.get("service_name"):
            return "service_id or service_name is required to book an appointment."
        return None

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from domain.appointment_service import get_appointment_service
        from services.entity_resolver_service import resolve_entity_context, resolve_relative_date, resolve_relative_time
        resolved = resolve_entity_context(ctx.params)
        
        start_time = resolved.get("start_time") or ctx.get("start_time")
        if not start_time:
            date_val = resolved.get("date") or ctx.get("date")
            time_val = resolved.get("time") or ctx.get("time")
            if date_val and time_val:
                resolved_date = resolve_relative_date(date_val)
                resolved_time = resolve_relative_time(time_val)
                start_time = f"{resolved_date}T{resolved_time}:00Z"

        service = get_appointment_service()
        return service.book(
            customer_id=resolved.get("customer_id"),
            branch_id=resolved.get("branch_id"),
            service_id=resolved.get("service_id"),
            start_time=start_time,
            staff_id=resolved.get("staff_id"),
            notes=ctx.get("notes"),
            tenant_id=ctx.tenant_id,
        )


class CancelAppointmentHandler(BaseHandler):
    """Cancel an existing appointment."""
    name = "CancelAppointmentHandler"
    permission_action = "appointment_cancel"

    def validate(self, ctx: HandlerContext) -> Optional[str]:
        if not ctx.get("appointment_id"):
            return "appointment_id is required to cancel."
        return None

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from domain.appointment_service import get_appointment_service
        service = get_appointment_service()
        return service.cancel(
            appointment_id=ctx.get("appointment_id"),
            customer_id=ctx.get("customer_id"),
            tenant_id=ctx.tenant_id,
        )


class RescheduleAppointmentHandler(BaseHandler):
    """Reschedule an existing appointment to a new time."""
    name = "RescheduleAppointmentHandler"
    permission_action = "appointment_reschedule"

    def validate(self, ctx: HandlerContext) -> Optional[str]:
        if not ctx.get("appointment_id"):
            return "appointment_id is required to reschedule."
        if not ctx.get("new_start_time") and not ctx.get("start_time") and not (ctx.get("date") and ctx.get("time")) and not (ctx.get("new_date") and ctx.get("new_time")):
            return "new_start_time or date/time is required to reschedule."
        return None

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from domain.appointment_service import get_appointment_service
        from services.entity_resolver_service import resolve_entity_context, resolve_relative_date, resolve_relative_time
        
        new_start_time = ctx.get("new_start_time") or ctx.get("start_time")
        new_date = ctx.get("new_date") or ctx.get("date")
        new_time = ctx.get("new_time") or ctx.get("time")
        
        resolved = resolve_entity_context({
            "start_time": new_start_time,
            "date": new_date,
            "time": new_time,
        })
        
        resolved_start_time = resolved.get("start_time")
        if not resolved_start_time:
            date_val = resolved.get("date") or new_date
            time_val = resolved.get("time") or new_time
            if date_val and time_val:
                resolved_date = resolve_relative_date(date_val)
                resolved_time = resolve_relative_time(time_val)
                resolved_start_time = f"{resolved_date}T{resolved_time}:00Z"
                
        service = get_appointment_service()
        return service.reschedule(
            appointment_id=ctx.get("appointment_id"),
            new_start_time=resolved_start_time or new_start_time,
            new_staff_id=ctx.get("new_staff_id"),
            customer_id=ctx.get("customer_id"),
            tenant_id=ctx.tenant_id,
        )


class ListAppointmentsHandler(BaseHandler):
    """List appointment history for a customer."""
    name = "ListAppointmentsHandler"
    permission_action = "appointment_history"

    def validate(self, ctx: HandlerContext) -> Optional[str]:
        if not ctx.get("customer_id"):
            if ctx.user_role == "CUSTOMER":
                ctx.params["customer_id"] = "current_user"
            else:
                return "customer_id is required."
        return None

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        try:
            from services.entity_resolver_service import resolve_entity_context
            resolved = resolve_entity_context({"customer_id": ctx.get("customer_id")})
            resolved_customer_id = resolved.get("customer_id") or ctx.get("customer_id")
            from tools.mcp_tool import mcp_execute
            return mcp_execute(
                resource="appointments",
                operation="select",
                filters={"customer_id": resolved_customer_id},
                agent_name="AppointmentWorkflow",
            )
        except Exception as exc:
            return {"success": False, "error": str(exc)}


class ListServicesHandler(BaseHandler):
    """List all active salon services."""
    name = "ListServicesHandler"
    permission_action = "appointment_services"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        try:
            from tools.discovery_tools import list_available_services
            return {"success": True, "result": list_available_services()}
        except Exception as exc:
            return {"success": False, "error": str(exc)}


class ListStaffHandler(BaseHandler):
    """List available stylists for a date/time."""
    name = "ListStaffHandler"
    permission_action = "appointment_staff"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        try:
            from tools.discovery_tools import list_available_staff
            return {"success": True, "result": list_available_staff(
                date=ctx.get("date"),
                time=ctx.get("time"),
                branch_id=ctx.get("branch_id"),
            )}
        except Exception as exc:
            return {"success": False, "error": str(exc)}


class SearchCustomersHandler(BaseHandler):
    """Search for a customer by name/email/phone."""
    name = "SearchCustomersHandler"
    permission_action = "appointment_search_customer"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        query = ctx.get("query") or ctx.get("customer_query") or ""
        try:
            from tools.discovery_tools import search_for_customers
            return {"success": True, "result": search_for_customers(customer_query=query)}
        except Exception as exc:
            return {"success": False, "error": str(exc)}
