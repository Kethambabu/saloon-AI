"""
MCP Metrics and Cache Management Routes.

Endpoints:
  * GET  /api/v1/agent/mcp-metrics     — Get metrics dashboard and cache statistics
  * POST /api/v1/agent/mcp-cache/clear — Clear the MCP in-memory cache
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import get_current_user
from mcp.metrics import get_metrics_tracker
from mcp.cache import get_cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["mcp_metrics"])


@router.get(
    "/mcp-metrics",
    status_code=status.HTTP_200_OK,
    summary="Get MCP metrics dashboard and cache statistics",
    description="Returns call counts, success/failure rates, average latencies, slow queries, and cache statistics.",
)
async def get_mcp_metrics(current_user=Depends(get_current_user)) -> Dict[str, Any]:
    """Get the latest MCP metrics and cache diagnostics."""
    # Enforce role safety: only admin or managers can view metrics
    from mcp.context_builder import build_context
    ctx = build_context(current_user)
    role_str = ctx.role if isinstance(ctx.role, str) else ctx.role.value
    if role_str not in ("ADMIN", "MANAGER"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Admins or Managers can view MCP performance metrics.",
        )

    tracker = get_metrics_tracker()
    cache = get_cache()

    return {
        "metrics": tracker.get_dashboard(),
        "cache": cache.get_stats(),
    }


@router.post(
    "/mcp-cache/clear",
    status_code=status.HTTP_200_OK,
    summary="Clear the MCP cache",
    description="Flushes all cached entries or a specific resource's cache.",
)
async def clear_mcp_cache(
    resource: str = None,
    current_user=Depends(get_current_user),
) -> Dict[str, Any]:
    """Clears the cache for all or a specific resource."""
    from mcp.context_builder import build_context
    ctx = build_context(current_user)
    role_str = ctx.role if isinstance(ctx.role, str) else ctx.role.value
    if role_str not in ("ADMIN", "MANAGER"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Admins or Managers can clear the cache.",
        )

    cache = get_cache()
    cache.clear(resource)

    return {
        "success": True,
        "message": f"Cache cleared for resource: {resource or 'ALL'}",
    }


# Also support GET request for ease of testing in browser if requested
@router.get(
    "/mcp-cache/clear",
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
async def clear_mcp_cache_get(
    resource: str = None,
    current_user=Depends(get_current_user),
) -> Dict[str, Any]:
    return await clear_mcp_cache(resource, current_user)
