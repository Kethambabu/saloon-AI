"""
Capability Tools v2 — Phase 2 Architecture.

Replaces direct workflow-class dispatch with WorkflowRegistry-based dynamic dispatch.
No giant if/else chains. Each tool constructs a HandlerContext and calls:

    get_workflow_registry().dispatch(workflow_name, action, ctx)

This version also:
  - Integrates the Enterprise Permission Model
  - Integrates the Capability Registry for action validation
  - Integrates the Token Optimizer for result compression
  - Is backward-compatible with Phase 1 capability_tools.py

All 6 agent capability tools are preserved with the same signatures.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _make_ctx(
    action: str,
    params: Dict[str, Any],
    role: str = "ADMIN",
    tenant_id: str = "default",
    session_id: str = "default",
    user_id: str = "anonymous",
) -> "HandlerContext":
    """Build a HandlerContext from capability tool arguments."""
    from handlers.base import HandlerContext
    return HandlerContext(
        params=params,
        tenant_id=tenant_id,
        user_id=user_id,
        user_role=role,
        session_id=session_id,
    )


def _dispatch(
    workflow_name: str,
    action: str,
    params: Dict[str, Any],
    role: str,
    tenant_id: str = "default",
    user_id: str = "anonymous",
) -> str:
    """
    Core dispatch: WorkflowRegistry → Handler → result string.
    Falls back to Phase 1 workflow class if WorkflowRegistry is unavailable.
    """
    # Build context
    try:
        ctx = _make_ctx(action, params, role=role, tenant_id=tenant_id, user_id=user_id)
    except Exception as exc:
        logger.error("[CapabilityToolsV2] Failed to build HandlerContext: %s", exc)
        return str({"success": False, "error": f"Context build error: {exc}"})

    # Try WorkflowRegistry dispatch
    try:
        from core.workflow_registry import get_workflow_registry
        registry = get_workflow_registry()
        result = registry.dispatch(workflow_name, action, ctx)
        # Compress result for token efficiency
        try:
            from core.token_optimizer import get_compressor
            return get_compressor().compress_tool_result(result, max_tokens=400)
        except Exception:
            return str(result)
    except Exception as exc:
        logger.warning(
            "[CapabilityToolsV2] WorkflowRegistry dispatch failed (%s). "
            "Falling back to Phase 1 capability tools. Error: %s",
            workflow_name, exc
        )

    # Phase 1 fallback
    try:
        from tools.capability_tools import (
            appointment_workflow as _apt,
            crm_workflow as _crm,
            recommendation_workflow as _rec,
            reputation_workflow as _rep,
            staff_workflow as _stf,
            analytics_workflow as _ana,
        )
        _fallback_map = {
            "appointment_workflow":    _apt,
            "crm_workflow":            _crm,
            "recommendation_workflow": _rec,
            "reputation_workflow":     _rep,
            "staff_workflow":          _stf,
            "analytics_workflow":      _ana,
        }
        fallback_fn = _fallback_map.get(workflow_name)
        if fallback_fn:
            return fallback_fn(action=action, params=params, role=role)
    except Exception as fallback_exc:
        logger.error("[CapabilityToolsV2] Phase 1 fallback also failed: %s", fallback_exc)

    return str({"success": False, "error": f"Dispatch failed for {workflow_name}.{action}"})


# ---------------------------------------------------------------------------
# Clara — Appointment Workflow
# ---------------------------------------------------------------------------
def appointment_workflow_v2(
    action: str,
    params: Optional[Dict[str, Any]] = None,
    role: str = "ADMIN",
    tenant_id: str = "default",
    user_id: str = "anonymous",
) -> str:
    """
    Clara's unified appointment capability tool (Phase 2).

    Actions:
        check_availability  — Check open slots for a date/staff/service
        book               — Book a new appointment
        cancel             — Cancel an appointment (appointment_id required)
        reschedule         — Reschedule (appointment_id + new_start_time required)
        history            — View appointment history (customer_id required)
        list_services      — List all available services
        list_staff         — List stylists for a date
        search_customers   — Search customer by name/email/phone

    Args:
        action:    One of the actions listed above.
        params:    Dict of action-specific parameters.
        role:      Caller's role (CUSTOMER | STAFF | MANAGER | OWNER | ADMIN).
        tenant_id: Tenant (salon chain) identifier.
        user_id:   Authenticated user UUID.
    """
    logger.info(
        "[CapabilityV2] appointment_workflow_v2 action=%s role=%s tenant=%s",
        action, role, tenant_id
    )
    return _dispatch("appointment_workflow", action, params or {}, role, tenant_id, user_id)


# ---------------------------------------------------------------------------
# Mia — CRM Workflow
# ---------------------------------------------------------------------------
def crm_workflow_v2(
    action: str,
    params: Optional[Dict[str, Any]] = None,
    role: str = "ADMIN",
    tenant_id: str = "default",
    user_id: str = "anonymous",
) -> str:
    """
    Mia's unified CRM capability tool (Phase 2).

    Actions:
        search_leads        — Search leads by status/branch
        create_lead         — Create a new CRM lead (first_name required)
        advance_lead        — Advance lead status (lead_id + new_status required)
        send_followup       — Send follow-up communication
        generate_message    — AI-generated follow-up message
        abandoned_bookings  — Detect abandoned booking leads
        conversion_analytics — Lead conversion rate breakdown
        pipeline_snapshot   — Full pipeline summary by status

    Args:
        action:    One of the actions listed above.
        params:    Dict of action-specific parameters.
        role:      Caller's role.
        tenant_id: Tenant identifier.
        user_id:   Authenticated user UUID.
    """
    logger.info(
        "[CapabilityV2] crm_workflow_v2 action=%s role=%s tenant=%s",
        action, role, tenant_id
    )
    return _dispatch("crm_workflow", action, params or {}, role, tenant_id, user_id)


# ---------------------------------------------------------------------------
# Max — Recommendation Workflow
# ---------------------------------------------------------------------------
def recommendation_workflow_v2(
    action: str,
    params: Optional[Dict[str, Any]] = None,
    role: str = "ADMIN",
    tenant_id: str = "default",
    user_id: str = "anonymous",
) -> str:
    """
    Max's unified recommendation capability tool (Phase 2).

    Actions:
        get_recommendations  — Get upsell recommendations for a customer
        accept               — Record recommendation acceptance
        reject               — Record recommendation rejection
        analytics            — Upsell conversion analytics

    Args:
        action:    One of the actions listed above.
        params:    Dict of action-specific parameters.
        role:      Caller's role.
        tenant_id: Tenant identifier.
        user_id:   Authenticated user UUID.
    """
    logger.info(
        "[CapabilityV2] recommendation_workflow_v2 action=%s role=%s tenant=%s",
        action, role, tenant_id
    )
    return _dispatch("recommendation_workflow", action, params or {}, role, tenant_id, user_id)


# ---------------------------------------------------------------------------
# Olivia — Reputation Workflow
# ---------------------------------------------------------------------------
def reputation_workflow_v2(
    action: str,
    params: Optional[Dict[str, Any]] = None,
    role: str = "ADMIN",
    tenant_id: str = "default",
    user_id: str = "anonymous",
) -> str:
    """
    Olivia's unified reputation capability tool (Phase 2).

    Actions:
        get_reviews     — Fetch reviews (optional filters: customer_id, sentiment, rating)
        analytics       — Average rating and sentiment analytics
        critical        — Critical/escalation-required reviews
        respond         — Draft AI response for a review (review_id required)
        scorecard       — Reputation scorecard by sentiment breakdown
        escalate        — Escalate a critical review (review_id required)

    Args:
        action:    One of the actions listed above.
        params:    Dict of action-specific parameters.
        role:      Caller's role.
        tenant_id: Tenant identifier.
        user_id:   Authenticated user UUID.
    """
    logger.info(
        "[CapabilityV2] reputation_workflow_v2 action=%s role=%s tenant=%s",
        action, role, tenant_id
    )
    return _dispatch("reputation_workflow", action, params or {}, role, tenant_id, user_id)


# ---------------------------------------------------------------------------
# Atlas Staff — Staff Workflow
# ---------------------------------------------------------------------------
def staff_workflow_v2(
    action: str,
    params: Optional[Dict[str, Any]] = None,
    role: str = "ADMIN",
    tenant_id: str = "default",
    user_id: str = "anonymous",
) -> str:
    """
    Atlas Staff's unified capability tool (Phase 2).

    Actions:
        get_schedule         — Staff schedule for a specific date
        today_schedule       — Today's appointments for a stylist
        next_customer        — Next upcoming appointment for a stylist
        customer_history     — History for a specific customer
        customer_preferences — Styling preferences for a customer
        staff_revenue        — Revenue generated by a stylist
        staff_performance    — KPI scorecard for a stylist
        pending_appointments — Unconfirmed appointments for a stylist
        create_leave         — Create a leave request
        send_reminders       — Send appointment reminders to upcoming customers

    Args:
        action:    One of the actions listed above.
        params:    Dict of action-specific parameters.
        role:      Caller's role.
        tenant_id: Tenant identifier.
        user_id:   Authenticated user UUID.
    """
    logger.info(
        "[CapabilityV2] staff_workflow_v2 action=%s role=%s tenant=%s",
        action, role, tenant_id
    )
    return _dispatch("staff_workflow", action, params or {}, role, tenant_id, user_id)


# ---------------------------------------------------------------------------
# Atlas BI — Analytics Workflow
# ---------------------------------------------------------------------------
def analytics_workflow_v2(
    action: str,
    params: Optional[Dict[str, Any]] = None,
    role: str = "ADMIN",
    tenant_id: str = "default",
    user_id: str = "anonymous",
) -> str:
    """
    Atlas BI's unified analytics capability tool (Phase 2).

    Actions:
        dashboard       — Full business overview dashboard
        revenue         — Revenue breakdown (daily/weekly/monthly)
        customers       — Customer growth and retention metrics
        staff           — Staff performance and ranking
        leads           — CRM lead analytics and funnel
        reviews         — Review and reputation analytics
        upsell          — Upsell conversion and revenue analytics
        insights        — AI-generated strategic insights
        forecast        — Revenue forecast model
        business_context — Deep context for BI queries (last N days)
        raw_sql         — Read-only SELECT query (ADMIN/OWNER only)
        cohort_reminders — Trigger returning cohort reminders

    Args:
        action:    One of the actions listed above.
        params:    Dict of action-specific parameters.
        role:      Caller's role.
        tenant_id: Tenant identifier.
        user_id:   Authenticated user UUID.
    """
    logger.info(
        "[CapabilityV2] analytics_workflow_v2 action=%s role=%s tenant=%s",
        action, role, tenant_id
    )
    return _dispatch("analytics_workflow", action, params or {}, role, tenant_id, user_id)


# ---------------------------------------------------------------------------
# Unified Capability Dispatcher (generic tool for agents)
# ---------------------------------------------------------------------------
def dispatch_capability(
    capability_name: str,
    action: str,
    params: Optional[Dict[str, Any]] = None,
    role: str = "ADMIN",
    tenant_id: str = "default",
    user_id: str = "anonymous",
) -> str:
    """
    Generic capability dispatcher using the CapabilityRegistry.

    Agents can call this instead of named tools — the registry resolves
    the workflow automatically from the capability name.

    Args:
        capability_name: Name registered in CapabilityRegistry (e.g. 'book_appointment')
        action:          Action to perform within the workflow
        params:          Action parameters dict
        role:            Caller role
        tenant_id:       Tenant identifier
        user_id:         Authenticated user UUID
    """
    logger.info(
        "[CapabilityV2] dispatch_capability name=%s action=%s role=%s",
        capability_name, action, tenant_id
    )
    try:
        from core.capability_registry import get_registry
        registry = get_registry()
        capability = registry.get(capability_name)
        if capability:
            return _dispatch(
                capability.workflow, action, params or {},
                role, tenant_id, user_id
            )
        else:
            logger.warning("[CapabilityV2] Capability '%s' not found in registry.", capability_name)
    except Exception as exc:
        logger.warning("[CapabilityV2] CapabilityRegistry lookup failed: %s", exc)

    return str({"success": False, "error": f"Capability '{capability_name}' not found."})
