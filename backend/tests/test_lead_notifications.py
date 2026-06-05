import os
import sys
import pytest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db import Base, Lead, LeadStatus, Customer, User, UserRole, Notification
from services.lead_service import send_lead_followup
from tools.lead_tools import create_followup_reminder

TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(name="db_session", scope="function")
def fixture_db_session():
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    # Create Admin user for fallback
    admin_user = User(
        email="admin@test.com",
        hashed_password="hashedpassword",
        role=UserRole.ADMIN,
        is_active=True
    )
    db.add(admin_user)
    db.commit()
    
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_send_lead_followup_links_and_notifies(db_session):
    # 1. Create a customer and user with matching email
    customer = Customer(
        first_name="Alice",
        last_name="Smith",
        email="alice@example.com",
        phone="+1-555-1234"
    )
    db_session.add(customer)
    db_session.commit()

    user = User(
        email="alice@example.com",
        hashed_password="hashedpassword",
        role=UserRole.CUSTOMER,
        customer_id=customer.id,
        is_active=True
    )
    db_session.add(user)
    db_session.commit()

    # 2. Create a lead with the same email but no customer_id
    lead = Lead(
        customer_name="Alice Smith",
        customer_email="alice@example.com",
        customer_phone="+1-555-1234",
        service_name="Signature Precision Haircut",
        status=LeadStatus.NEW,
        lead_score=70
    )
    db_session.add(lead)
    db_session.commit()

    assert lead.customer_id is None
    assert lead.followup_count == 0
    assert lead.last_contacted is None

    # 3. Call send_lead_followup
    res = send_lead_followup(lead.id, db_session)
    assert res["success"] is True

    # 4. Refresh lead from db
    db_session.refresh(lead)
    assert lead.customer_id == customer.id
    assert lead.status == LeadStatus.CONTACTED
    assert lead.followup_count == 1
    assert lead.last_contacted is not None

    # 5. Verify notification was created for Alice
    notifications = db_session.query(Notification).filter(Notification.user_id == user.id).all()
    assert len(notifications) == 1
    assert notifications[0].title == "Unfinished Booking Reminder"
    assert "Alice" in lead.notes or "follow-up" in lead.notes.lower()


def test_create_followup_reminder_links_and_notifies(db_session):
    # 1. Create a customer and user with matching phone
    customer = Customer(
        first_name="Bob",
        last_name="Jones",
        email="bob@example.com",
        phone="+1-555-9876"
    )
    db_session.add(customer)
    db_session.commit()

    user = User(
        email="bob@example.com",
        hashed_password="hashedpassword",
        role=UserRole.CUSTOMER,
        customer_id=customer.id,
        is_active=True
    )
    db_session.add(user)
    db_session.commit()

    # 2. Create a lead with the same phone but no customer_id
    lead = Lead(
        customer_name="Bob Jones",
        customer_email="bob@other.com", # different email, match by phone
        customer_phone="+1-555-9876",
        service_name="Balayage & Creative Color",
        status=LeadStatus.NEW,
        lead_score=85
    )
    db_session.add(lead)
    db_session.commit()

    assert lead.customer_id is None

    # 3. Call create_followup_reminder (the tool wrapper)
    res = create_followup_reminder(
        lead_id=lead.id,
        channel="sms",
        message="Hey Bob, don't forget your Balayage!",
        db=db_session
    )
    assert res["success"] is True

    # 4. Verify lead was updated
    db_session.refresh(lead)
    assert lead.customer_id == customer.id
    assert lead.status == LeadStatus.CONTACTED
    assert lead.followup_count == 1
    assert lead.last_contacted is not None

    # 5. Verify notification was created
    notifications = db_session.query(Notification).filter(Notification.user_id == user.id).all()
    assert len(notifications) == 1
    assert notifications[0].title == "Unfinished Booking Reminder"
