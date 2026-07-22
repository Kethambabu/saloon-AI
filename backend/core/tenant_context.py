"""
backend/core/tenant_context.py
================================
Multi-tenant context management for SalonAI Phase 2.

Provides:
- :class:`TenantContext` dataclass describing a tenant's plan and features.
- :class:`TenantRegistry` for registering, looking up, and validating tenants.
- :class:`TenantIsolationGuard` for cross-tenant access enforcement.
- :data:`current_tenant_id` :class:`contextvars.ContextVar` for async-safe
  per-request tenant tracking.
- :func:`set_current_tenant` / :func:`get_current_tenant` helpers.

Usage::

    from core.tenant_context import (
        get_tenant_registry,
        set_current_tenant,
        get_current_tenant,
        TenantIsolationGuard,
    )

    registry = get_tenant_registry()
    set_current_tenant("salon_abc")
    ctx = registry.get_tenant("salon_abc")
    guard = TenantIsolationGuard()
    safe_data = guard.enforce_isolation("salon_abc", raw_data)
"""

from __future__ import annotations

import contextvars
import logging
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Plan enumeration
# ---------------------------------------------------------------------------
class Plan(str, Enum):
    """Subscription plan tiers for SalonAI tenants."""

    FREE = "FREE"
    STARTER = "STARTER"
    GROWTH = "GROWTH"
    ENTERPRISE = "ENTERPRISE"


# ---------------------------------------------------------------------------
# TenantContext dataclass
# ---------------------------------------------------------------------------
@dataclass
class TenantContext:
    """Represents a single tenant's runtime configuration.

    Attributes:
        tenant_id:        Unique identifier for this tenant (e.g. ``"salon_abc"``).
        salon_name:       Human-readable name of the salon.
        plan:             Subscription plan – one of the :class:`Plan` values.
        branch_ids:       List of branch identifiers belonging to this tenant.
        features_enabled: List of feature flag strings active for this tenant
                          (e.g. ``["ai_recommendations", "crm"]``).
        rate_limit_rpm:   Maximum API requests per minute allowed for this tenant.
        max_agents:       Maximum number of concurrent AI agent sessions allowed.
    """

    tenant_id: str
    salon_name: str
    plan: Plan = Plan.STARTER
    branch_ids: List[str] = field(default_factory=list)
    features_enabled: List[str] = field(default_factory=list)
    rate_limit_rpm: int = 60
    max_agents: int = 3


# ---------------------------------------------------------------------------
# Plan defaults helper
# ---------------------------------------------------------------------------
_PLAN_DEFAULTS: Dict[Plan, Dict[str, Any]] = {
    Plan.FREE: {
        "features_enabled": ["appointments", "basic_reporting"],
        "rate_limit_rpm": 30,
        "max_agents": 1,
    },
    Plan.STARTER: {
        "features_enabled": ["appointments", "crm", "basic_reporting"],
        "rate_limit_rpm": 60,
        "max_agents": 2,
    },
    Plan.GROWTH: {
        "features_enabled": [
            "appointments",
            "crm",
            "recommendations",
            "reputation",
            "advanced_reporting",
        ],
        "rate_limit_rpm": 120,
        "max_agents": 4,
    },
    Plan.ENTERPRISE: {
        "features_enabled": [
            "appointments",
            "crm",
            "recommendations",
            "reputation",
            "staff_dashboard",
            "analytics",
            "advanced_reporting",
            "raw_sql",
            "ai_insights",
            "multi_branch",
            "white_label",
            "custom_integrations",
        ],
        "rate_limit_rpm": 600,
        "max_agents": 10,
    },
}


def build_tenant_context(
    tenant_id: str,
    salon_name: str,
    plan: Plan,
    branch_ids: Optional[List[str]] = None,
    feature_overrides: Optional[List[str]] = None,
) -> TenantContext:
    """Convenience factory that applies plan defaults.

    Args:
        tenant_id:         Unique tenant identifier.
        salon_name:        Display name of the salon.
        plan:              Subscription plan tier.
        branch_ids:        Optional explicit branch list (defaults to ``[]``).
        feature_overrides: Optional explicit feature list; if provided it
                           replaces the plan defaults.

    Returns:
        A fully configured :class:`TenantContext`.
    """
    defaults = _PLAN_DEFAULTS[plan]
    return TenantContext(
        tenant_id=tenant_id,
        salon_name=salon_name,
        plan=plan,
        branch_ids=branch_ids or [],
        features_enabled=feature_overrides or list(defaults["features_enabled"]),
        rate_limit_rpm=int(defaults["rate_limit_rpm"]),
        max_agents=int(defaults["max_agents"]),
    )


# ---------------------------------------------------------------------------
# TenantRegistry
# ---------------------------------------------------------------------------
class TenantRegistry:
    """Thread-safe registry of active tenant configurations.

    Tenants are keyed by their ``tenant_id`` string.  All public methods are
    safe to call from multiple threads concurrently.
    """

    def __init__(self) -> None:
        self._tenants: Dict[str, TenantContext] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    def register_tenant(self, tenant_context: TenantContext) -> None:
        """Register or update a tenant in the registry.

        Args:
            tenant_context: A fully populated :class:`TenantContext`.

        Example::

            registry.register_tenant(TenantContext(
                tenant_id="salon_abc",
                salon_name="Luxe Salon",
                plan=Plan.GROWTH,
            ))
        """
        with self._lock:
            is_update = tenant_context.tenant_id in self._tenants
            self._tenants[tenant_context.tenant_id] = tenant_context

        action = "Updated" if is_update else "Registered"
        logger.info(
            "[TenantRegistry] %s tenant_id='%s' salon_name='%s' plan='%s' "
            "features=%s rate_limit_rpm=%d max_agents=%d",
            action,
            tenant_context.tenant_id,
            tenant_context.salon_name,
            tenant_context.plan,
            tenant_context.features_enabled,
            tenant_context.rate_limit_rpm,
            tenant_context.max_agents,
        )

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------
    def get_tenant(self, tenant_id: str) -> Optional[TenantContext]:
        """Retrieve a tenant's context by ID.

        Args:
            tenant_id: The tenant identifier to look up.

        Returns:
            :class:`TenantContext` if registered, else ``None``.
        """
        tenant = self._tenants.get(tenant_id)
        if tenant is None:
            logger.warning(
                "[TenantRegistry] get_tenant: tenant_id='%s' not found.", tenant_id
            )
        else:
            logger.debug(
                "[TenantRegistry] get_tenant: tenant_id='%s' found plan='%s'",
                tenant_id,
                tenant.plan,
            )
        return tenant

    # ------------------------------------------------------------------
    # Feature validation
    # ------------------------------------------------------------------
    def validate_feature(self, tenant_id: str, feature: str) -> bool:
        """Check whether *feature* is enabled for *tenant_id*.

        Args:
            tenant_id: The tenant to check.
            feature:   Feature flag string (e.g. ``"ai_insights"``).

        Returns:
            ``True`` if the tenant exists and has the feature enabled,
            ``False`` otherwise.
        """
        tenant = self.get_tenant(tenant_id)
        if tenant is None:
            logger.warning(
                "[TenantRegistry] validate_feature: tenant_id='%s' not found — "
                "feature='%s' denied.",
                tenant_id,
                feature,
            )
            return False
        enabled = feature in tenant.features_enabled
        logger.debug(
            "[TenantRegistry] validate_feature tenant_id='%s' feature='%s' "
            "enabled=%s",
            tenant_id,
            feature,
            enabled,
        )
        return enabled

    # ------------------------------------------------------------------
    # Rate limit
    # ------------------------------------------------------------------
    def get_rate_limit(self, tenant_id: str) -> int:
        """Return the requests-per-minute limit for *tenant_id*.

        Args:
            tenant_id: The tenant to query.

        Returns:
            Integer RPM limit, or ``0`` if the tenant is not registered.
        """
        tenant = self.get_tenant(tenant_id)
        if tenant is None:
            logger.warning(
                "[TenantRegistry] get_rate_limit: tenant_id='%s' not found — "
                "returning 0.",
                tenant_id,
            )
            return 0
        logger.debug(
            "[TenantRegistry] get_rate_limit tenant_id='%s' rpm=%d",
            tenant_id,
            tenant.rate_limit_rpm,
        )
        return tenant.rate_limit_rpm

    # ------------------------------------------------------------------
    # Listing
    # ------------------------------------------------------------------
    def list_tenants(self) -> List[str]:
        """Return a sorted list of all registered tenant IDs.

        Returns:
            Sorted list of tenant ID strings.
        """
        with self._lock:
            ids = sorted(self._tenants.keys())
        logger.debug("[TenantRegistry] list_tenants count=%d", len(ids))
        return ids


# ---------------------------------------------------------------------------
# TenantIsolationGuard
# ---------------------------------------------------------------------------
class TenantIsolationGuard:
    """Enforces strict tenant data isolation.

    Prevents cross-tenant data leakage by validating access and filtering
    collections to a single tenant's data.
    """

    # ------------------------------------------------------------------
    # Access validation
    # ------------------------------------------------------------------
    def validate_tenant_access(
        self, tenant_id: str, resource_tenant_id: str
    ) -> bool:
        """Assert that *tenant_id* is allowed to access resources owned by
        *resource_tenant_id*.

        Args:
            tenant_id:          The requesting tenant's ID.
            resource_tenant_id: The tenant ID embedded in the resource.

        Returns:
            ``True`` if both IDs match.

        Raises:
            PermissionError: If the IDs differ (cross-tenant access attempt).

        Example::

            guard.validate_tenant_access("salon_a", "salon_a")  # OK
            guard.validate_tenant_access("salon_a", "salon_b")  # raises
        """
        if tenant_id == resource_tenant_id:
            logger.debug(
                "[TenantIsolationGuard] Access validated tenant_id='%s'", tenant_id
            )
            return True

        logger.error(
            "[TenantIsolationGuard] CROSS-TENANT ACCESS BLOCKED: "
            "requesting_tenant='%s' resource_tenant='%s'",
            tenant_id,
            resource_tenant_id,
        )
        raise PermissionError(
            f"Cross-tenant access denied: tenant '{tenant_id}' attempted to "
            f"access resources belonging to '{resource_tenant_id}'."
        )

    # ------------------------------------------------------------------
    # Data isolation
    # ------------------------------------------------------------------
    def enforce_isolation(
        self,
        tenant_id: str,
        data_list: List[Any],
        tenant_field: str = "tenant_id",
    ) -> List[Any]:
        """Filter *data_list* to only items owned by *tenant_id*.

        Each item in *data_list* may be a dict or an object with a
        ``tenant_field`` attribute.  Items that do not carry the field are
        excluded and logged.

        Args:
            tenant_id:    The owning tenant whose data to retain.
            data_list:    A list of dicts or objects to filter.
            tenant_field: The field name used to identify the owning tenant
                          (default: ``"tenant_id"``).

        Returns:
            Filtered list containing only items whose *tenant_field* equals
            *tenant_id*.

        Example::

            safe = guard.enforce_isolation("salon_a", raw_records)
        """
        filtered: List[Any] = []
        skipped = 0

        for item in data_list:
            # Support both dict and object access
            if isinstance(item, dict):
                item_tenant = item.get(tenant_field)
            else:
                item_tenant = getattr(item, tenant_field, None)

            if item_tenant is None:
                logger.warning(
                    "[TenantIsolationGuard] enforce_isolation tenant_id='%s': "
                    "item missing field '%s' — excluded.",
                    tenant_id,
                    tenant_field,
                )
                skipped += 1
                continue

            if item_tenant == tenant_id:
                filtered.append(item)
            else:
                logger.debug(
                    "[TenantIsolationGuard] enforce_isolation tenant_id='%s': "
                    "item with %s='%s' excluded.",
                    tenant_id,
                    tenant_field,
                    item_tenant,
                )
                skipped += 1

        logger.info(
            "[TenantIsolationGuard] enforce_isolation tenant_id='%s' "
            "total=%d kept=%d skipped=%d",
            tenant_id,
            len(data_list),
            len(filtered),
            skipped,
        )
        return filtered


# ---------------------------------------------------------------------------
# Async-safe current tenant ContextVar
# ---------------------------------------------------------------------------
current_tenant_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "current_tenant_id", default="default"
)
"""Async-safe :class:`contextvars.ContextVar` holding the current request's
tenant ID.  Each coroutine/thread inherits its own copy via Python's
context variable system.

Default value is ``"default"`` (the pre-registered enterprise tenant).
"""


def set_current_tenant(tenant_id: str) -> contextvars.Token:
    """Set the current tenant ID for the active async context.

    Args:
        tenant_id: The tenant ID to activate.

    Returns:
        A :class:`contextvars.Token` that can be used to restore the
        previous value via :meth:`contextvars.ContextVar.reset`.

    Example::

        token = set_current_tenant("salon_abc")
        # ... do work ...
        current_tenant_id.reset(token)
    """
    token = current_tenant_id.set(tenant_id)
    logger.debug(
        "[TenantContext] set_current_tenant tenant_id='%s'", tenant_id
    )
    return token


def get_current_tenant() -> str:
    """Return the current tenant ID from the active async context.

    Returns:
        The tenant ID string, or ``"default"`` if not set.

    Example::

        tid = get_current_tenant()
    """
    tid = current_tenant_id.get()
    logger.debug("[TenantContext] get_current_tenant -> '%s'", tid)
    return tid


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------
_tenant_registry_instance: Optional[TenantRegistry] = None
_tenant_registry_lock = threading.Lock()


def get_tenant_registry() -> TenantRegistry:
    """Return the process-wide singleton :class:`TenantRegistry`.

    On first call a ``"default"`` tenant is pre-registered with the
    ENTERPRISE plan and all features enabled.  This ensures that code which
    does not explicitly set a tenant still works correctly.

    Returns:
        The global :class:`TenantRegistry` instance.

    Example::

        registry = get_tenant_registry()
        registry.register_tenant(TenantContext(
            tenant_id="salon_xyz",
            salon_name="XYZ Salon",
            plan=Plan.GROWTH,
        ))
    """
    global _tenant_registry_instance  # pylint: disable=global-statement
    if _tenant_registry_instance is None:
        with _tenant_registry_lock:
            if _tenant_registry_instance is None:
                reg = TenantRegistry()
                # Pre-register the default tenant with ENTERPRISE plan
                default_tenant = build_tenant_context(
                    tenant_id="default",
                    salon_name="Default Salon (Development)",
                    plan=Plan.ENTERPRISE,
                    branch_ids=["branch_001"],
                )
                reg.register_tenant(default_tenant)
                _tenant_registry_instance = reg
                logger.info(
                    "[TenantRegistry] Singleton created; 'default' tenant "
                    "pre-registered with ENTERPRISE plan."
                )
    return _tenant_registry_instance

