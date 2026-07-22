"""
MCP Package — SalonAI Workforce MCP Architecture.

This package provides a role-aware Model Context Protocol (MCP) layer
for the SalonAI Workforce Platform.
"""

from mcp.schemas import MCPContext, MCPRequest, MCPResponse, MCPRole
from mcp.salon_mcp import SalonMCP
from mcp.permissions import check_permission, ROLE_PERMISSIONS, get_allowed_resources
from mcp.context_builder import build_context, build_context_from_dict
from mcp.query_guard import validate_and_sanitise, GuardViolationError

# MCP Phase 3 extensions
from mcp.rate_limiter import get_rate_limiter, MCPRateLimiter, RateLimitExceeded
from mcp.cache import get_cache, MCPCache
from mcp.metrics import get_metrics_tracker, MCPMetricsTracker
from mcp.audit_log import get_audit_logger, MCPAuditLogger
from mcp.salon_mcp_write import SalonMCPWrite

__all__ = [
    # Core class
    "SalonMCP",
    "SalonMCPWrite",

    # Schemas
    "MCPContext",
    "MCPRequest",
    "MCPResponse",
    "MCPRole",

    # Permissions
    "check_permission",
    "ROLE_PERMISSIONS",
    "get_allowed_resources",

    # Context
    "build_context",
    "build_context_from_dict",

    # Guard
    "validate_and_sanitise",
    "GuardViolationError",

    # Rate Limiting
    "get_rate_limiter",
    "MCPRateLimiter",
    "RateLimitExceeded",

    # Cache
    "get_cache",
    "MCPCache",

    # Metrics
    "get_metrics_tracker",
    "MCPMetricsTracker",

    # Audit Log
    "get_audit_logger",
    "MCPAuditLogger",
]

