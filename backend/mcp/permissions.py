"""
MCP Permissions Layer — Role-based access control for SalonMCP.

ROLE_PERMISSIONS defines which resources each role may access.
check_permission() is the single gate called by SalonMCP before executing
any database operation.

Design principles
-----------------
* ADMIN is a wildcard — can access everything.
* STAFF has internal visibility (appointments, staff, services, branches,
  reviews) but NOT revenue/analytics or the full customer / all-staff roster.
* CUSTOMER has self-service access only (own appointments, reviews, loyalty,
  services catalogue, branches, offers, knowledge base).
* Permissions are additive and resource-level.  Fine-grained row filtering
  is handled by query_guard.py.
"""

from __future__ import annotations

import logging
from typing import Dict, FrozenSet, Set, Union

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Permission Registry
# ---------------------------------------------------------------------------

# The special sentinel "*" means "all resources" (ADMIN only).
_WILDCARD = "*"

#: Mapping of role → set of permitted resource names.
#: Keep resource names lowercase and consistent with MCPRequest.resource values.
ROLE_PERMISSIONS: Dict[str, Union[FrozenSet[str], str]] = {
    "CUSTOMER": frozenset({
        "appointments",
        "reviews",
        "loyalty_points",
        "services",
        "branches",
        "offers",
        "knowledge",
    }),
    "STAFF": frozenset({
        "appointments",
        "staff",
        "reviews",
        "services",
        "branches",
    }),
    "ADMIN": _WILDCARD,   # Admin may access any resource
}

# ---------------------------------------------------------------------------
# Public helper
# ---------------------------------------------------------------------------

def check_permission(role: str, resource: str) -> bool:
    """
    Return True if *role* is allowed to access *resource*.

    Parameters
    ----------
    role:
        Caller role string — "CUSTOMER", "STAFF", or "ADMIN".
    resource:
        The resource name from MCPRequest.resource (e.g. "appointments").

    Returns
    -------
    bool
        True  → access granted.
        False → access denied.
    """
    role = (role or "").upper().strip()
    resource = (resource or "").lower().strip()

    allowed = ROLE_PERMISSIONS.get(role)

    if allowed is None:
        logger.warning(
            "[Permissions] Unknown role '%s' attempted to access resource '%s'. "
            "Denying by default.",
            role, resource
        )
        return False

    if allowed == _WILDCARD:
        logger.debug("[Permissions] ADMIN wildcard granted for resource '%s'.", resource)
        return True

    granted = resource in allowed
    if granted:
        logger.debug(
            "[Permissions] Role '%s' granted access to resource '%s'.",
            role, resource
        )
    else:
        logger.warning(
            "[Permissions] Role '%s' DENIED access to resource '%s'.",
            role, resource
        )
    return granted


def get_allowed_resources(role: str) -> Union[Set[str], str]:
    """
    Return the set of resources permitted for *role*, or '*' for ADMIN.

    Useful for documentation / diagnostics endpoints.
    """
    role = (role or "").upper().strip()
    allowed = ROLE_PERMISSIONS.get(role, frozenset())
    return allowed if isinstance(allowed, str) else set(allowed)
