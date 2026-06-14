"""
MCP Context Builder — Constructs role-aware MCPContext from authenticated users.

Every incoming MCP request passes through build_context() which reads the
FastAPI-resolved current_user object and produces a typed MCPContext that
the rest of the MCP stack relies on.

Context shapes by role
----------------------

CUSTOMER
    {
        "user_id":    "...",
        "role":       "CUSTOMER",
        "customer_id":"...",
        "staff_id":   None,
        "branch_id":  None
    }

STAFF
    {
        "user_id":  "...",
        "role":     "STAFF",
        "staff_id": "...",
        "branch_id":"...",
        "customer_id": None
    }

ADMIN
    {
        "user_id": "...",
        "role":    "ADMIN",
        "customer_id": None,
        "staff_id":    None,
        "branch_id":   None
    }
"""

from __future__ import annotations

import logging
from typing import Optional

from mcp.schemas import MCPContext, MCPRole

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------------

def build_context(
    current_user,
    session_id: Optional[str] = None,
) -> MCPContext:
    """
    Build an MCPContext from the resolved FastAPI current_user dependency.

    Parameters
    ----------
    current_user:
        The User ORM object (or any object with .id, .role, .customer_id,
        .staff_id attributes) produced by api/deps.py get_current_user().
    session_id:
        Optional conversation/session identifier forwarded from the request.

    Returns
    -------
    MCPContext
        Fully populated, role-keyed context object.
    """
    # Normalise role — supports both string and Enum-backed role attributes
    raw_role = current_user.role
    if hasattr(raw_role, "value"):
        raw_role = raw_role.value          # e.g. <UserRole.CUSTOMER: 'CUSTOMER'>
    role_str = str(raw_role).upper().strip()

    # Validate role against known MCPRoles; fall back to CUSTOMER if unknown
    try:
        role = MCPRole(role_str)
    except ValueError:
        logger.warning(
            "[ContextBuilder] Unknown role '%s' for user '%s'. "
            "Defaulting to CUSTOMER context.",
            role_str, current_user.id
        )
        role = MCPRole.CUSTOMER

    # Resolve optional linked profile ids
    customer_id: Optional[str] = None
    staff_id: Optional[str] = None
    branch_id: Optional[str] = None

    if role == MCPRole.CUSTOMER:
        # Prefer explicit customer_id attribute, fall back to nested .customer.id
        customer_id = (
            str(current_user.customer_id)
            if getattr(current_user, "customer_id", None)
            else (
                str(current_user.customer.id)
                if getattr(current_user, "customer", None)
                else None
            )
        )

    elif role == MCPRole.STAFF:
        staff_id = (
            str(current_user.staff_id)
            if getattr(current_user, "staff_id", None)
            else (
                str(current_user.staff.id)
                if getattr(current_user, "staff", None)
                else None
            )
        )
        branch_id = (
            str(current_user.staff.branch_id)
            if getattr(current_user, "staff", None)
            and getattr(current_user.staff, "branch_id", None)
            else None
        )

    # ADMIN gets no linked profile by design

    ctx = MCPContext(
        user_id=str(current_user.id),
        role=role,
        customer_id=customer_id,
        staff_id=staff_id,
        branch_id=branch_id,
        session_id=session_id,
    )

    logger.debug(
        "[ContextBuilder] Built MCPContext → user_id=%s role=%s customer_id=%s staff_id=%s branch_id=%s",
        ctx.user_id, ctx.role, ctx.customer_id, ctx.staff_id, ctx.branch_id
    )
    return ctx


# ---------------------------------------------------------------------------
# Convenience: build from plain dict (useful for testing / internal calls)
# ---------------------------------------------------------------------------

def build_context_from_dict(data: dict, session_id: Optional[str] = None) -> MCPContext:
    """
    Build an MCPContext from a plain dict.

    Expected keys: user_id (str), role (str), and optionally customer_id,
    staff_id, branch_id.

    This is useful when writing unit tests or calling SalonMCP from scheduled
    jobs where there is no FastAPI request context.
    """
    role_str = str(data.get("role", "CUSTOMER")).upper()
    try:
        role = MCPRole(role_str)
    except ValueError:
        role = MCPRole.CUSTOMER

    return MCPContext(
        user_id=str(data.get("user_id", "system")),
        role=role,
        customer_id=str(data["customer_id"]) if data.get("customer_id") else None,
        staff_id=str(data["staff_id"]) if data.get("staff_id") else None,
        branch_id=str(data["branch_id"]) if data.get("branch_id") else None,
        session_id=session_id,
    )
