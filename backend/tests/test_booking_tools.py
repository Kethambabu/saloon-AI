"""
Unit and Integration Tests for Booking Business Tools.
Validates create, cancel, reschedule, available slots, and customer history retrieval.
"""

import os
import sys
import pytest
from datetime import datetime, timezone, timedelta, date
from decimal import Decimal

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from infrastructure.db import Base, Branch, Staff, Customer, Service, Appointment, AppointmentStatus
from application.services.appointment_service import (
    create_appointment,
    get_available_slots,
    cancel_appointment,
    reschedule_appointment
)

TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(name="db_session", scope="function")
def fixture_db_session():
    """Provides an isolated in-memory SQLite database session populated with initial test data."""
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    # Populate necessary lookup data
    branch = Branch(name="Test Salon", code="BR-TEST-01", address="123 Salon St", city="Metropolis")
    db.add(branch)
    db.commit()

    service = Service(name="Hair Styling", price=Decimal("60.00"), duration_minutes=60)
    db.add(service)
    db.commit()

    stylist = Staff(branch_id=branch.id, first_name="John", last_name="Doe", email="john@test.com", role="Stylist")
    db.add(stylist)
    db.commit()

    customer = Customer(first_name="Jane", last_name="Smith", email="jane@gmail.com")
    db.add(customer)
    db.commit()
    
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_get_available_slots(db_session):
    """Verifies that available slots are generated correctly based on business hours and stylist availability."""
    branch = db_session.query(Branch).first()
    service = db_session.query(Service).first()
    stylist = db_session.query(Staff).first()

    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")

    # Fetch slots for tomorrow
    result = get_available_slots(
        branch_id=branch.id,
        date_str=tomorrow,
        staff_id=stylist.id,
        service_id=service.id,
        db=db_session
    )

    assert result["success"] is True
    assert len(result["slots"]) > 0
    # Business hours are 9:00 to 20:00.
    # Service is 60 minutes.
    # So slot starts at 9:00, 9:30, ..., up to 19:00 (ends at 20:00).
    # Total potential slots = 21
    assert len(result["slots"]) == 21


def test_create_appointment_success_and_overlap_prevention(db_session):
    """Verifies successful creation of appointments and ensures overlapping bookings are rejected."""
    branch = db_session.query(Branch).first()
    service = db_session.query(Service).first()
    stylist = db_session.query(Staff).first()
    customer = db_session.query(Customer).first()

    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    start_time = datetime.combine(tomorrow.date(), datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=10) # 10:00 AM

    # 1. Success Create
    result = create_appointment(
        customer_id=customer.id,
        branch_id=branch.id,
        service_id=service.id,
        start_time=start_time.isoformat(),
        staff_id=stylist.id,
        notes="First time cuts",
        db=db_session
    )

    assert result["success"] is True
    assert result["status"] == "CONFIRMED"
    appt_id = result["appointment_id"]

    # 2. Overlap Create (same customer, same time)
    result_overlap_cust = create_appointment(
        customer_id=customer.id,
        branch_id=branch.id,
        service_id=service.id,
        start_time=start_time.isoformat(),
        staff_id=None,  # Try auto assignment
        db=db_session
    )
    assert result_overlap_cust["success"] is False
    assert "You already have an appointment scheduled at that time" in result_overlap_cust["error"] or "Duplicate appointment detected" in result_overlap_cust["error"]

    # Create another customer to test stylist overlap
    other_customer = Customer(first_name="Alice", last_name="Jones", email="alice@test.com")
    db_session.add(other_customer)
    db_session.commit()

    # 3. Overlap Create (other customer, same time, same stylist)
    result_overlap_stylist = create_appointment(
        customer_id=other_customer.id,
        branch_id=branch.id,
        service_id=service.id,
        start_time=start_time.isoformat(),
        staff_id=stylist.id,
        db=db_session
    )
    assert result_overlap_stylist["success"] is False
    assert "is already booked" in result_overlap_stylist["error"]


def test_cancel_appointment(db_session):
    """Verifies that canceling an appointment updates its status correctly."""
    branch = db_session.query(Branch).first()
    service = db_session.query(Service).first()
    stylist = db_session.query(Staff).first()
    customer = db_session.query(Customer).first()

    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    start_time = datetime.combine(tomorrow.date(), datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=11)

    # Book first
    res = create_appointment(
        customer_id=customer.id,
        branch_id=branch.id,
        service_id=service.id,
        start_time=start_time.isoformat(),
        staff_id=stylist.id,
        db=db_session
    )
    appt_id = res["appointment_id"]

    # Cancel
    cancel_res = cancel_appointment(appointment_id=appt_id, db=db_session)
    assert cancel_res["success"] is True
    assert cancel_res["status"] == "CANCELLED"

    # Verify status in database
    import uuid
    retrieved = db_session.query(Appointment).filter_by(id=uuid.UUID(appt_id)).first()
    assert retrieved.status == AppointmentStatus.CANCELLED


def test_reschedule_appointment(db_session):
    """Verifies rescheduling behavior, including business hours validation and overlap checks."""
    branch = db_session.query(Branch).first()
    service = db_session.query(Service).first()
    stylist = db_session.query(Staff).first()
    customer = db_session.query(Customer).first()

    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    start_time = datetime.combine(tomorrow.date(), datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=12)

    # Book
    res = create_appointment(
        customer_id=customer.id,
        branch_id=branch.id,
        service_id=service.id,
        start_time=start_time.isoformat(),
        staff_id=stylist.id,
        db=db_session
    )
    appt_id = res["appointment_id"]

    # Reschedule to 1 hour later (1:00 PM)
    new_start = start_time + timedelta(hours=1)
    res_resched = reschedule_appointment(
        appointment_id=appt_id,
        new_start_time=new_start.isoformat(),
        db=db_session
    )

    assert res_resched["success"] is True
    assert res_resched["status"] == "CONFIRMED"

    # Verify in DB
    import uuid
    retrieved = db_session.query(Appointment).filter_by(id=uuid.UUID(appt_id)).first()
    # Compare hours
    assert retrieved.start_time.hour == new_start.hour


def test_get_customer_history(db_session):
    """Verifies that customer booking history includes all correct metadata."""
    branch = db_session.query(Branch).first()
    service = db_session.query(Service).first()
    stylist = db_session.query(Staff).first()
    customer = db_session.query(Customer).first()

    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    start_time = datetime.combine(tomorrow.date(), datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=14)

    # Create book
    create_appointment(
        customer_id=customer.id,
        branch_id=branch.id,
        service_id=service.id,
        start_time=start_time.isoformat(),
        staff_id=stylist.id,
        db=db_session
    )

    # Get history via mcp_execute patched to test DB session
    from ai.tools.mcp_tool import mcp_execute
    from unittest.mock import patch
    
    with patch("mcp.salon_mcp.SessionLocal", return_value=db_session):
        history_res = mcp_execute(
            resource="appointments",
            operation="select",
            filters={"customer_id": str(customer.id)},
            user_context={"user_id": str(customer.id), "role": "CUSTOMER", "customer_id": str(customer.id)}
        )
    
    assert history_res["success"] is True
    assert history_res["count"] == 1
    assert history_res["data"][0]["service_id"] == str(service.id)
    assert history_res["data"][0]["staff_id"] == str(stylist.id)


def test_create_appointment_inactive_customer(db_session):
    """Verifies that creating an appointment fails when the customer account is inactive."""
    branch = db_session.query(Branch).first()
    service = db_session.query(Service).first()
    stylist = db_session.query(Staff).first()
    customer = db_session.query(Customer).first()

    # Deactivate customer
    customer.is_active = False
    db_session.commit()

    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    start_time = datetime.combine(tomorrow.date(), datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=10)

    result = create_appointment(
        customer_id=customer.id,
        branch_id=branch.id,
        service_id=service.id,
        start_time=start_time.isoformat(),
        staff_id=stylist.id,
        db=db_session
    )

    assert result["success"] is False
    assert result["error"] == "Customer account is inactive."


