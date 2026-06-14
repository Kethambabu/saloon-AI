"""
Permission Guard Service for SalonAI Workforce Platform.

Phase 1 Architecture — Workflow-Level Permission Validation.

Validates that the requesting user's role is permitted to invoke a given
workflow action BEFORE any MCP calls or database mutations are made.

Permission Matrix
-----------------
Workflow            CUSTOMER  STAFF  MANAGER  OWNER  ADMIN
appointment_book       ✓        ✓       ✓       ✓      ✓
appointment_cancel     ✓*       ✓       ✓       ✓      ✓   (* own appts only)
appointment_reschedule ✓*       ✓       ✓       ✓      ✓
appointment_check      ✓        ✓       ✓       ✓      ✓
appointment_history    ✓*       ✓       ✓       ✓      ✓
crm_search             ✗        ✗       ✓       ✓      ✓
crm_create_lead        ✗        ✓       ✓       ✓      ✓
crm_advance_lead       ✗        ✓       ✓       ✓      ✓
crm_send_followup      ✗        ✓       ✓       ✓      ✓
crm_analytics          ✗        ✗       ✓       ✓      ✓
recommendation_fetch   ✓        ✓       ✓       ✓      ✓
recommendation_accept  ✓        ✓       ✓       ✓      ✓
recommendation_reject  ✓        ✓       ✓       ✓      ✓
reputation_read        ✓        ✓       ✓       ✓      ✓
reputation_respond     ✗        ✗       ✓       ✓      ✓
reputation_escalate    ✗        ✗       ✓       ✓      ✓
staff_schedule         ✗        ✓       ✓       ✓      ✓
staff_leave            ✗        ✓       ✓       ✓      ✓
staff_reminders        ✗        ✓       ✓       ✓      ✓
analytics_dashboard    ✗        ✗       ✓       ✓      ✓
analytics_revenue      ✗        ✗       ✓       ✓      ✓
analytics_raw_sql      ✗        ✗       ✗       ✓      ✓
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Permission Matrix
# ---------------------------------------------------------------------------

# Roles ordered from most to least privileged
_ALL_ROLES: Set[str] = {"CUSTOMER", "STAFF", "MANAGER", "OWNER", "ADMIN"}

# Map: action_key → set of roles allowed to perform it
_ACTION_PERMISSIONS: Dict[str, Set[str]] = {
    # Chat action (allowed for everyone)
    "chat":                        {"CUSTOMER", "STAFF", "MANAGER", "OWNER", "ADMIN"},

    # Appointment workflow actions
    "appointment_book":            {"CUSTOMER", "STAFF", "MANAGER", "OWNER", "ADMIN"},
    "appointment_cancel":          {"CUSTOMER", "STAFF", "MANAGER", "OWNER", "ADMIN"},
    "appointment_reschedule":      {"CUSTOMER", "STAFF", "MANAGER", "OWNER", "ADMIN"},
    "appointment_check":           {"CUSTOMER", "STAFF", "MANAGER", "OWNER", "ADMIN"},
    "appointment_history":         {"CUSTOMER", "STAFF", "MANAGER", "OWNER", "ADMIN"},
    "appointment_services":        {"CUSTOMER", "STAFF", "MANAGER", "OWNER", "ADMIN"},
    "appointment_staff":           {"CUSTOMER", "STAFF", "MANAGER", "OWNER", "ADMIN"},
    "appointment_search_customer": {"CUSTOMER", "STAFF", "MANAGER", "OWNER", "ADMIN"},

    # CRM workflow actions
    "crm_search":                  {"MANAGER", "OWNER", "ADMIN"},
    "crm_create_lead":             {"STAFF", "MANAGER", "OWNER", "ADMIN"},
    "crm_advance_lead":            {"STAFF", "MANAGER", "OWNER", "ADMIN"},
    "crm_send_followup":           {"STAFF", "MANAGER", "OWNER", "ADMIN"},
    "crm_message":                 {"STAFF", "MANAGER", "OWNER", "ADMIN"},
    "crm_analytics":               {"MANAGER", "OWNER", "ADMIN"},
    "crm_pipeline":                {"MANAGER", "OWNER", "ADMIN"},
    "crm_abandoned":               {"STAFF", "MANAGER", "OWNER", "ADMIN"},

    # Recommendation workflow actions
    "recommendation_fetch":        {"CUSTOMER", "STAFF", "MANAGER", "OWNER", "ADMIN"},
    "recommendation_accept":       {"CUSTOMER", "STAFF", "MANAGER", "OWNER", "ADMIN"},
    "recommendation_reject":       {"CUSTOMER", "STAFF", "MANAGER", "OWNER", "ADMIN"},
    "recommendation_analytics":    {"MANAGER", "OWNER", "ADMIN"},

    # Reputation workflow actions
    "reputation_read":             {"CUSTOMER", "STAFF", "MANAGER", "OWNER", "ADMIN"},
    "reputation_analytics":        {"STAFF", "MANAGER", "OWNER", "ADMIN"},
    "reputation_critical":         {"STAFF", "MANAGER", "OWNER", "ADMIN"},
    "reputation_respond":          {"MANAGER", "OWNER", "ADMIN"},
    "reputation_escalate":         {"MANAGER", "OWNER", "ADMIN"},
    "reputation_scorecard":        {"STAFF", "MANAGER", "OWNER", "ADMIN"},

    # Staff workflow actions
    "staff_schedule":              {"STAFF", "MANAGER", "OWNER", "ADMIN"},
    "staff_today":                 {"STAFF", "MANAGER", "OWNER", "ADMIN"},
    "staff_next_customer":         {"STAFF", "MANAGER", "OWNER", "ADMIN"},
    "staff_customer_history":      {"STAFF", "MANAGER", "OWNER", "ADMIN"},
    "staff_preferences":           {"STAFF", "MANAGER", "OWNER", "ADMIN"},
    "staff_revenue":               {"STAFF", "MANAGER", "OWNER", "ADMIN"},
    "staff_performance":           {"STAFF", "MANAGER", "OWNER", "ADMIN"},
    "staff_pending":               {"STAFF", "MANAGER", "OWNER", "ADMIN"},
    "staff_leave":                 {"STAFF", "MANAGER", "OWNER", "ADMIN"},
    "staff_reminders":             {"STAFF", "MANAGER", "OWNER", "ADMIN"},

    # Analytics workflow actions
    "analytics_dashboard":         {"MANAGER", "OWNER", "ADMIN"},
    "analytics_revenue":           {"MANAGER", "OWNER", "ADMIN"},
    "analytics_customers":         {"MANAGER", "OWNER", "ADMIN"},
    "analytics_staff":             {"MANAGER", "OWNER", "ADMIN"},
    "analytics_leads":             {"MANAGER", "OWNER", "ADMIN"},
    "analytics_reviews":           {"MANAGER", "OWNER", "ADMIN"},
    "analytics_upsell":            {"MANAGER", "OWNER", "ADMIN"},
    "analytics_insights":          {"MANAGER", "OWNER", "ADMIN"},
    "analytics_forecast":          {"MANAGER", "OWNER", "ADMIN"},
    "analytics_context":           {"MANAGER", "OWNER", "ADMIN"},
    "analytics_raw_sql":           {"OWNER", "ADMIN"},
    "analytics_cohort_reminders":  {"MANAGER", "OWNER", "ADMIN"},
}


class PermissionDeniedError(Exception):
    """Raised when a user role is not authorized to invoke a workflow action."""

    def __init__(self, action: str, role: str) -> None:
        self.action = action
        self.role = role
        super().__init__(
            f"Role '{role}' is not permitted to perform action '{action}'."
        )


# ---------------------------------------------------------------------------
# Validation function
# ---------------------------------------------------------------------------

def validate_workflow_permission(
    action: str,
    role: str,
    raise_on_deny: bool = True,
) -> bool:
    """
    Validate that *role* is allowed to invoke *action*.

    Args:
        action:        The workflow action key (e.g. 'appointment_book').
        role:          The user's role string (case-insensitive).
        raise_on_deny: If True, raises PermissionDeniedError on failure.
                       If False, returns False silently.

    Returns:
        True if permitted, False otherwise (only when raise_on_deny=False).

    Raises:
        PermissionDeniedError: When permission is denied and raise_on_deny=True.
    """
    role_upper = (role or "CUSTOMER").upper()
    allowed_roles = _ACTION_PERMISSIONS.get(action, set())

    if role_upper not in _ALL_ROLES:
        logger.warning(
            "[PermissionGuard] Unknown role '%s' — defaulting to CUSTOMER.", role_upper
        )
        role_upper = "CUSTOMER"

    if role_upper in allowed_roles:
        logger.debug(
            "[PermissionGuard] ALLOWED: role=%s action=%s", role_upper, action
        )
        return True

    logger.warning(
        "[PermissionGuard] DENIED: role=%s attempted action='%s'. "
        "Allowed roles: %s",
        role_upper, action, sorted(allowed_roles)
    )

    if raise_on_deny:
        raise PermissionDeniedError(action=action, role=role_upper)
    return False


def get_allowed_actions(role: str) -> List[str]:
    """Return all actions the given role is permitted to invoke."""
    role_upper = (role or "CUSTOMER").upper()
    return sorted(
        action for action, allowed in _ACTION_PERMISSIONS.items()
        if role_upper in allowed
    )


def permission_check(action: str, role: str) -> Dict[str, object]:
    """
    Non-raising permission check that returns a structured result dict.

    Returns:
        {
          "allowed": bool,
          "action": str,
          "role": str,
          "error": str | None,
        }
    """
    allowed = validate_workflow_permission(action, role, raise_on_deny=False)
    return {
        "allowed": allowed,
        "action": action,
        "role": role.upper(),
        "error": None if allowed else f"Role '{role.upper()}' cannot perform '{action}'.",
    }
