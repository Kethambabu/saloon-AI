"""
Regression tests for three production bugs found in the cancel/reschedule
fallback-resolution path (application/services/appointment_service.py) and
the appointment-rescheduled domain event (infrastructure/events/event_bus.py).

Background — all three bugs were reachable any time Clara (or another
caller) couldn't supply the exact `appointment_id` for a cancel/reschedule
request, which the system prompt explicitly anticipates can happen ("NEVER
invent or hallucinate an appointment_id" — implying it sometimes will):

1. Wrong-appointment fallback: when `appointment_id` didn't resolve to a
   real appointment, the code fell back to the customer's "latest active
   appointment" — but implemented "latest" as the appointment furthest in
   the future (`ORDER BY start_time DESC`), not the next upcoming one, and
   picked it silently even when the customer had multiple active bookings.
   A customer asking to cancel their appointment this week could end up
   having a completely different appointment weeks out cancelled instead,
   with no warning.

2. Placeholder false-positives: `_is_placeholder_value()` flagged any
   identifier merely *containing* the substrings "1234", "0000", "1111",
   "aaaa", or "abcd" anywhere as a hallucinated LLM placeholder. Real,
   randomly-generated UUIDs have a non-trivial chance of containing one of
   those 4-hex-digit runs by pure coincidence (~0.12% empirically), which
   caused real appointment/customer/staff/branch/service identifiers to be
   intermittently rejected as "invalid" for no reason a customer or support
   agent could reproduce or explain.

3. AppointmentRescheduledEvent was missing a `customer_id` field even though
   `AppointmentService.reschedule()` always constructed it with
   `customer_id=...`, so every successful reschedule's event publish raised
   `TypeError` (swallowed by a bare except + error log). The reschedule
   itself still succeeded, but the domain event was never actually
   delivered — silently breaking any current or future subscriber (e.g.
   reschedule notifications, analytics) and spamming error logs on every
   single reschedule.
"""

import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from infrastructure.db import Base, Branch, Staff, Customer, Service, Appointment, AppointmentStatus
from infrastructure.events.event_bus import get_event_bus
from application.services.appointment_service import (
    create_appointment,
    cancel_appointment,
    reschedule_appointment,
    _is_placeholder_value,
)

TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(name="db_session", scope="function")
def fixture_db_session():
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    branch = Branch(name="Test Salon", code="BR-TEST-02", address="1 Salon Ave", city="Metropolis")
    db.add(branch)
    db.commit()

    service = Service(name="Hair Styling", price=Decimal("60.00"), duration_minutes=60)
    db.add(service)
    db.commit()

    stylist_a = Staff(branch_id=branch.id, first_name="John", last_name="Doe", email="john@test.com", role="Stylist")
    stylist_b = Staff(branch_id=branch.id, first_name="Amy", last_name="Lee", email="amy@test.com", role="Stylist")
    db.add_all([stylist_a, stylist_b])
    db.commit()

    customer = Customer(first_name="Jane", last_name="Smith", email="jane@gmail.com")
    db.add(customer)
    db.commit()

    try:
        yield {"db": db, "branch": branch, "service": service, "stylist_a": stylist_a, "stylist_b": stylist_b, "customer": customer}
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def _book(ctx, days_out, hour, staff):
    dt = datetime.now(timezone.utc) + timedelta(days=days_out)
    start = datetime.combine(dt.date(), datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=hour)
    res = create_appointment(
        customer_id=ctx["customer"].id,
        branch_id=ctx["branch"].id,
        service_id=ctx["service"].id,
        start_time=start.isoformat(),
        staff_id=staff.id,
        db=ctx["db"],
    )
    assert res["success"] is True, res
    return res["appointment_id"], start


def test_cancel_with_bad_id_and_multiple_active_appointments_refuses_and_lists_both(db_session):
    """Bug #1: must NOT silently guess (and must not pick 'furthest in the
    future') when the customer has more than one active appointment."""
    ctx = db_session
    soon_id, _ = _book(ctx, days_out=2, hour=11, staff=ctx["stylist_a"])
    later_id, _ = _book(ctx, days_out=10, hour=14, staff=ctx["stylist_b"])

    result = cancel_appointment(
        appointment_id="not-a-real-id-the-llm-made-up",
        customer_id=str(ctx["customer"].id),
        db=ctx["db"],
    )
    assert result["success"] is False
    assert soon_id in result["error"]
    assert later_id in result["error"]

    soon = ctx["db"].query(Appointment).filter_by(id=uuid.UUID(soon_id)).first()
    later = ctx["db"].query(Appointment).filter_by(id=uuid.UUID(later_id)).first()
    assert soon.status == AppointmentStatus.CONFIRMED, "sooner appointment must be untouched"
    assert later.status == AppointmentStatus.CONFIRMED, "later appointment must be untouched"


def test_cancel_with_bad_id_and_single_active_appointment_auto_resolves(db_session):
    """When there's exactly one active appointment, the fallback may still
    resolve it automatically — only ambiguity (2+) must be refused."""
    ctx = db_session
    only_id, _ = _book(ctx, days_out=3, hour=10, staff=ctx["stylist_a"])

    result = cancel_appointment(
        appointment_id="still-garbage",
        customer_id=str(ctx["customer"].id),
        db=ctx["db"],
    )
    assert result["success"] is True, result
    appt = ctx["db"].query(Appointment).filter_by(id=uuid.UUID(only_id)).first()
    assert appt.status == AppointmentStatus.CANCELLED


def test_cancel_real_id_cancels_only_that_appointment(db_session):
    """Sanity check: Clara's designed happy path (real appointment_id from
    a prior `history` call) must still work exactly as before, even when
    the customer has multiple active appointments."""
    ctx = db_session
    soon_id, _ = _book(ctx, days_out=2, hour=11, staff=ctx["stylist_a"])
    later_id, _ = _book(ctx, days_out=10, hour=14, staff=ctx["stylist_b"])

    result = cancel_appointment(appointment_id=soon_id, customer_id=str(ctx["customer"].id), db=ctx["db"])
    assert result["success"] is True, result

    soon = ctx["db"].query(Appointment).filter_by(id=uuid.UUID(soon_id)).first()
    later = ctx["db"].query(Appointment).filter_by(id=uuid.UUID(later_id)).first()
    assert soon.status == AppointmentStatus.CANCELLED
    assert later.status == AppointmentStatus.CONFIRMED, "unrelated appointment must never be touched"


def test_reschedule_with_bad_id_and_multiple_active_appointments_refuses(db_session):
    """Same fallback-safety guarantee, on the reschedule path."""
    ctx = db_session
    soon_id, _ = _book(ctx, days_out=2, hour=11, staff=ctx["stylist_a"])
    later_id, later_start = _book(ctx, days_out=10, hour=14, staff=ctx["stylist_b"])

    new_start = (later_start + timedelta(days=1)).isoformat()
    result = reschedule_appointment(
        appointment_id="totally-made-up",
        new_start_time=new_start,
        customer_id=str(ctx["customer"].id),
        db=ctx["db"],
    )
    assert result["success"] is False
    assert soon_id in result["error"]
    assert later_id in result["error"]

    soon = ctx["db"].query(Appointment).filter_by(id=uuid.UUID(soon_id)).first()
    later = ctx["db"].query(Appointment).filter_by(id=uuid.UUID(later_id)).first()
    assert soon.start_time is not None and soon.status == AppointmentStatus.CONFIRMED
    assert later.status == AppointmentStatus.CONFIRMED


def test_placeholder_detection_does_not_false_positive_on_real_uuids_containing_digit_runs(db_session):
    """Bug #2 regression: a real UUID that happens to contain '1234', '0000',
    '1111', 'aaaa', or 'abcd' as a SUBSTRING must never be treated as a
    hallucinated placeholder — only exact-value matches or fully-degenerate
    UUIDs (e.g. all-zeros) should be."""
    real_uuid_with_1234 = "5a758e33-583f-4ea5-bd46-1234af20ac20"
    real_uuid_with_abcd = "9abcdef1-2345-6789-0abc-def123456789".replace("9abcdef1", "9fabcde1")  # keep 'abcd' substr, valid hex
    assert not _is_placeholder_value(real_uuid_with_1234)
    assert not _is_placeholder_value(str(uuid.uuid4()))

    # Exact-value / fully-degenerate placeholders must still be caught.
    assert _is_placeholder_value("1234")
    assert _is_placeholder_value("0000")
    assert _is_placeholder_value("first_branch_id")
    assert _is_placeholder_value("00000000-0000-0000-0000-000000000000")
    assert _is_placeholder_value("12345678-1234-1234-1234-123456789012")

    # And an appointment whose real, randomly-generated ID happens to
    # contain one of those substrings must still be cancellable normally.
    ctx = db_session
    appt_id, _ = _book(ctx, days_out=2, hour=11, staff=ctx["stylist_a"])
    # Force the stored id to contain a "1234" run so this test is
    # deterministic rather than relying on a lucky random UUID.
    appt = ctx["db"].query(Appointment).filter_by(id=uuid.UUID(appt_id)).first()
    forced_id = uuid.UUID("5a758e33-583f-4ea5-bd46-1234af20ac20")
    appt.id = forced_id
    ctx["db"].commit()

    result = cancel_appointment(appointment_id=str(forced_id), customer_id=str(ctx["customer"].id), db=ctx["db"])
    assert result["success"] is True, result


def test_reschedule_event_publishes_with_customer_id(db_session):
    """Bug #3 regression: AppointmentRescheduledEvent must accept
    customer_id (matching how AppointmentService.reschedule() constructs
    it) and actually be delivered to subscribers, not silently dropped."""
    ctx = db_session
    appt_id, start = _book(ctx, days_out=2, hour=11, staff=ctx["stylist_a"])

    received = []
    bus = get_event_bus()
    bus.subscribe("appointment.rescheduled", lambda evt: received.append(evt))

    new_start = (start + timedelta(days=1, hours=1)).isoformat()
    result = reschedule_appointment(
        appointment_id=appt_id,
        new_start_time=new_start,
        customer_id=str(ctx["customer"].id),
        db=ctx["db"],
    )
    assert result["success"] is True, result
    assert len(received) == 1, "AppointmentRescheduledEvent must be delivered exactly once"
    assert received[0].customer_id == str(ctx["customer"].id)
    assert received[0].appointment_id == appt_id
