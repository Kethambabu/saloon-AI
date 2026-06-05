import os
import sys
import pytest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db import Base, Branch, Staff, Customer, Service, StaffLeave
from tools.booking_tools import create_appointment, reschedule_appointment

TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(name="db_session", scope="function")
def fixture_db_session():
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    branch = Branch(name="Test Salon", code="BR-TEST-01", address="123 Salon St", city="Metropolis")
    db.add(branch)
    db.commit()

    service = Service(name="Hair Styling", price=60.00, duration_minutes=60)
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

def test_booking_on_leave_date_fails(db_session):
    branch = db_session.query(Branch).first()
    service = db_session.query(Service).first()
    stylist = db_session.query(Staff).first()
    customer = db_session.query(Customer).first()

    # Schedule leave for stylist on a specific date (e.g. tomorrow)
    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    leave_date = tomorrow.date()
    
    leave = StaffLeave(
        staff_id=stylist.id,
        leave_date=leave_date,
        reason="Vacation"
    )
    db_session.add(leave)
    db_session.commit()

    # Attempt to book appointment on that leave day (12:00 PM)
    appt_time = datetime.combine(leave_date, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=12)
    
    res = create_appointment(
        customer_id=customer.id,
        branch_id=branch.id,
        service_id=service.id,
        start_time=appt_time.isoformat(),
        staff_id=stylist.id,
        db=db_session
    )
    
    assert res["success"] is False
    assert "is unavailable" in res["error"]

def test_reschedule_to_leave_date_fails(db_session):
    branch = db_session.query(Branch).first()
    service = db_session.query(Service).first()
    stylist = db_session.query(Staff).first()
    customer = db_session.query(Customer).first()

    # Create a valid appointment for tomorrow
    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    tomorrow_time = datetime.combine(tomorrow.date(), datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=12)

    res = create_appointment(
        customer_id=customer.id,
        branch_id=branch.id,
        service_id=service.id,
        start_time=tomorrow_time.isoformat(),
        staff_id=stylist.id,
        db=db_session
    )
    assert res["success"] is True
    appt_id = res["appointment_id"]

    # Register leave for the day after tomorrow
    day_after = datetime.now(timezone.utc) + timedelta(days=2)
    leave_date = day_after.date()
    
    leave = StaffLeave(
        staff_id=stylist.id,
        leave_date=leave_date,
        reason="Medical Leave"
    )
    db_session.add(leave)
    db_session.commit()

    # Try to reschedule to that leave day (12:00 PM)
    resched_time = datetime.combine(leave_date, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=12)
    
    res_resched = reschedule_appointment(
        appointment_id=appt_id,
        new_start_time=resched_time.isoformat(),
        db=db_session
    )
    
    assert res_resched["success"] is False
    assert "is unavailable" in res_resched["error"]
