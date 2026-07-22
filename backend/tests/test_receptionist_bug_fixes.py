"""
Regression tests for receptionist booking bugs reported by the user:

1. Booking a past date must be rejected (must be in the future).
2. Booking an already-passed time slot *today* must be rejected AND the response
   must proactively suggest the next available slots today.
3. Booking with a stylist who is on leave that day must be rejected AND the
   response must suggest an alternative available stylist by name.
4. A stale pending_booking candidate (e.g. from an earlier "list open slots"
   turn) must not silently hijack a later, unrelated request for a different
   service ("sticky booking" leak).
5. An unparseable / calendar-invalid date (e.g. "Feb 30th") must be rejected
   outright instead of silently degrading to today's date.

These exercise the actual live production path used by the Clara_Receptionist
AutoGen agent: ai.tools.capabilities.appointment_workflow_v2 -> _dispatch ->
Handler -> application/services (NOT the legacy ai/agents/receptionist_agent.py
state machine, which is no longer wired into MultiAgentOrchestrator).
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from infrastructure.db import Base, Branch, Staff, Customer, Service, StaffLeave
from application.services.appointment_service import create_appointment
from ai.orchestrator import AgentIntent

TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(name="db_session", scope="function")
def fixture_db_session():
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    branch = Branch(name="Test Salon", code="BR-TEST-BUGFIX", address="1 Salon St", city="Metropolis")
    db.add(branch)
    db.commit()

    service = Service(name="Hair Styling", price=60.00, duration_minutes=60)
    db.add(service)
    db.commit()

    stylist_a = Staff(branch_id=branch.id, first_name="Alice", last_name="OnLeave", email="alice@test.com", role="Stylist")
    stylist_b = Staff(branch_id=branch.id, first_name="Bob", last_name="Available", email="bob@test.com", role="Stylist")
    db.add_all([stylist_a, stylist_b])
    db.commit()

    customer = Customer(first_name="Jane", last_name="Smith", email="jane.bugfix@test.com")
    db.add(customer)
    db.commit()

    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_book_past_date_rejected(db_session):
    """Bug 1: booking yesterday must be rejected as 'must be in the future'."""
    branch = db_session.query(Branch).first()
    service = db_session.query(Service).first()
    customer = db_session.query(Customer).first()

    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    start_time = yesterday.replace(hour=12, minute=0, second=0, microsecond=0)

    res = create_appointment(
        customer_id=customer.id,
        branch_id=branch.id,
        service_id=service.id,
        start_time=start_time.isoformat(),
        db=db_session,
    )
    assert res["success"] is False
    assert "past" in res["error"].lower()


def test_book_already_passed_time_today_suggests_next_slots(db_session):
    """Bug 2: booking 10 AM when it's already 6:40 PM today must be rejected
    AND the appointment_workflow_v2 tool response must list next available
    slots today instead of leaving the user to guess."""
    from ai.tools.capabilities import _dispatch

    branch = db_session.query(Branch).first()
    service = db_session.query(Service).first()
    customer = db_session.query(Customer).first()

    today = datetime.now(timezone.utc).date()
    fixed_now = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=18, minutes=40)

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now if tz else fixed_now.replace(tzinfo=None)

    with patch("application.services.datetime_validation.datetime", FrozenDateTime), \
         patch("datetime.datetime", FrozenDateTime):
        with patch("application.services.entity_resolver_service.SessionLocal", return_value=db_session), \
             patch("application.services.availability_service.SessionLocal", return_value=db_session):
            result = _dispatch(
                workflow_name="appointment_workflow",
                action="book",
                params={
                    "customer_id": str(customer.id),
                    "branch_id": str(branch.id),
                    "service_id": str(service.id),
                    "start_time": f"{today.isoformat()}T10:00:00Z",
                },
                role="CUSTOMER",
            )

    assert "already passed today" in result
    assert "next available slots today" in result.lower()


def test_book_staff_on_leave_suggests_alternative_stylist(db_session):
    """Bug 3: booking with a stylist who is on leave must be rejected AND the
    error must clearly say that stylist is on leave and suggest another
    available stylist by name."""
    branch = db_session.query(Branch).first()
    service = db_session.query(Service).first()
    customer = db_session.query(Customer).first()
    alice = db_session.query(Staff).filter(Staff.first_name == "Alice").first()
    bob = db_session.query(Staff).filter(Staff.first_name == "Bob").first()

    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    leave_date = tomorrow.date()
    db_session.add(StaffLeave(staff_id=alice.id, leave_date=leave_date, reason="Vacation"))
    db_session.commit()

    appt_time = datetime.combine(leave_date, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=12)

    res = create_appointment(
        customer_id=customer.id,
        branch_id=branch.id,
        service_id=service.id,
        start_time=appt_time.isoformat(),
        staff_id=alice.id,
        db=db_session,
    )

    assert res["success"] is False
    assert "is unavailable" in res["error"]
    assert "on leave" in res["error"].lower()
    assert "book another stylist" in res["error"].lower()
    assert bob.full_name in res["error"]


def test_appointment_param_normalization_handles_stylist_and_month_name_date():
    """Ensure weak-model param shapes normalize instead of silently degrading to 'today'."""
    from ai.tools.capabilities import _normalize_appointment_params

    normalized = _normalize_appointment_params({
        "stylist": "Marcus Johnson",
        "serviceName": "Haircut",
        "date": {"month": "July", "day": 24},
    })

    assert normalized["staff_name"] == "Marcus Johnson"
    assert normalized["service_name"] == "Haircut"
    assert normalized["date"] == f"{datetime.now(timezone.utc).year:04d}-07-24"


def test_appointment_workflow_rejects_unreadable_structured_date():
    """Unreadable date objects must fail fast rather than defaulting to today's slots."""
    from ai.tools.capabilities import _dispatch

    result = _dispatch(
        workflow_name="appointment_workflow",
        action="check_availability",
        params={"date": {"day": "abc", "month": "mystery"}},
        role="CUSTOMER",
    )

    assert "couldn't read the appointment date" in result.lower()


def test_check_availability_requires_explicit_date():
    """Availability checks must not silently default to today's date."""
    from core.handlers import CheckAvailabilityHandler, HandlerContext

    ctx = HandlerContext(
        params={
            "service_name": "Haircut",
            "staff_name": "Marcus Johnson",
        },
        user_role="CUSTOMER",
    )
    res = CheckAvailabilityHandler().execute(ctx)
    assert res["success"] is False
    assert "provide the appointment date" in res["error"].lower()


def test_looks_like_new_request_detects_different_service():
    """A message naming a different service than the pending candidate must
    read as a fresh ask, not a reply to the pending confirmation."""
    from ai.orchestrator import _looks_like_new_request

    pending = {"service": "Haircut", "staff_name": "Priya", "date": "2026-07-29"}
    assert _looks_like_new_request("Can I get a manicure tomorrow at 2 PM?", pending) is True
    assert _looks_like_new_request("I'd like a haircut with likhith next Friday", pending) is True
    # A bare confirmation/selection reply must NOT be misread as a new request.
    assert _looks_like_new_request("11am works for me", pending) is False
    assert _looks_like_new_request("yes", pending) is False


@pytest.mark.asyncio
async def test_stale_pending_booking_dropped_for_unrelated_new_request():
    """Bug 4 (sticky pending_booking leak): once a booking candidate is
    stashed on the session (e.g. after listing open slots for a Priya
    haircut), an unrelated follow-up request for a different service must
    start its own fresh flow instead of being silently folded into
    completing the old, unrelated candidate — which previously caused a
    "manicure tomorrow at 2pm" request to book a leftover Priya haircut
    instead."""
    from ai.orchestrator import MultiAgentOrchestrator
    from application.services.conversation_state_service import SessionState

    orchestrator = MultiAgentOrchestrator(name="Orchestrator")
    session = SessionState(session_id="test-stale-pending", user_id="cust-1", user_role="CUSTOMER")
    session.pending_booking = {"service": "Haircut", "staff_name": "Priya", "date": "2026-07-29"}

    with patch.object(orchestrator.state_service, "_save_session"):
        intent = orchestrator._resolve_intent_with_state(
            "Can I get a manicure tomorrow at 2 PM?", session, "CUSTOMER"
        )

    assert session.pending_booking == {}
    assert intent == AgentIntent.BOOKING  # still a booking-shaped ask, just not the stale one


@pytest.mark.asyncio
async def test_pending_booking_kept_for_genuine_confirmation_reply():
    """A plain confirmation/selection reply must keep riding the sticky
    pending_booking context instead of being treated as a new request."""
    from ai.orchestrator import MultiAgentOrchestrator
    from application.services.conversation_state_service import SessionState

    orchestrator = MultiAgentOrchestrator(name="Orchestrator")
    session = SessionState(session_id="test-sticky-pending", user_id="cust-1", user_role="CUSTOMER")
    session.pending_booking = {"service": "Haircut", "staff_name": "Priya", "date": "2026-07-29"}

    intent = orchestrator._resolve_intent_with_state("11am works for me", session, "CUSTOMER")

    assert session.pending_booking == {"service": "Haircut", "staff_name": "Priya", "date": "2026-07-29"}
    assert intent == AgentIntent.BOOKING


def test_resolve_relative_date_rejects_invalid_calendar_date():
    """Bug 5: 'Feb 30th' (a non-existent calendar date) must raise instead of
    silently degrading to today's date."""
    from application.services.entity_resolver_service import resolve_relative_date

    with pytest.raises(ValueError):
        resolve_relative_date("Feb 30th")


def test_validate_appointment_datetime_rejects_unparseable_date():
    """Bug 5: an appointment request for an unparseable/invalid date must be
    rejected with a clear message, not silently marked valid."""
    from application.services.datetime_validation import validate_appointment_datetime

    result = validate_appointment_datetime("Feb 30th")
    assert result["valid"] is False
    assert "understand" in result["reason"].lower()


def test_book_with_time_only_and_date_keeps_requested_date():
    """When date is provided separately, a time-only start_time must not become 'today'."""
    from core.handlers import BookAppointmentHandler, HandlerContext

    captured: dict[str, str] = {}

    class _MockAppointmentService:
        def book(self, customer_id, branch_id, service_id, start_time, staff_id=None, notes=None, tenant_id="default", db=None):
            captured["start_time"] = start_time
            return {"success": True, "appointment_id": "appt-1", "start_time": start_time}

    with patch("application.services.appointment_service.get_appointment_service", return_value=_MockAppointmentService()), \
         patch("application.services.entity_resolver_service.resolve_entity_context", return_value={
             "customer_id": "cust-1",
             "branch_id": "branch-1",
             "service_id": "service-1",
             "staff_id": "staff-1",
         }):
        ctx = HandlerContext(
            params={
                "customer_name": "Jane",
                "branch_name": "Main Salon",
                "service_name": "Haircut",
                "staff_name": "Marcus Johnson",
                "date": "July 24",
                "start_time": "09:00",
            },
            user_role="CUSTOMER",
        )
        res = BookAppointmentHandler().execute(ctx)

    assert res["success"] is True
    assert captured["start_time"].endswith("T09:00:00Z")
    assert "-07-24T09:00:00Z" in captured["start_time"]
