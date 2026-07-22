import os
import sys
import pytest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from infrastructure.db import Base, Branch, Staff, Customer, Service, Appointment, AppointmentStatus
from application.services.appointment_service import auto_cancel_all_expired_appointments
from infrastructure.events.event_bus import get_event_bus, AppointmentCancelledEvent

TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(name="db_session", scope="function")
def fixture_db_session():
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    branch = Branch(name="AutoCancel Test Branch", code="BR-AC-01", address="456 Auto St", city="TestCity")
    db.add(branch)
    db.commit()

    service = Service(name="Haircut", price=40.00, duration_minutes=30)
    db.add(service)
    db.commit()

    stylist = Staff(branch_id=branch.id, first_name="Alex", last_name="Smith", email="alex@test.com", role="Stylist")
    db.add(stylist)
    db.commit()

    customer = Customer(first_name="Bob", last_name="Marley", email="bob@test.com")
    db.add(customer)
    db.commit()
    
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_auto_cancel_past_appointments(db_session):
    branch = db_session.query(Branch).first()
    service = db_session.query(Service).first()
    stylist = db_session.query(Staff).first()
    customer = db_session.query(Customer).first()

    now = datetime.now(timezone.utc)
    past_time_1 = now - timedelta(hours=2)
    past_time_2 = now - timedelta(days=1)
    future_time = now + timedelta(days=1)

    # 1. Past pending appointment
    past_pending = Appointment(
        customer_id=customer.id,
        branch_id=branch.id,
        service_id=service.id,
        staff_id=stylist.id,
        start_time=past_time_1,
        end_time=past_time_1 + timedelta(minutes=30),
        status=AppointmentStatus.PENDING,
        notes="Customer requested early slot"
    )
    # 2. Past confirmed appointment
    past_confirmed = Appointment(
        customer_id=customer.id,
        branch_id=branch.id,
        service_id=service.id,
        staff_id=stylist.id,
        start_time=past_time_2,
        end_time=past_time_2 + timedelta(minutes=30),
        status=AppointmentStatus.CONFIRMED,
    )
    # 3. Future confirmed appointment
    future_appt = Appointment(
        customer_id=customer.id,
        branch_id=branch.id,
        service_id=service.id,
        staff_id=stylist.id,
        start_time=future_time,
        end_time=future_time + timedelta(minutes=30),
        status=AppointmentStatus.CONFIRMED,
    )

    db_session.add_all([past_pending, past_confirmed, future_appt])
    db_session.commit()

    received_events = []
    def event_listener(event):
        if isinstance(event, AppointmentCancelledEvent):
            received_events.append(event)

    event_bus = get_event_bus()
    event_bus.subscribe(AppointmentCancelledEvent, event_listener)

    cancelled_count = auto_cancel_all_expired_appointments(db_session)

    assert cancelled_count == 2

    # Refresh objects from DB
    db_session.refresh(past_pending)
    db_session.refresh(past_confirmed)
    db_session.refresh(future_appt)

    assert past_pending.status == AppointmentStatus.CANCELLED
    assert "[Auto-cancelled: Booking time/date passed]" in past_pending.notes
    assert past_pending.notes.startswith("Customer requested early slot")

    assert past_confirmed.status == AppointmentStatus.CANCELLED
    assert past_confirmed.notes == "[Auto-cancelled: Booking time/date passed]"

    assert future_appt.status == AppointmentStatus.CONFIRMED

    # Verify event bus received 2 events
    assert len(received_events) == 2
    assert all(e.reason == "Booking time/date passed" for e in received_events)
    assert all(e.cancelled_by == "SYSTEM_AUTO_CANCEL" for e in received_events)
