"""
End-to-end tests of Clara through the REAL orchestrator (MultiAgentOrchestrator),
using a scripted fake LLM client in place of a live Groq/HuggingFace/Gemini call.
These exercise the actual production code path (ai/orchestrator.py's tool-iteration
loop, the deterministic pending-booking confirmation short-circuit, and
ai/tools/capabilities.py -> core/handlers.py -> application/services/*) end to end,
without needing real network access to an LLM provider.

Covers three behaviors CLARA_RECEPTIONIST_FIX.md flagged as unverified/risky:
  1. A single user turn that needs two sequential tool calls (check_availability,
     then book) actually completes both in one turn (max_tool_iterations).
  2. reflect_on_tool_use=True is configured on every agent, so a turn that ends on
     a tool call always produces a clean natural-language reply, never a raw JSON
     tool-result dump (verified both directly on agent config and behaviorally).
  3. The "yes" reply on a *later* turn completes the previously-checked booking
     deterministically, without re-invoking the LLM at all -- and, if the
     candidate is missing a required field (e.g. service, because
     check_availability doesn't strictly require one), the customer gets a clear
     clarifying question instead of a leaked technical error and a wrong
     "different time or stylist" suggestion.
  4. A model that books correctly but then narrates the WRONG date/time in its
     own final sentence (observed in real testing: a live model confirmed
     "2026-02-30" -- a date that cannot exist on any calendar) must be
     overridden with a ground-truth confirmation built from the actual
     successful `book` call's params, never left as the model's own prose.
"""

import os
import sys
import uuid
import json
import pytest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from infrastructure.db.database import SessionLocal
from infrastructure.db.models import Branch, Staff, Customer, Service, Appointment
from autogen_core import FunctionCall
from autogen_core.models import (
    ChatCompletionClient, CreateResult, RequestUsage,
    FunctionExecutionResultMessage, ModelInfo, ModelFamily,
)
import ai.orchestrator as orch_mod
from ai.orchestrator import AgentIntent


@pytest.fixture(name="clara_db")
def fixture_clara_db():
    db = SessionLocal()
    branch = db.query(Branch).filter(Branch.name == "Clara E2E Salon").first()
    if not branch:
        branch = Branch(name="Clara E2E Salon", code="BR-E2E-01", address="1 E2E St", city="Metropolis", is_active=True)
        db.add(branch)
        db.commit()
    service = db.query(Service).filter(Service.name == "E2E Haircut").first()
    if not service:
        service = Service(name="E2E Haircut", price=70.00, duration_minutes=45, is_active=True)
        db.add(service)
        db.commit()
    staff = db.query(Staff).filter(Staff.first_name == "E2EStylist").first()
    if not staff:
        staff = Staff(branch_id=branch.id, first_name="E2EStylist", last_name="Test", email="e2estylist@test.com", role="Stylist", is_active=True)
        db.add(staff)
        db.commit()
    customer = db.query(Customer).filter(Customer.email == "e2e.customer@example.com").first()
    if not customer:
        customer = Customer(first_name="E2E", last_name="Customer", email="e2e.customer@example.com", is_active=True)
        db.add(customer)
        db.commit()
    try:
        yield {"db": db, "branch": branch, "service": service, "staff": staff, "customer": customer}
    finally:
        db.close()


class ScriptedFakeClient(ChatCompletionClient):
    """Scripts: turn A -> check_availability, then (seeing success) a plain-text
    reply asking to confirm; if `auto_book` is True, instead scripts check_availability
    then book then a text reply (single-turn multi-tool-call scenario)."""

    def __init__(self, branch_id, service_id, staff_id, date_str, time_str,
                 include_service=True, auto_book=False):
        self.branch_id, self.service_id, self.staff_id = branch_id, service_id, staff_id
        self.date_str, self.time_str = date_str, time_str
        self.include_service = include_service
        self.auto_book = auto_book
        self.call_count = 0

    def _check_availability_call(self):
        params = {"branch_id": self.branch_id, "staff_id": self.staff_id,
                  "date": self.date_str, "time": self.time_str}
        if self.include_service:
            params["service_id"] = self.service_id
        return FunctionCall(id="call_1", name="appointment_workflow_v2",
                             arguments=json.dumps({"action": "check_availability", "params": params}))

    def _book_call(self):
        params = {"branch_id": self.branch_id, "service_id": self.service_id,
                  "staff_id": self.staff_id, "date": self.date_str, "time": self.time_str}
        return FunctionCall(id="call_2", name="appointment_workflow_v2",
                             arguments=json.dumps({"action": "book", "params": params}))

    async def create(self, messages, *, tools=(), json_output=None,
                      extra_create_args={}, cancellation_token=None, tool_choice="auto"):
        self.call_count += 1
        num_results = sum(1 for m in messages if isinstance(m, FunctionExecutionResultMessage))

        if tool_choice == "none":
            return CreateResult(finish_reason="stop", content="Here you go — all done!",
                                 usage=RequestUsage(prompt_tokens=5, completion_tokens=5), cached=False)

        if self.auto_book:
            if num_results == 0:
                return CreateResult(finish_reason="function_calls", content=[self._check_availability_call()],
                                     usage=RequestUsage(prompt_tokens=5, completion_tokens=5), cached=False)
            elif num_results == 1:
                return CreateResult(finish_reason="function_calls", content=[self._book_call()],
                                     usage=RequestUsage(prompt_tokens=5, completion_tokens=5), cached=False)
            else:
                return CreateResult(finish_reason="stop",
                                     content="You're all set! Your haircut is booked. Anything else?",
                                     usage=RequestUsage(prompt_tokens=5, completion_tokens=5), cached=False)

        # Two-turn "check then ask to confirm" script
        if num_results == 0:
            return CreateResult(finish_reason="function_calls", content=[self._check_availability_call()],
                                 usage=RequestUsage(prompt_tokens=5, completion_tokens=5), cached=False)
        service_bit = "E2E Haircut, " if self.include_service else ""
        return CreateResult(
            finish_reason="stop",
            content=(f"Great news — {self.time_str} on {self.date_str} is open. Summary: {service_bit}"
                     f"with your requested stylist, on {self.date_str} at {self.time_str}. "
                     "Would you like me to confirm this booking?"),
            usage=RequestUsage(prompt_tokens=5, completion_tokens=5), cached=False,
        )

    def create_stream(self, *a, **k):
        raise NotImplementedError

    async def close(self): pass
    def actual_usage(self): return RequestUsage(prompt_tokens=0, completion_tokens=0)
    def total_usage(self): return RequestUsage(prompt_tokens=0, completion_tokens=0)
    def count_tokens(self, messages, *, tools=()): return 0
    def remaining_tokens(self, messages, *, tools=()): return 100000

    @property
    def capabilities(self):
        return {"vision": False, "function_calling": True, "json_output": False}

    @property
    def model_info(self) -> ModelInfo:
        return ModelInfo(vision=False, function_calling=True, json_output=False,
                          family=ModelFamily.UNKNOWN, structured_output=False)


def _make_orchestrator(monkeypatch, fake_client):
    monkeypatch.setattr(orch_mod, "_create_model_client", lambda: fake_client)
    return orch_mod.MultiAgentOrchestrator(tenant_id="default")


def test_all_agents_configured_for_reflect_on_tool_use(monkeypatch):
    """Config-level regression guard: without reflect_on_tool_use=True, a turn
    whose last model action is a tool call falls back to AutoGen's default
    ToolCallSummaryMessage, whose default format is literally the raw tool
    result -- a direct violation of every agent's "never leak tool output"
    rule. Cheap to check directly without exercising the whole loop."""
    fake_client = ScriptedFakeClient("b", "s", "st", "2026-01-01", "10:00")
    orchestrator = _make_orchestrator(monkeypatch, fake_client)
    for intent, agent in orchestrator.agents.items():
        assert agent._reflect_on_tool_use is True, (
            f"{agent.name} ({intent}) must have reflect_on_tool_use=True"
        )


@pytest.mark.asyncio
async def test_single_turn_check_then_book_chains_two_tool_calls(clara_db, monkeypatch):
    """'Book me a slot if it's free' must complete check_availability AND book
    in the SAME turn -- no extra user round-trip -- and the reply must be
    clean natural language, never a raw JSON dump."""
    ctx = clara_db
    d = (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%d")
    t = "11:00"
    fake_client = ScriptedFakeClient(str(ctx["branch"].id), str(ctx["service"].id), str(ctx["staff"].id),
                                      d, t, auto_book=True)
    orchestrator = _make_orchestrator(monkeypatch, fake_client)

    result = await orchestrator.process({
        "query": f"Book me an E2E Haircut with E2EStylist on {d} at {t} if it's free.",
        "session_id": f"e2e-chain-{uuid.uuid4()}",
        "user_id": str(ctx["customer"].id),
        "user_role": "CUSTOMER",
        "customer_id": str(ctx["customer"].id),
        "tenant_id": "default",
    })

    response_text = result.get("response", "")
    assert not response_text.strip().startswith("{") and not response_text.strip().startswith("["), (
        f"Raw JSON leaked to the customer: {response_text!r}"
    )
    assert fake_client.call_count == 3  # check_availability, book, final text

    appt = ctx["db"].query(Appointment).filter(
        Appointment.customer_id == ctx["customer"].id, Appointment.staff_id == ctx["staff"].id,
    ).order_by(Appointment.created_at.desc()).first()
    assert appt is not None, "Booking should have been created in a single turn"


@pytest.mark.asyncio
async def test_confirm_on_later_turn_completes_booking_without_llm(clara_db, monkeypatch):
    """check_availability now, 'yes' on a LATER, separate turn -> must complete
    deterministically (no LLM re-invocation) and confirm with the real service
    name, not a duplicated 'Your your appointment' fallback phrase."""
    ctx = clara_db
    d = (datetime.now(timezone.utc) + timedelta(days=6)).strftime("%Y-%m-%d")
    t = "13:00"
    fake_client = ScriptedFakeClient(str(ctx["branch"].id), str(ctx["service"].id), str(ctx["staff"].id),
                                      d, t, include_service=True)
    orchestrator = _make_orchestrator(monkeypatch, fake_client)
    session_id = f"e2e-confirm-{uuid.uuid4()}"
    kwargs = dict(session_id=session_id, user_id=str(ctx["customer"].id), user_role="CUSTOMER",
                  customer_id=str(ctx["customer"].id), tenant_id="default")

    r1 = await orchestrator.process({"query": f"Is E2EStylist free for a haircut on {d} at {t}?", **kwargs})
    assert "confirm" in r1["response"].lower()

    calls_before = fake_client.call_count
    r2 = await orchestrator.process({"query": "yes", **kwargs})
    assert fake_client.call_count == calls_before, "'yes' must not re-invoke the LLM"
    assert "your your" not in r2["response"].lower(), "Duplicated 'your your' grammar bug regressed"
    assert "e2e haircut" in r2["response"].lower(), "Confirmation should name the actual service"

    appt = ctx["db"].query(Appointment).filter(
        Appointment.customer_id == ctx["customer"].id, Appointment.staff_id == ctx["staff"].id,
    ).order_by(Appointment.created_at.desc()).first()
    assert appt is not None


@pytest.mark.asyncio
async def test_confirm_with_missing_service_asks_instead_of_leaking_error(clara_db, monkeypatch):
    """check_availability without a service (a normal case -- availability
    checks don't require one), then 'yes': must ask a clear, direct question
    about the missing service -- not leak the internal field name
    ("service_id") or suggest changing the time/stylist, which was never
    the actual problem."""
    ctx = clara_db
    d = (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%d")
    t = "17:00"
    fake_client = ScriptedFakeClient(str(ctx["branch"].id), str(ctx["service"].id), str(ctx["staff"].id),
                                      d, t, include_service=False)
    orchestrator = _make_orchestrator(monkeypatch, fake_client)
    session_id = f"e2e-missing-svc-{uuid.uuid4()}"
    kwargs = dict(session_id=session_id, user_id=str(ctx["customer"].id), user_role="CUSTOMER",
                  customer_id=str(ctx["customer"].id), tenant_id="default")

    await orchestrator.process({"query": f"Is E2EStylist free on {d} at {t}?", **kwargs})
    calls_before = fake_client.call_count
    r2 = await orchestrator.process({"query": "yes", **kwargs})

    assert fake_client.call_count == calls_before, "'yes' must not re-invoke the LLM"
    resp_lower = r2["response"].lower()
    assert "service_id" not in resp_lower, "Raw field name must never leak to the customer"
    # Caught now by the proactive _missing_pending_booking_fields pre-check
    # (before any dispatch/error-string-matching happens at all), so the
    # exact wording differs from the older service_id-error-string special
    # case, but the customer-facing contract is identical: name "service" as
    # the thing to ask about, clearly and directly.
    assert "service" in resp_lower, "Must ask a clear, direct question about the missing service"
    assert "different time or stylist" not in resp_lower, (
        "Must not suggest changing time/stylist when the actual gap is the service"
    )

    appt = ctx["db"].query(Appointment).filter(
        Appointment.customer_id == ctx["customer"].id, Appointment.staff_id == ctx["staff"].id,
    ).order_by(Appointment.created_at.desc()).first()
    assert appt is None, "No booking should have been created without a service"


class DateHallucinatingFakeClient(ChatCompletionClient):
    """Reproduces exactly what was observed in a real live conversation: the
    model calls check_availability and book correctly (with the real,
    requested date), but then narrates a WRONG date in its own final
    sentence -- e.g. a calendar-invalid "2026-02-30" that could never have
    actually been booked, since every date-validation path in this codebase
    rejects such dates. The orchestrator's ground-truth override
    (_extract_last_successful_book_params / _format_booking_confirmation)
    must replace this hallucinated sentence with one built from the real
    book call's params."""

    def __init__(self, branch_id, service_id, staff_id, date_str, time_str):
        self.branch_id, self.service_id, self.staff_id = branch_id, service_id, staff_id
        self.date_str, self.time_str = date_str, time_str
        self.call_count = 0

    async def create(self, messages, *, tools=(), json_output=None,
                      extra_create_args={}, cancellation_token=None, tool_choice="auto"):
        self.call_count += 1
        num_results = sum(1 for m in messages if isinstance(m, FunctionExecutionResultMessage))
        if tool_choice == "none":
            return CreateResult(finish_reason="stop", content="You're all set for 2026-02-30!",
                                 usage=RequestUsage(prompt_tokens=5, completion_tokens=5), cached=False)
        if num_results == 0:
            call = FunctionCall(
                id="call_1", name="appointment_workflow_v2",
                arguments=json.dumps({"action": "check_availability", "params": {
                    "branch_id": self.branch_id, "staff_id": self.staff_id,
                    "date": self.date_str, "time": self.time_str,
                }}),
            )
            return CreateResult(finish_reason="function_calls", content=[call],
                                 usage=RequestUsage(prompt_tokens=5, completion_tokens=5), cached=False)
        elif num_results == 1:
            call = FunctionCall(
                id="call_2", name="appointment_workflow_v2",
                arguments=json.dumps({"action": "book", "params": {
                    "branch_id": self.branch_id, "service_id": self.service_id,
                    "staff_id": self.staff_id, "date": self.date_str, "time": self.time_str,
                }}),
            )
            return CreateResult(finish_reason="function_calls", content=[call],
                                 usage=RequestUsage(prompt_tokens=5, completion_tokens=5), cached=False)
        else:
            # The model's own narration hallucinates an impossible date, even
            # though the actual `book` call above used the correct one.
            return CreateResult(
                finish_reason="stop",
                content="You're all set! Your appointment on 2026-02-30 at 14:00 has been booked!",
                usage=RequestUsage(prompt_tokens=5, completion_tokens=5), cached=False,
            )

    def create_stream(self, *a, **k):
        raise NotImplementedError

    async def close(self): pass
    def actual_usage(self): return RequestUsage(prompt_tokens=0, completion_tokens=0)
    def total_usage(self): return RequestUsage(prompt_tokens=0, completion_tokens=0)
    def count_tokens(self, messages, *, tools=()): return 0
    def remaining_tokens(self, messages, *, tools=()): return 100000

    @property
    def capabilities(self):
        return {"vision": False, "function_calling": True, "json_output": False}

    @property
    def model_info(self) -> ModelInfo:
        return ModelInfo(vision=False, function_calling=True, json_output=False,
                          family=ModelFamily.UNKNOWN, structured_output=False)


@pytest.mark.asyncio
async def test_hallucinated_confirmation_date_is_overridden_with_ground_truth(clara_db, monkeypatch):
    """Regression test for a real bug found in live testing: a model that
    books the CORRECT date/time but then states a different, calendar-invalid
    date in its own confirmation sentence must have that sentence replaced
    with one built from the actual successful `book` call, not left as-is."""
    ctx = clara_db
    d = (datetime.now(timezone.utc) + timedelta(days=3)).strftime("%Y-%m-%d")
    t = "14:00"
    fake_client = DateHallucinatingFakeClient(str(ctx["branch"].id), str(ctx["service"].id),
                                               str(ctx["staff"].id), d, t)
    orchestrator = _make_orchestrator(monkeypatch, fake_client)

    result = await orchestrator.process({
        "query": f"Book me an E2E Haircut with E2EStylist tomorrow at {t}.",
        "session_id": f"e2e-hallucination-{uuid.uuid4()}",
        "user_id": str(ctx["customer"].id),
        "user_role": "CUSTOMER",
        "customer_id": str(ctx["customer"].id),
        "tenant_id": "default",
    })

    response_text = result.get("response", "")
    assert "2026-02-30" not in response_text, (
        "The model's hallucinated, calendar-invalid date leaked into the customer-facing "
        "confirmation instead of being overridden with ground truth"
    )
    assert d in response_text, "Confirmation must state the actual booked date"

    appt = ctx["db"].query(Appointment).filter(
        Appointment.customer_id == ctx["customer"].id, Appointment.staff_id == ctx["staff"].id,
    ).order_by(Appointment.created_at.desc()).first()
    assert appt is not None
    assert appt.start_time.strftime("%Y-%m-%d") == d, "The actually stored appointment must use the real date"


def test_availability_question_is_treated_as_new_request():
    """Direct regression guard for a real bug found in live testing: after a
    prior pending booking existed, a customer asking a plain availability
    question -- "Is Priya free at 3pm?" -- was being misread by the LLM-based
    pending-reply fallback classifier as a "confirm" of the stale, unrelated
    candidate (extracting "3pm" as if it were the customer's answer), which
    could have driven a wrong/unconfirmed booking. `_looks_like_new_request`
    must catch this phrasing deterministically so it never reaches that LLM
    fallback at all."""
    pending = {"service_id": "s1", "staff_id": "st1", "date": "2026-08-01", "time": "10:00"}
    for query in (
        "Is Priya free at 3pm?",
        "is Priya free at 3pm",
        "Is Alexandra available tomorrow?",
        "Are you open on Sunday?",
        "is anyone available at noon",
    ):
        assert orch_mod._looks_like_new_request(query, pending) is True, (
            f"Availability question must be treated as a new request: {query!r}"
        )
    # Sanity: genuine confirmation replies must NOT be misclassified by this
    # same new regex as a fresh request.
    for query in ("yes", "yes please", "11am is fine", "sounds good", "confirm"):
        assert orch_mod._looks_like_new_request(query, pending) is False, (
            f"Genuine confirmation reply wrongly flagged as a new request: {query!r}"
        )


def test_missing_pending_booking_fields_helper():
    """Direct unit test of the proactive pre-check that avoids a doomed
    book() dispatch: it must name every required field absent from a pending
    candidate, covering service/date/time -- not just the two error strings
    that were previously special-cased (service_id, branch_id)."""
    assert orch_mod._missing_pending_booking_fields(
        {"service_id": "s1", "date": "2026-08-01", "time": "10:00"}
    ) == []
    assert orch_mod._missing_pending_booking_fields(
        {"service_id": "s1", "date": "2026-08-01"}
    ) == ["time"]
    assert orch_mod._missing_pending_booking_fields(
        {"service_id": "s1", "time": "10:00"}
    ) == ["date"]
    assert orch_mod._missing_pending_booking_fields(
        {"date": "2026-08-01", "time": "10:00"}
    ) == ["service"]
    assert orch_mod._missing_pending_booking_fields({}) == ["service", "date", "time"]
    # start_time alone (as used by the reschedule replay path) satisfies both
    # date and time without either being present as separate keys.
    assert orch_mod._missing_pending_booking_fields(
        {"service_id": "s1", "start_time": "2026-08-01T10:00:00"}
    ) == []


class CheckWithoutTimeFakeClient(ChatCompletionClient):
    """Reproduces the real bug chain: a check_availability call succeeds and
    is captured as the pending candidate WITHOUT a time (check_availability
    doesn't strictly require one, so this is a normal outcome, not a client
    bug). Confirming with a bare "yes" must now hit the proactive
    _missing_pending_booking_fields guard -- asking directly for the time
    and clearing the stale candidate -- instead of dispatching a doomed
    book() call, leaking its raw "Appointment time is required to book."
    error, and leaving pending_booking alive for a later, unrelated message
    to be misread against."""

    def __init__(self, branch_id, service_id, staff_id, date_str):
        self.branch_id, self.service_id, self.staff_id = branch_id, service_id, staff_id
        self.date_str = date_str
        self.call_count = 0

    async def create(self, messages, *, tools=(), json_output=None,
                      extra_create_args={}, cancellation_token=None, tool_choice="auto"):
        self.call_count += 1
        num_results = sum(1 for m in messages if isinstance(m, FunctionExecutionResultMessage))
        if tool_choice == "none":
            return CreateResult(finish_reason="stop", content="Here you go!",
                                 usage=RequestUsage(prompt_tokens=5, completion_tokens=5), cached=False)
        if num_results == 0:
            call = FunctionCall(
                id="call_1", name="appointment_workflow_v2",
                arguments=json.dumps({"action": "check_availability", "params": {
                    "branch_id": self.branch_id, "service_id": self.service_id,
                    "staff_id": self.staff_id, "date": self.date_str,
                }}),
            )
            return CreateResult(finish_reason="function_calls", content=[call],
                                 usage=RequestUsage(prompt_tokens=5, completion_tokens=5), cached=False)
        return CreateResult(
            finish_reason="stop",
            content=f"Good news, {self.date_str} looks open. What time would you like, and shall I confirm?",
            usage=RequestUsage(prompt_tokens=5, completion_tokens=5), cached=False,
        )

    def create_stream(self, *a, **k):
        raise NotImplementedError

    async def close(self): pass
    def actual_usage(self): return RequestUsage(prompt_tokens=0, completion_tokens=0)
    def total_usage(self): return RequestUsage(prompt_tokens=0, completion_tokens=0)
    def count_tokens(self, messages, *, tools=()): return 0
    def remaining_tokens(self, messages, *, tools=()): return 100000

    @property
    def capabilities(self):
        return {"vision": False, "function_calling": True, "json_output": False}

    @property
    def model_info(self) -> ModelInfo:
        return ModelInfo(vision=False, function_calling=True, json_output=False,
                          family=ModelFamily.UNKNOWN, structured_output=False)


@pytest.mark.asyncio
async def test_confirm_with_missing_time_asks_and_clears_stale_pending(clara_db, monkeypatch):
    """Regression test for the most severe bug found in live testing: a
    pending candidate missing 'time', confirmed with 'yes', must (1) ask
    directly for the time instead of leaking the Handler's raw validation
    error, and (2) actually clear pending_booking -- previously the generic
    failure path left it alive, so a later unrelated message could be
    misrouted into completing this dead, half-formed candidate."""
    ctx = clara_db
    d = (datetime.now(timezone.utc) + timedelta(days=5)).strftime("%Y-%m-%d")
    fake_client = CheckWithoutTimeFakeClient(str(ctx["branch"].id), str(ctx["service"].id), str(ctx["staff"].id), d)
    orchestrator = _make_orchestrator(monkeypatch, fake_client)
    session_id = f"e2e-missing-time-{uuid.uuid4()}"
    kwargs = dict(session_id=session_id, user_id=str(ctx["customer"].id), user_role="CUSTOMER",
                  customer_id=str(ctx["customer"].id), tenant_id="default")

    await orchestrator.process({"query": f"Is E2EStylist free on {d}?", **kwargs})
    calls_before = fake_client.call_count
    r2 = await orchestrator.process({"query": "yes", **kwargs})

    assert fake_client.call_count == calls_before, "'yes' must not re-invoke the LLM"
    resp_lower = r2["response"].lower()
    assert "time is required to book" not in resp_lower, "Raw Handler error must never leak to the customer"
    assert "time" in resp_lower, "Must ask directly about the missing time"
    assert "different time or stylist" not in resp_lower

    from application.services.conversation_state_service import get_state_service
    pending_after = get_state_service().get_pending_booking(session_id)
    assert pending_after == {}, (
        "pending_booking must be cleared after a failed confirmation, not left alive for a "
        "later unrelated message to be misrouted against"
    )

    appt = ctx["db"].query(Appointment).filter(
        Appointment.customer_id == ctx["customer"].id, Appointment.staff_id == ctx["staff"].id,
    ).order_by(Appointment.created_at.desc()).first()
    assert appt is None, "No booking should have been created without a time"


class StringEncodedParamsFakeClient(ChatCompletionClient):
    """Reproduces a real bug found in live testing: 'Can I get a Botox
    appointment?' returned the raw text 'validation error for
    appointment_workflow_v2args ... Input should be a valid dictionary
    [type=dict_type ...]' directly to the customer. Root cause: some
    models (especially weaker fallback ones) sometimes emit a tool call's
    `params` argument as a JSON-encoded STRING rather than a native object
    -- e.g. {"action": "check_availability", "params": "{\\"service\\":
    \\"Botox\\"}"} instead of params being a nested object. The orchestrator's
    tool wrapper closures already had code to coerce a string params back
    into a dict, but that code was unreachable: the wrapper's OWN type hint
    (`params: Optional[Dict[str, Any]]`) let AutoGen build a pydantic schema
    that rejected the call outright, before the wrapper body ever ran, and
    that raw pydantic ValidationError became the tool's "result", which the
    model then simply echoed back verbatim as its reply. This client scripts
    exactly that malformed call shape."""

    def __init__(self, branch_id, service_id, staff_id, date_str, time_str):
        self.branch_id, self.service_id, self.staff_id = branch_id, service_id, staff_id
        self.date_str, self.time_str = date_str, time_str
        self.call_count = 0

    @staticmethod
    def _last_tool_result_content(messages):
        """Pull the raw string content of the most recent tool result, the
        same thing a real model actually sees when it's asked to narrate a
        turn that ended on a tool call. A confused/weak model faced with a
        tool error frequently just echoes it verbatim -- this is what
        actually happened live, not something the orchestrator code invents
        on its own -- so an honest test double must behave the same way
        instead of always returning a fixed, clean sentence regardless of
        whether the tool call actually succeeded."""
        for m in reversed(messages):
            if isinstance(m, FunctionExecutionResultMessage):
                for item in m.content:
                    return getattr(item, "content", None)
        return None

    async def create(self, messages, *, tools=(), json_output=None,
                      extra_create_args={}, cancellation_token=None, tool_choice="auto"):
        self.call_count += 1
        num_results = sum(1 for m in messages if isinstance(m, FunctionExecutionResultMessage))
        if num_results == 0 and tool_choice != "none":
            # The bug: `params` is itself a JSON string, not a nested object.
            inner_params_str = json.dumps({
                "branch_id": self.branch_id, "service_id": self.service_id,
                "staff_id": self.staff_id, "date": self.date_str, "time": self.time_str,
            })
            call = FunctionCall(
                id="call_1", name="appointment_workflow_v2",
                arguments=json.dumps({"action": "check_availability", "params": inner_params_str}),
            )
            return CreateResult(finish_reason="function_calls", content=[call],
                                 usage=RequestUsage(prompt_tokens=5, completion_tokens=5), cached=False)
        # Whether this is the tool_choice="none" reflect-on-tool-use call or
        # the natural next-turn call, narrate based on what the tool
        # actually returned -- echoing it verbatim if the call errored,
        # exactly like the real model that produced this bug live.
        last_content = self._last_tool_result_content(messages)
        narration = last_content if last_content else f"Good news, {self.time_str} on {self.date_str} looks open. Shall I confirm?"
        return CreateResult(finish_reason="stop", content=narration,
                             usage=RequestUsage(prompt_tokens=5, completion_tokens=5), cached=False)

    def create_stream(self, *a, **k):
        raise NotImplementedError

    async def close(self): pass
    def actual_usage(self): return RequestUsage(prompt_tokens=0, completion_tokens=0)
    def total_usage(self): return RequestUsage(prompt_tokens=0, completion_tokens=0)
    def count_tokens(self, messages, *, tools=()): return 0
    def remaining_tokens(self, messages, *, tools=()): return 100000

    @property
    def capabilities(self):
        return {"vision": False, "function_calling": True, "json_output": False}

    @property
    def model_info(self) -> ModelInfo:
        return ModelInfo(vision=False, function_calling=True, json_output=False,
                          family=ModelFamily.UNKNOWN, structured_output=False)


@pytest.mark.asyncio
async def test_string_encoded_params_does_not_leak_pydantic_error(clara_db, monkeypatch):
    """Regression test for the Botox-appointment bug from live testing: a
    tool call whose `params` is a JSON-encoded string (not a native object)
    must still work -- never surface a raw pydantic ValidationError as the
    customer-facing reply."""
    ctx = clara_db
    d = (datetime.now(timezone.utc) + timedelta(days=4)).strftime("%Y-%m-%d")
    t = "12:00"
    fake_client = StringEncodedParamsFakeClient(
        str(ctx["branch"].id), str(ctx["service"].id), str(ctx["staff"].id), d, t
    )
    orchestrator = _make_orchestrator(monkeypatch, fake_client)

    result = await orchestrator.process({
        "query": f"Can I get an E2E Haircut with E2EStylist on {d} at {t}?",
        "session_id": f"e2e-string-params-{uuid.uuid4()}",
        "user_id": str(ctx["customer"].id),
        "user_role": "CUSTOMER",
        "customer_id": str(ctx["customer"].id),
        "tenant_id": "default",
    })

    response_text = result.get("response", "")
    resp_lower = response_text.lower()
    assert "validation error" not in resp_lower, f"Raw pydantic error leaked: {response_text!r}"
    assert "dict_type" not in resp_lower, f"Raw pydantic error leaked: {response_text!r}"
    assert "pydantic" not in resp_lower, f"Raw pydantic error leaked: {response_text!r}"
    assert result.get("success") is True
    assert t in response_text or "confirm" in resp_lower, (
        "The string-encoded params call should have succeeded normally, not failed"
    )
