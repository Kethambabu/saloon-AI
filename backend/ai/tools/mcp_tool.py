"""
MCP Tool Wrapper — Single database access tool for all agents.

This is the primary Phase 2 tool that agents call instead of individual
CRUD tool functions.  It wraps SalonMCP with:

    1. Context injection (builds MCPContext from a user_context dict)
    2. Permission + guard enforcement (inside SalonMCP)
    3. Aggregation support (count/sum/avg/group_by)
    4. Fallback to old CRUD tools on failure (safe migration)
    5. Observability monitoring (MCPMonitor)
    6. Audit logging (MCPAuditLogger inside SalonMCP)

Architecture
------------
Agent
  ↓
mcp_execute()           ← this file
  ↓
SalonMCP                ← permissions + guard + SQLAlchemy
  ↓
Supabase / PostgreSQL

Usage by agents
---------------
from ai.tools.mcp_tool import mcp_execute

result = mcp_execute(
    resource="appointments",
    operation="select",
    filters={"customer_id": "abc-123"},
    agent_name="Clara",
    user_context={"user_id": "u1", "role": "CUSTOMER", "customer_id": "abc-123"},
)
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Caller-identity resolution (fail-closed)
# ---------------------------------------------------------------------------

def _resolve_default_user_context() -> Dict[str, Any]:
    """
    Resolve an MCP user_context when the caller didn't supply one.

    The authoritative source of "who is calling" for a live request is the
    ``current_user_role`` / ``current_user_id`` ContextVars set once per
    request by the orchestrator (ai/orchestrator.py). Those default to
    ADMIN/"anonymous" only when there is NO active request (background
    jobs, scheduled tasks, scripts, tests) — a legitimate case that should
    get full internal access.

    Previously this fell back to regex-parsing the LLM prompt text for a
    "[SYSTEM CUSTOMER/STAFF CONTEXT: ... ID: ...]" marker, and silently
    escalated to ADMIN wildcard access whenever that parsing failed for
    *any* reason (format drift, truncated context, etc.) — even for a real,
    authenticated CUSTOMER/STAFF request. That is a fail-open privilege
    escalation. We now trust the ContextVars for role/user_id (fail-closed:
    a non-admin role stays non-admin even if we can't resolve their linked
    customer_id/staff_id — query_guard then correctly denies the request
    for missing customer_id rather than silently granting ADMIN access).
    """
    try:
        from ai.orchestrator import current_user_role, current_user_id
        role = (current_user_role.get() or "ADMIN").upper()
        user_id = current_user_id.get() or "anonymous"
    except Exception:
        role, user_id = "ADMIN", "system"

    if role == "ADMIN" and user_id in ("anonymous", "system"):
        # No live request context — legitimate internal/scheduled caller.
        return {"user_id": "system", "role": "ADMIN"}

    ctx: Dict[str, Any] = {"user_id": user_id, "role": role}

    if role in ("CUSTOMER", "STAFF"):
        linked_id = None
        # Primary: authoritative DB lookup — users.customer_id / users.staff_id —
        # rather than regex-parsing the LLM prompt text.
        try:
            import uuid as _uuid
            from infrastructure.db.database import SessionLocal
            from infrastructure.db.models import User as _UserModel
            db = SessionLocal()
            try:
                user_row = db.query(_UserModel).filter(_UserModel.id == _uuid.UUID(str(user_id))).first()
                if user_row:
                    linked_id = str(user_row.customer_id) if role == "CUSTOMER" else str(user_row.staff_id) if user_row.staff_id else None
            finally:
                db.close()
        except Exception:
            linked_id = None

        # Secondary fallback: regex-parsed prompt context (legacy mechanism,
        # kept for call sites without a resolvable DB user_id, e.g. tests).
        if not linked_id:
            try:
                if role == "CUSTOMER":
                    from application.services.entity_resolver_service import _get_context_customer_id
                    linked_id = _get_context_customer_id()
                else:
                    from application.services.entity_resolver_service import _get_context_staff_id
                    linked_id = _get_context_staff_id()
            except Exception:
                linked_id = None

        # Last resort: an inert placeholder (never a real other person's id),
        # so a lookup fails closed (no matching row) instead of escalating.
        ctx["customer_id" if role == "CUSTOMER" else "staff_id"] = linked_id or user_id

    return ctx


# ---------------------------------------------------------------------------
# Aggregate helper (for Atlas BI)
# ---------------------------------------------------------------------------

def _run_aggregate(
    resource: str,
    metric: str,
    group_by: Optional[str],
    filters: Dict[str, Any],
    context,
) -> Dict[str, Any]:
    """
    Execute an aggregate operation via SQLAlchemy.

    Supports: count, sum, avg, group_by.
    Falls back gracefully for unsupported metrics.
    """
    from infrastructure.db.database import SessionLocal
    from mcp.resource_registry import resolve_model, supports_aggregate
    from mcp.query_guard import validate_and_sanitise

    if not supports_aggregate(resource, metric):
        return {
            "success": False,
            "error": f"Aggregate metric '{metric}' is not supported for resource '{resource}'.",
            "resource": resource,
            "operation": "aggregate",
            "data": None,
        }

    model = resolve_model(resource)
    if model is None:
        return {
            "success": False,
            "error": f"Unknown resource '{resource}'.",
            "resource": resource,
            "operation": "aggregate",
            "data": None,
        }

    try:
        safe_filters = validate_and_sanitise(context, resource, "select", filters)
    except Exception as exc:
        return {
            "success": False,
            "error": str(exc),
            "error_code": "GUARD_VIOLATION",
            "resource": resource,
            "operation": "aggregate",
            "data": None,
        }

    import uuid
    from sqlalchemy import func, text as sa_text

    db = SessionLocal()
    try:
        if metric == "count":
            if group_by and hasattr(model, group_by):
                col = getattr(model, group_by)
                rows = (
                    db.query(col, func.count(model.id))
                    .filter(*[getattr(model, k) == v for k, v in safe_filters.items() if hasattr(model, k)])
                    .group_by(col)
                    .all()
                )
                data = [{"group": str(r[0].value if hasattr(r[0], "value") else r[0]), "count": r[1]} for r in rows]
            else:
                q = db.query(func.count(model.id))
                for k, v in safe_filters.items():
                    if hasattr(model, k):
                        try:
                            v = uuid.UUID(str(v))
                        except Exception:
                            pass
                        q = q.filter(getattr(model, k) == v)
                data = {"count": q.scalar() or 0}

        elif metric in ("sum", "avg"):
            # Try to find a numeric column: price, points_change, rating, loyalty_points
            numeric_cols = ["price", "points_change", "rating", "loyalty_points", "revenue"]
            target_col = None
            for nc in numeric_cols:
                if hasattr(model, nc):
                    target_col = nc
                    break

            if not target_col:
                return {
                    "success": False,
                    "error": f"No numeric column found on '{resource}' for {metric} aggregation.",
                    "resource": resource,
                    "operation": "aggregate",
                    "data": None,
                }

            col = getattr(model, target_col)
            agg_fn = func.sum(col) if metric == "sum" else func.avg(col)
            q = db.query(agg_fn)
            for k, v in safe_filters.items():
                if hasattr(model, k):
                    try:
                        v = uuid.UUID(str(v))
                    except Exception:
                        pass
                    q = q.filter(getattr(model, k) == v)
            value = q.scalar()
            data = {metric: round(float(value), 2) if value is not None else 0.0, "column": target_col}

        elif metric == "group_by":
            if not group_by:
                return {
                    "success": False,
                    "error": "group_by metric requires a 'group_by' field in filters.",
                    "resource": resource,
                    "operation": "aggregate",
                    "data": None,
                }
            if not hasattr(model, group_by):
                return {
                    "success": False,
                    "error": f"Field '{group_by}' does not exist on resource '{resource}'.",
                    "resource": resource,
                    "operation": "aggregate",
                    "data": None,
                }
            col = getattr(model, group_by)
            rows = (
                db.query(col, func.count(model.id))
                .group_by(col)
                .all()
            )
            data = [{"group": str(r[0].value if hasattr(r[0], "value") else r[0]), "count": r[1]} for r in rows]

        else:
            data = {}

        return {
            "success": True,
            "resource": resource,
            "operation": "aggregate",
            "metric": metric,
            "data": data,
        }

    except Exception as exc:
        logger.error("[MCPTool] Aggregate query failed: %s", exc, exc_info=True)
        return {
            "success": False,
            "error": str(exc),
            "resource": resource,
            "operation": "aggregate",
            "data": None,
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Main mcp_execute function
# ---------------------------------------------------------------------------

def mcp_execute(
    resource: str,
    operation: str = "select",
    filters: Optional[Dict[str, Any]] = None,
    agent_name: str = "Agent",
    user_context: Optional[Dict[str, Any]] = None,
    limit: int = 50,
    offset: int = 0,
    # Aggregate-specific
    metric: Optional[str] = None,
    group_by: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Universal MCP database access tool for all agents.

    This is the SINGLE tool that agents use for all database reads.
    Write operations (booking, cancellation, lead creation) still use
    their dedicated business-logic tools.

    Parameters
    ----------
    resource:       Target resource name: "appointments" | "reviews" | "services" |
                    "staff" | "customers" | "leads" | "branches" | "loyalty_points"
    operation:      "select" | "aggregate"
    filters:        Key-value filter dict (e.g. {"customer_id": "abc-123"})
    agent_name:     Name of the calling agent (for observability)
    user_context:   Dict with user_id, role, customer_id, staff_id etc.
                    If None, defaults to ADMIN context (for internal/scheduled calls).
    limit:          Max rows to return (default 50)
    offset:         Pagination offset (default 0)
    metric:         For aggregate operations: "count" | "sum" | "avg" | "group_by"
    group_by:       Field name to group by (for group_by metric)

    Returns
    -------
    dict
        {
            "success": bool,
            "resource": str,
            "operation": str,
            "data": list | dict | None,
            "count": int,
            "error": str | None,
            "error_code": str | None,
            "via": "mcp" | "fallback"
        }
    """
    t_start = time.perf_counter()
    filters = filters or {}

    try:
        from mcp.context_builder import build_context_from_dict
        from mcp.salon_mcp import SalonMCP
        from application.services.mcp_monitor import get_monitor

        monitor = get_monitor()

        # Build MCP context
        if user_context is None or not user_context:
            user_context = _resolve_default_user_context()

        ctx = build_context_from_dict(user_context)
        role_str = ctx.role if isinstance(ctx.role, str) else ctx.role.value

        # ------------------------------------
        # Aggregate path
        # ------------------------------------
        if operation == "aggregate":
            if not metric:
                return {
                    "success": False,
                    "error": "operation='aggregate' requires 'metric' parameter.",
                    "resource": resource,
                    "operation": operation,
                    "data": None,
                    "via": "mcp",
                }
            result = _run_aggregate(resource, metric, group_by, filters, ctx)
            elapsed = (time.perf_counter() - t_start) * 1000
            monitor.record(
                agent=agent_name,
                resource=resource,
                operation=f"aggregate:{metric}",
                elapsed_ms=elapsed,
                role=role_str,
                success=result.get("success", False),
                error=result.get("error"),
            )
            result["via"] = "mcp"
            return result

        # ------------------------------------
        # Select path
        # ------------------------------------
        mcp = SalonMCP()

        method_map = {
            "appointments":   mcp.get_appointments,
            "reviews":        mcp.get_reviews,
            "services":       mcp.get_services,
            "staff":          mcp.get_staff,
            "customers":      mcp.get_customers,
            "leads":          mcp.get_leads,
            "branches":       mcp.get_branches,
            "loyalty_points": mcp.get_loyalty_points,
        }

        mcp_method = method_map.get(resource.lower())
        if not mcp_method:
            return {
                "success": False,
                "error": f"Resource '{resource}' is not supported by mcp_execute.",
                "resource": resource,
                "operation": operation,
                "data": None,
                "count": 0,
                "via": "mcp",
            }

        response = mcp_method(context=ctx, filters=filters, limit=limit, offset=offset)

        elapsed = (time.perf_counter() - t_start) * 1000
        monitor.record(
            agent=agent_name,
            resource=resource,
            operation=operation,
            elapsed_ms=elapsed,
            role=role_str,
            success=response.success,
            error=response.error,
            filters_used=list(filters.keys()),
            rows_returned=response.count,
        )

        return {
            "success": response.success,
            "resource": response.resource,
            "operation": response.operation,
            "data": response.data,
            "count": response.count,
            "error": response.error,
            "error_code": response.error_code,
            "metadata": response.metadata,
            "via": "mcp",
        }

    except Exception as exc:
        elapsed = (time.perf_counter() - t_start) * 1000
        logger.error(
            "[MCPTool] mcp_execute failed for resource='%s' agent='%s': %s",
            resource, agent_name, exc, exc_info=True
        )

        # ------------------------------------------------------------------
        # Fallback to old CRUD tools (Phase 2 safety net)
        # ------------------------------------------------------------------
        logger.warning(
            "[MCPTool] Falling back to legacy CRUD tools for resource='%s'", resource
        )
        return _fallback_execute(resource, operation, filters, limit)


def _fallback_execute(
    resource: str,
    operation: str,
    filters: Dict[str, Any],
    limit: int,
) -> Dict[str, Any]:
    """
    Last-resort fallback to legacy SQLAlchemy CRUD patterns.
    Runs a raw DB query without permissions (ADMIN-level) if MCP fails.
    """
    try:
        from infrastructure.db.database import SessionLocal
        from mcp.resource_registry import resolve_model
        import uuid

        model = resolve_model(resource)
        if not model:
            return {
                "success": False,
                "error": f"No fallback available for resource '{resource}'.",
                "resource": resource,
                "operation": operation,
                "data": None,
                "count": 0,
                "via": "fallback_error",
            }

        db = SessionLocal()
        try:
            q = db.query(model)
            for k, v in filters.items():
                if hasattr(model, k):
                    try:
                        v = uuid.UUID(str(v))
                    except Exception:
                        pass
                    q = q.filter(getattr(model, k) == v)
            rows = q.limit(limit).all()
            data = []
            for row in rows:
                r = {}
                for col in row.__table__.columns:
                    val = getattr(row, col.name, None)
                    if isinstance(val, uuid.UUID):
                        val = str(val)
                    elif hasattr(val, "isoformat"):
                        val = val.isoformat()
                    elif hasattr(val, "value"):
                        val = val.value
                    r[col.name] = val
                data.append(r)

            logger.info(
                "[MCPTool] Fallback query succeeded for resource='%s', rows=%d",
                resource, len(data)
            )
            return {
                "success": True,
                "resource": resource,
                "operation": operation,
                "data": data,
                "count": len(data),
                "error": None,
                "via": "fallback",
            }
        finally:
            db.close()

    except Exception as fallback_exc:
        logger.error("[MCPTool] Fallback also failed: %s", fallback_exc)
        return {
            "success": False,
            "error": f"Both MCP and fallback failed: {fallback_exc}",
            "resource": resource,
            "operation": operation,
            "data": None,
            "count": 0,
            "via": "fallback_error",
        }


def mcp_write(
    resource: str,
    operation: str,  # "insert", "update", "delete"
    data: Optional[Union[Dict[str, Any], str]] = None,
    filters: Optional[Union[Dict[str, Any], str]] = None,
    agent_name: str = "Agent",
    user_context: Optional[Union[Dict[str, Any], str]] = None,
) -> Dict[str, Any]:
    """
    Universal MCP database write tool for all agents.

    Allows creating, updating, and deleting records safely via SalonMCP.
    """
    t_start = time.perf_counter()
    
    # Parse data if it is a string
    if isinstance(data, str) and data.strip():
        try:
            import json
            data = json.loads(data)
        except Exception:
            try:
                import ast
                data = ast.literal_eval(data)
            except Exception:
                data = {}
    if not isinstance(data, dict):
        data = {}

    # Parse filters if it is a string
    if isinstance(filters, str) and filters.strip():
        try:
            import json
            filters = json.loads(filters)
        except Exception:
            try:
                import ast
                filters = ast.literal_eval(filters)
            except Exception:
                filters = {}
    if not isinstance(filters, dict):
        filters = {}

    # Parse user_context if it is a string
    if isinstance(user_context, str) and user_context.strip():
        try:
            import json
            user_context = json.loads(user_context)
        except Exception:
            try:
                import ast
                user_context = ast.literal_eval(user_context)
            except Exception:
                user_context = {}
    if not isinstance(user_context, dict):
        user_context = {}

    try:
        from mcp.context_builder import build_context_from_dict
        from mcp.salon_mcp import SalonMCP
        from application.services.mcp_monitor import get_monitor

        monitor = get_monitor()

        if user_context is None or not user_context:
            user_context = _resolve_default_user_context()

        ctx = build_context_from_dict(user_context)
        role_str = ctx.role if isinstance(ctx.role, str) else ctx.role.value

        mcp = SalonMCP()
        response = mcp.execute_write(
            context=ctx,
            resource=resource,
            operation=operation,
            data=data,
            filters=filters,
            agent_name=agent_name,
        )

        elapsed = (time.perf_counter() - t_start) * 1000
        monitor.record(
            agent=agent_name,
            resource=resource,
            operation=operation,
            elapsed_ms=elapsed,
            role=role_str,
            success=response.success,
            error=response.error,
        )

        # Invalidate caches on successful write
        if response.success:
            try:
                from infrastructure.cache.token_optimizer import get_cache
                if resource.lower() in ("appointments", "bookings"):
                    get_cache("availability").clear()
                    get_cache("staff").clear()
                elif resource.lower() in ("leads", "reviews"):
                    get_cache("analytics").clear()
                elif resource.lower() == "staff":
                    get_cache("staff").clear()
                    get_cache("availability").clear()
            except Exception as e:
                logger.warning(f"Cache invalidation failed: {e}")

        return {
            "success": response.success,
            "resource": response.resource,
            "operation": response.operation,
            "data": response.data,
            "count": response.count,
            "error": response.error,
            "error_code": response.error_code,
            "metadata": response.metadata,
            "via": "mcp",
        }
    except Exception as exc:
        logger.error(
            "[MCPTool] mcp_write failed for resource='%s' operation='%s' agent='%s': %s",
            resource, operation, agent_name, exc, exc_info=True
        )
        return {
            "success": False,
            "resource": resource,
            "operation": operation,
            "data": None,
            "count": 0,
            "error": str(exc),
            "via": "mcp_error",
        }


def mcp_read(
    resource: str,
    operation: str = "select",
    filters: Optional[Union[Dict[str, Any], str]] = None,
    agent_name: str = "Agent",
    user_context: Optional[Union[Dict[str, Any], str]] = None,
    limit: Optional[int] = 50,
    offset: Optional[int] = 0,
    metric: Optional[str] = None,
    group_by: Optional[str] = None,
) -> Any:
    """
    Universal MCP database read tool for all agents.
    Exposes read-only database query operations, aggregate calculations, and statistics.
    """
    res_lower = str(resource).strip().lower()
    oper_lower = str(operation).strip().lower()
    
    # Parse filters if it is a string
    flts = filters
    if isinstance(flts, str) and flts.strip():
        try:
            import json
            flts = json.loads(flts)
        except Exception:
            try:
                import ast
                flts = ast.literal_eval(flts)
            except Exception:
                flts = {}
    if not isinstance(flts, dict):
        flts = {}

    # Parse user_context if it is a string
    ctx_dict = user_context
    if isinstance(ctx_dict, str) and ctx_dict.strip():
        try:
            import json
            ctx_dict = json.loads(ctx_dict)
        except Exception:
            try:
                import ast
                ctx_dict = ast.literal_eval(ctx_dict)
            except Exception:
                ctx_dict = {}
    if not isinstance(ctx_dict, dict):
        ctx_dict = {}

    # Re-assign to variables used by downstream logic
    filters = flts
    user_context = ctx_dict
    
    limit_val = limit if limit is not None else 50
    offset_val = offset if offset is not None else 0

    logger.info(f"[MCPRead] Consolidated read: resource='{res_lower}', operation='{oper_lower}'")

    # Try cache check
    try:
        from infrastructure.cache.token_optimizer import get_cache
        cache_domain = "analytics"
        if res_lower in ("schedule", "today_schedule", "next_customer", "customer_history", "customer_preferences", "pending_appointments"):
            cache_domain = "staff"
        elif res_lower in ("services", "staff") or oper_lower == "check_availability":
            cache_domain = "availability"
        
        # Serialize arguments to make a clean cache key
        import json
        key_filters = json.dumps(filters or {}, default=str)
        key_ctx = json.dumps(user_context or {}, default=str)
        
        cache = get_cache(cache_domain)
        cached = cache.get("mcp_read", res_lower, oper_lower, key_filters, limit_val, offset_val, metric, group_by, key_ctx)
        if cached is not None:
            logger.info(f"⚡ MCPRead cache HIT: resource='{res_lower}', operation='{oper_lower}'")
            return cached
    except Exception as e:
        logger.warning(f"MCPRead cache get failed: {e}")

    ret_val = None
    try:
        # 1. Receptionist & Customer lookups
        if res_lower == "services":
            from ai.agents.receptionist_agent import get_available_services
            ret_val = get_available_services()
            
        elif res_lower == "staff":
            if "date" in flts or "time" in flts:
                from ai.agents.receptionist_agent import get_available_staff
                ret_val = get_available_staff(
                    date=flts.get("date"),
                    time=flts.get("time"),
                    branch_id=flts.get("branch_id")
                )
            # Default to standard mcp_execute
            
        elif res_lower == "customers" and oper_lower == "select":
            if "query" in flts or "customer_query" in flts:
                from ai.agents.receptionist_agent import search_customers
                q = flts.get("query") or flts.get("customer_query")
                ret_val = search_customers(customer_query=q)

        elif res_lower == "appointments" and oper_lower == "check_availability":
            from application.services.datetime_validation import validate_appointment_datetime
            val = validate_appointment_datetime(flts.get("date"))
            if not val["valid"]:
                ret_val = val["reason"]
            else:
                from ai.agents.receptionist_agent import check_stylist_availability
                ret_val = check_stylist_availability(
                    branch_id=flts.get("branch_id"),
                    date=flts.get("date"),
                    staff_id=flts.get("staff_id"),
                    service_id=flts.get("service_id")
                )

        elif res_lower == "appointments" and oper_lower == "select":
            if "customer_id" in flts:
                from ai.agents.receptionist_agent import check_customer_booking_history
                ret_val = check_customer_booking_history(customer_id=flts.get("customer_id"))

        # 2. Reputation/Review lookups
        elif res_lower == "reviews" and oper_lower == "select":
            from ai.agents.reputation_agent import view_customer_reviews
            ret_val = view_customer_reviews(
                customer_id=flts.get("customer_id"),
                staff_id=flts.get("staff_id"),
                sentiment=flts.get("sentiment"),
                rating=flts.get("rating")
            )

        elif res_lower == "reviews" and oper_lower == "aggregate":
            if group_by == "sentiment":
                from ai.agents.reputation_agent import view_reputation_scorecard
                ret_val = view_reputation_scorecard()
            else:
                from ai.agents.reputation_agent import view_review_analytics
                ret_val = view_review_analytics()

        # 3. CRM & Lead lookups
        elif res_lower == "leads" and oper_lower == "select":
            from ai.agents.lead_followup_agent import search_leads
            ret_val = search_leads(
                status_filter=flts.get("status") or flts.get("status_filter"),
                branch_id=flts.get("branch_id"),
                source_filter=flts.get("source") or flts.get("source_filter")
            )

        elif res_lower == "leads" and oper_lower == "aggregate":
            if metric == "group_by":
                from ai.agents.lead_followup_agent import view_conversion_analytics
                ret_val = view_conversion_analytics(
                    period_days=flts.get("period_days", 30),
                    branch_id=flts.get("branch_id")
                )
            else:
                from ai.agents.lead_followup_agent import view_pipeline_snapshot
                ret_val = view_pipeline_snapshot(branch_id=flts.get("branch_id"))

        # 4. Business Intelligence lookups
        elif res_lower == "dashboard":
            from ai.agents.bi_agent import get_dashboard_summary
            period = flts.get("period") or flts.get("dashboardPeriod") or "today"
            ret_val = get_dashboard_summary(period=period)

        elif res_lower == "revenue":
            from ai.agents.bi_agent import get_revenue_summary
            ret_val = get_revenue_summary()

        elif res_lower == "customer_summary":
            from ai.agents.bi_agent import get_customer_summary
            ret_val = get_customer_summary()

        elif res_lower == "staff_summary":
            from ai.agents.bi_agent import get_staff_summary
            ret_val = get_staff_summary()

        elif res_lower == "lead_summary":
            from ai.agents.bi_agent import get_lead_summary
            ret_val = get_lead_summary()

        elif res_lower == "review_summary":
            from ai.agents.bi_agent import get_review_summary
            ret_val = get_review_summary()

        elif res_lower == "upsell_summary":
            from ai.agents.bi_agent import get_upsell_summary
            ret_val = get_upsell_summary()

        elif res_lower == "ai_insights":
            from ai.agents.bi_agent import generate_ai_insights
            ret_val = generate_ai_insights()

        elif res_lower == "forecast":
            from ai.agents.bi_agent import forecast_revenue
            ret_val = forecast_revenue()

        elif res_lower == "business_context":
            from ai.agents.bi_agent import retrieve_business_context
            ret_val = retrieve_business_context(days=flts.get("days", 90))

        elif res_lower == "db_schema":
            caller_role = str((user_context or {}).get("role", "")).upper()
            if caller_role not in ("ADMIN", "OWNER"):
                ret_val = {"success": False, "error": "Database schema resources are restricted to ADMIN/OWNER roles."}
            else:
                from ai.agents.bi_agent import get_database_schema
                ret_val = get_database_schema()

        elif res_lower == "raw_sql":
            caller_role = str((user_context or {}).get("role", "")).upper()
            if caller_role not in ("ADMIN", "OWNER"):
                ret_val = {"success": False, "error": "Raw SQL analytics queries are restricted to ADMIN/OWNER roles."}
            else:
                from ai.agents.bi_agent import query_raw_analytics_database
                ret_val = query_raw_analytics_database(sql_select_query=flts.get("sql"))

        # 5. Staff Assistant lookups
        staff_ident = flts.get("staff_id") or flts.get("staff_name") or flts.get("name") or flts.get("stylist")
        if not staff_ident and user_context:
            staff_ident = user_context.get("staff_id")

        if res_lower == "schedule":
            from application.services.staff_service import get_schedule
            ret_val = get_schedule(staff_id=staff_ident, date_str=flts.get("date"))

        elif res_lower == "today_schedule":
            from application.services.staff_service import get_today_schedule
            ret_val = get_today_schedule(staff_id=staff_ident)

        elif res_lower == "next_customer":
            from application.services.staff_service import get_next_customer
            ret_val = get_next_customer(staff_id=staff_ident)

        elif res_lower == "customer_history":
            from application.services.staff_service import get_customer_history
            ret_val = get_customer_history(customer_name=flts.get("customer_name") or flts.get("name") or flts.get("customer_id"))

        elif res_lower == "customer_preferences":
            from application.services.staff_service import get_customer_preferences
            ret_val = get_customer_preferences(customer_name=flts.get("customer_name") or flts.get("name") or flts.get("customer_id"))

        elif res_lower == "staff_revenue":
            from application.services.staff_service import get_staff_revenue
            ret_val = get_staff_revenue(staff_id=staff_ident)

        elif res_lower == "staff_performance":
            from application.services.staff_service import get_staff_performance
            ret_val = get_staff_performance(staff_id=staff_ident)

        elif res_lower == "pending_appointments":
            from application.services.staff_service import get_pending_appointments
            ret_val = get_pending_appointments(staff_id=staff_ident)

        # 6. Upsell lookups
        elif res_lower == "recommendations":
            from ai.agents.upsell_agent import get_customer_recommendations
            ret_val = get_customer_recommendations(customer_id=flts.get("customer_id"))

        elif res_lower == "upsell_analytics":
            from ai.agents.upsell_agent import get_upsell_analytics
            ret_val = get_upsell_analytics()

    except Exception as e:
        logger.error(f"Error in mcp_read Facade for resource={res_lower}: {str(e)}", exc_info=True)
        ret_val = f"Error reading data: {str(e)}"

    if ret_val is None:
        # Standard fallback to direct database mcp_execute
        ret_val = mcp_execute(
            resource=resource,
            operation=operation,
            filters=filters,
            agent_name=agent_name,
            user_context=user_context,
            limit=limit_val,
            offset=offset_val,
            metric=metric,
            group_by=group_by,
        )

    # Store in cache
    try:
        from infrastructure.cache.token_optimizer import get_cache
        cache_domain = "analytics"
        if res_lower in ("schedule", "today_schedule", "next_customer", "customer_history", "customer_preferences", "pending_appointments"):
            cache_domain = "staff"
        elif res_lower in ("services", "staff") or oper_lower == "check_availability":
            cache_domain = "availability"
            
        import json
        key_filters = json.dumps(filters or {}, default=str)
        key_ctx = json.dumps(user_context or {}, default=str)
        
        # Set domain-appropriate TTL
        ttl_val = 60
        if cache_domain == "analytics":
            ttl_val = 300
        elif cache_domain == "availability":
            ttl_val = 30
            
        # Do not cache error responses
        is_error = False
        if isinstance(ret_val, str) and ret_val.startswith("Error"):
            is_error = True
        elif isinstance(ret_val, dict) and not ret_val.get("success", True):
            is_error = True
            
        if not is_error:
            get_cache(cache_domain).set(ret_val, "mcp_read", res_lower, oper_lower, key_filters, limit_val, offset_val, metric, group_by, key_ctx, ttl=ttl_val)
    except Exception as e:
        logger.warning(f"MCPRead cache set failed: {e}")

    return ret_val




