"""
Base Handler — Phase 2 Architecture.

All handlers implement this interface. The WorkflowRegistry dispatches
to handlers by action name using a dict lookup instead of if/else chains.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

try:
    from infrastructure.db.database import SessionLocal
except ImportError:
    SessionLocal = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)



class HandlerContext:
    """
    Carries the full request context from orchestrator to handler.

    Attributes:
        params:      Action-specific parameters dict.
        tenant_id:   Tenant (salon chain) UUID for multi-tenant isolation.
        user_id:     Authenticated user UUID.
        user_role:   Role string (CUSTOMER | STAFF | MANAGER | OWNER | ADMIN).
        session_id:  Conversation session ID.
        branch_id:   Resolved branch UUID (optional).
        trace_id:    Unique request trace ID for logging/observability.
    """

    def __init__(
        self,
        params: Dict[str, Any],
        tenant_id: str = "default",
        user_id: str = "anonymous",
        user_role: str = "CUSTOMER",
        session_id: str = "default",
        branch_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> None:
        self.params = params
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.user_role = user_role
        self.session_id = session_id
        self.branch_id = branch_id
        self.trace_id = trace_id or self._generate_trace_id()

    @staticmethod
    def _generate_trace_id() -> str:
        import uuid
        return str(uuid.uuid4())[:8]

    def get(self, key: str, default: Any = None) -> Any:
        """Convenience accessor for params dict."""
        return self.params.get(key, default)

    def __repr__(self) -> str:
        return (
            f"<HandlerContext tenant={self.tenant_id} user={self.user_id} "
            f"role={self.user_role} trace={self.trace_id}>"
        )


class BaseHandler(ABC):
    """
    Abstract base class for all Phase 2 handlers.

    Subclasses implement `handle(ctx)` and optionally override
    `validate(ctx)` for parameter validation.
    """

    #: Human-readable name for logging and registry display.
    name: str = "BaseHandler"

    #: Permission action key validated before execution.
    permission_action: Optional[str] = None

    def __init__(self) -> None:
        self.logger = logging.getLogger(f"handler.{self.name}")

    def execute(self, ctx: HandlerContext) -> Dict[str, Any]:
        """
        Main dispatch method. Runs validate → permission check → handle.

        Returns:
            Result dict with at minimum {"success": bool, ...}.
        """
        # 1. Validate inputs
        validation_error = self.validate(ctx)
        if validation_error:
            self.logger.warning(
                "[%s] Validation failed (trace=%s): %s",
                self.name, ctx.trace_id, validation_error
            )
            return {"success": False, "error": validation_error, "handler": self.name}

        # 2. Permission check
        if self.permission_action:
            try:
                from application.services.permission_guard import validate_workflow_permission
                validate_workflow_permission(self.permission_action, ctx.user_role)
            except Exception as exc:
                self.logger.warning(
                    "[%s] Permission denied (trace=%s): %s",
                    self.name, ctx.trace_id, exc
                )
                return {"success": False, "error": str(exc), "handler": self.name}

        # 3. Execute handler
        try:
            self.logger.info(
                "[%s] Executing (trace=%s tenant=%s)",
                self.name, ctx.trace_id, ctx.tenant_id
            )
            result = self.handle(ctx)
            result["handler"] = self.name
            result["trace_id"] = ctx.trace_id
            return result
        except Exception as exc:
            self.logger.error(
                "[%s] Unhandled error (trace=%s): %s",
                self.name, ctx.trace_id, exc, exc_info=True
            )
            return {
                "success": False,
                "error": f"{self.name} failed: {exc}",
                "handler": self.name,
                "trace_id": ctx.trace_id,
            }

    @abstractmethod
    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        """Implement business logic. Must return a dict with 'success' key."""
        ...

    def validate(self, ctx: HandlerContext) -> Optional[str]:
        """
        Optional input validation.
        Return an error string if invalid, or None if valid.
        """
        return None



# =========================================================================
# CONSOLIDATED HANDLERS IMPLEMENTATION
# =========================================================================


# From handlers/appointment_handlers.py





from typing import Any, Dict, Optional


class CheckAvailabilityHandler(BaseHandler):
    """Check available booking slots for a given date/staff/service."""
    name = "CheckAvailabilityHandler"
    permission_action = "appointment_check"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from application.services.datetime_validation import validate_appointment_datetime
        req_d = ctx.get("date") or ctx.get("start_time")
        req_t = ctx.get("time")
        val = validate_appointment_datetime(req_d, req_t)
        if not val["valid"]:
            return {"success": False, "error": val["reason"], "slots": []}

        from ai.workflows.booking_workflow import check_availability_workflow
        from application.services.entity_resolver_service import resolve_entity_context
        resolved = resolve_entity_context(ctx.params)
        
        date_str = resolved.get("date") or ctx.get("date")
        if not date_str:
            start_time = resolved.get("start_time") or ctx.get("start_time")
            if start_time and len(start_time) >= 10:
                date_str = start_time[:10]
                
        return check_availability_workflow(
            branch_id=resolved.get("branch_id"),
            date_str=date_str or "",
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
        from application.services.datetime_validation import validate_appointment_datetime
        req_d = ctx.get("start_time") or ctx.get("date")
        req_t = ctx.get("time")
        val = validate_appointment_datetime(req_d, req_t)
        if not val["valid"]:
            result = {"success": False, "error": val["reason"]}
            # If the requested time today has already passed, proactively surface the
            # next available slots today instead of just rejecting the request outright.
            if "already passed today" in val["reason"]:
                try:
                    from application.services.entity_resolver_service import resolve_entity_context as _rec
                    from application.services.availability_service import get_available_slots
                    resolved_for_sugg = _rec(ctx.params)
                    date_str = (req_d or "")[:10] if req_d else None
                    if date_str:
                        avail = get_available_slots(
                            branch_id=resolved_for_sugg.get("branch_id"),
                            date_str=date_str,
                            staff_id=resolved_for_sugg.get("staff_id"),
                            service_id=resolved_for_sugg.get("service_id"),
                        )
                        if avail.get("success"):
                            result["suggested_slots"] = avail.get("slots", [])
                except Exception as sug_exc:
                    logger.warning("[BookAppointmentHandler] next-slot suggestion failed: %s", sug_exc)
            return result

        from application.services.appointment_service import get_appointment_service
        from application.services.entity_resolver_service import resolve_entity_context, resolve_relative_date, resolve_relative_time
        resolved = resolve_entity_context(ctx.params)

        if resolved.get("_resolution_errors") and not resolved.get("customer_id"):
            # A customer name/id was supplied but couldn't be resolved unambiguously —
            # do not silently book against no customer (or, previously, a random one).
            return {"success": False, "error": "; ".join(resolved["_resolution_errors"])}

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
        from application.services.appointment_service import get_appointment_service
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
        from application.services.datetime_validation import validate_appointment_datetime
        req_d = ctx.get("new_start_time") or ctx.get("start_time") or ctx.get("new_date") or ctx.get("date")
        req_t = ctx.get("new_time") or ctx.get("time")
        val = validate_appointment_datetime(req_d, req_t)
        if not val["valid"]:
            return {"success": False, "error": val["reason"]}

        from application.services.appointment_service import get_appointment_service
        from application.services.entity_resolver_service import resolve_entity_context, resolve_relative_date, resolve_relative_time
        
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
            from application.services.entity_resolver_service import resolve_entity_context
            resolved = resolve_entity_context({"customer_id": ctx.get("customer_id")})
            resolved_customer_id = resolved.get("customer_id") or ctx.get("customer_id")
            from ai.tools.mcp_tool import mcp_execute
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
            from ai.tools.discovery import list_available_services
            return {"success": True, "result": list_available_services()}
        except Exception as exc:
            return {"success": False, "error": str(exc)}


class ListStaffHandler(BaseHandler):
    """List available stylists for a date/time."""
    name = "ListStaffHandler"
    permission_action = "appointment_staff"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        try:
            from ai.tools.discovery import list_available_staff
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
            from ai.tools.discovery import search_for_customers
            return {"success": True, "result": search_for_customers(customer_query=query)}
        except Exception as exc:
            return {"success": False, "error": str(exc)}



# From handlers/crm_handlers.py




from typing import Any, Dict, Optional


class SearchLeadsHandler(BaseHandler):
    name = "SearchLeadsHandler"
    permission_action = "crm_search"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from ai.tools.mcp_tool import mcp_execute
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
        from ai.workflows.lead_workflow import create_lead_workflow
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
        from ai.workflows.lead_workflow import advance_lead_status_workflow
        return advance_lead_status_workflow(
            lead_id=ctx.get("lead_id"),
            new_status=ctx.get("new_status"),
            notes=ctx.get("notes"),
        )


class SendFollowupHandler(BaseHandler):
    name = "SendFollowupHandler"
    permission_action = "crm_send_followup"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from ai.workflows.lead_workflow import create_followup_reminder_workflow
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
        from ai.workflows.lead_workflow import generate_followup_message_workflow
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
        from ai.workflows.lead_workflow import detect_abandoned_bookings_workflow
        return detect_abandoned_bookings_workflow(
            branch_id=ctx.get("branch_id"),
            lookback_days=int(ctx.get("lookback_days") or 30),
        )


class ConversionAnalyticsHandler(BaseHandler):
    name = "ConversionAnalyticsHandler"
    permission_action = "crm_analytics"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from ai.tools.mcp_tool import mcp_execute
        return mcp_execute(
            resource="leads", operation="aggregate", metric="group_by",
            group_by="status", agent_name="CRMWorkflow"
        )


class PipelineSnapshotHandler(BaseHandler):
    name = "PipelineSnapshotHandler"
    permission_action = "crm_pipeline"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from ai.tools.mcp_tool import mcp_execute
        return mcp_execute(
            resource="leads", operation="aggregate", metric="count",
            group_by="status", agent_name="CRMWorkflow"
        )



# From handlers/reputation_handlers.py




from typing import Any, Dict, Optional
from ai.workflows.review_workflow import ReviewWorkflow


class GetReviewsHandler(BaseHandler):
    name = "GetReviewsHandler"
    permission_action = "reputation_read"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        return ReviewWorkflow.get_reviews(
            customer_id=ctx.get("customer_id"),
            staff_id=ctx.get("staff_id"),
            sentiment=ctx.get("sentiment"),
            rating=ctx.get("rating"),
        )


class ReviewAnalyticsHandler(BaseHandler):
    name = "ReviewAnalyticsHandler"
    permission_action = "reputation_analytics"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        return ReviewWorkflow.get_analytics()


class CriticalReviewsHandler(BaseHandler):
    name = "CriticalReviewsHandler"
    permission_action = "reputation_critical"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        return ReviewWorkflow.get_critical_reviews()


class DraftResponseHandler(BaseHandler):
    name = "DraftResponseHandler"
    permission_action = "reputation_respond"

    def validate(self, ctx: HandlerContext) -> Optional[str]:
        if not ctx.get("review_id"):
            return "review_id is required."
        return None

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        return ReviewWorkflow.draft_response(
            review_id=ctx.get("review_id"),
            custom_response=ctx.get("custom_response"),
        )


class ReputationScorecardHandler(BaseHandler):
    name = "ReputationScorecardHandler"
    permission_action = "reputation_scorecard"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        return ReviewWorkflow.get_scorecard()


class EscalateReviewHandler(BaseHandler):
    name = "EscalateReviewHandler"
    permission_action = "reputation_escalate"

    def validate(self, ctx: HandlerContext) -> Optional[str]:
        if not ctx.get("review_id"):
            return "review_id is required."
        return None

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        return ReviewWorkflow.escalate_review(review_id=ctx.get("review_id"))


# Alias for registry compatibility
ReputationAnalyticsHandler = ReviewAnalyticsHandler


# From handlers/recommendation_handlers.py




from typing import Any, Dict, Optional


class GetRecommendationsHandler(BaseHandler):
    name = "GetRecommendationsHandler"
    permission_action = "recommendation_fetch"

    def validate(self, ctx: HandlerContext) -> Optional[str]:
        if not ctx.get("customer_id"):
            return "customer_id is required."
        return None

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from ai.workflows.upsell_workflow import get_customer_recommendations_workflow
        return get_customer_recommendations_workflow(customer_id=ctx.get("customer_id"))


class AcceptRecommendationHandler(BaseHandler):
    name = "AcceptRecommendationHandler"
    permission_action = "recommendation_accept"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from ai.workflows.upsell_workflow import accept_recommendation_workflow
        return accept_recommendation_workflow(
            customer_id=ctx.get("customer_id", ""),
            service_id=ctx.get("service_id", ""),
            appointment_id=ctx.get("appointment_id"),
        )


class RejectRecommendationHandler(BaseHandler):
    name = "RejectRecommendationHandler"
    permission_action = "recommendation_reject"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from ai.workflows.upsell_workflow import reject_recommendation_workflow
        return reject_recommendation_workflow(
            customer_id=ctx.get("customer_id", ""),
            service_id=ctx.get("service_id", ""),
            appointment_id=ctx.get("appointment_id"),
        )


class UpsellAnalyticsHandler(BaseHandler):
    name = "UpsellAnalyticsHandler"
    permission_action = "recommendation_analytics"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from ai.workflows.upsell_workflow import get_upsell_analytics_workflow
        return get_upsell_analytics_workflow()


# Alias for registry compatibility
RecommendationAnalyticsHandler = UpsellAnalyticsHandler




# From handlers/staff_handlers.py




from typing import Any, Dict, Optional
from application.services.entity_resolver_service import resolve_relative_date


class GetScheduleHandler(BaseHandler):
    name = "GetScheduleHandler"
    permission_action = "staff_schedule"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from application.services.staff_service import get_schedule
        date = resolve_relative_date(ctx.get("date")) if ctx.get("date") else None
        return {"success": True, "result": get_schedule(staff_id=ctx.get("staff_id"), date_str=date)}


class TodayScheduleHandler(BaseHandler):
    name = "TodayScheduleHandler"
    permission_action = "staff_today"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from application.services.staff_service import get_today_schedule
        return {"success": True, "result": get_today_schedule(staff_id=ctx.get("staff_id"))}


class NextCustomerHandler(BaseHandler):
    name = "NextCustomerHandler"
    permission_action = "staff_next_customer"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from application.services.staff_service import get_next_customer
        return {"success": True, "result": get_next_customer(staff_id=ctx.get("staff_id"))}


def _is_error_result_string(result: Any) -> bool:
    """get_customer_history/get_customer_preferences/recommend_services return
    plain human-readable strings (by design, for direct LLM consumption) and
    report failures as string content rather than raising. Without this check
    the handlers around them always reported success=True even when the
    string was an error message."""
    return isinstance(result, str) and (
        result.startswith("Error") or result.startswith("No customer found")
    )


class CustomerHistoryHandler(BaseHandler):
    name = "CustomerHistoryHandler"
    permission_action = "staff_customer_history"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from application.services.staff_service import get_customer_history
        name = ctx.get("customer_name") or ctx.get("customer_id", "")
        result = get_customer_history(customer_name=name)
        return {"success": not _is_error_result_string(result), "result": result}


class CustomerPreferencesHandler(BaseHandler):
    name = "CustomerPreferencesHandler"
    permission_action = "staff_preferences"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from application.services.staff_service import get_customer_preferences
        name = ctx.get("customer_name") or ctx.get("customer_id", "")
        result = get_customer_preferences(customer_name=name)
        return {"success": not _is_error_result_string(result), "result": result}


class StaffRevenueHandler(BaseHandler):
    name = "StaffRevenueHandler"
    permission_action = "staff_revenue"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from application.services.staff_service import get_staff_revenue
        return {"success": True, "result": get_staff_revenue(staff_id=ctx.get("staff_id"))}


class StaffPerformanceHandler(BaseHandler):
    name = "StaffPerformanceHandler"
    permission_action = "staff_performance"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from application.services.staff_service import get_staff_performance
        return {"success": True, "result": get_staff_performance(staff_id=ctx.get("staff_id"))}


class PendingAppointmentsHandler(BaseHandler):
    name = "PendingAppointmentsHandler"
    permission_action = "staff_pending"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from application.services.staff_service import get_pending_appointments
        return {"success": True, "result": get_pending_appointments(staff_id=ctx.get("staff_id"))}


class CreateLeaveHandler(BaseHandler):
    name = "CreateLeaveHandler"
    permission_action = "staff_leave"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from application.services.staff_service import create_leave_request
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
        from application.services.staff_service import send_customer_reminders
        return {"success": True, "result": send_customer_reminders(staff_id=ctx.get("staff_id"))}


class GetLeavesHandler(BaseHandler):
    name = "GetLeavesHandler"
    permission_action = "staff_get_leaves"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from application.services.staff_service import get_leaves
        return {"success": True, "result": get_leaves(staff_id=ctx.get("staff_id"))}


class CancelLeaveHandler(BaseHandler):
    name = "CancelLeaveHandler"
    permission_action = "staff_cancel_leave"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from application.services.staff_service import cancel_leave
        leave_date = resolve_relative_date(ctx.get("leave_date") or ctx.get("date"))
        return {"success": True, "result": cancel_leave(
            staff_id=ctx.get("staff_id"),
            leave_date_str=leave_date
        )}


class RecommendServicesHandler(BaseHandler):
    name = "RecommendServicesHandler"
    permission_action = "staff_recommend_services"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from application.services.staff_service import recommend_services
        name = ctx.get("customer_name") or ctx.get("customer_id") or ""
        result = recommend_services(customer_id=name)
        return {"success": not _is_error_result_string(result), "result": result}


# Alias for registry compatibility
StaffKPIHandler = StaffPerformanceHandler


class StaffRawSQLHandler(BaseHandler):
    name = "StaffRawSQLHandler"
    permission_action = "staff_raw_sql"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        # 1. Resolve staff_id from user_id
        if SessionLocal is None:
            return {"success": False, "error": "Database session unavailable."}
        session = SessionLocal()
        try:
            import uuid
            user_uuid = uuid.UUID(ctx.user_id) if isinstance(ctx.user_id, str) else ctx.user_id
            from infrastructure.db import User
            user = session.query(User).filter(User.id == user_uuid).first()
            if not user or not user.staff_id:
                return {"success": False, "error": "No associated staff member found for this user."}
            staff_id = str(user.staff_id)
        finally:
            session.close()

        sql = ctx.get("sql") or ctx.get("query", "")
        if not sql:
            return {"success": False, "error": "'sql' parameter is required."}

        sql_upper = sql.strip().upper()
        if not sql_upper.startswith("SELECT"):
            return {"success": False, "error": "Only SELECT statements are allowed."}

        if "USERS" in sql_upper:
            return {"success": False, "error": "Access to the users table is forbidden."}

        if staff_id not in sql:
            return {
                "success": False,
                "error": f"Security violation: Your query must filter by your own staff ID ('{staff_id}') to ensure row-level security."
            }

        try:
            from ai.agents.bi_agent import query_raw_analytics_database
        except ImportError:
            return {"success": False, "error": "Analytics database module is unavailable."}
        raw_result = query_raw_analytics_database(sql_select_query=sql)

        # Post-filter rows for defense-in-depth
        filtered = []
        if isinstance(raw_result, list):
            for row in raw_result:
                if isinstance(row, dict):
                    # If the row has staff_id or id, verify it matches
                    s_id = row.get("staff_id") or row.get("id")
                    if s_id and str(s_id) != staff_id:
                        continue
                filtered.append(row)
            return {"success": True, "result": filtered}
        return {"success": True, "result": raw_result}


class StaffServicesHandler(BaseHandler):
    """Return a ranked breakdown of the services a staff member performs most often."""
    name = "StaffServicesHandler"
    permission_action = "staff_schedule"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from application.services.staff_service import get_staff_services
        staff_id = ctx.get("staff_id") or ctx.user_id
        result = get_staff_services(staff_id=staff_id)
        is_error = isinstance(result, str) and (
            result.startswith("Error") or result.startswith("No completed")
        )
        return {"success": not is_error, "result": result}


class AvgAppointmentDurationHandler(BaseHandler):
    """Return the average appointment duration (in minutes) for a staff member."""
    name = "AvgAppointmentDurationHandler"
    permission_action = "staff_schedule"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from application.services.staff_service import get_avg_appointment_duration
        staff_id = ctx.get("staff_id") or ctx.user_id
        result = get_avg_appointment_duration(staff_id=staff_id)
        is_error = isinstance(result, str) and (
            result.startswith("Error") or result.startswith("No completed")
        )
        return {"success": not is_error, "result": result}


# =========================================================================
# ANALYTICS HANDLERS
# =========================================================================



class DashboardHandler(BaseHandler):
    name = "DashboardHandler"
    permission_action = "analytics_dashboard"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from ai.agents.bi_agent import get_dashboard_summary
        return {"success": True, "result": get_dashboard_summary()}


class ExecutiveScorecardHandler(BaseHandler):
    name = "ExecutiveScorecardHandler"
    permission_action = "analytics_dashboard"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from infrastructure.db.database import SessionLocal
        from application.services.analytics_service import AnalyticsService
        db = SessionLocal()
        try:
            return {"success": True, "result": AnalyticsService.get_executive_scorecard(db)}
        finally:
            db.close()


# =========================================================================
# REVENUE ANALYTICS
# =========================================================================

class RevenueHandler(BaseHandler):
    name = "RevenueHandler"
    permission_action = "analytics_revenue"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from ai.agents.bi_agent import get_revenue_summary
        return {"success": True, "result": get_revenue_summary()}


class RevenueByPeriodHandler(BaseHandler):
    name = "RevenueByPeriodHandler"
    permission_action = "analytics_revenue"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from infrastructure.db.database import SessionLocal
        from application.services.analytics_service import AnalyticsService
        period = ctx.get("period") or "monthly"
        db = SessionLocal()
        try:
            return {"success": True, "result": AnalyticsService.get_revenue_by_period(db, period=period)}
        finally:
            db.close()


class AverageTicketHandler(BaseHandler):
    name = "AverageTicketHandler"
    permission_action = "analytics_revenue"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from infrastructure.db.database import SessionLocal
        from application.services.analytics_service import AnalyticsService
        db = SessionLocal()
        try:
            return {"success": True, "result": AnalyticsService.get_average_ticket_analysis(db)}
        finally:
            db.close()


class RevenuePerStaffHandler(BaseHandler):
    name = "RevenuePerStaffHandler"
    permission_action = "analytics_revenue"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from infrastructure.db.database import SessionLocal
        from application.services.analytics_service import AnalyticsService
        period_days = int(ctx.get("period_days") or 30)
        db = SessionLocal()
        try:
            return {"success": True, "result": AnalyticsService.get_revenue_per_staff_analysis(db, period_days=period_days)}
        finally:
            db.close()


# =========================================================================
# CUSTOMER ANALYTICS
# =========================================================================

class CustomerMetricsHandler(BaseHandler):
    name = "CustomerMetricsHandler"
    permission_action = "analytics_customers"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from ai.agents.bi_agent import get_customer_summary
        return {"success": True, "result": get_customer_summary()}


class CustomerAcquisitionHandler(BaseHandler):
    name = "CustomerAcquisitionHandler"
    permission_action = "analytics_customers"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from infrastructure.db.database import SessionLocal
        from application.services.analytics_service import AnalyticsService
        db = SessionLocal()
        try:
            return {"success": True, "result": AnalyticsService.get_customer_acquisition_analysis(db)}
        finally:
            db.close()


class ChurnAnalysisHandler(BaseHandler):
    name = "ChurnAnalysisHandler"
    permission_action = "analytics_customers"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from infrastructure.db.database import SessionLocal
        from application.services.analytics_service import AnalyticsService
        inactive_days = int(ctx.get("inactive_days") or 90)
        db = SessionLocal()
        try:
            return {"success": True, "result": AnalyticsService.get_churn_analysis(db, inactive_days=inactive_days)}
        finally:
            db.close()


class CohortAnalysisHandler(BaseHandler):
    name = "CohortAnalysisHandler"
    permission_action = "analytics_customers"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from infrastructure.db.database import SessionLocal
        from application.services.analytics_service import AnalyticsService
        db = SessionLocal()
        try:
            return {"success": True, "result": AnalyticsService.get_cohort_analysis(db)}
        finally:
            db.close()


# =========================================================================
# STAFF ANALYTICS
# =========================================================================

class BIStaffPerformanceHandler(BaseHandler):
    name = "BIStaffPerformanceHandler"
    permission_action = "analytics_staff"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from ai.agents.bi_agent import get_staff_summary
        return {"success": True, "result": get_staff_summary()}


class StaffUtilizationHandler(BaseHandler):
    name = "StaffUtilizationHandler"
    permission_action = "analytics_staff"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from infrastructure.db.database import SessionLocal
        from application.services.analytics_service import AnalyticsService
        period_days = int(ctx.get("period_days") or 30)
        db = SessionLocal()
        try:
            return {"success": True, "result": AnalyticsService.get_staff_utilization(db, period_days=period_days)}
        finally:
            db.close()


# =========================================================================
# APPOINTMENT ANALYTICS
# =========================================================================

class AppointmentTrendsHandler(BaseHandler):
    name = "AppointmentTrendsHandler"
    permission_action = "analytics_appointments"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from infrastructure.db.database import SessionLocal
        from application.services.analytics_service import AnalyticsService
        period_days = int(ctx.get("period_days") or 30)
        db = SessionLocal()
        try:
            return {"success": True, "result": AnalyticsService.get_appointment_trends(db, period_days=period_days)}
        finally:
            db.close()


class PeakHoursHandler(BaseHandler):
    name = "PeakHoursHandler"
    permission_action = "analytics_appointments"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from infrastructure.db.database import SessionLocal
        from application.services.analytics_service import AnalyticsService
        db = SessionLocal()
        try:
            return {"success": True, "result": AnalyticsService.get_peak_hours_analysis(db)}
        finally:
            db.close()


class NoShowAnalysisHandler(BaseHandler):
    name = "NoShowAnalysisHandler"
    permission_action = "analytics_appointments"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from infrastructure.db.database import SessionLocal
        from application.services.analytics_service import AnalyticsService
        db = SessionLocal()
        try:
            return {"success": True, "result": AnalyticsService.get_no_show_analysis(db)}
        finally:
            db.close()


class CapacityAnalysisHandler(BaseHandler):
    name = "CapacityAnalysisHandler"
    permission_action = "analytics_appointments"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from infrastructure.db.database import SessionLocal
        from application.services.analytics_service import AnalyticsService
        db = SessionLocal()
        try:
            return {"success": True, "result": AnalyticsService.get_capacity_analysis(db)}
        finally:
            db.close()


class BookingLeadTimeHandler(BaseHandler):
    name = "BookingLeadTimeHandler"
    permission_action = "analytics_appointments"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from infrastructure.db.database import SessionLocal
        from application.services.analytics_service import AnalyticsService
        db = SessionLocal()
        try:
            return {"success": True, "result": AnalyticsService.get_booking_lead_time_analysis(db)}
        finally:
            db.close()


# =========================================================================
# LEAD & CRM ANALYTICS
# =========================================================================

class LeadAnalyticsHandler(BaseHandler):
    name = "LeadAnalyticsHandler"
    permission_action = "analytics_leads"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from ai.agents.bi_agent import get_lead_summary
        return {"success": True, "result": get_lead_summary()}


class LeadPipelineAnalysisHandler(BaseHandler):
    name = "LeadPipelineAnalysisHandler"
    permission_action = "analytics_leads"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from infrastructure.db.database import SessionLocal
        from application.services.analytics_service import AnalyticsService
        db = SessionLocal()
        try:
            return {"success": True, "result": AnalyticsService.get_lead_pipeline_analysis(db)}
        finally:
            db.close()


# =========================================================================
# SERVICE ANALYTICS
# =========================================================================

class ServicePopularityHandler(BaseHandler):
    name = "ServicePopularityHandler"
    permission_action = "analytics_services"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from infrastructure.db.database import SessionLocal
        from application.services.analytics_service import AnalyticsService
        db = SessionLocal()
        try:
            return {"success": True, "result": AnalyticsService.get_service_popularity(db)}
        finally:
            db.close()


# =========================================================================
# REVIEW & REPUTATION
# =========================================================================

class BIReviewAnalyticsHandler(BaseHandler):
    name = "BIReviewAnalyticsHandler"
    permission_action = "analytics_reviews"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from ai.agents.bi_agent import get_review_summary
        return {"success": True, "result": get_review_summary()}


class ReviewTrendsHandler(BaseHandler):
    name = "ReviewTrendsHandler"
    permission_action = "analytics_reviews"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from infrastructure.db.database import SessionLocal
        from application.services.analytics_service import AnalyticsService
        period_days = int(ctx.get("period_days") or 30)
        db = SessionLocal()
        try:
            return {"success": True, "result": AnalyticsService.get_review_trends(db, period_days=period_days)}
        finally:
            db.close()


# =========================================================================
# UPSELL ANALYTICS
# =========================================================================

class BIUpsellAnalyticsHandler(BaseHandler):
    name = "BIUpsellAnalyticsHandler"
    permission_action = "analytics_upsell"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from ai.agents.bi_agent import get_upsell_summary
        return {"success": True, "result": get_upsell_summary()}


class UpsellConversionHandler(BaseHandler):
    name = "UpsellConversionHandler"
    permission_action = "analytics_upsell"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from infrastructure.db.database import SessionLocal
        from application.services.analytics_service import AnalyticsService
        db = SessionLocal()
        try:
            return {"success": True, "result": AnalyticsService.get_upsell_conversion_analysis(db)}
        finally:
            db.close()


# =========================================================================
# BRANCH / MULTI-LOCATION
# =========================================================================

class BranchComparisonHandler(BaseHandler):
    name = "BranchComparisonHandler"
    permission_action = "analytics_branches"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from infrastructure.db.database import SessionLocal
        from application.services.analytics_service import AnalyticsService
        db = SessionLocal()
        try:
            return {"success": True, "result": AnalyticsService.get_branch_comparison(db)}
        finally:
            db.close()


# =========================================================================
# OTHER CORE HANDLERS
# =========================================================================

class ForecastHandler(BaseHandler):
    name = "ForecastHandler"
    permission_action = "analytics_forecast"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from ai.agents.bi_agent import forecast_revenue
        return {"success": True, "result": forecast_revenue()}


class AIInsightsHandler(BaseHandler):
    name = "AIInsightsHandler"
    permission_action = "analytics_insights"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from ai.agents.bi_agent import generate_ai_insights
        return {"success": True, "result": generate_ai_insights()}


class BusinessContextHandler(BaseHandler):
    name = "BusinessContextHandler"
    permission_action = "analytics_context"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from ai.agents.bi_agent import retrieve_business_context
        days = int(ctx.get("days") or 90)
        return {"success": True, "result": retrieve_business_context(days=days)}


class RawSQLHandler(BaseHandler):
    name = "RawSQLHandler"
    permission_action = "analytics_raw_sql"

    def validate(self, ctx: HandlerContext) -> Optional[str]:
        sql = ctx.get("sql") or ctx.get("query", "")
        if not sql:
            return "'sql' parameter is required for raw SQL queries."
        sql_upper = sql.strip().upper()
        if not sql_upper.startswith("SELECT"):
            return "Only SELECT statements are allowed."
        return None

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        # Defense-in-depth: execute() already enforces permission_action
        # (analytics_raw_sql: OWNER/ADMIN only, per permission_guard.py) before
        # handle() is ever called. raw_sql is deliberately narrower than the
        # BUSINESS_INTELLIGENCE-intent role gate (which also admits MANAGER), so
        # this explicit re-check stays as a second, independent gate rather than
        # relying solely on upstream intent routing or the generic permission_guard
        # matrix staying in sync.
        if (ctx.user_role or "").upper() not in ("ADMIN", "OWNER"):
            return {
                "success": False,
                "error": "Raw SQL analytics queries are restricted to ADMIN/OWNER roles.",
            }
        validation_error = self.validate(ctx)
        if validation_error:
            return {"success": False, "error": validation_error}
        from ai.agents.bi_agent import query_raw_analytics_database
        sql = ctx.get("sql") or ctx.get("query", "")
        return {"success": True, "result": query_raw_analytics_database(sql_select_query=sql)}


class CohortRemindersHandler(BaseHandler):
    name = "CohortRemindersHandler"
    permission_action = "analytics_cohort_reminders"

    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        from ai.agents.bi_agent import trigger_returning_cohort_reminders
        return {"success": True, "result": trigger_returning_cohort_reminders()}
