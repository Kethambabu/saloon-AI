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
import json
from typing import Any, Dict, Optional, Union

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
    from core.handlers import HandlerContext
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
    params: Union[Dict[str, Any], str],
    role: Optional[str],
    tenant_id: Optional[str] = "default",
    user_id: Optional[str] = "anonymous",
) -> str:
    """
    Core dispatch: WorkflowRegistry → Handler → result string.
    Falls back to Phase 1 workflow class if WorkflowRegistry is unavailable.
    """
    # Safety net: redirect search_knowledge_base action if LLM incorrectly targets workflow tool
    if action == "search_knowledge_base":
        logger.info(
            "[CapabilityToolsV2] Intercepted action='search_knowledge_base' on workflow '%s'. Redirecting to RAGUnified.",
            workflow_name
        )
        from infrastructure.rag.rag_unified import search_knowledge_base
        if not params:
            params = {}
        elif isinstance(params, str):
            try:
                params = json.loads(params)
            except Exception:
                params = {"query": params}
        domain = params.get("domain", "policies")
        query = params.get("query", "")
        customer_id = params.get("customer_id")
        staff_id = params.get("staff_id")
        return search_knowledge_base(domain=domain, query=query, customer_id=customer_id, staff_id=staff_id)

    role = role or "ADMIN"
    tenant_id = tenant_id or "default"
    user_id = user_id or "anonymous"
    if not params:
        params = {}
    elif isinstance(params, str):
        try:
            params = json.loads(params)
        except Exception as exc:
            logger.warning("[CapabilityToolsV2] Failed to parse params string '%s': %s", params, exc)
            params = {}
    # Normalize action aliases for appointment workflow
    if workflow_name == "appointment_workflow":
        action_mapping = {
            "confirm_booking": "book",
            "confirm": "book",
            "booking": "book",
            "create_booking": "book",
            "check_slots": "check_availability",
            "slots": "check_availability",
            "availability": "check_availability",
            "cancel_booking": "cancel",
            "cancel_appointment": "cancel",
            "reschedule_booking": "reschedule",
            "reschedule_appointment": "reschedule",
            "list_appointments": "history",
            "appointments": "history",
        }
        if action in action_mapping:
            logger.info("[CapabilityToolsV2] Mapping action alias '%s' to '%s'", action, action_mapping[action])
            action = action_mapping[action]

        if action in ("check_availability", "book", "reschedule"):
            from application.services.datetime_validation import validate_appointment_datetime
            req_d = params.get("start_time") or params.get("new_start_time") or params.get("date") or params.get("new_date")
            req_t = params.get("time") or params.get("new_time")
            val = validate_appointment_datetime(req_d, req_t)
            if not val["valid"]:
                logger.info("[CapabilityToolsV2] Terminating appointment_workflow action='%s' due to past datetime: %s", action, val["reason"])
                reason = val["reason"]
                # If a same-day booking attempt failed only because the requested time
                # has already passed, proactively suggest the remaining slots today
                # instead of leaving the customer to guess a new time blind.
                if action == "book" and "already passed today" in reason:
                    try:
                        from application.services.entity_resolver_service import resolve_entity_context
                        from application.services.availability_service import get_available_slots
                        resolved = resolve_entity_context(params)
                        date_str = (req_d or "")[:10] if req_d else None
                        if date_str:
                            avail = get_available_slots(
                                branch_id=resolved.get("branch_id"),
                                date_str=date_str,
                                staff_id=resolved.get("staff_id"),
                                service_id=resolved.get("service_id"),
                            )
                            if avail.get("success") and avail.get("slots"):
                                times = []
                                for s in avail["slots"][:5]:
                                    t = s.get("time") or (s.get("start_time") or "")[11:16]
                                    if t:
                                        times.append(t)
                                if times:
                                    reason += f" The next available slots today are: {', '.join(times)}."
                    except Exception as sug_exc:
                        logger.warning("[CapabilityToolsV2] next-slot suggestion failed: %s", sug_exc)
                return reason

    # Build context
    try:
        ctx = _make_ctx(action, params, role=role, tenant_id=tenant_id, user_id=user_id)
    except Exception as exc:
        logger.error("[CapabilityToolsV2] Failed to build HandlerContext: %s", exc)
        return str({"success": False, "error": f"Context build error: {exc}"})

    # Caching check for read actions
    READ_ACTIONS = {
        # appointment
        "check_availability": "availability",
        "list_services": "availability",
        "list_staff": "availability",
        "history": "staff",
        "search_customers": "staff",
        # crm
        "search_leads": "analytics",
        "abandoned_bookings": "analytics",
        "conversion_analytics": "analytics",
        "pipeline_snapshot": "analytics",
        # recommendation
        "get_recommendations": "analytics",
        "analytics": "analytics",
        # reputation
        "get_reviews": "analytics",
        "critical": "analytics",
        "scorecard": "analytics",
        # staff
        "get_schedule": "staff",
        "today_schedule": "staff",
        "next_customer": "staff",
        "customer_history": "staff",
        "customer_preferences": "staff",
        "staff_revenue": "analytics",
        "staff_performance": "analytics",
        "pending_appointments": "staff",
        "get_leaves": "staff",
        "recommend_services": "staff",
        "staff_services": "analytics",
        "avg_appointment_duration": "analytics",
        # NOTE: staff raw_sql is excluded from cache as results depend on the SQL query itself
        # analytics
        "dashboard": "analytics",
        "revenue": "analytics",
        "customers": "analytics",
        "staff": "analytics",
        "leads": "analytics",
        "reviews": "analytics",
        "upsell": "analytics",
        "insights": "analytics",
        "forecast": "analytics",
        "business_context": "analytics",
        # analytics — specialist actions (added alongside the Phase 2 BI prompt
        # expansion; without a cache_domain here these never hit the
        # capability_dispatch cache and always recompute from scratch)
        "executive_scorecard": "analytics",
        "revenue_by_period": "analytics",
        "average_ticket": "analytics",
        "revenue_per_staff": "analytics",
        "customer_acquisition": "analytics",
        "churn_analysis": "analytics",
        "cohort_analysis": "analytics",
        "staff_utilization": "analytics",
        "appointment_trends": "analytics",
        "peak_hours": "analytics",
        "no_show_analysis": "analytics",
        "capacity_analysis": "analytics",
        "booking_lead_time": "analytics",
        "lead_pipeline": "analytics",
        "service_popularity": "analytics",
        "review_trends": "analytics",
        "upsell_conversion": "analytics",
        "branch_comparison": "analytics",
        "raw_sql": "analytics",
        # NOTE: "cohort_reminders" is intentionally excluded — it triggers
        # sending real reminders (a side effect), not a pure read, so it must
        # never be served from cache.
    }

    INVALIDATION_RULES = {
        # appointment
        "book": ["availability", "staff"],
        "cancel": ["availability", "staff"],
        "reschedule": ["availability", "staff"],
        # crm
        "create_lead": ["analytics"],
        "advance_lead": ["analytics"],
        "send_followup": ["analytics"],
        # recommendation
        "accept": ["analytics"],
        "reject": ["analytics"],
        # reputation
        "respond": ["analytics"],
        "escalate": ["analytics"],
        # staff
        "create_leave": ["staff", "availability"],
        "send_reminders": ["staff"],
        "cancel_leave": ["staff", "availability"],
    }

    cache_domain = READ_ACTIONS.get(action)
    if cache_domain:
        try:
            import json
            from infrastructure.cache.token_optimizer import get_cache
            key_params = json.dumps(params or {}, default=str)
            cache = get_cache(cache_domain)
            cached = cache.get("capability_dispatch", workflow_name, action, key_params, str(role), str(tenant_id), str(user_id))
            if cached is not None:
                logger.info("[CapabilityToolsV2] Cache HIT namespace=capability_dispatch workflow=%s action=%s", workflow_name, action)
                return cached
        except Exception as e:
            logger.warning("[CapabilityToolsV2] Cache check failed: %s", e)

    # Try WorkflowRegistry dispatch
    try:
        from core.workflow_registry import get_workflow_registry
        registry = get_workflow_registry()
        result = registry.dispatch(workflow_name, action, ctx)
        # Compress result for token efficiency
        try:
            from infrastructure.cache.token_optimizer import get_compressor
            final_res = get_compressor().compress_tool_result(result, max_tokens=400)
        except Exception:
            final_res = str(result)

        # Cache successful read results
        if cache_domain:
            try:
                import json
                from infrastructure.cache.token_optimizer import get_cache
                key_params = json.dumps(params or {}, default=str)
                get_cache(cache_domain).set(final_res, "capability_dispatch", workflow_name, action, key_params, str(role), str(tenant_id), str(user_id))
            except Exception as e:
                logger.warning("[CapabilityToolsV2] Cache set failed: %s", e)

        # Invalidate caches on write actions
        if action in INVALIDATION_RULES:
            for domain in INVALIDATION_RULES[action]:
                try:
                    from infrastructure.cache.token_optimizer import get_cache
                    get_cache(domain).clear()
                    logger.info("[CapabilityToolsV2] Invalidated cache domain=%s due to action=%s", domain, action)
                except Exception as e:
                    logger.warning("[CapabilityToolsV2] Invalidation failed for domain=%s: %s", domain, e)

        return final_res
    except Exception as exc:
        logger.warning(
            "[CapabilityToolsV2] WorkflowRegistry dispatch failed (%s). "
            "Falling back to Phase 1 capability tools. Error: %s",
            workflow_name, exc
        )

    # Phase 1 fallback
    try:
        from ai.tools.capabilities import (
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
            fallback_res = fallback_fn(action=action, params=params, role=role)
            # Cache the fallback result if it is a read
            if cache_domain:
                try:
                    import json
                    from infrastructure.cache.token_optimizer import get_cache
                    key_params = json.dumps(params or {}, default=str)
                    get_cache(cache_domain).set(fallback_res, "capability_dispatch", workflow_name, action, key_params, str(role), str(tenant_id), str(user_id))
                except Exception as e:
                    logger.warning("[CapabilityToolsV2] Fallback cache set failed: %s", e)

            # Invalidate caches on fallback writes
            if action in INVALIDATION_RULES:
                for domain in INVALIDATION_RULES[action]:
                    try:
                        from infrastructure.cache.token_optimizer import get_cache
                        get_cache(domain).clear()
                    except Exception as e:
                        logger.warning("[CapabilityToolsV2] Fallback invalidation failed: %s", e)
            return fallback_res
    except Exception as fallback_exc:
        logger.error("[CapabilityToolsV2] Phase 1 fallback also failed: %s", fallback_exc)

    return str({"success": False, "error": f"Dispatch failed for {workflow_name}.{action}"})


# ---------------------------------------------------------------------------
# Clara — Appointment Workflow
# ---------------------------------------------------------------------------
def appointment_workflow_v2(
    action: str,
    params: Optional[Union[Dict[str, Any], str]] = None,
    role: Optional[str] = "ADMIN",
    tenant_id: Optional[str] = "default",
    user_id: Optional[str] = "anonymous",
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
    params: Optional[Union[Dict[str, Any], str]] = None,
    role: Optional[str] = "ADMIN",
    tenant_id: Optional[str] = "default",
    user_id: Optional[str] = "anonymous",
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
    params: Optional[Union[Dict[str, Any], str]] = None,
    role: Optional[str] = "ADMIN",
    tenant_id: Optional[str] = "default",
    user_id: Optional[str] = "anonymous",
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
    params: Optional[Union[Dict[str, Any], str]] = None,
    role: Optional[str] = "ADMIN",
    tenant_id: Optional[str] = "default",
    user_id: Optional[str] = "anonymous",
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
    params: Optional[Union[Dict[str, Any], str]] = None,
    role: Optional[str] = "ADMIN",
    tenant_id: Optional[str] = "default",
    user_id: Optional[str] = "anonymous",
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
        get_leaves           — View registered leave requests
        cancel_leave         — Cancel a leave request
        recommend_services   — Query personalized upsell recommendations for a customer
        raw_sql              — Execute a secure read-only SELECT query filtered to the logged-in stylist's staff_id

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
    params: Optional[Union[Dict[str, Any], str]] = None,
    role: Optional[str] = "ADMIN",
    tenant_id: Optional[str] = "default",
    user_id: Optional[str] = "anonymous",
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
    params: Optional[Union[Dict[str, Any], str]] = None,
    role: Optional[str] = "ADMIN",
    tenant_id: Optional[str] = "default",
    user_id: Optional[str] = "anonymous",
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

