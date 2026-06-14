"""
backend/core/capability_registry.py
=====================================
Capability Registry for SalonAI Phase 2.

Maps agent capabilities to handler class paths, allowed roles, and
associated workflows.  Pre-registers all six SalonAI agents (Clara, Mia,
Max, Olivia, Atlas-Staff, Atlas-BI) with their full action catalogs.

Usage::

    from backend.core.capability_registry import get_registry

    registry = get_registry()
    cap = registry.get("book_appointment")
    caps = registry.list_for_role("receptionist")
    cap = registry.resolve_capability("clara", "book_appointment")
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Capability dataclass
# ---------------------------------------------------------------------------
@dataclass
class Capability:
    """Describes a single registerable agent capability.

    Attributes:
        name:                Unique capability key (e.g. ``"book_appointment"``).
        description:         Human-readable summary of what this capability does.
        handler_class_path:  Dot-separated import path to the handler class
                             (e.g. ``"backend.handlers.appointment_handlers.BookAppointmentHandler"``).
        action_keys:         List of action strings that resolve to this capability.
        roles_allowed:       List of IAM role strings permitted to invoke this capability.
        workflow:            Name of the workflow this capability belongs to
                             (e.g. ``"appointment_workflow"``).
    """

    name: str
    description: str
    handler_class_path: str
    action_keys: List[str] = field(default_factory=list)
    roles_allowed: List[str] = field(default_factory=list)
    workflow: str = field(default="")


# ---------------------------------------------------------------------------
# CapabilityRegistry
# ---------------------------------------------------------------------------
class CapabilityRegistry:
    """Thread-safe registry of agent capabilities.

    Capabilities are keyed by their ``name`` attribute.  The registry
    supports lookup by name, role, and workflow, as well as a higher-level
    ``resolve_capability`` that accepts an agent display name and an action
    key string.
    """

    def __init__(self) -> None:
        self._capabilities: Dict[str, Capability] = {}
        # agent_name (lower) -> workflow name
        self._agent_workflow_map: Dict[str, str] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    def register(self, capability: Capability) -> None:
        """Add *capability* to the registry.

        If a capability with the same name already exists it is overwritten
        and a warning is emitted.

        Args:
            capability: A fully populated :class:`Capability` instance.
        """
        with self._lock:
            if capability.name in self._capabilities:
                logger.warning(
                    "[CapabilityRegistry] Overwriting existing capability name='%s' "
                    "workflow='%s'",
                    capability.name,
                    capability.workflow,
                )
            self._capabilities[capability.name] = capability
        logger.debug(
            "[CapabilityRegistry] Registered capability name='%s' workflow='%s' "
            "roles=%s actions=%s",
            capability.name,
            capability.workflow,
            capability.roles_allowed,
            capability.action_keys,
        )

    def _register_agent_workflow(self, agent_name: str, workflow: str) -> None:
        """Internal helper to map an agent display name to a workflow."""
        with self._lock:
            self._agent_workflow_map[agent_name.lower()] = workflow

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------
    def get(self, capability_name: str) -> Optional[Capability]:
        """Retrieve a capability by its unique name.

        Args:
            capability_name: The ``name`` field of the desired capability.

        Returns:
            :class:`Capability` if found, else ``None``.
        """
        cap = self._capabilities.get(capability_name)
        if cap is None:
            logger.warning(
                "[CapabilityRegistry] Capability not found: name='%s'",
                capability_name,
            )
        return cap

    def list_for_role(self, role: str) -> List[Capability]:
        """Return all capabilities that permit *role*.

        Args:
            role: IAM role string (e.g. ``"receptionist"``).

        Returns:
            List of :class:`Capability` objects whose ``roles_allowed``
            includes *role*.
        """
        with self._lock:
            caps = [
                c for c in self._capabilities.values() if role in c.roles_allowed
            ]
        logger.debug(
            "[CapabilityRegistry] list_for_role role='%s' count=%d", role, len(caps)
        )
        return caps

    def list_for_workflow(self, workflow: str) -> List[Capability]:
        """Return all capabilities belonging to *workflow*.

        Args:
            workflow: Workflow name string (e.g. ``"appointment_workflow"``).

        Returns:
            List of matching :class:`Capability` objects.
        """
        with self._lock:
            caps = [
                c for c in self._capabilities.values() if c.workflow == workflow
            ]
        logger.debug(
            "[CapabilityRegistry] list_for_workflow workflow='%s' count=%d",
            workflow,
            len(caps),
        )
        return caps

    def all_names(self) -> List[str]:
        """Return all registered capability names.

        Returns:
            Sorted list of name strings.
        """
        with self._lock:
            names = sorted(self._capabilities.keys())
        logger.debug("[CapabilityRegistry] all_names count=%d", len(names))
        return names

    # ------------------------------------------------------------------
    # High-level resolution
    # ------------------------------------------------------------------
    def resolve_capability(
        self, agent_name: str, action: str
    ) -> Optional[Capability]:
        """Resolve a capability by agent display name and action key.

        First the agent name is mapped to its workflow; then every
        capability in that workflow is searched for one whose
        ``action_keys`` list contains *action*.

        Args:
            agent_name: Agent display name (case-insensitive, e.g. ``"Clara"``).
            action:     Action key string (e.g. ``"book_appointment"``).

        Returns:
            Matching :class:`Capability` or ``None`` if not found.
        """
        with self._lock:
            workflow = self._agent_workflow_map.get(agent_name.lower())
        if workflow is None:
            logger.warning(
                "[CapabilityRegistry] resolve_capability: unknown agent_name='%s'",
                agent_name,
            )
            return None

        with self._lock:
            for cap in self._capabilities.values():
                if cap.workflow == workflow and action in cap.action_keys:
                    logger.debug(
                        "[CapabilityRegistry] Resolved agent='%s' action='%s' -> "
                        "capability='%s' workflow='%s'",
                        agent_name,
                        action,
                        cap.name,
                        workflow,
                    )
                    return cap

        logger.warning(
            "[CapabilityRegistry] resolve_capability: no capability for "
            "agent='%s' action='%s' workflow='%s'",
            agent_name,
            action,
            workflow,
        )
        return None


# ---------------------------------------------------------------------------
# Pre-registered capabilities
# ---------------------------------------------------------------------------

_CLARA_ROLES = ["receptionist", "admin", "owner"]
_MIA_ROLES = ["receptionist", "admin", "owner", "sales"]
_MAX_ROLES = ["receptionist", "admin", "owner", "staff"]
_OLIVIA_ROLES = ["admin", "owner", "manager"]
_ATLAS_STAFF_ROLES = ["staff", "admin", "owner"]
_ATLAS_BI_ROLES = ["admin", "owner", "analyst"]

_DEFAULT_CAPABILITIES: List[Capability] = [
    # ------------------------------------------------------------------ Clara
    Capability(
        name="check_availability",
        description="Check staff/slot availability for a given time window.",
        handler_class_path="backend.handlers.appointment_handlers.CheckAvailabilityHandler",
        action_keys=["check_availability", "availability"],
        roles_allowed=_CLARA_ROLES,
        workflow="appointment_workflow",
    ),
    Capability(
        name="book_appointment",
        description="Book a new appointment for a customer.",
        handler_class_path="backend.handlers.appointment_handlers.BookAppointmentHandler",
        action_keys=["book_appointment", "book"],
        roles_allowed=_CLARA_ROLES,
        workflow="appointment_workflow",
    ),
    Capability(
        name="cancel_appointment",
        description="Cancel an existing appointment.",
        handler_class_path="backend.handlers.appointment_handlers.CancelAppointmentHandler",
        action_keys=["cancel_appointment", "cancel"],
        roles_allowed=_CLARA_ROLES,
        workflow="appointment_workflow",
    ),
    Capability(
        name="reschedule_appointment",
        description="Move an existing appointment to a new time slot.",
        handler_class_path="backend.handlers.appointment_handlers.RescheduleAppointmentHandler",
        action_keys=["reschedule_appointment", "reschedule"],
        roles_allowed=_CLARA_ROLES,
        workflow="appointment_workflow",
    ),
    Capability(
        name="list_appointments",
        description="List appointments for a customer or staff member.",
        handler_class_path="backend.handlers.appointment_handlers.ListAppointmentsHandler",
        action_keys=["list_appointments", "history"],
        roles_allowed=_CLARA_ROLES,
        workflow="appointment_workflow",
    ),
    Capability(
        name="list_services",
        description="Retrieve the salon's service catalogue.",
        handler_class_path="backend.handlers.appointment_handlers.ListServicesHandler",
        action_keys=["list_services", "services"],
        roles_allowed=_CLARA_ROLES,
        workflow="appointment_workflow",
    ),
    Capability(
        name="list_staff",
        description="Retrieve available staff members.",
        handler_class_path="backend.handlers.appointment_handlers.ListStaffHandler",
        action_keys=["list_staff", "staff"],
        roles_allowed=_CLARA_ROLES,
        workflow="appointment_workflow",
    ),
    Capability(
        name="search_customers",
        description="Search for customers by name, phone, or email.",
        handler_class_path="backend.handlers.appointment_handlers.SearchCustomersHandler",
        action_keys=["search_customers", "find_customer"],
        roles_allowed=_CLARA_ROLES,
        workflow="appointment_workflow",
    ),
    # ------------------------------------------------------------------ Mia
    Capability(
        name="search_leads",
        description="Search CRM leads by various criteria.",
        handler_class_path="backend.handlers.crm_handlers.SearchLeadsHandler",
        action_keys=["search_leads"],
        roles_allowed=_MIA_ROLES,
        workflow="crm_workflow",
    ),
    Capability(
        name="create_lead",
        description="Create a new lead record in the CRM.",
        handler_class_path="backend.handlers.crm_handlers.CreateLeadHandler",
        action_keys=["create_lead"],
        roles_allowed=_MIA_ROLES,
        workflow="crm_workflow",
    ),
    Capability(
        name="advance_lead",
        description="Advance a lead to the next pipeline stage.",
        handler_class_path="backend.handlers.crm_handlers.AdvanceLeadHandler",
        action_keys=["advance_lead"],
        roles_allowed=_MIA_ROLES,
        workflow="crm_workflow",
    ),
    Capability(
        name="send_followup",
        description="Send a follow-up message to a lead.",
        handler_class_path="backend.handlers.crm_handlers.SendFollowupHandler",
        action_keys=["send_followup"],
        roles_allowed=_MIA_ROLES,
        workflow="crm_workflow",
    ),
    Capability(
        name="generate_message",
        description="AI-generate a personalised outreach message for a lead.",
        handler_class_path="backend.handlers.crm_handlers.GenerateMessageHandler",
        action_keys=["generate_message"],
        roles_allowed=_MIA_ROLES,
        workflow="crm_workflow",
    ),
    Capability(
        name="detect_abandoned",
        description="Detect customers who started booking but did not complete.",
        handler_class_path="backend.handlers.crm_handlers.DetectAbandonedHandler",
        action_keys=["detect_abandoned", "abandoned_bookings"],
        roles_allowed=_MIA_ROLES,
        workflow="crm_workflow",
    ),
    Capability(
        name="conversion_analytics",
        description="Return lead-to-customer conversion metrics.",
        handler_class_path="backend.handlers.crm_handlers.ConversionAnalyticsHandler",
        action_keys=["conversion_analytics"],
        roles_allowed=_MIA_ROLES,
        workflow="crm_workflow",
    ),
    Capability(
        name="pipeline_snapshot",
        description="Return a snapshot of the current CRM pipeline.",
        handler_class_path="backend.handlers.crm_handlers.PipelineSnapshotHandler",
        action_keys=["pipeline_snapshot"],
        roles_allowed=_MIA_ROLES,
        workflow="crm_workflow",
    ),
    # ------------------------------------------------------------------ Max
    Capability(
        name="get_recommendations",
        description="Retrieve AI-generated upsell/cross-sell recommendations.",
        handler_class_path="backend.handlers.recommendation_handlers.GetRecommendationsHandler",
        action_keys=["get_recommendations"],
        roles_allowed=_MAX_ROLES,
        workflow="recommendation_workflow",
    ),
    Capability(
        name="accept_recommendation",
        description="Record that a recommendation was accepted.",
        handler_class_path="backend.handlers.recommendation_handlers.AcceptRecommendationHandler",
        action_keys=["accept_recommendation", "accept"],
        roles_allowed=_MAX_ROLES,
        workflow="recommendation_workflow",
    ),
    Capability(
        name="reject_recommendation",
        description="Record that a recommendation was rejected.",
        handler_class_path="backend.handlers.recommendation_handlers.RejectRecommendationHandler",
        action_keys=["reject_recommendation", "reject"],
        roles_allowed=_MAX_ROLES,
        workflow="recommendation_workflow",
    ),
    Capability(
        name="recommendation_analytics",
        description="Analytics on recommendation acceptance/rejection rates.",
        handler_class_path="backend.handlers.recommendation_handlers.RecommendationAnalyticsHandler",
        action_keys=["recommendation_analytics"],
        roles_allowed=_MAX_ROLES,
        workflow="recommendation_workflow",
    ),
    # ---------------------------------------------------------------- Olivia
    Capability(
        name="get_reviews",
        description="Fetch reviews from all connected platforms.",
        handler_class_path="backend.handlers.reputation_handlers.GetReviewsHandler",
        action_keys=["get_reviews"],
        roles_allowed=_OLIVIA_ROLES,
        workflow="reputation_workflow",
    ),
    Capability(
        name="review_analytics",
        description="Aggregate review score analytics over a time range.",
        handler_class_path="backend.handlers.reputation_handlers.ReputationAnalyticsHandler",
        action_keys=["review_analytics", "analytics"],
        roles_allowed=_OLIVIA_ROLES,
        workflow="reputation_workflow",
    ),
    Capability(
        name="critical_reviews",
        description="Surface low-score reviews that require urgent attention.",
        handler_class_path="backend.handlers.reputation_handlers.CriticalReviewsHandler",
        action_keys=["critical_reviews", "critical"],
        roles_allowed=_OLIVIA_ROLES,
        workflow="reputation_workflow",
    ),
    Capability(
        name="draft_response",
        description="AI-draft a response to a specific review.",
        handler_class_path="backend.handlers.reputation_handlers.DraftResponseHandler",
        action_keys=["draft_response", "respond"],
        roles_allowed=_OLIVIA_ROLES,
        workflow="reputation_workflow",
    ),
    Capability(
        name="reputation_scorecard",
        description="Compute an overall reputation scorecard for the salon.",
        handler_class_path="backend.handlers.reputation_handlers.ReputationScorecardHandler",
        action_keys=["reputation_scorecard", "scorecard"],
        roles_allowed=_OLIVIA_ROLES,
        workflow="reputation_workflow",
    ),
    Capability(
        name="escalate_review",
        description="Escalate a negative review to management.",
        handler_class_path="backend.handlers.reputation_handlers.EscalateReviewHandler",
        action_keys=["escalate_review", "escalate"],
        roles_allowed=_OLIVIA_ROLES,
        workflow="reputation_workflow",
    ),
    # ------------------------------------------------------------- Atlas Staff
    Capability(
        name="get_schedule",
        description="Retrieve a staff member's full schedule.",
        handler_class_path="backend.handlers.staff_handlers.GetScheduleHandler",
        action_keys=["get_schedule"],
        roles_allowed=_ATLAS_STAFF_ROLES,
        workflow="staff_workflow",
    ),
    Capability(
        name="today_schedule",
        description="Get today's appointments for a staff member.",
        handler_class_path="backend.handlers.staff_handlers.TodayScheduleHandler",
        action_keys=["today_schedule"],
        roles_allowed=_ATLAS_STAFF_ROLES,
        workflow="staff_workflow",
    ),
    Capability(
        name="next_customer",
        description="Return details about the next upcoming customer.",
        handler_class_path="backend.handlers.staff_handlers.NextCustomerHandler",
        action_keys=["next_customer"],
        roles_allowed=_ATLAS_STAFF_ROLES,
        workflow="staff_workflow",
    ),
    Capability(
        name="customer_history",
        description="Retrieve visit and service history for a customer.",
        handler_class_path="backend.handlers.staff_handlers.CustomerHistoryHandler",
        action_keys=["customer_history"],
        roles_allowed=_ATLAS_STAFF_ROLES,
        workflow="staff_workflow",
    ),
    Capability(
        name="customer_preferences",
        description="Retrieve stored preferences for a customer.",
        handler_class_path="backend.handlers.staff_handlers.CustomerPreferencesHandler",
        action_keys=["customer_preferences"],
        roles_allowed=_ATLAS_STAFF_ROLES,
        workflow="staff_workflow",
    ),
    Capability(
        name="staff_revenue",
        description="Revenue generated by a staff member over a period.",
        handler_class_path="backend.handlers.staff_handlers.StaffRevenueHandler",
        action_keys=["staff_revenue"],
        roles_allowed=_ATLAS_STAFF_ROLES,
        workflow="staff_workflow",
    ),
    Capability(
        name="staff_performance",
        description="KPIs and performance metrics for a staff member.",
        handler_class_path="backend.handlers.staff_handlers.StaffKPIHandler",
        action_keys=["staff_performance"],
        roles_allowed=_ATLAS_STAFF_ROLES,
        workflow="staff_workflow",
    ),
    Capability(
        name="pending_appointments",
        description="List appointments awaiting staff confirmation.",
        handler_class_path="backend.handlers.staff_handlers.PendingAppointmentsHandler",
        action_keys=["pending_appointments"],
        roles_allowed=_ATLAS_STAFF_ROLES,
        workflow="staff_workflow",
    ),
    Capability(
        name="create_leave",
        description="Create a leave or time-off request for a staff member.",
        handler_class_path="backend.handlers.staff_handlers.CreateLeaveHandler",
        action_keys=["create_leave"],
        roles_allowed=_ATLAS_STAFF_ROLES,
        workflow="staff_workflow",
    ),
    Capability(
        name="send_reminders",
        description="Send appointment reminder messages to customers.",
        handler_class_path="backend.handlers.staff_handlers.SendRemindersHandler",
        action_keys=["send_reminders"],
        roles_allowed=_ATLAS_STAFF_ROLES,
        workflow="staff_workflow",
    ),
    # -------------------------------------------------------------- Atlas BI
    Capability(
        name="dashboard",
        description="Return the main BI dashboard summary.",
        handler_class_path="backend.handlers.analytics_handlers.DashboardHandler",
        action_keys=["dashboard"],
        roles_allowed=_ATLAS_BI_ROLES,
        workflow="analytics_workflow",
    ),
    Capability(
        name="revenue",
        description="Revenue analytics broken down by period, service, or staff.",
        handler_class_path="backend.handlers.analytics_handlers.RevenueHandler",
        action_keys=["revenue"],
        roles_allowed=_ATLAS_BI_ROLES,
        workflow="analytics_workflow",
    ),
    Capability(
        name="customers",
        description="Customer metrics including retention and churn.",
        handler_class_path="backend.handlers.analytics_handlers.CustomerMetricsHandler",
        action_keys=["customers"],
        roles_allowed=_ATLAS_BI_ROLES,
        workflow="analytics_workflow",
    ),
    Capability(
        name="staff_analytics",
        description="Staff performance analytics across the salon.",
        handler_class_path="backend.handlers.analytics_handlers.StaffPerformanceHandler",
        action_keys=["staff_analytics", "staff"],
        roles_allowed=_ATLAS_BI_ROLES,
        workflow="analytics_workflow",
    ),
    Capability(
        name="leads_analytics",
        description="Lead funnel and conversion analytics.",
        handler_class_path="backend.handlers.analytics_handlers.LeadAnalyticsHandler",
        action_keys=["leads_analytics", "leads"],
        roles_allowed=_ATLAS_BI_ROLES,
        workflow="analytics_workflow",
    ),
    Capability(
        name="reviews_analytics",
        description="Aggregated review and sentiment analytics.",
        handler_class_path="backend.handlers.analytics_handlers.ReviewAnalyticsHandler",
        action_keys=["reviews_analytics", "reviews"],
        roles_allowed=_ATLAS_BI_ROLES,
        workflow="analytics_workflow",
    ),
    Capability(
        name="upsell_analytics",
        description="Analytics on upsell/cross-sell performance.",
        handler_class_path="backend.handlers.analytics_handlers.UpsellAnalyticsHandler",
        action_keys=["upsell_analytics", "upsell"],
        roles_allowed=_ATLAS_BI_ROLES,
        workflow="analytics_workflow",
    ),
    Capability(
        name="ai_insights",
        description="AI-generated actionable business insights.",
        handler_class_path="backend.handlers.analytics_handlers.AIInsightsHandler",
        action_keys=["ai_insights", "insights"],
        roles_allowed=_ATLAS_BI_ROLES,
        workflow="analytics_workflow",
    ),
    Capability(
        name="forecast",
        description="Revenue and appointment volume forecasting.",
        handler_class_path="backend.handlers.analytics_handlers.ForecastHandler",
        action_keys=["forecast"],
        roles_allowed=_ATLAS_BI_ROLES,
        workflow="analytics_workflow",
    ),
    Capability(
        name="business_context",
        description="Retrieve high-level business context for a tenant.",
        handler_class_path="backend.handlers.analytics_handlers.BusinessContextHandler",
        action_keys=["business_context"],
        roles_allowed=_ATLAS_BI_ROLES,
        workflow="analytics_workflow",
    ),
    Capability(
        name="raw_sql",
        description="Execute a safe, read-only raw SQL query (admin only).",
        handler_class_path="backend.handlers.analytics_handlers.RawSQLHandler",
        action_keys=["raw_sql"],
        roles_allowed=["admin", "owner"],
        workflow="analytics_workflow",
    ),
    Capability(
        name="cohort_reminders",
        description="Send targeted reminders to cohort segments.",
        handler_class_path="backend.handlers.analytics_handlers.CohortRemindersHandler",
        action_keys=["cohort_reminders"],
        roles_allowed=_ATLAS_BI_ROLES,
        workflow="analytics_workflow",
    ),
]

# Agent name → workflow mapping
_AGENT_WORKFLOW_MAP: Dict[str, str] = {
    "clara": "appointment_workflow",
    "mia": "crm_workflow",
    "max": "recommendation_workflow",
    "olivia": "reputation_workflow",
    "atlas staff": "staff_workflow",
    "atlas-staff": "staff_workflow",
    "atlas_staff": "staff_workflow",
    "atlas bi": "analytics_workflow",
    "atlas-bi": "analytics_workflow",
    "atlas_bi": "analytics_workflow",
}


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------
_registry_instance: Optional[CapabilityRegistry] = None
_registry_lock = threading.Lock()


def get_registry() -> CapabilityRegistry:
    """Return the process-wide singleton :class:`CapabilityRegistry`.

    On first call the registry is populated with all default capabilities for
    all six SalonAI agents.

    Returns:
        The global :class:`CapabilityRegistry` instance.

    Example::

        registry = get_registry()
        cap = registry.resolve_capability("clara", "book_appointment")
    """
    global _registry_instance  # pylint: disable=global-statement
    if _registry_instance is None:
        with _registry_lock:
            if _registry_instance is None:
                reg = CapabilityRegistry()
                for cap in _DEFAULT_CAPABILITIES:
                    reg.register(cap)
                for agent, workflow in _AGENT_WORKFLOW_MAP.items():
                    reg._register_agent_workflow(agent, workflow)  # noqa: SLF001
                _registry_instance = reg
                logger.info(
                    "[CapabilityRegistry] Singleton created with %d capabilities.",
                    len(_DEFAULT_CAPABILITIES),
                )
    return _registry_instance
