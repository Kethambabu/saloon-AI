"""
MCP Query Guard — Prevents dangerous cross-role data access.

The query guard sits between the permissions check and the actual database
query.  While permissions.py grants access at the *resource* level, the
query guard enforces *row-level* safety by:

  1. Blocking explicitly forbidden resource-operation pairs per role.
  2. Injecting mandatory filters so a customer can only see their own rows.
  3. Raising GuardViolationError when a request would expose restricted data.

Forbidden Access Matrix
-----------------------

CUSTOMER must NEVER access:
  - customers table directly
  - all appointments (only own)
  - all reviews (only own)
  - leads (any operation)
  - revenue / analytics resources

STAFF must NEVER access:
  - revenue / analytics resources
  - all customers list
  - all staff roster (may access own staff record)
  - leads (read/write)

ADMIN:
  - No restrictions.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Set

from mcp.schemas import MCPContext, MCPRole

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom Exception
# ---------------------------------------------------------------------------

class GuardViolationError(PermissionError):
    """Raised when a request is blocked by the Query Guard."""

    def __init__(self, message: str, role: str, resource: str, operation: str):
        super().__init__(message)
        self.role = role
        self.resource = resource
        self.operation = operation
        self.error_code = "GUARD_VIOLATION"


# ---------------------------------------------------------------------------
# Forbidden resource sets per role
# ---------------------------------------------------------------------------

#: Resources that CUSTOMER callers can NEVER touch regardless of filters.
_CUSTOMER_FORBIDDEN: Set[str] = {
    "customers",        # Raw customers table — use own profile endpoint instead
    "leads",            # Internal CRM data
    "revenue",          # Business financials
    "analytics",        # Aggregated business metrics
    "staff_schedules",  # Internal scheduling
    "payroll",
}

#: Resources that STAFF callers can NEVER touch.
_STAFF_FORBIDDEN: Set[str] = {
    "revenue",
    "analytics",
    "leads",
    "payroll",
}

#: Read-only resources for STAFF (insert/update/delete blocked).
_STAFF_READONLY: Set[str] = {
    "customers",
    "staff",         # Can view but not modify other staff records
}

#: Resources where CUSTOMER must always have their customer_id injected as filter.
_CUSTOMER_SELF_ONLY: Set[str] = {
    "appointments",
    "reviews",
    "loyalty_points",
    "offers",
}


# ---------------------------------------------------------------------------
# Guard logic
# ---------------------------------------------------------------------------

def validate_and_sanitise(
    context: MCPContext,
    resource: str,
    operation: str,
    filters: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Validate the MCP request against role-based guard rules and return
    a *sanitised* (potentially enriched) filters dict.

    Parameters
    ----------
    context:
        The MCPContext built by context_builder.py.
    resource:
        Resource name (lowercase), e.g. "appointments".
    operation:
        Operation string: "select" | "insert" | "update" | "delete".
    filters:
        The original filters dict from MCPRequest.

    Returns
    -------
    dict
        A (possibly enriched) filters dict that is safe to pass to SQLAlchemy.

    Raises
    ------
    GuardViolationError
        If the request violates a guard rule.
    """
    role: str = context.role if isinstance(context.role, str) else context.role.value
    resource = resource.lower().strip()
    operation = operation.lower().strip()

    # Make a mutable copy so we can inject mandatory filters safely
    safe_filters: Dict[str, Any] = dict(filters)

    # ------------------------------------------------------------------
    # ADMIN — no restrictions
    # ------------------------------------------------------------------
    if role == MCPRole.ADMIN or role == "ADMIN":
        logger.debug("[QueryGuard] ADMIN request — no guard rules applied.")
        return safe_filters

    # ------------------------------------------------------------------
    # CUSTOMER guard rules
    # ------------------------------------------------------------------
    if role == MCPRole.CUSTOMER or role == "CUSTOMER":
        if resource in _CUSTOMER_FORBIDDEN:
            raise GuardViolationError(
                f"CUSTOMER is not permitted to access resource '{resource}'.",
                role=role,
                resource=resource,
                operation=operation,
            )

        # Inject mandatory self-filter for personal resources
        if resource in _CUSTOMER_SELF_ONLY:
            customer_id = context.customer_id
            if not customer_id:
                raise GuardViolationError(
                    f"CUSTOMER context is missing customer_id. Cannot safely filter resource '{resource}'.",
                    role=role,
                    resource=resource,
                    operation=operation,
                )
            # Force-override any supplied customer_id with the authenticated one
            if "customer_id" in safe_filters and safe_filters["customer_id"] != customer_id:
                logger.warning(
                    "[QueryGuard] CUSTOMER tried to query customer_id='%s' "
                    "but their authenticated id is '%s'. Overriding.",
                    safe_filters["customer_id"], customer_id
                )
            safe_filters["customer_id"] = customer_id
            logger.debug(
                "[QueryGuard] CUSTOMER mandatory filter injected: customer_id=%s for resource '%s'.",
                customer_id, resource
            )

        return safe_filters

    # ------------------------------------------------------------------
    # STAFF guard rules
    # ------------------------------------------------------------------
    if role == MCPRole.STAFF or role == "STAFF":
        if resource in _STAFF_FORBIDDEN:
            raise GuardViolationError(
                f"STAFF is not permitted to access resource '{resource}'.",
                role=role,
                resource=resource,
                operation=operation,
            )

        if resource in _STAFF_READONLY and operation in ("insert", "update", "delete"):
            raise GuardViolationError(
                f"STAFF is only allowed read access on resource '{resource}'. "
                f"Operation '{operation}' is forbidden.",
                role=role,
                resource=resource,
                operation=operation,
            )

        # Optionally narrow appointments to own branch
        if resource == "appointments" and context.branch_id:
            if "branch_id" not in safe_filters:
                safe_filters["branch_id"] = context.branch_id
                logger.debug(
                    "[QueryGuard] STAFF branch filter injected: branch_id=%s.",
                    context.branch_id
                )

        return safe_filters

    # ------------------------------------------------------------------
    # Unknown role — deny by default
    # ------------------------------------------------------------------
    raise GuardViolationError(
        f"Unrecognised role '{role}' in query guard. Denying request.",
        role=role,
        resource=resource,
        operation=operation,
    )
