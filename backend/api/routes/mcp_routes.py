"""
MCP Test Routes — Isolated endpoint for testing the MCP layer.

Endpoint:  POST /api/v1/agent/mcp-test

This endpoint exists SOLELY for testing Phase 1 MCP components:
  * Permissions
  * Context building
  * Query guard
  * Audit logging
  * SalonMCP data retrieval

It is NOT used by any agent. Agents continue to use their existing tools.
Remove or restrict this endpoint in production if desired.

Example request body:
    {
        "resource": "appointments",
        "operation": "select",
        "filters": {},
        "limit": 10
    }

Example response:
    {
        "success": true,
        "resource": "appointments",
        "operation": "select",
        "role_used": "CUSTOMER",
        "data": [...],
        "count": 3,
        "permission_granted": true,
        "guard_passed": true,
        "audit_logged": true
    }
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import get_current_user
from mcp.schemas import MCPTestRequest, MCPTestResponse
from mcp.context_builder import build_context
from mcp.permissions import check_permission
from mcp.query_guard import GuardViolationError
from mcp.salon_mcp import SalonMCP
from application.services.audit_service import get_audit_logger

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["mcp"])

# Shared SalonMCP instance (lightweight — no heavy initialisation)
_salon_mcp = SalonMCP()


@router.post(
    "/mcp-test",
    response_model=MCPTestResponse,
    status_code=status.HTTP_200_OK,
    summary="Test the MCP layer (permissions, guard, audit)",
    description=(
        "Send an MCPTestRequest to verify that the MCP permission system, "
        "query guard, and audit logging all work correctly. "
        "The caller's role is derived from their JWT token automatically."
    ),
)
async def mcp_test(
    payload: MCPTestRequest,
    current_user=Depends(get_current_user),
) -> MCPTestResponse:
    """
    MCP test endpoint — calls SalonMCP directly and returns a detailed breakdown
    of what happened (permission check result, guard outcome, data count, etc.).
    """
    t_start = time.perf_counter()

    # Diagnostic/debug endpoint — restrict to privileged roles, consistent with
    # /mcp-metrics and /mcp-cache/clear, rather than exposing raw MCP internals
    # (permission_granted/guard_passed/error_code breakdowns) to any authenticated role.
    role_val = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if role_val not in ("ADMIN", "MANAGER", "OWNER"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Admins, Managers, or Owners can access the MCP test endpoint.",
        )

    # 1. Build MCP context from the authenticated user
    try:
        ctx = build_context(current_user, session_id=None)
    except Exception as exc:
        logger.error("[MCPTest] Failed to build context: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to build MCP context: {exc}",
        )

    role_str: str = ctx.role if isinstance(ctx.role, str) else ctx.role.value

    logger.info(
        "[MCPTest] Incoming test | user=%s role=%s resource=%s operation=%s",
        ctx.user_id, role_str, payload.resource, payload.operation,
    )

    # 2. Check permissions
    permission_granted = check_permission(role_str, payload.resource)
    if not permission_granted:
        audit = get_audit_logger()
        audit.log(
            user_id=ctx.user_id,
            role=role_str,
            resource=payload.resource,
            operation=payload.operation,
            success=False,
            error="PERMISSION_DENIED",
        )
        return MCPTestResponse(
            success=False,
            resource=payload.resource,
            operation=payload.operation,
            role_used=role_str,
            error=f"Role '{role_str}' does not have permission to access '{payload.resource}'.",
            error_code="PERMISSION_DENIED",
            permission_granted=False,
            guard_passed=False,
            audit_logged=True,
        )

    # 3. Route to the appropriate SalonMCP method
    method_map = {
        "appointments":   _salon_mcp.get_appointments,
        "reviews":        _salon_mcp.get_reviews,
        "services":       _salon_mcp.get_services,
        "staff":          _salon_mcp.get_staff,
        "customers":      _salon_mcp.get_customers,
        "leads":          _salon_mcp.get_leads,
        "branches":       _salon_mcp.get_branches,
        "loyalty_points": _salon_mcp.get_loyalty_points,
    }

    mcp_method = method_map.get(payload.resource)
    if not mcp_method:
        return MCPTestResponse(
            success=False,
            resource=payload.resource,
            operation=payload.operation,
            role_used=role_str,
            error=f"Resource '{payload.resource}' is not supported by SalonMCP yet.",
            error_code="UNSUPPORTED_RESOURCE",
            permission_granted=permission_granted,
            guard_passed=False,
            audit_logged=False,
        )

    # 4. Call the MCP method (permissions + guard + query + audit all run inside)
    try:
        mcp_response = mcp_method(
            context=ctx,
            filters=payload.filters,
            limit=payload.limit,
        )
    except GuardViolationError as gve:
        return MCPTestResponse(
            success=False,
            resource=payload.resource,
            operation=payload.operation,
            role_used=role_str,
            error=str(gve),
            error_code="GUARD_VIOLATION",
            permission_granted=permission_granted,
            guard_passed=False,
            audit_logged=True,
        )
    except Exception as exc:
        logger.error("[MCPTest] Unexpected error: %s", exc, exc_info=True)
        return MCPTestResponse(
            success=False,
            resource=payload.resource,
            operation=payload.operation,
            role_used=role_str,
            error=str(exc),
            error_code="INTERNAL_ERROR",
            permission_granted=permission_granted,
            guard_passed=False,
            audit_logged=False,
        )

    elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)
    logger.info(
        "[MCPTest] Completed | success=%s resource=%s count=%s elapsed_ms=%s",
        mcp_response.success, payload.resource, mcp_response.count, elapsed_ms,
    )

    return MCPTestResponse(
        success=mcp_response.success,
        resource=mcp_response.resource,
        operation=mcp_response.operation,
        role_used=role_str,
        data=mcp_response.data,
        count=mcp_response.count,
        error=mcp_response.error,
        error_code=mcp_response.error_code,
        permission_granted=permission_granted,
        guard_passed=mcp_response.success,   # If MCP succeeded, guard was satisfied
        audit_logged=True,                    # Audit always fires inside SalonMCP
    )


# ---------------------------------------------------------------------------
# Info endpoint — list available MCP resources for the calling role
# ---------------------------------------------------------------------------

@router.get(
    "/mcp-info",
    status_code=status.HTTP_200_OK,
    summary="Get MCP capabilities for current role",
    description="Returns the list of resources accessible to the authenticated user's role.",
)
async def mcp_info(current_user=Depends(get_current_user)) -> Dict[str, Any]:
    """
    Diagnostic endpoint: shows what resources the calling role can access,
    along with the current MCP context.
    """
    from mcp.permissions import get_allowed_resources

    role_val = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if role_val not in ("ADMIN", "MANAGER", "OWNER"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Admins, Managers, or Owners can access MCP diagnostic info.",
        )

    ctx = build_context(current_user)
    role_str = ctx.role if isinstance(ctx.role, str) else ctx.role.value
    allowed = get_allowed_resources(role_str)

    return {
        "role": role_str,
        "user_id": ctx.user_id,
        "customer_id": ctx.customer_id,
        "staff_id": ctx.staff_id,
        "branch_id": ctx.branch_id,
        "allowed_resources": sorted(allowed) if isinstance(allowed, set) else allowed,
        "supported_mcp_resources": [
            "appointments", "reviews", "services", "staff",
            "customers", "leads", "branches", "loyalty_points",
        ],
    }

