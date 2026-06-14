"""
Staff Handlers — Phase 2.
"""

from __future__ import annotations
from typing import Any, Dict, Optional
from handlers.base import BaseHandler, HandlerContext
from services.entity_resolver_service import resolve_relative_date


class GetScheduleHandler(BaseHandler):
    name = "GetScheduleHandler"
    permission_action = "staff_schedule"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from tools.staff_tools import get_schedule
        date = resolve_relative_date(ctx.get("date")) if ctx.get("date") else None
        return {"success": True, "result": get_schedule(staff_id=ctx.get("staff_id"), date_str=date)}


class TodayScheduleHandler(BaseHandler):
    name = "TodayScheduleHandler"
    permission_action = "staff_today"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from tools.staff_tools import get_today_schedule
        return {"success": True, "result": get_today_schedule(staff_id=ctx.get("staff_id"))}


class NextCustomerHandler(BaseHandler):
    name = "NextCustomerHandler"
    permission_action = "staff_next_customer"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from tools.staff_tools import get_next_customer
        return {"success": True, "result": get_next_customer(staff_id=ctx.get("staff_id"))}


class CustomerHistoryHandler(BaseHandler):
    name = "CustomerHistoryHandler"
    permission_action = "staff_customer_history"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from tools.staff_tools import get_customer_history
        name = ctx.get("customer_name") or ctx.get("customer_id", "")
        return {"success": True, "result": get_customer_history(customer_name=name)}


class CustomerPreferencesHandler(BaseHandler):
    name = "CustomerPreferencesHandler"
    permission_action = "staff_preferences"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from tools.staff_tools import get_customer_preferences
        name = ctx.get("customer_name") or ctx.get("customer_id", "")
        return {"success": True, "result": get_customer_preferences(customer_name=name)}


class StaffRevenueHandler(BaseHandler):
    name = "StaffRevenueHandler"
    permission_action = "staff_revenue"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from tools.staff_tools import get_staff_revenue
        return {"success": True, "result": get_staff_revenue(staff_id=ctx.get("staff_id"))}


class StaffPerformanceHandler(BaseHandler):
    name = "StaffPerformanceHandler"
    permission_action = "staff_performance"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from tools.staff_tools import get_staff_performance
        return {"success": True, "result": get_staff_performance(staff_id=ctx.get("staff_id"))}


class PendingAppointmentsHandler(BaseHandler):
    name = "PendingAppointmentsHandler"
    permission_action = "staff_pending"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from tools.staff_tools import get_pending_appointments
        return {"success": True, "result": get_pending_appointments(staff_id=ctx.get("staff_id"))}


class CreateLeaveHandler(BaseHandler):
    name = "CreateLeaveHandler"
    permission_action = "staff_leave"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from tools.staff_tools import create_leave_request
        leave_date = resolve_relative_date(ctx.get("leave_date") or ctx.get("date"))
        return {"success": True, "result": create_leave_request(
            staff_id=ctx.get("staff_id"),
            leave_date=leave_date,
            reason=ctx.get("reason"),
        )}


class SendRemindersHandler(BaseHandler):
    name = "SendRemindersHandler"
    permission_action = "staff_reminders"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from tools.staff_tools import send_customer_reminders
        return {"success": True, "result": send_customer_reminders(staff_id=ctx.get("staff_id"))}


# Alias for registry compatibility
StaffKPIHandler = StaffPerformanceHandler

