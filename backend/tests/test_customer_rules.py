"""
Unit and Integration Tests for Customer rules (Leave bounds, Status flow, duplicate check, reminders, waitlist).
"""

import os
import sys
import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db import Base, Branch, Staff, Customer, Service, Appointment, AppointmentStatus, Notification, User, Waitlist
from tools.booking_tools import (
    create_appointment,
    cancel_appointment,
    add_to_waitlist,
    send_appointment_reminders,
    is_staff_on_leave
)

TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(name="db_session", scope="function")
def fixture_db_session():
    """Provides populated in-memory SQLite db."""
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    # Populate
    branch = Branch(name="Test Salon", code="BR-TEST-01", address="123 Salon St", city="Metropolis")
    db.add(branch)
    db.commit()

    service = Service(name="Hair Spa", price=Decimal("90.00"), duration_minutes=90)
    db.add(service)
    db.commit()

    # Leave target: Alexandra Chen
    stylist1 = Staff(branch_id=branch.id, first_name="Alexandra", last_name="Chen", email="alex@test.com", role="Stylist")
    db.add(stylist1)
    db.commit()

    customer = Customer(first_name="Jane", last_name="Smith", email="jane@gmail.com")
    db.add(customer)
    db.commit()

    user = User(email="jane@gmail.com", hashed_password="hashed_password", role="CUSTOMER", customer_id=customer.id)
    db.add(user)
    db.commit()
    
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_staff_leave_management(db_session):
    """Rule 7: Enforce staff leave bounds."""
    stylist = db_session.query(Staff).filter(Staff.first_name == "Alexandra").first()
    
    # June 10 is leave day for Alexandra Chen
    on_leave, name = is_staff_on_leave(stylist.id, "2026-06-10", db_session)
    assert on_leave is True
    assert name == "Alexandra Chen"

    # Try booking Alexandra Chen on June 10
    branch = db_session.query(Branch).first()
    service = db_session.query(Service).first()
    customer = db_session.query(Customer).first()
    
    start_time = "2026-06-10T17:00:00Z"
    
    res = create_appointment(
        customer_id=customer.id,
        branch_id=branch.id,
        service_id=service.id,
        start_time=start_time,
        staff_id=stylist.id,
        db=db_session
    )
    assert res["success"] is False
    assert "Alexandra Chen is unavailable on 2026-06-10" in res["error"]


def test_duplicate_appointment_detection(db_session):
    """Rule 5: Prevent exact duplicate appointments."""
    branch = db_session.query(Branch).first()
    service = db_session.query(Service).first()
    customer = db_session.query(Customer).first()
    stylist = db_session.query(Staff).first()

    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    start_time = datetime.combine(tomorrow.date(), datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=10)

    # First booking
    res1 = create_appointment(
        customer_id=customer.id,
        branch_id=branch.id,
        service_id=service.id,
        start_time=start_time.isoformat(),
        staff_id=stylist.id,
        db=db_session
    )
    assert res1["success"] is True

    # Duplicate booking
    res2 = create_appointment(
        customer_id=customer.id,
        branch_id=branch.id,
        service_id=service.id,
        start_time=start_time.isoformat(),
        staff_id=stylist.id,
        db=db_session
    )
    assert res2["success"] is False
    assert "Duplicate appointment detected" in res2["error"]


def test_lazy_reminders(db_session):
    """Rule 11: Appointment Reminder System (lazy creation)."""
    from unittest.mock import patch
    
    branch = db_session.query(Branch).first()
    service = db_session.query(Service).first()
    customer = db_session.query(Customer).first()
    stylist = db_session.query(Staff).first()
    user = db_session.query(User).first()

    # Appointment in 1 hour (triggers 2-hour reminder)
    now = datetime.now(timezone.utc)
    appt_time = now + timedelta(hours=1)
    
    # Check that there are no reminders yet
    notifs = db_session.query(Notification).filter(Notification.user_id == user.id).all()
    assert len(notifs) == 0

    # Book the appointment
    with patch("tools.booking_tools._is_within_business_hours", return_value=True):
        res = create_appointment(
            customer_id=customer.id,
            branch_id=branch.id,
            service_id=service.id,
            start_time=appt_time.isoformat(),
            staff_id=stylist.id,
            db=db_session
        )
    assert res["success"] is True
    # Mark appointment as CONFIRMED since new appointments are initialized as PENDING
    import uuid
    appt = db_session.query(Appointment).filter_by(id=uuid.UUID(res["appointment_id"])).first()
    appt.status = AppointmentStatus.CONFIRMED
    db_session.commit()

    # Trigger reminders
    count = send_appointment_reminders(customer.id, db_session)
    assert count == 1

    # Verify notification created in DB
    notifs = db_session.query(Notification).filter(Notification.user_id == user.id).all()
    assert len(notifs) == 2
    assert any("Upcoming Appointment in 2 Hours" in n.title for n in notifs)


def test_waitlist_system(db_session):
    """Rule 16: Join waitlist and release notification on cancellation."""
    branch = db_session.query(Branch).first()
    service = db_session.query(Service).first()
    customer = db_session.query(Customer).first()
    stylist = db_session.query(Staff).first()
    user = db_session.query(User).first()

    tomorrow = datetime.now(timezone.utc) + timedelta(days=2)
    start_time = datetime.combine(tomorrow.date(), datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=12)
    date_str = start_time.strftime("%Y-%m-%d")
    time_str = start_time.strftime("%H:%M")

    # 1. Book the slot
    res = create_appointment(
        customer_id=customer.id,
        branch_id=branch.id,
        service_id=service.id,
        start_time=start_time.isoformat(),
        staff_id=stylist.id,
        db=db_session
    )
    assert res["success"] is True
    appt_id = res["appointment_id"]

    # 2. Join waitlist
    wl_res = add_to_waitlist(
        customer_id=customer.id,
        branch_id=branch.id,
        service_id=service.id,
        date_str=date_str,
        time_str=time_str,
        staff_id=stylist.id,
        db=db_session
    )
    assert wl_res["success"] is True
    assert "Successfully joined the waitlist" in wl_res["message"]

    # 3. Verify waitlist entry exists in DB
    wl_entry = db_session.query(Waitlist).filter(Waitlist.customer_id == customer.id).first()
    assert wl_entry is not None
    assert wl_entry.is_notified is False

    # 4. Cancel appointment (releases slot and triggers waitlist release notification!)
    cancel_res = cancel_appointment(appointment_id=appt_id, db=db_session)
    assert cancel_res["success"] is True

    # 5. Check if notification was created and waitlist status updated
    db_session.expire_all()
    wl_entry_updated = db_session.query(Waitlist).filter(Waitlist.customer_id == customer.id).first()
    assert wl_entry_updated.is_notified is True

    notifs = db_session.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.title == "Waitlist Slot Available!"
    ).all()
    assert len(notifs) == 1
    assert "Waitlist Slot Available!" in notifs[0].title


def test_returning_cohort_reminders(db_session):
    """Assert returning cohort customers automatically receive one daily reminder only."""
    from services.analytics_service import AnalyticsService
    
    branch = db_session.query(Branch).first()
    service = db_session.query(Service).first()
    customer = db_session.query(Customer).first()
    stylist = db_session.query(Staff).first()
    user = db_session.query(User).first()

    # 1. Before completed appointments, customer has 0 bookings - not in returning cohort
    reminders_sent = AnalyticsService.send_returning_cohort_reminders(db_session)
    assert reminders_sent == 0
    
    # Verify no reminders created
    notifs = db_session.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.title == "Returning Cohort Daily Reminder"
    ).all()
    assert len(notifs) == 0

    # 2. Add 2 completed appointments to qualify customer for Returning Cohort
    appt1 = Appointment(
        customer_id=customer.id,
        branch_id=branch.id,
        service_id=service.id,
        staff_id=stylist.id,
        start_time=datetime.now(timezone.utc) - timedelta(days=2),
        end_time=datetime.now(timezone.utc) - timedelta(days=2, hours=-1),
        status=AppointmentStatus.COMPLETED
    )
    appt2 = Appointment(
        customer_id=customer.id,
        branch_id=branch.id,
        service_id=service.id,
        staff_id=stylist.id,
        start_time=datetime.now(timezone.utc) - timedelta(days=1),
        end_time=datetime.now(timezone.utc) - timedelta(days=1, hours=-1),
        status=AppointmentStatus.COMPLETED
    )
    db_session.add_all([appt1, appt2])
    db_session.commit()

    # 3. Trigger reminders - should send 1 reminder
    reminders_sent = AnalyticsService.send_returning_cohort_reminders(db_session)
    assert reminders_sent == 1

    # Verify notification created
    notifs = db_session.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.title == "Returning Cohort Daily Reminder"
    ).all()
    assert len(notifs) == 1
    assert "valued returning clients" in notifs[0].message
    assert "0 points" in notifs[0].message  # customer has 0 loyalty points initially

    # 4. Trigger reminders again on the same day - should send 0 reminders (already sent constraint)
    reminders_sent_again = AnalyticsService.send_returning_cohort_reminders(db_session)
    assert reminders_sent_again == 0

    # Verify no duplicate notification is created
    notifs_again = db_session.query(Notification).filter(
        Notification.user_id == user.id,
        Notification.title == "Returning Cohort Daily Reminder"
    ).all()
    assert len(notifs_again) == 1
