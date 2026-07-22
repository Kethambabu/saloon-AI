import os
import sys
import pytest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from infrastructure.db import Base, Branch, Staff, Customer, Service
from application.services.availability_service import AvailabilityService
from application.services.appointment_service import create_appointment


TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(name="db_session", scope="function")
def fixture_db_session():
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    branch = Branch(name="Main Salon", code="BR-MAIN-01", address="123 Main St", city="TestCity")
    db.add(branch)
    db.commit()

    service = Service(name="Hair Spa", price=80.00, duration_minutes=60)
    db.add(service)
    db.commit()

    stylist = Staff(branch_id=branch.id, first_name="Marcus", last_name="Johnson", email="marcus@test.com", role="Stylist")
    db.add(stylist)
    db.commit()

    customer = Customer(first_name="Jane", last_name="Doe", email="jane@test.com")
    db.add(customer)
    db.commit()
    
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_get_available_slots_past_date(db_session):
    branch = db_session.query(Branch).first()
    service = db_session.query(Service).first()
    stylist = db_session.query(Staff).first()

    today = datetime.now(timezone.utc).date()
    past_date_str = (today - timedelta(days=1)).strftime("%Y-%m-%d")

    res = AvailabilityService.get_available_slots(
        branch_id=branch.id,
        date_str=past_date_str,
        staff_id=stylist.id,
        service_id=service.id,
        db=db_session
    )

    assert res["success"] is False
    assert "I'm sorry, but appointments cannot be booked for past dates or times." in res["error"] or "has already passed" in res["error"]
    assert res["slots"] == []


def test_get_available_slots_today_excludes_past_time_slots(db_session, monkeypatch):
    branch = db_session.query(Branch).first()
    service = db_session.query(Service).first()
    stylist = db_session.query(Staff).first()

    today_str = datetime.now().strftime("%Y-%m-%d")

    fixed_now = datetime.strptime(f"{today_str} 16:30:00", "%Y-%m-%d %H:%M:%S")

    class MockDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_now

    import application.services.availability_service as avail_mod
    monkeypatch.setattr(avail_mod.datetime, "datetime", MockDatetime)

    res = avail_mod.AvailabilityService.get_available_slots(
        branch_id=branch.id,
        date_str=today_str,
        staff_id=stylist.id,
        service_id=service.id,
        db=db_session
    )

    assert res["success"] is True
    slots = res["slots"]
    times = [s["time"] for s in slots]

    for past_t in ["09:00", "11:00", "12:00", "14:00", "16:00", "16:30"]:
        assert past_t not in times, f"Past slot {past_t} should have been filtered out."

    for future_t in ["17:00", "18:00", "19:00"]:
        assert future_t in times, f"Future slot {future_t} should be available."


def test_create_appointment_past_time_fails(db_session):
    branch = db_session.query(Branch).first()
    service = db_session.query(Service).first()
    stylist = db_session.query(Staff).first()
    customer = db_session.query(Customer).first()

    # Create past datetime (e.g. 2 hours ago in UTC)
    past_dt = datetime.now(timezone.utc) - timedelta(hours=2)

    res = create_appointment(
        customer_id=customer.id,
        branch_id=branch.id,
        service_id=service.id,
        start_time=past_dt.isoformat(),
        staff_id=stylist.id,
        db=db_session
    )

    assert res["success"] is False
    assert "has already passed" in res["error"] or "past dates or times" in res["error"]
