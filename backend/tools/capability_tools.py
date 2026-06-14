"""
Capability Tool Layer for SalonAI Workforce Platform.

Phase 1 Architecture — High-Level Agent Tool Functions.

Each agent receives ONE capability tool instead of raw mcp_read / execute_transaction.
The tool internally delegates to the appropriate Workflow class, which in turn
calls existing MCP functions. Agents no longer construct low-level
resource/operation/filter combinations.

Tool mapping:
  Clara (Receptionist)   → appointment_workflow()
  Mia (Lead Follow-up)   → crm_workflow()
  Max (Upsell)           → recommendation_workflow()
  Olivia (Reputation)    → reputation_workflow()
  Atlas Staff            → staff_workflow()
  Atlas BI               → analytics_workflow()

Each tool accepts an `action` string and a `parameters` dict, routes to the
appropriate workflow method, runs permission validation, and returns a JSON
string for the agent to parse.

Backward Compatibility:
  mcp_read() and execute_transaction() remain unchanged in tools/mcp_tool.py
  and tools/transaction_unified.py.  Agents that still call them will continue
  to work during the transition period.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional, Union

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok(data: Any) -> str:
    """Serialize a successful result to JSON string for agent consumption."""
    if isinstance(data, str):
        return data
    try:
        return json.dumps({"success": True, "data": data}, default=str)
    except Exception:
        return str(data)


def _err(msg: str) -> str:
    """Serialize an error result to JSON string."""
    return json.dumps({"success": False, "error": msg})


def _parse_params(parameters: Union[Dict[str, Any], str]) -> Dict[str, Any]:
    """Parse parameters that may arrive as a JSON string or dict."""
    res = {}
    if isinstance(parameters, dict):
        res = dict(parameters)
    elif isinstance(parameters, str) and parameters.strip():
        try:
            res = json.loads(parameters)
        except Exception:
            try:
                import ast
                val = ast.literal_eval(parameters)
                if isinstance(val, dict):
                    res = val
            except Exception:
                pass
    return res



# ---------------------------------------------------------------------------
# 1. appointment_workflow  — for Clara (Receptionist)
# ---------------------------------------------------------------------------

def appointment_workflow(
    action: str,
    parameters: Union[Dict[str, Any], str] = "",
    user_role: str = "CUSTOMER",
    branch_id: Optional[str] = None,
    date: Optional[str] = None,
    staff_id: Optional[str] = None,
    service_id: Optional[str] = None,
    start_time: Optional[str] = None,
    notes: Optional[str] = None,
    appointment_id: Optional[str] = None,
    new_start_time: Optional[str] = None,
    new_staff_id: Optional[str] = None,
    query: Optional[str] = None,
    customer_query: Optional[str] = None,
    customer_id: Optional[str] = None,
    time: Optional[str] = None,
) -> str:
    """
    Unified appointment capability tool for Clara the Receptionist.

    Replaces direct mcp_read() / execute_transaction() calls for all
    booking-related operations.

    Args:
        action: One of:
            - 'check_availability'   — check open slots
            - 'book'                 — create new appointment
            - 'cancel'               — cancel existing appointment
            - 'reschedule'           — reschedule to new time
            - 'history'              — get customer booking history
            - 'list_services'        — list all active services
            - 'list_staff'           — list available stylists
            - 'search_customers'     — find customer by name/email/phone
        parameters: Dict of action-specific parameters (or JSON string).
        user_role: Calling user's role for permission validation.

    Returns:
        JSON string with result data or error.
    """
    params = _parse_params(parameters)
    # Merge explicit parameters if passed outside parameters dict
    for k, v in [
        ("branch_id", branch_id),
        ("date", date),
        ("staff_id", staff_id),
        ("service_id", service_id),
        ("start_time", start_time),
        ("notes", notes),
        ("appointment_id", appointment_id),
        ("new_start_time", new_start_time),
        ("new_staff_id", new_staff_id),
        ("query", query),
        ("customer_query", customer_query),
        ("customer_id", customer_id),
        ("time", time),
    ]:
        if v is not None and v != "":
            params[k] = v
    action_lower = str(action).strip().lower()

    logger.info(
        "[CapabilityTool] appointment_workflow called: action='%s' role='%s'",
        action_lower, user_role
    )

    # Permission mapping
    _action_perm_map = {
        "check_availability": "appointment_check",
        "book":               "appointment_book",
        "cancel":             "appointment_cancel",
        "reschedule":         "appointment_reschedule",
        "history":            "appointment_history",
        "list_services":      "appointment_services",
        "list_staff":         "appointment_staff",
        "search_customers":   "appointment_search_customer",
    }

    perm_key = _action_perm_map.get(action_lower)
    if perm_key:
        try:
            from services.permission_guard import validate_workflow_permission
            validate_workflow_permission(perm_key, user_role)
        except Exception as exc:
            return _err(str(exc))

    try:
        from workflows.appointment_workflow import AppointmentWorkflow as AW

        if action_lower == "check_availability":
            result = AW.check_availability(
                branch_id=params.get("branch_id"),
                date=params.get("date"),
                staff_id=params.get("staff_id"),
                service_id=params.get("service_id"),
            )
        elif action_lower == "book":
            cust_id = params.get("customer_id")
            if not cust_id and user_role == "CUSTOMER":
                cust_id = "current_user"
            result = AW.book_appointment(
                customer_id=cust_id,
                branch_id=params.get("branch_id"),
                service_id=params.get("service_id"),
                start_time=params.get("start_time"),
                staff_id=params.get("staff_id"),
                notes=params.get("notes"),
            )
        elif action_lower == "cancel":
            cust_id = params.get("customer_id")
            if not cust_id and user_role == "CUSTOMER":
                cust_id = "current_user"
            result = AW.cancel_appointment(
                appointment_id=params.get("appointment_id"),
                customer_id=cust_id,
            )
        elif action_lower == "reschedule":
            cust_id = params.get("customer_id")
            if not cust_id and user_role == "CUSTOMER":
                cust_id = "current_user"
            result = AW.reschedule_appointment(
                appointment_id=params.get("appointment_id"),
                new_start_time=params.get("new_start_time"),
                new_staff_id=params.get("new_staff_id"),
                customer_id=cust_id,
            )
        elif action_lower == "history":
            cust_id = params.get("customer_id")
            if not cust_id and user_role == "CUSTOMER":
                cust_id = "current_user"
            if not cust_id:
                return _err("'history' action requires 'customer_id'.")
            result = AW.get_customer_history(customer_id=cust_id)
        elif action_lower == "list_services":
            result = AW.list_services()
        elif action_lower == "list_staff":
            result = AW.list_staff(
                date=params.get("date"),
                time=params.get("time"),
                branch_id=params.get("branch_id"),
            )
        elif action_lower == "search_customers":
            query = params.get("query") or params.get("customer_query") or ""
            result = AW.search_customers(query=query)
        else:
            return _err(
                f"Unknown appointment action '{action_lower}'. "
                "Valid: check_availability, book, cancel, reschedule, "
                "history, list_services, list_staff, search_customers."
            )

        return _ok(result)

    except Exception as exc:
        logger.error("[CapabilityTool] appointment_workflow error: %s", exc, exc_info=True)
        return _err(f"appointment_workflow failed: {exc}")


# ---------------------------------------------------------------------------
# 2. crm_workflow  — for Mia (Lead Follow-up)
# ---------------------------------------------------------------------------

def crm_workflow(
    action: str,
    parameters: Union[Dict[str, Any], str] = "",
    user_role: str = "STAFF",
    status_filter: Optional[str] = None,
    status: Optional[str] = None,
    branch_id: Optional[str] = None,
    source_filter: Optional[str] = None,
    source: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    notes: Optional[str] = None,
    lead_id: Optional[str] = None,
    new_status: Optional[str] = None,
    channel: Optional[str] = None,
    message: Optional[str] = None,
    scheduled_at: Optional[str] = None,
    customer_id: Optional[str] = None,
    tone: Optional[str] = None,
    lookback_days: Optional[Union[int, str]] = None,
    period_days: Optional[Union[int, str]] = None,
) -> str:
    """
    Unified CRM capability tool for Mia the Lead Follow-up Specialist.

    Replaces direct mcp_read() / execute_transaction() calls for all
    CRM / lead management operations.

    Args:
        action: One of:
            - 'search_leads'         — filter CRM leads
            - 'create_lead'          — register new prospect
            - 'advance_lead'         — move lead to next stage
            - 'send_followup'        — schedule follow-up reminder
            - 'generate_message'     — draft personalized message
            - 'abandoned_bookings'   — detect no-shows / cancellations
            - 'conversion_analytics' — lead conversion analytics
            - 'pipeline_snapshot'    — quick pipeline count
        parameters: Dict of action-specific parameters (or JSON string).
        user_role: Calling user's role for permission validation.

    Returns:
        JSON string with result data or error.
    """
    params = _parse_params(parameters)
    # Merge explicit parameters if passed outside parameters dict
    for k, v in [
        ("status_filter", status_filter),
        ("status", status),
        ("branch_id", branch_id),
        ("source_filter", source_filter),
        ("source", source),
        ("first_name", first_name),
        ("last_name", last_name),
        ("email", email),
        ("phone", phone),
        ("notes", notes),
        ("lead_id", lead_id),
        ("new_status", new_status),
        ("channel", channel),
        ("message", message),
        ("scheduled_at", scheduled_at),
        ("customer_id", customer_id),
        ("tone", tone),
        ("lookback_days", lookback_days),
        ("period_days", period_days),
    ]:
        if v is not None and v != "":
            params[k] = v
    action_lower = str(action).strip().lower()

    logger.info(
        "[CapabilityTool] crm_workflow called: action='%s' role='%s'",
        action_lower, user_role
    )

    _action_perm_map = {
        "search_leads":         "crm_search",
        "create_lead":          "crm_create_lead",
        "advance_lead":         "crm_advance_lead",
        "send_followup":        "crm_send_followup",
        "generate_message":     "crm_message",
        "abandoned_bookings":   "crm_abandoned",
        "conversion_analytics": "crm_analytics",
        "pipeline_snapshot":    "crm_pipeline",
    }

    perm_key = _action_perm_map.get(action_lower)
    if perm_key:
        try:
            from services.permission_guard import validate_workflow_permission
            validate_workflow_permission(perm_key, user_role)
        except Exception as exc:
            return _err(str(exc))

    try:
        from workflows.crm_workflow import CRMWorkflow as CW

        if action_lower == "search_leads":
            result = CW.search_leads(
                status_filter=params.get("status_filter") or params.get("status"),
                branch_id=params.get("branch_id"),
                source_filter=params.get("source_filter") or params.get("source"),
            )
        elif action_lower == "create_lead":
            result = CW.create_lead(
                first_name=params.get("first_name", ""),
                email=params.get("email"),
                phone=params.get("phone"),
                last_name=params.get("last_name"),
                source=params.get("source"),
                branch_id=params.get("branch_id"),
                notes=params.get("notes"),
            )
        elif action_lower == "advance_lead":
            result = CW.advance_lead_status(
                lead_id=params.get("lead_id", ""),
                new_status=params.get("new_status", ""),
                notes=params.get("notes"),
            )
        elif action_lower == "send_followup":
            result = CW.send_followup_reminder(
                lead_id=params.get("lead_id", ""),
                channel=params.get("channel", "email"),
                message=params.get("message", ""),
                scheduled_at=params.get("scheduled_at"),
            )
        elif action_lower == "generate_message":
            result = CW.generate_personalized_message(
                customer_id=params.get("customer_id"),
                lead_id=params.get("lead_id"),
                channel=params.get("channel", "email"),
                tone=params.get("tone", "warm"),
            )
        elif action_lower == "abandoned_bookings":
            result = CW.detect_abandoned_bookings(
                branch_id=params.get("branch_id"),
                lookback_days=int(params.get("lookback_days", 30)),
            )
        elif action_lower == "conversion_analytics":
            result = CW.get_conversion_analytics(
                period_days=int(params.get("period_days", 30)),
                branch_id=params.get("branch_id"),
            )
        elif action_lower == "pipeline_snapshot":
            result = CW.get_pipeline_snapshot(branch_id=params.get("branch_id"))
        else:
            return _err(
                f"Unknown CRM action '{action_lower}'. "
                "Valid: search_leads, create_lead, advance_lead, send_followup, "
                "generate_message, abandoned_bookings, conversion_analytics, pipeline_snapshot."
            )

        return _ok(result)

    except Exception as exc:
        logger.error("[CapabilityTool] crm_workflow error: %s", exc, exc_info=True)
        return _err(f"crm_workflow failed: {exc}")


# ---------------------------------------------------------------------------
# 3. recommendation_workflow  — for Max (Upsell)
# ---------------------------------------------------------------------------

def recommendation_workflow(
    action: str,
    parameters: Union[Dict[str, Any], str] = "",
    user_role: str = "CUSTOMER",
    customer_id: Optional[str] = None,
    service_id: Optional[str] = None,
    appointment_id: Optional[str] = None,
) -> str:
    """
    Unified recommendation capability tool for Max the Upsell Specialist.

    Replaces direct mcp_read() / execute_transaction() calls for all
    upsell / recommendation operations.

    Args:
        action: One of:
            - 'get_recommendations'  — fetch personalized recommendations
            - 'accept'               — record accepted recommendation
            - 'reject'               — record rejected recommendation
            - 'analytics'            — upsell performance analytics
        parameters: Dict of action-specific parameters (or JSON string).
        user_role: Calling user's role for permission validation.

    Returns:
        JSON string with result data or error.
    """
    params = _parse_params(parameters)
    # Merge explicit parameters if passed outside parameters dict
    for k, v in [
        ("customer_id", customer_id),
        ("service_id", service_id),
        ("appointment_id", appointment_id),
    ]:
        if v is not None and v != "":
            params[k] = v
    action_lower = str(action).strip().lower()

    logger.info(
        "[CapabilityTool] recommendation_workflow called: action='%s' role='%s'",
        action_lower, user_role
    )

    _action_perm_map = {
        "get_recommendations": "recommendation_fetch",
        "accept":              "recommendation_accept",
        "reject":              "recommendation_reject",
        "analytics":           "recommendation_analytics",
    }

    perm_key = _action_perm_map.get(action_lower)
    if perm_key:
        try:
            from services.permission_guard import validate_workflow_permission
            validate_workflow_permission(perm_key, user_role)
        except Exception as exc:
            return _err(str(exc))

    try:
        from workflows.recommendation_workflow import RecommendationWorkflow as RW

        if action_lower == "get_recommendations":
            customer_id = params.get("customer_id", "")
            result = RW.get_recommendations(customer_id=customer_id)
        elif action_lower == "accept":
            result = RW.accept_recommendation(
                customer_id=params.get("customer_id", ""),
                service_id=params.get("service_id", ""),
                appointment_id=params.get("appointment_id"),
            )
        elif action_lower == "reject":
            result = RW.reject_recommendation(
                customer_id=params.get("customer_id", ""),
                service_id=params.get("service_id", ""),
                appointment_id=params.get("appointment_id"),
            )
        elif action_lower == "analytics":
            result = RW.get_analytics()
        else:
            return _err(
                f"Unknown recommendation action '{action_lower}'. "
                "Valid: get_recommendations, accept, reject, analytics."
            )

        return _ok(result)

    except Exception as exc:
        logger.error("[CapabilityTool] recommendation_workflow error: %s", exc, exc_info=True)
        return _err(f"recommendation_workflow failed: {exc}")


# ---------------------------------------------------------------------------
# 4. reputation_workflow  — for Olivia (Reputation)
# ---------------------------------------------------------------------------

def reputation_workflow(
    action: str,
    parameters: Union[Dict[str, Any], str] = "",
    user_role: str = "STAFF",
    customer_id: Optional[str] = None,
    staff_id: Optional[str] = None,
    sentiment: Optional[str] = None,
    rating: Optional[Union[int, str]] = None,
    review_id: Optional[str] = None,
    custom_response: Optional[str] = None,
) -> str:
    """
    Unified reputation capability tool for Olivia the Reputation Manager.

    Replaces direct mcp_read() / execute_transaction() calls for all
    review / reputation management operations.

    Args:
        action: One of:
            - 'get_reviews'     — fetch reviews with optional filters
            - 'analytics'       — reputation analytics (avg rating etc.)
            - 'critical'        — get all critical-sentiment reviews
            - 'respond'         — draft a response to a review
            - 'scorecard'       — reputation scorecard by sentiment
            - 'escalate'        — escalate a critical review
        parameters: Dict of action-specific parameters (or JSON string).
        user_role: Calling user's role for permission validation.

    Returns:
        JSON string with result data or error.
    """
    params = _parse_params(parameters)
    # Merge explicit parameters if passed outside parameters dict
    for k, v in [
        ("customer_id", customer_id),
        ("staff_id", staff_id),
        ("sentiment", sentiment),
        ("rating", rating),
        ("review_id", review_id),
        ("custom_response", custom_response),
    ]:
        if v is not None and v != "":
            params[k] = v
    action_lower = str(action).strip().lower()

    logger.info(
        "[CapabilityTool] reputation_workflow called: action='%s' role='%s'",
        action_lower, user_role
    )

    _action_perm_map = {
        "get_reviews": "reputation_read",
        "analytics":   "reputation_analytics",
        "critical":    "reputation_critical",
        "respond":     "reputation_respond",
        "scorecard":   "reputation_scorecard",
        "escalate":    "reputation_escalate",
    }

    perm_key = _action_perm_map.get(action_lower)
    if perm_key:
        try:
            from services.permission_guard import validate_workflow_permission
            validate_workflow_permission(perm_key, user_role)
        except Exception as exc:
            return _err(str(exc))

    try:
        from workflows.review_workflow_v2 import ReviewWorkflow as RWF

        if action_lower == "get_reviews":
            result = RWF.get_reviews(
                customer_id=params.get("customer_id"),
                staff_id=params.get("staff_id"),
                sentiment=params.get("sentiment"),
                rating=params.get("rating"),
            )
        elif action_lower == "analytics":
            result = RWF.get_analytics()
        elif action_lower == "critical":
            result = RWF.get_critical_reviews()
        elif action_lower == "respond":
            review_id = params.get("review_id", "")
            result = RWF.draft_response(
                review_id=review_id,
                custom_response=params.get("custom_response"),
            )
        elif action_lower == "scorecard":
            result = RWF.get_scorecard()
        elif action_lower == "escalate":
            review_id = params.get("review_id", "")
            result = RWF.escalate_review(review_id=review_id)
        else:
            return _err(
                f"Unknown reputation action '{action_lower}'. "
                "Valid: get_reviews, analytics, critical, respond, scorecard, escalate."
            )

        return _ok(result)

    except Exception as exc:
        logger.error("[CapabilityTool] reputation_workflow error: %s", exc, exc_info=True)
        return _err(f"reputation_workflow failed: {exc}")


# ---------------------------------------------------------------------------
# 5. staff_workflow  — for Atlas Staff
# ---------------------------------------------------------------------------

def staff_workflow(
    action: str,
    parameters: Union[Dict[str, Any], str] = "",
    user_role: str = "STAFF",
    staff_id: Optional[str] = None,
    staff_name: Optional[str] = None,
    date: Optional[str] = None,
    customer_name: Optional[str] = None,
    customer_id: Optional[str] = None,
    leave_date: Optional[str] = None,
    reason: Optional[str] = None,
) -> str:
    """
    Unified staff capability tool for Atlas the Staff Productivity Assistant.

    Replaces direct mcp_read() / execute_transaction() calls for all
    staff schedule and productivity operations.

    Args:
        action: One of:
            - 'get_schedule'         — schedule for a specific date
            - 'today_schedule'       — today's full schedule
            - 'next_customer'        — next upcoming customer
            - 'customer_history'     — booking history of a customer
            - 'customer_preferences' — styling preferences of a customer
            - 'staff_revenue'        — revenue generated by a stylist
            - 'staff_performance'    — KPI benchmarks for a stylist
            - 'pending_appointments' — unconfirmed appointments
            - 'create_leave'         — log a leave request
            - 'send_reminders'       — send appointment reminders
        parameters: Dict of action-specific parameters (or JSON string).
        user_role: Calling user's role for permission validation.

    Returns:
        JSON string with result data or error.
    """
    params = _parse_params(parameters)
    # Merge explicit parameters if passed outside parameters dict
    for k, v in [
        ("staff_id", staff_id),
        ("staff_name", staff_name),
        ("date", date),
        ("customer_name", customer_name),
        ("customer_id", customer_id),
        ("leave_date", leave_date),
        ("reason", reason),
    ]:
        if v is not None and v != "":
            params[k] = v
    action_lower = str(action).strip().lower()

    logger.info(
        "[CapabilityTool] staff_workflow called: action='%s' role='%s'",
        action_lower, user_role
    )

    _action_perm_map = {
        "get_schedule":         "staff_schedule",
        "today_schedule":       "staff_today",
        "next_customer":        "staff_next_customer",
        "customer_history":     "staff_customer_history",
        "customer_preferences": "staff_preferences",
        "staff_revenue":        "staff_revenue",
        "staff_performance":    "staff_performance",
        "pending_appointments": "staff_pending",
        "create_leave":         "staff_leave",
        "send_reminders":       "staff_reminders",
    }

    perm_key = _action_perm_map.get(action_lower)
    if perm_key:
        try:
            from services.permission_guard import validate_workflow_permission
            validate_workflow_permission(perm_key, user_role)
        except Exception as exc:
            return _err(str(exc))

    try:
        from workflows.staff_workflow import StaffWorkflow as SW

        staff_id = params.get("staff_id") or params.get("staff_name")

        if action_lower == "get_schedule":
            result = SW.get_schedule(
                staff_id=staff_id,
                date=params.get("date"),
            )
        elif action_lower == "today_schedule":
            result = SW.get_today_schedule(staff_id=staff_id)
        elif action_lower == "next_customer":
            result = SW.get_next_customer(staff_id=staff_id)
        elif action_lower == "customer_history":
            result = SW.get_customer_history(
                customer_name=params.get("customer_name") or params.get("customer_id", "")
            )
        elif action_lower == "customer_preferences":
            result = SW.get_customer_preferences(
                customer_name=params.get("customer_name") or params.get("customer_id", "")
            )
        elif action_lower == "staff_revenue":
            result = SW.get_staff_revenue(staff_id=staff_id)
        elif action_lower == "staff_performance":
            result = SW.get_staff_performance(staff_id=staff_id)
        elif action_lower == "pending_appointments":
            result = SW.get_pending_appointments(staff_id=staff_id)
        elif action_lower == "create_leave":
            result = SW.create_leave_request(
                staff_id=staff_id,
                leave_date=params.get("leave_date") or params.get("date"),
                reason=params.get("reason"),
            )
        elif action_lower == "send_reminders":
            result = SW.send_customer_reminders(staff_id=staff_id)
        else:
            return _err(
                f"Unknown staff action '{action_lower}'. "
                "Valid: get_schedule, today_schedule, next_customer, customer_history, "
                "customer_preferences, staff_revenue, staff_performance, "
                "pending_appointments, create_leave, send_reminders."
            )

        return _ok(result)

    except Exception as exc:
        logger.error("[CapabilityTool] staff_workflow error: %s", exc, exc_info=True)
        return _err(f"staff_workflow failed: {exc}")


# ---------------------------------------------------------------------------
# 6. analytics_workflow  — for Atlas BI
# ---------------------------------------------------------------------------

def analytics_workflow(
    action: str,
    parameters: Union[Dict[str, Any], str] = "",
    user_role: str = "ADMIN",
    days: Optional[Union[int, str]] = None,
    sql: Optional[str] = None,
    query: Optional[str] = None,
) -> str:
    """
    Unified analytics capability tool for Atlas the BI Analyst.

    Replaces direct mcp_read() calls for all business intelligence queries.

    Args:
        action: One of:
            - 'dashboard'          — core KPI dashboard
            - 'revenue'            — revenue intelligence aggregates
            - 'customers'          — customer retention & LTV metrics
            - 'staff'              — stylist performance benchmarks
            - 'leads'              — CRM conversion pipeline
            - 'reviews'            — reputation rating aggregates
            - 'upsell'             — upsell performance metrics
            - 'insights'           — AI-generated business insights
            - 'forecast'           — revenue and booking forecast
            - 'business_context'   — historical RAG context snapshots
            - 'raw_sql'            — custom SELECT SQL query
            - 'cohort_reminders'   — trigger returning-cohort reminders
        parameters: Dict of action-specific parameters (or JSON string).
        user_role: Calling user's role for permission validation.

    Returns:
        JSON string with result data or error.
    """
    params = _parse_params(parameters)
    # Merge explicit parameters if passed outside parameters dict
    for k, v in [
        ("days", days),
        ("sql", sql),
        ("query", query),
    ]:
        if v is not None and v != "":
            params[k] = v
    action_lower = str(action).strip().lower()

    logger.info(
        "[CapabilityTool] analytics_workflow called: action='%s' role='%s'",
        action_lower, user_role
    )

    _action_perm_map = {
        "dashboard":         "analytics_dashboard",
        "revenue":           "analytics_revenue",
        "customers":         "analytics_customers",
        "staff":             "analytics_staff",
        "leads":             "analytics_leads",
        "reviews":           "analytics_reviews",
        "upsell":            "analytics_upsell",
        "insights":          "analytics_insights",
        "forecast":          "analytics_forecast",
        "business_context":  "analytics_context",
        "raw_sql":           "analytics_raw_sql",
        "cohort_reminders":  "analytics_cohort_reminders",
    }

    perm_key = _action_perm_map.get(action_lower)
    if perm_key:
        try:
            from services.permission_guard import validate_workflow_permission
            validate_workflow_permission(perm_key, user_role)
        except Exception as exc:
            return _err(str(exc))

    try:
        from workflows.analytics_workflow import AnalyticsWorkflow as AW

        if action_lower == "dashboard":
            result = AW.get_dashboard()
        elif action_lower == "revenue":
            result = AW.get_revenue()
        elif action_lower == "customers":
            result = AW.get_customers()
        elif action_lower == "staff":
            result = AW.get_staff()
        elif action_lower == "leads":
            result = AW.get_leads()
        elif action_lower == "reviews":
            result = AW.get_reviews()
        elif action_lower == "upsell":
            result = AW.get_upsell()
        elif action_lower == "insights":
            result = AW.get_ai_insights()
        elif action_lower == "forecast":
            result = AW.get_forecast()
        elif action_lower == "business_context":
            result = AW.get_business_context(
                days=int(params.get("days", 90))
            )
        elif action_lower == "raw_sql":
            sql = params.get("sql") or params.get("query", "")
            if not sql:
                return _err("'raw_sql' action requires 'sql' parameter.")
            result = AW.run_raw_sql(sql_query=sql)
        elif action_lower == "cohort_reminders":
            result = AW.trigger_cohort_reminders()
        else:
            return _err(
                f"Unknown analytics action '{action_lower}'. "
                "Valid: dashboard, revenue, customers, staff, leads, reviews, "
                "upsell, insights, forecast, business_context, raw_sql, cohort_reminders."
            )

        return _ok(result)

    except Exception as exc:
        logger.error("[CapabilityTool] analytics_workflow error: %s", exc, exc_info=True)
        return _err(f"analytics_workflow failed: {exc}")
