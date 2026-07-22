"""
Regression coverage for WorkflowRegistry.dispatch().

dispatch() used to call handler.handle(ctx) directly, skipping
BaseHandler.execute()'s validate() + permission_action RBAC check for every
handler across all 6 agents. A CUSTOMER could therefore invoke any workflow
action regardless of its declared permission_action restriction (e.g.
crm_search, which is MANAGER+ only). dispatch() now calls handler.execute(ctx)
so the permission check actually runs on the real dispatch path, not just
when a handler is invoked directly in a test.
"""

from core.workflow_registry import get_workflow_registry
from core.handlers import HandlerContext


def test_dispatch_rejects_role_not_permitted_for_action():
    """CUSTOMER is not in crm_search's allowed roles (MANAGER/OWNER/ADMIN only) —
    dispatch() must reject it before any handler business logic runs."""
    registry = get_workflow_registry()
    ctx = HandlerContext(params={"query": "test"}, user_role="CUSTOMER")

    result = registry.dispatch("crm_workflow", "search_leads", ctx)

    assert result.get("success") is False
    assert "not permitted" in result.get("error", "").lower()


def test_dispatch_allows_role_permitted_for_action():
    """MANAGER is permitted to call crm_search — dispatch() must not block it
    on the permission check (any failure here would be business logic, not RBAC)."""
    registry = get_workflow_registry()
    ctx = HandlerContext(params={"query": "test"}, user_role="MANAGER")

    result = registry.dispatch("crm_workflow", "search_leads", ctx)

    assert "not permitted" not in str(result.get("error", "")).lower()


def test_dispatch_rejects_customer_from_raw_sql():
    """analytics_raw_sql is OWNER/ADMIN only — CUSTOMER must be rejected via the
    real dispatch path (not just RawSQLHandler's own inline role check)."""
    registry = get_workflow_registry()
    ctx = HandlerContext(params={"sql": "SELECT 1"}, user_role="CUSTOMER")

    result = registry.dispatch("analytics_workflow", "raw_sql", ctx)

    assert result.get("success") is False
    assert "not permitted" in result.get("error", "").lower()


def test_bi_and_agent_specific_analytics_handlers_are_distinct_classes():
    """core/handlers.py used to define ReviewAnalyticsHandler, UpsellAnalyticsHandler,
    and StaffPerformanceHandler TWICE each (once for their owning agent's own
    'analytics'/'staff_performance' action, once again for Atlas BI's cross-cutting
    analytics_workflow action). Python class-name rebinding meant the second
    definition silently shadowed the first at the bare name, and only alias names
    (ReputationAnalyticsHandler / RecommendationAnalyticsHandler / StaffKPIHandler)
    protected the first definition from being lost. This worked by accident of
    definition order; the BI-specific classes are now uniquely named
    (BIReviewAnalyticsHandler / BIUpsellAnalyticsHandler / BIStaffPerformanceHandler)
    so there is no shadowing landmine regardless of future edit order.
    """
    import core.handlers as h

    assert h.BIReviewAnalyticsHandler is not h.ReputationAnalyticsHandler
    assert h.BIUpsellAnalyticsHandler is not h.RecommendationAnalyticsHandler
    assert h.BIStaffPerformanceHandler is not h.StaffKPIHandler

    assert h.ReputationAnalyticsHandler.permission_action == "reputation_analytics"
    assert h.RecommendationAnalyticsHandler.permission_action == "recommendation_analytics"
    assert h.StaffKPIHandler.permission_action == "staff_performance"

    assert h.BIReviewAnalyticsHandler.permission_action == "analytics_reviews"
    assert h.BIUpsellAnalyticsHandler.permission_action == "analytics_upsell"
    assert h.BIStaffPerformanceHandler.permission_action == "analytics_staff"


def test_registry_resolves_reputation_and_recommendation_analytics_to_their_own_agent():
    """reputation_workflow.analytics and recommendation_workflow.analytics must
    dispatch to their OWN agent's handler, not Atlas BI's cross-cutting one."""
    registry = get_workflow_registry()

    reputation_handler = registry._workflows["reputation_workflow"]["analytics"]
    recommendation_handler = registry._workflows["recommendation_workflow"]["analytics"]
    bi_reviews_handler = registry._workflows["analytics_workflow"]["reviews"]
    bi_upsell_handler = registry._workflows["analytics_workflow"]["upsell"]

    assert type(reputation_handler).__name__ == "ReviewAnalyticsHandler"
    assert reputation_handler.permission_action == "reputation_analytics"
    assert type(recommendation_handler).__name__ == "UpsellAnalyticsHandler"
    assert recommendation_handler.permission_action == "recommendation_analytics"

    assert type(bi_reviews_handler).__name__ == "BIReviewAnalyticsHandler"
    assert type(bi_upsell_handler).__name__ == "BIUpsellAnalyticsHandler"


def test_customer_history_handler_reports_failure_for_unresolvable_customer():
    """get_customer_history() returns a plain error STRING (by design, for direct
    LLM display) rather than raising. CustomerHistoryHandler used to hardcode
    success=True regardless of that string's content, so a 'customer not found'
    error was reported to callers as a successful result."""
    registry = get_workflow_registry()
    ctx = HandlerContext(
        params={"customer_name": "Totally Nonexistent Person XYZ"}, user_role="STAFF"
    )

    result = registry.dispatch("staff_workflow", "customer_history", ctx)

    assert result.get("success") is False
    assert "not" in result.get("result", "").lower() or "no customer found" in result.get("result", "").lower()
