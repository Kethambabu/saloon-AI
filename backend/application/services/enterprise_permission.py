"""
Enterprise Permission Model — Phase 2 Architecture.

Extends Phase 1 PermissionGuard with:
  - Resource-level ownership checks (CUSTOMER can only access own appointments)
  - Field-level filtering (hide sensitive fields from lower roles)
  - Plan-level feature gating (per-tenant SaaS plan restrictions)
  - Audit logging for all permission decisions
  - Fine-grained ABAC (Attribute-Based Access Control) policies
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Role Hierarchy
# ---------------------------------------------------------------------------
_ROLE_RANK: Dict[str, int] = {
    "CUSTOMER": 0,
    "STAFF":    1,
    "MANAGER":  2,
    "OWNER":    3,
    "ADMIN":    4,
}


def role_rank(role: str) -> int:
    """Numeric rank of a role — higher = more privileged."""
    return _ROLE_RANK.get(role.upper(), 0)


def has_at_least_role(user_role: str, minimum_role: str) -> bool:
    """Return True if user_role >= minimum_role in the privilege hierarchy."""
    return role_rank(user_role) >= role_rank(minimum_role)


# ---------------------------------------------------------------------------
# Resource Ownership Policy
# ---------------------------------------------------------------------------
class OwnershipPolicy:
    """
    Enforces that CUSTOMER role users can only access their own resources.

    Rules:
      - CUSTOMER can read/write appointments where customer_id == self.customer_id
      - CUSTOMER can read/write reviews where customer_id == self.customer_id
      - CUSTOMER cannot access other customers' data
      - STAFF+ have broader access within their branch
      - MANAGER+ have cross-branch access
      - ADMIN has global access
    """

    @staticmethod
    def validate_customer_resource_access(
        user_role: str,
        user_customer_id: Optional[str],
        resource_customer_id: Optional[str],
    ) -> bool:
        """
        Validate a CUSTOMER-role user is only accessing their own resource.

        Args:
            user_role:            The user's role string.
            user_customer_id:     The authenticated customer's UUID.
            resource_customer_id: The resource's customer_id field.

        Returns:
            True if access is allowed, False otherwise.
        """
        role_upper = (user_role or "CUSTOMER").upper()

        # Staff and above have unrestricted customer resource access
        if role_rank(role_upper) >= role_rank("STAFF"):
            return True

        # Customer role: must own the resource
        if role_upper == "CUSTOMER":
            if not user_customer_id or not resource_customer_id:
                return False
            return str(user_customer_id) == str(resource_customer_id)

        return False

    @staticmethod
    def validate_staff_branch_access(
        user_role: str,
        user_branch_id: Optional[str],
        resource_branch_id: Optional[str],
    ) -> bool:
        """
        Validate a STAFF-role user only accesses data within their branch.

        MANAGER+ have cross-branch access.
        """
        role_upper = (user_role or "CUSTOMER").upper()

        if role_rank(role_upper) >= role_rank("MANAGER"):
            return True  # MANAGER+ cross-branch

        if role_upper == "STAFF":
            if not user_branch_id or not resource_branch_id:
                return True  # No branch restriction if not set
            return str(user_branch_id) == str(resource_branch_id)

        return True  # CUSTOMER role is handled by customer ownership policy


# ---------------------------------------------------------------------------
# Field-Level Security
# ---------------------------------------------------------------------------

# Map: role → set of fields that are HIDDEN from that role
_FIELD_RESTRICTIONS: Dict[str, Set[str]] = {
    "CUSTOMER": {
        "hashed_password", "refresh_token", "cost_price",
        "staff_notes_internal", "lead_score", "admin_comments",
        "followup_count", "last_contacted",
    },
    "STAFF": {
        "hashed_password", "refresh_token", "cost_price",
    },
    "MANAGER": {
        "hashed_password", "refresh_token",
    },
    "OWNER": {
        "hashed_password", "refresh_token",
    },
    "ADMIN": set(),  # Admin sees everything
}


def filter_fields(data: Dict[str, Any], user_role: str) -> Dict[str, Any]:
    """
    Remove fields the user's role is not permitted to see.

    Args:
        data:      The data dict (e.g. customer record, appointment).
        user_role: Role string.

    Returns:
        Filtered dict with restricted fields removed.
    """
    role_upper = (user_role or "CUSTOMER").upper()
    restricted = _FIELD_RESTRICTIONS.get(role_upper, set())
    return {k: v for k, v in data.items() if k not in restricted}


def filter_list_fields(data_list: List[Dict[str, Any]], user_role: str) -> List[Dict[str, Any]]:
    """Apply field filtering to a list of data dicts."""
    return [filter_fields(item, user_role) for item in data_list]


# ---------------------------------------------------------------------------
# Plan-Level Feature Gating
# ---------------------------------------------------------------------------
_PLAN_FEATURES: Dict[str, Set[str]] = {
    "FREE": {
        "chat",
        "appointment_book", "appointment_check", "appointment_cancel",
        "reputation_read",
    },
    "STARTER": {
        "chat",
        "appointment_book", "appointment_check", "appointment_cancel",
        "appointment_reschedule", "reputation_read", "reputation_respond",
        "crm_create_lead", "staff_schedule", "staff_today",
    },
    "GROWTH": {
        "chat",
        "appointment_book", "appointment_check", "appointment_cancel",
        "appointment_reschedule", "appointment_history", "appointment_services",
        "appointment_staff", "appointment_search_customer",
        "crm_create_lead", "crm_advance_lead", "crm_send_followup",
        "crm_message", "crm_abandoned",
        "reputation_read", "reputation_respond", "reputation_escalate",
        "reputation_scorecard", "reputation_analytics", "reputation_critical",
        "recommendation_fetch", "recommendation_accept", "recommendation_reject",
        "staff_schedule", "staff_today", "staff_next_customer",
        "staff_customer_history", "staff_leave", "staff_reminders",
        "analytics_dashboard", "analytics_revenue",
    },
    "ENTERPRISE": set(),  # All features unlocked
}


def validate_plan_feature(tenant_plan: str, feature_action: str) -> bool:
    """
    Validate that the tenant's SaaS plan includes the requested feature.

    Args:
        tenant_plan:    Plan string (FREE | STARTER | GROWTH | ENTERPRISE).
        feature_action: The action key to check.

    Returns:
        True if allowed by plan, False otherwise.
    """
    plan_upper = (tenant_plan or "FREE").upper()

    if plan_upper == "ENTERPRISE":
        return True  # Unlimited

    allowed = _PLAN_FEATURES.get(plan_upper, set())
    is_allowed = feature_action in allowed

    if not is_allowed:
        logger.warning(
            "[EnterprisePermission] Plan %s does not include feature '%s'.",
            plan_upper, feature_action
        )

    return is_allowed


# ---------------------------------------------------------------------------
# Audit Logger
# ---------------------------------------------------------------------------
class PermissionAuditLogger:
    """
    Structured audit logger for permission decisions.
    In production: pipe to SIEM / audit table.
    """

    @staticmethod
    def log_allow(
        user_id: str,
        role: str,
        tenant_id: str,
        action: str,
        resource_id: Optional[str] = None,
    ) -> None:
        logger.info(
            "[AUDIT:ALLOW] user=%s role=%s tenant=%s action=%s resource=%s ts=%s",
            user_id, role, tenant_id, action, resource_id,
            datetime.now(timezone.utc).isoformat(),
        )

    @staticmethod
    def log_deny(
        user_id: str,
        role: str,
        tenant_id: str,
        action: str,
        reason: str,
        resource_id: Optional[str] = None,
    ) -> None:
        logger.warning(
            "[AUDIT:DENY] user=%s role=%s tenant=%s action=%s resource=%s reason=%s ts=%s",
            user_id, role, tenant_id, action, resource_id, reason,
            datetime.now(timezone.utc).isoformat(),
        )


# ---------------------------------------------------------------------------
# Unified Enterprise Permission Check
# ---------------------------------------------------------------------------
audit = PermissionAuditLogger()


def check_enterprise_permission(
    action: str,
    user_role: str,
    user_id: str = "anonymous",
    tenant_id: str = "default",
    tenant_plan: str = "ENTERPRISE",
    resource_customer_id: Optional[str] = None,
    user_customer_id: Optional[str] = None,
    resource_branch_id: Optional[str] = None,
    user_branch_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Full enterprise permission check combining:
      1. Role-based action permission (from permission_guard)
      2. Plan-level feature gating
      3. Resource ownership validation
      4. Audit logging

    Returns:
        {
          "allowed": bool,
          "reason":  str (if denied),
          "action":  str,
          "role":    str,
          "tenant":  str,
        }
    """
    role_upper = (user_role or "CUSTOMER").upper()

    # Step 1: Role-based permission
    try:
        from application.services.permission_guard import validate_workflow_permission
        validate_workflow_permission(action, role_upper)
    except Exception as exc:
        audit.log_deny(user_id, role_upper, tenant_id, action, reason=str(exc))
        return {"allowed": False, "reason": str(exc), "action": action, "role": role_upper, "tenant": tenant_id}

    # Step 2: Plan feature gate
    if not validate_plan_feature(tenant_plan, action):
        reason = f"Plan '{tenant_plan}' does not include '{action}'. Upgrade required."
        audit.log_deny(user_id, role_upper, tenant_id, action, reason=reason)
        return {"allowed": False, "reason": reason, "action": action, "role": role_upper, "tenant": tenant_id}

    # Step 3: Resource ownership (CUSTOMER role only)
    if resource_customer_id and role_upper == "CUSTOMER":
        if not OwnershipPolicy.validate_customer_resource_access(
            role_upper, user_customer_id, resource_customer_id
        ):
            reason = "CUSTOMER role can only access own resources."
            audit.log_deny(user_id, role_upper, tenant_id, action, reason=reason,
                           resource_id=resource_customer_id)
            return {"allowed": False, "reason": reason, "action": action, "role": role_upper, "tenant": tenant_id}

    # Step 4: Branch isolation (STAFF role)
    if resource_branch_id and role_upper == "STAFF":
        if not OwnershipPolicy.validate_staff_branch_access(
            role_upper, user_branch_id, resource_branch_id
        ):
            reason = "STAFF role is restricted to their assigned branch."
            audit.log_deny(user_id, role_upper, tenant_id, action, reason=reason)
            return {"allowed": False, "reason": reason, "action": action, "role": role_upper, "tenant": tenant_id}

    # All checks passed
    audit.log_allow(user_id, role_upper, tenant_id, action)
    return {"allowed": True, "action": action, "role": role_upper, "tenant": tenant_id}

