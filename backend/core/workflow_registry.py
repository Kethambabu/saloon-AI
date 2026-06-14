"""
backend/core/workflow_registry.py
==================================
Pure dict-dispatch WorkflowRegistry for SalonAI Phase 2.

Maps (workflow_name, action_key) pairs to :class:`BaseHandler` instances.
All six agent workflows are pre-registered; handler classes are imported
lazily from the ``backend.handlers`` package.

Usage::

    from backend.core.workflow_registry import get_workflow_registry

    reg = get_workflow_registry()
    result = reg.dispatch("appointment_workflow", "book", ctx)
"""

from __future__ import annotations

import importlib
import logging
import threading
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lazy import helper
# ---------------------------------------------------------------------------

def _import_handler(module_path: str, class_name: str) -> Any:
    """Import and return *class_name* from *module_path*.

    Returns ``None`` if the import fails, logging a warning.  This allows the
    registry to be constructed even when handler modules are not yet present
    (e.g. during unit testing of the registry itself).

    Args:
        module_path: Dotted module path, e.g. ``"backend.handlers.appointment"``.
        class_name:  Name of the class to import.

    Returns:
        Class object or ``None``.
    """
    try:
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
    except (ImportError, AttributeError) as exc:
        logger.warning(
            "[WorkflowRegistry] Could not import %s.%s: %s",
            module_path,
            class_name,
            exc,
        )
        return None


# ---------------------------------------------------------------------------
# Handler/Context base – imported from handlers.base if available
# ---------------------------------------------------------------------------
try:
    from backend.handlers.base import BaseHandler, HandlerContext  # type: ignore
except ImportError:  # pragma: no cover – fallback for standalone testing
    class HandlerContext:  # type: ignore
        """Minimal stand-in HandlerContext used when handlers.base is absent."""

        def __init__(self, **kwargs: Any) -> None:
            for k, v in kwargs.items():
                setattr(self, k, v)
            self.trace_id: str = getattr(self, "trace_id", "")
            self.tenant_id: str = getattr(self, "tenant_id", "")

    class BaseHandler:  # type: ignore
        """Minimal stand-in BaseHandler used when handlers.base is absent."""

        def handle(self, ctx: "HandlerContext") -> Dict[str, Any]:  # noqa: D102
            raise NotImplementedError


# ---------------------------------------------------------------------------
# WorkflowRegistry
# ---------------------------------------------------------------------------
class WorkflowRegistry:
    """Registry that dispatches (workflow, action) pairs to handler instances.

    Workflows are stored as ``Dict[action_key, handler_instance]`` and all
    dispatch is done via a single dict lookup — there are **no if/else
    chains**.

    Thread safety:
        A :class:`threading.Lock` guards the internal workflow store so that
        ``register_workflow`` calls from multiple threads are safe.  Dispatch
        acquires the lock only long enough to retrieve the handler reference,
        then releases it before calling ``handler.handle(ctx)``.
    """

    def __init__(self) -> None:
        # workflow_name -> { action_key -> handler_instance }
        self._workflows: Dict[str, Dict[str, BaseHandler]] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    def register_workflow(
        self,
        workflow_name: str,
        handlers: Dict[str, Any],
    ) -> None:
        """Register a workflow and its action-to-handler mapping.

        If the workflow already exists, new handlers are merged; existing
        action keys are overwritten.

        Args:
            workflow_name: Unique workflow identifier
                           (e.g. ``"appointment_workflow"``).
            handlers:      Dict mapping action key string to a
                           :class:`BaseHandler` *instance* (or ``None``
                           if the import failed).
        """
        with self._lock:
            if workflow_name not in self._workflows:
                self._workflows[workflow_name] = {}
            valid_count = 0
            for action, handler in handlers.items():
                if handler is None:
                    logger.warning(
                        "[WorkflowRegistry] workflow='%s' action='%s' has no "
                        "handler (import failed); skipping.",
                        workflow_name,
                        action,
                    )
                    continue
                self._workflows[workflow_name][action] = handler
                valid_count += 1

        logger.info(
            "[WorkflowRegistry] Registered workflow='%s' with %d/%d valid actions.",
            workflow_name,
            valid_count,
            len(handlers),
        )

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------
    def dispatch(
        self,
        workflow_name: str,
        action: str,
        ctx: "HandlerContext",
    ) -> Dict[str, Any]:
        """Dispatch *action* within *workflow_name* to its registered handler.

        Uses a pure dict lookup — no if/else chains.

        Args:
            workflow_name: Workflow identifier.
            action:        Action key string.
            ctx:           :class:`HandlerContext` passed to the handler.

        Returns:
            Result dict from the handler, or an error dict if the workflow
            or action is not registered.

        Example::

            result = reg.dispatch("appointment_workflow", "book", ctx)
        """
        trace_id = getattr(ctx, "trace_id", "")
        tenant_id = getattr(ctx, "tenant_id", "")

        with self._lock:
            workflow = self._workflows.get(workflow_name)

        if workflow is None:
            logger.error(
                "[WorkflowRegistry] workflow='%s' action='%s' trace_id='%s' "
                "tenant_id='%s' — workflow not registered.",
                workflow_name,
                action,
                trace_id,
                tenant_id,
            )
            return {
                "error": f"Workflow '{workflow_name}' is not registered.",
                "workflow": workflow_name,
                "action": action,
            }

        handler: Optional[BaseHandler] = workflow.get(action)

        if handler is None:
            logger.error(
                "[WorkflowRegistry] workflow='%s' action='%s' trace_id='%s' "
                "tenant_id='%s' — action not found.",
                workflow_name,
                action,
                trace_id,
                tenant_id,
            )
            available = sorted(workflow.keys())
            return {
                "error": (
                    f"Action '{action}' not found in workflow '{workflow_name}'. "
                    f"Available: {available}"
                ),
                "workflow": workflow_name,
                "action": action,
                "available_actions": available,
            }

        logger.info(
            "[WorkflowRegistry] Dispatching workflow='%s' action='%s' "
            "handler='%s' trace_id='%s' tenant_id='%s'",
            workflow_name,
            action,
            type(handler).__name__,
            trace_id,
            tenant_id,
        )

        try:
            result = handler.handle(ctx)
            logger.debug(
                "[WorkflowRegistry] Completed workflow='%s' action='%s' "
                "trace_id='%s' tenant_id='%s'",
                workflow_name,
                action,
                trace_id,
                tenant_id,
            )
            return result
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "[WorkflowRegistry] Handler raised exception workflow='%s' "
                "action='%s' trace_id='%s' tenant_id='%s': %s",
                workflow_name,
                action,
                trace_id,
                tenant_id,
                exc,
            )
            return {
                "error": f"Handler error: {exc}",
                "workflow": workflow_name,
                "action": action,
            }

    # ------------------------------------------------------------------
    # Introspection helpers
    # ------------------------------------------------------------------
    def list_workflows(self) -> List[str]:
        """Return a sorted list of all registered workflow names.

        Returns:
            List of workflow name strings.
        """
        with self._lock:
            names = sorted(self._workflows.keys())
        logger.debug("[WorkflowRegistry] list_workflows count=%d", len(names))
        return names

    def list_actions(self, workflow_name: str) -> List[str]:
        """Return a sorted list of action keys in *workflow_name*.

        Args:
            workflow_name: The workflow to inspect.

        Returns:
            Sorted list of action key strings, or empty list if workflow
            is not registered.
        """
        with self._lock:
            workflow = self._workflows.get(workflow_name, {})
            actions = sorted(workflow.keys())
        logger.debug(
            "[WorkflowRegistry] list_actions workflow='%s' count=%d",
            workflow_name,
            len(actions),
        )
        return actions


# ---------------------------------------------------------------------------
# Workflow definitions – handler import table
# ---------------------------------------------------------------------------
# Each entry is (module_path, class_name).  _import_handler() returns None
# on failure so the registry silently skips unavailable handlers.

def _make_instance(module_path: str, class_name: str) -> Optional[Any]:
    """Import and instantiate *class_name* from *module_path*."""
    cls = _import_handler(module_path, class_name)
    if cls is None:
        return None
    try:
        return cls()
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning(
            "[WorkflowRegistry] Could not instantiate %s.%s: %s",
            module_path,
            class_name,
            exc,
        )
        return None


_APT = "backend.handlers.appointment_handlers"
_CRM = "backend.handlers.crm_handlers"
_REP = "backend.handlers.reputation_handlers"
_REC = "backend.handlers.recommendation_handlers"
_STF = "backend.handlers.staff_handlers"
_ANL = "backend.handlers.analytics_handlers"

_WORKFLOW_DEFINITIONS: Dict[str, Dict[str, tuple]] = {
    "appointment_workflow": {
        "check_availability": (_APT, "CheckAvailabilityHandler"),
        "book":               (_APT, "BookAppointmentHandler"),
        "cancel":             (_APT, "CancelAppointmentHandler"),
        "reschedule":         (_APT, "RescheduleAppointmentHandler"),
        "history":            (_APT, "ListAppointmentsHandler"),
        "list_services":      (_APT, "ListServicesHandler"),
        "list_staff":         (_APT, "ListStaffHandler"),
        "search_customers":   (_APT, "SearchCustomersHandler"),
    },
    "crm_workflow": {
        "search_leads":          (_CRM, "SearchLeadsHandler"),
        "create_lead":           (_CRM, "CreateLeadHandler"),
        "advance_lead":          (_CRM, "AdvanceLeadHandler"),
        "send_followup":         (_CRM, "SendFollowupHandler"),
        "generate_message":      (_CRM, "GenerateMessageHandler"),
        "abandoned_bookings":    (_CRM, "DetectAbandonedHandler"),
        "conversion_analytics":  (_CRM, "ConversionAnalyticsHandler"),
        "pipeline_snapshot":     (_CRM, "PipelineSnapshotHandler"),
    },
    "reputation_workflow": {
        "get_reviews": (_REP, "GetReviewsHandler"),
        "analytics":   (_REP, "ReputationAnalyticsHandler"),
        "critical":    (_REP, "CriticalReviewsHandler"),
        "respond":     (_REP, "DraftResponseHandler"),
        "scorecard":   (_REP, "ReputationScorecardHandler"),
        "escalate":    (_REP, "EscalateReviewHandler"),
    },
    "recommendation_workflow": {
        "get_recommendations": (_REC, "GetRecommendationsHandler"),
        "accept":              (_REC, "AcceptRecommendationHandler"),
        "reject":              (_REC, "RejectRecommendationHandler"),
        "analytics":           (_REC, "RecommendationAnalyticsHandler"),
    },
    "staff_workflow": {
        "get_schedule":        (_STF, "GetScheduleHandler"),
        "today_schedule":      (_STF, "TodayScheduleHandler"),
        "next_customer":       (_STF, "NextCustomerHandler"),
        "customer_history":    (_STF, "CustomerHistoryHandler"),
        "customer_preferences":(_STF, "CustomerPreferencesHandler"),
        "staff_revenue":       (_STF, "StaffRevenueHandler"),
        "staff_performance":   (_STF, "StaffKPIHandler"),
        "pending_appointments":(_STF, "PendingAppointmentsHandler"),
        "create_leave":        (_STF, "CreateLeaveHandler"),
        "send_reminders":      (_STF, "SendRemindersHandler"),
    },
    "analytics_workflow": {
        "dashboard":       (_ANL, "DashboardHandler"),
        "revenue":         (_ANL, "RevenueHandler"),
        "customers":       (_ANL, "CustomerMetricsHandler"),
        "staff":           (_ANL, "StaffPerformanceHandler"),
        "leads":           (_ANL, "LeadAnalyticsHandler"),
        "reviews":         (_ANL, "ReviewAnalyticsHandler"),
        "upsell":          (_ANL, "UpsellAnalyticsHandler"),
        "insights":        (_ANL, "AIInsightsHandler"),
        "forecast":        (_ANL, "ForecastHandler"),
        "business_context":(_ANL, "BusinessContextHandler"),
        "raw_sql":         (_ANL, "RawSQLHandler"),
        "cohort_reminders":(_ANL, "CohortRemindersHandler"),
    },
}


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------
_registry_instance: Optional[WorkflowRegistry] = None
_registry_lock = threading.Lock()


def get_workflow_registry() -> WorkflowRegistry:
    """Return the process-wide singleton :class:`WorkflowRegistry`.

    On first call, all six agent workflows are registered using the handler
    definitions in ``_WORKFLOW_DEFINITIONS``.  Handler imports that fail are
    silently skipped and logged as warnings.

    Returns:
        The global :class:`WorkflowRegistry` instance.

    Example::

        reg = get_workflow_registry()
        result = reg.dispatch("crm_workflow", "create_lead", ctx)
    """
    global _registry_instance  # pylint: disable=global-statement
    if _registry_instance is None:
        with _registry_lock:
            if _registry_instance is None:
                reg = WorkflowRegistry()
                for workflow_name, action_map in _WORKFLOW_DEFINITIONS.items():
                    handlers: Dict[str, Any] = {
                        action: _make_instance(mod, cls)
                        for action, (mod, cls) in action_map.items()
                    }
                    reg.register_workflow(workflow_name, handlers)
                _registry_instance = reg
                logger.info(
                    "[WorkflowRegistry] Singleton created with workflows: %s",
                    reg.list_workflows(),
                )
    return _registry_instance
