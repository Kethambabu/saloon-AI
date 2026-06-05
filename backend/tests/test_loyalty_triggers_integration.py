"""
Integration Tests for Loyalty Point Triggers during Booking Completion, Cancellation, and Review Submission.
"""

import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import uuid

from db import Base, Branch, Staff, Customer, Service, Appointment, AppointmentStatus, Review, User
from tools.booking_tools import create_appointment, cancel_appointment
from services.review_service import ReviewService

TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(name="db_session", scope="function")
def fixture_db_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    branch = Branch(name="Test Salon", code="BR-TEST-01", address="123 Salon St", city="Metropolis")
    db.add(branch)
    db.commit()

    service = Service(name="Hair Styling", price=Decimal("60.00"), duration_minutes=60)
    db.add(service)
    db.commit()

    stylist = Staff(branch_id=branch.id, first_name="John", last_name="Doe", email="john@test.com", role="Stylist")
    db.add(stylist)
    db.commit()

    customer = Customer(first_name="Jane", last_name="Smith", email="jane@gmail.com", loyalty_points=0)
    db.add(customer)
    db.commit()
    
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_loyalty_on_appointment_completion_and_cancellation(db_session):
    branch = db_session.query(Branch).first()
    service = db_session.query(Service).first()
    stylist = db_session.query(Staff).first()
    customer = db_session.query(Customer).first()

    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    start_time = datetime.combine(tomorrow.date(), datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=10)

    # 1. Book appointment (starts PENDING, loyalty points still 0)
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
    
    db_session.refresh(customer)
    assert customer.loyalty_points == 0

    # 2. Complete appointment
    appt = db_session.query(Appointment).filter_by(id=uuid.UUID(appt_id)).first()
    
    from tools.loyalty_triggers import trigger_loyalty_update_on_completion
    trigger_loyalty_update_on_completion(db_session, appt.id, customer.id)
    
    db_session.refresh(customer)
    assert customer.loyalty_points == 100

    # 3. Cancel appointment (triggers penalty of -50 points)
    res2 = create_appointment(
        customer_id=customer.id,
        branch_id=branch.id,
        service_id=service.id,
        start_time=(start_time + timedelta(hours=2)).isoformat(),
        staff_id=stylist.id,
        db=db_session
    )
    appt_id2 = res2["appointment_id"]
    
    # Cancel it
    cancel_res = cancel_appointment(appointment_id=appt_id2, db=db_session)
    assert cancel_res["success"] is True
    
    db_session.refresh(customer)
    assert customer.loyalty_points == 50  # 100 - 50 = 50


def test_loyalty_on_review_submission(db_session):
    branch = db_session.query(Branch).first()
    service = db_session.query(Service).first()
    stylist = db_session.query(Staff).first()
    customer = db_session.query(Customer).first()

    # Submit a review
    result = ReviewService.submit_review(
        db=db_session,
        customer_id=str(customer.id),
        rating=5,
        comment="Absolutely wonderful service!",
        staff_id=str(stylist.id)
    )
    assert result["success"] is True
    
    db_session.refresh(customer)
    # Review submission: +25 base, 5-star rating: +50 bonus = +75 points total
    assert customer.loyalty_points == 75
