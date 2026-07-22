"""
SalonMCP Core — Role-aware data access layer for SalonAI Workforce Platform.

SalonMCP is the central gatekeeper for all MCP-based database operations.
It enforces the full MCP pipeline:

    1. Rate Limiting check (rate_limiter.py)
    2. Permission check (permissions.py)
    3. Query guard / mandatory filter injection (query_guard.py)
    4. Caching layer lookup (cache.py)
    5. SQLAlchemy database query
    6. Performance metrics collection (metrics.py)
    7. Audit logging (audit_log.py)

Available methods
-----------------
* get_appointments(context, filters, limit, offset, agent_name)
* get_reviews(context, filters, limit, offset, agent_name)
* get_services(context, filters, limit, offset, agent_name)
* get_staff(context, filters, limit, offset, agent_name)
* get_customers(context, filters, limit, offset, agent_name)
* get_leads(context, filters, limit, offset, agent_name)
* get_branches(context, filters, limit, offset, agent_name)
* get_loyalty_points(context, filters, limit, offset, agent_name)
* execute_write(context, resource, operation, data, filters, agent_name)

Each method returns a standardised MCPResponse envelope.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from infrastructure.db.database import SessionLocal
from infrastructure.db import models as M
from mcp.schemas import MCPContext, MCPRequest, MCPResponse
from mcp.permissions import check_permission
from mcp.query_guard import validate_and_sanitise, GuardViolationError

# MCP extensions
from mcp.rate_limiter import get_rate_limiter, RateLimitExceeded
from mcp.cache import get_cache
from mcp.metrics import get_metrics_tracker
from mcp.audit_log import get_audit_logger
from mcp.salon_mcp_write import SalonMCPWrite

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _model_to_dict(obj) -> Dict[str, Any]:
    """Convert a SQLAlchemy ORM row to a plain dict (non-recursive)."""
    result: Dict[str, Any] = {}
    for col in obj.__table__.columns:
        val = getattr(obj, col.name, None)
        if isinstance(val, uuid.UUID):
            val = str(val)
        elif hasattr(val, "isoformat"):    # datetime / date / time
            val = val.isoformat()
        elif hasattr(val, "value"):        # Enum
            val = val.value
        result[col.name] = val
    return result


def _apply_filters(query, model, filters: Dict[str, Any]):
    """Apply key=value filters to a SQLAlchemy query."""
    for key, value in filters.items():
        if hasattr(model, key):
            col = getattr(model, key)
            if isinstance(value, str):
                # Support UUID string comparison
                try:
                    value = uuid.UUID(value)
                except (ValueError, AttributeError):
                    pass
            # Support advanced comparison operators like ge, le, gt, lt
            if isinstance(value, dict) and "op" in value and "value" in value:
                op = value["op"]
                val = value["value"]
                if op == "ge":
                    query = query.filter(col >= val)
                elif op == "le":
                    query = query.filter(col <= val)
                elif op == "gt":
                    query = query.filter(col > val)
                elif op == "lt":
                    query = query.filter(col < val)
            else:
                query = query.filter(col == value)
        else:
            logger.warning("[SalonMCP] Unknown filter key '%s' on model '%s'. Ignoring.", key, model.__tablename__)
    return query


def _build_error_response(resource: str, operation: str, error: str, code: str) -> MCPResponse:
    return MCPResponse(
        success=False,
        resource=resource,
        operation=operation,
        error=error,
        error_code=code,
    )


# ---------------------------------------------------------------------------
# SalonMCP Class
# ---------------------------------------------------------------------------

class SalonMCP:
    """
    MCP data access layer for SalonAI Workforce Platform.

    Usage::

        from mcp.salon_mcp import SalonMCP
        mcp = SalonMCP()
        response = mcp.get_appointments(context=ctx, filters={"customer_id": "..."})
    """

    def _log_audit(
        self,
        context: MCPContext,
        resource: str,
        operation: str,
        success: bool,
        error: Optional[str] = None,
        agent_name: str = "unknown",
    ) -> None:
        """Fire audit log — never raises."""
        try:
            audit = get_audit_logger()
            audit.log_action(
                user_id=context.user_id,
                role=context.role if isinstance(context.role, str) else context.role.value,
                agent_name=agent_name,
                action=operation,
                resource=resource,
                status="SUCCESS" if success else f"FAILED: {error or 'UNKNOWN'}",
            )
        except Exception as exc:
            logger.warning("[SalonMCP] Audit logging failed (non-fatal): %s", exc)

    # ------------------------------------------------------------------
    # Internal query executor
    # ------------------------------------------------------------------

    def _execute(
        self,
        context: MCPContext,
        resource: str,
        operation: str,
        model,
        filters: Dict[str, Any],
        limit: int = 50,
        offset: int = 0,
        agent_name: str = "unknown",
    ) -> MCPResponse:
        """
        Central MCP execution pipeline:
        rate limit → permission → guard → cache → query → metrics → audit.
        """
        t_start = time.perf_counter()
        role_str = context.role if isinstance(context.role, str) else context.role.value

        # 1. Rate Limiting Check
        limiter = get_rate_limiter()
        try:
            limiter.check(context.user_id, role_str)
        except RateLimitExceeded as rle:
            self._log_audit(context, resource, operation, False, "RATE_LIMIT_EXCEEDED", agent_name)
            elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)
            get_metrics_tracker().record(
                resource=resource,
                operation=operation,
                agent_name=agent_name,
                success=False,
                duration_ms=elapsed_ms,
                error_code="RATE_LIMIT_EXCEEDED",
                filters=filters
            )
            return _build_error_response(resource, operation, str(rle), "RATE_LIMIT_EXCEEDED")

        # 2. Permission gate
        if not check_permission(role_str, resource):
            self._log_audit(context, resource, operation, False, "PERMISSION_DENIED", agent_name)
            elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)
            get_metrics_tracker().record(
                resource=resource,
                operation=operation,
                agent_name=agent_name,
                success=False,
                duration_ms=elapsed_ms,
                error_code="PERMISSION_DENIED",
                filters=filters
            )
            return _build_error_response(
                resource, operation,
                f"Role '{role_str}' does not have permission to access resource '{resource}'.",
                "PERMISSION_DENIED",
            )

        # 3. Query guard — may enrich / override filters
        try:
            safe_filters = validate_and_sanitise(context, resource, operation, filters)
        except GuardViolationError as gve:
            self._log_audit(context, resource, operation, False, str(gve), agent_name)
            elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)
            get_metrics_tracker().record(
                resource=resource,
                operation=operation,
                agent_name=agent_name,
                success=False,
                duration_ms=elapsed_ms,
                error_code=gve.error_code,
                filters=filters
            )
            return _build_error_response(resource, operation, str(gve), gve.error_code)

        # 4. Check Cache (only for select operations)
        if operation == "select":
            cache = get_cache()
            cached_data = cache.get(resource, safe_filters, limit, offset)
            if cached_data is not None:
                elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)
                self._log_audit(context, resource, operation, True, agent_name=agent_name)
                get_metrics_tracker().record(
                    resource=resource,
                    operation=operation,
                    agent_name=agent_name,
                    success=True,
                    duration_ms=elapsed_ms,
                    filters=safe_filters
                )
                return MCPResponse(
                    success=True,
                    resource=resource,
                    operation=operation,
                    data=cached_data,
                    count=len(cached_data),
                    metadata={
                        "execution_time_ms": elapsed_ms,
                        "role": role_str,
                        "filters_applied": list(safe_filters.keys()),
                        "limit": limit,
                        "offset": offset,
                        "cache_hit": True,
                    },
                )

        # 5. Database query
        db: Session = SessionLocal()
        try:
            q = db.query(model)
            q = _apply_filters(q, model, safe_filters)

            # Ordering (newest first by default for timestamped models)
            if hasattr(model, "created_at"):
                q = q.order_by(model.created_at.desc())

            rows = q.offset(offset).limit(limit).all()
            data = [_model_to_dict(r) for r in rows]

            if resource.lower() == "appointments":
                for item in data:
                    import uuid
                    if item.get("service_id"):
                        from infrastructure.db.models import Service
                        try:
                            svc_uuid = uuid.UUID(str(item["service_id"]))
                        except Exception:
                            svc_uuid = item["service_id"]
                        svc = db.query(Service).filter(Service.id == svc_uuid).first()
                        if svc:
                            item["service_name"] = svc.name
                    if item.get("staff_id"):
                        from infrastructure.db.models import Staff
                        try:
                            staff_uuid = uuid.UUID(str(item["staff_id"]))
                        except Exception:
                            staff_uuid = item["staff_id"]
                        st = db.query(Staff).filter(Staff.id == staff_uuid).first()
                        if st:
                            item["staff_name"] = st.full_name
                    if item.get("branch_id"):
                        from infrastructure.db.models import Branch
                        try:
                            branch_uuid = uuid.UUID(str(item["branch_id"]))
                        except Exception:
                            branch_uuid = item["branch_id"]
                        br = db.query(Branch).filter(Branch.id == branch_uuid).first()
                        if br:
                            item["branch_name"] = br.name
            elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)

            self._log_audit(context, resource, operation, True, agent_name=agent_name)
            
            # Cache the result
            if operation == "select":
                get_cache().set(resource, safe_filters, data, limit, offset)

            get_metrics_tracker().record(
                resource=resource,
                operation=operation,
                agent_name=agent_name,
                success=True,
                duration_ms=elapsed_ms,
                filters=safe_filters
            )

            return MCPResponse(
                success=True,
                resource=resource,
                operation=operation,
                data=data,
                count=len(data),
                metadata={
                    "execution_time_ms": elapsed_ms,
                    "role": role_str,
                    "filters_applied": list(safe_filters.keys()),
                    "limit": limit,
                    "offset": offset,
                    "cache_hit": False,
                },
            )
        except Exception as exc:
            logger.error("[SalonMCP] DB query failed for resource '%s': %s", resource, exc, exc_info=True)
            self._log_audit(context, resource, operation, False, str(exc), agent_name)
            elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)
            get_metrics_tracker().record(
                resource=resource,
                operation=operation,
                agent_name=agent_name,
                success=False,
                duration_ms=elapsed_ms,
                error_code="DB_ERROR",
                filters=filters
            )
            return _build_error_response(resource, operation, f"Database error: {exc}", "DB_ERROR")
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Public MCP methods
    # ------------------------------------------------------------------

    def get_appointments(
        self,
        context: MCPContext,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 50,
        offset: int = 0,
        agent_name: str = "unknown",
    ) -> MCPResponse:
        return self._execute(
            context, "appointments", "select",
            M.Appointment, filters or {}, limit, offset, agent_name
        )

    def get_reviews(
        self,
        context: MCPContext,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 50,
        offset: int = 0,
        agent_name: str = "unknown",
    ) -> MCPResponse:
        return self._execute(
            context, "reviews", "select",
            M.Review, filters or {}, limit, offset, agent_name
        )

    def get_services(
        self,
        context: MCPContext,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        offset: int = 0,
        agent_name: str = "unknown",
    ) -> MCPResponse:
        effective_filters = {"is_active": True, **(filters or {})}
        return self._execute(
            context, "services", "select",
            M.Service, effective_filters, limit, offset, agent_name
        )

    def get_staff(
        self,
        context: MCPContext,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 50,
        offset: int = 0,
        agent_name: str = "unknown",
    ) -> MCPResponse:
        return self._execute(
            context, "staff", "select",
            M.Staff, filters or {}, limit, offset, agent_name
        )

    def get_customers(
        self,
        context: MCPContext,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 50,
        offset: int = 0,
        agent_name: str = "unknown",
    ) -> MCPResponse:
        return self._execute(
            context, "customers", "select",
            M.Customer, filters or {}, limit, offset, agent_name
        )

    def get_leads(
        self,
        context: MCPContext,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 50,
        offset: int = 0,
        agent_name: str = "unknown",
    ) -> MCPResponse:
        return self._execute(
            context, "leads", "select",
            M.Lead, filters or {}, limit, offset, agent_name
        )

    def get_branches(
        self,
        context: MCPContext,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 50,
        offset: int = 0,
        agent_name: str = "unknown",
    ) -> MCPResponse:
        return self._execute(
            context, "branches", "select",
            M.Branch, filters or {}, limit, offset, agent_name
        )

    def get_loyalty_points(
        self,
        context: MCPContext,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 100,
        offset: int = 0,
        agent_name: str = "unknown",
    ) -> MCPResponse:
        return self._execute(
            context, "loyalty_points", "select",
            M.LoyaltyTransaction, filters or {}, limit, offset, agent_name
        )

    # ------------------------------------------------------------------
    # Write Operation Dispatcher
    # ------------------------------------------------------------------

    def execute_write(
        self,
        context: MCPContext,
        resource: str,
        operation: str,
        data: Optional[Dict[str, Any]] = None,
        filters: Optional[Dict[str, Any]] = None,
        agent_name: str = "unknown",
    ) -> MCPResponse:
        """
        Execute database write operations (insert, update, delete) via MCP.
        """
        # Clear cache for the resource on write to avoid stale cached reads
        get_cache().clear(resource)
        
        writer = SalonMCPWrite()
        return writer.execute_write(context, resource, operation, data, filters, agent_name)

