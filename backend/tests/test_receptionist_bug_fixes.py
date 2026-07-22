"""
Regression tests for three receptionist booking bugs reported by the user:

1. Booking a past date must be rejected (must be in the future).
2. Booking an already-passed time slot *today* must be rejected AND the response
   must proactively suggest the next available slots today.
3. Booking with a stylist who is on leave that day must be rejected AND the
   response must suggest an alternative available stylist by name.

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
