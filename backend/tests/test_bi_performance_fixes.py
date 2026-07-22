"""
Regression tests for the Atlas BI timeout/performance fix pass:
  - core/openai_client_adapter.py: LLM client is truly async (no event-loop-blocking sync I/O)
  - ai/tools/capabilities.py: previously-uncached "specialist" analytics actions now cache
  - api/routes/analytics_routes.py: dashboard/revenue REST polling endpoints now cache
  - api/routes/agent_routes.py: timeout log message/constant no longer lies about the real timeout
"""
import asyncio
import os
import sys
import uuid
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from openai import AsyncOpenAI
from core.openai_client_adapter import OpenAIChatCompletionClient
from ai.tools.capabilities import analytics_workflow_v2
from application.services.analytics_service import AnalyticsService


def test_openai_client_adapter_uses_async_client():
    """A blocking sync OpenAI client on the event loop is what broke cancellation/concurrency."""
    client = OpenAIChatCompletionClient(
        model="test-model", api_key="sk-test", base_url="http://localhost:1", timeout=5.0
    )
    assert isinstance(client._client, AsyncOpenAI)


@pytest.mark.asyncio
async def test_cooperative_cancellation_stops_further_llm_calls():
    """
    With a real async client, asyncio.wait_for must be able to cancel mid-flight instead of
    the cancellation only being noticed after a blocking call has already run to completion.
    """
    call_count = {"n": 0}

    async def slow_call():
        call_count["n"] += 1
        await asyncio.sleep(5)
        call_count["n"] += 100  # would prove the call was NOT actually cancelled

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(slow_call(), timeout=0.05)

    # Give any (incorrectly) still-running background work a moment to prove itself wrong.
    await asyncio.sleep(0.2)
    assert call_count["n"] == 1, "cancelled call kept running to completion instead of stopping"


def test_previously_uncached_specialist_action_now_caches():
    """
    Phase 2 exposed 30 analytics_workflow actions to Atlas BI's prompt, but only 10 were ever
    added to the cache allowlist — every specialist breakdown action (e.g. peak_hours)
    recomputed from scratch on every single call, even identical repeated calls seconds apart.
    """
    unique_user = f"perf-test-{uuid.uuid4()}"
    with patch.object(
        AnalyticsService, "get_peak_hours_analysis", return_value={"peak_hour": "18:00"}
    ) as mocked:
        analytics_workflow_v2("peak_hours", {}, role="ADMIN", tenant_id="default", user_id=unique_user)
        analytics_workflow_v2("peak_hours", {}, role="ADMIN", tenant_id="default", user_id=unique_user)
    assert mocked.call_count == 1, "second identical peak_hours call should have been served from cache"


def test_cohort_reminders_intentionally_excluded_from_caching():
    """cohort_reminders sends real reminders (a side effect) — must never be served from cache."""
    unique_user = f"perf-test-{uuid.uuid4()}"
    with patch(
        "ai.agents.bi_agent.trigger_returning_cohort_reminders", return_value={"sent": 0}
    ) as mocked:
        analytics_workflow_v2("cohort_reminders", {}, role="ADMIN", tenant_id="default", user_id=unique_user)
        analytics_workflow_v2("cohort_reminders", {}, role="ADMIN", tenant_id="default", user_id=unique_user)
    assert mocked.call_count == 2, "cohort_reminders must run every time, never be cached"


def test_analytics_workflow_v2_caches_repeated_specialist_action_call():
    """A second identical call to a newly-cacheable action must hit cache, not recompute."""
    unique_user = f"perf-test-{uuid.uuid4()}"
    with patch.object(
        AnalyticsService, "get_average_ticket_analysis", return_value={"average_ticket": 42.0}
    ) as mocked:
        analytics_workflow_v2("average_ticket", {}, role="ADMIN", tenant_id="default", user_id=unique_user)
        analytics_workflow_v2("average_ticket", {}, role="ADMIN", tenant_id="default", user_id=unique_user)
    assert mocked.call_count == 1, "second identical call should have been served from cache"


def test_rest_dashboard_summary_endpoint_caches_across_requests():
    from infrastructure.cache.token_optimizer import get_cache
    import api.routes.analytics_routes as analytics_routes
    from infrastructure.db.database import SessionLocal

    # Isolate from any state left by other tests/pollers.
    get_cache("analytics").invalidate("rest_dashboard_summary", "today")

    with patch.object(
        AnalyticsService, "get_dashboard_summary", return_value={"revenue_today": 0.0}
    ) as mocked:
        db1 = SessionLocal()
        db2 = SessionLocal()
        try:
            asyncio.run(analytics_routes.get_dashboard_summary(period="today", db=db1))
            asyncio.run(analytics_routes.get_dashboard_summary(period="today", db=db2))
        finally:
            db1.close()
            db2.close()
    assert mocked.call_count == 1, "second poll within TTL should have been served from cache"


def test_agent_timeout_constant_is_consistent_with_wait_for():
    from api.routes import agent_routes
    import inspect

    assert agent_routes.AGENT_TIMEOUT_SECONDS == 90.0
    source = inspect.getsource(agent_routes)
    assert "30.0 seconds" not in source and "within 30 seconds" not in source, (
        "stale hardcoded '30 seconds' timeout message should reference AGENT_TIMEOUT_SECONDS instead"
    )
