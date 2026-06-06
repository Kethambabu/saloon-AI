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


def test_notification_clearing_behavior(db_session):
    # 1. Create a customer and user
    customer = Customer(
        first_name="Jane",
        last_name="Doe",
        email="jane@example.com",
        phone="+1-555-4321"
    )
    db_session.add(customer)
    db_session.commit()

    user = User(
        email="jane@example.com",
        hashed_password="hashedpassword",
        role=UserRole.CUSTOMER,
        customer_id=customer.id,
        is_active=True
    )
    db_session.add(user)
    db_session.commit()

    # 2. Add a notification
    notif = Notification(
        user_id=user.id,
        title="Test Notification Title",
        message="This is a test notification",
        is_read=False,
        is_cleared=False
    )
    db_session.add(notif)
    db_session.commit()

    # 3. Retrieve notifications via get_user_notifications -> should return it
    from api.routes.notification_routes import get_user_notifications, clear_all_notifications
    res_list = get_user_notifications(current_user=user, db=db_session)
    assert len(res_list) == 1
    assert res_list[0].title == "Test Notification Title"

    # 4. Clear notifications via clear_all_notifications
    clear_res = clear_all_notifications(current_user=user, db=db_session)
    assert clear_res["success"] is True

    # 5. Retrieve again -> should return 0 since they are marked as is_cleared=True
    res_list_after = get_user_notifications(current_user=user, db=db_session)
    assert len(res_list_after) == 0

    # 6. Verify notification still exists in the database table
    db_notif = db_session.query(Notification).filter(Notification.user_id == user.id).first()
    assert db_notif is not None
    assert db_notif.is_cleared is True
    assert db_notif.is_read is True


def test_lead_dismissal(db_session):
    # 1. Create customer and user
    customer = Customer(
        first_name="Diana",
        last_name="Prince",
        email="diana@example.com",
        phone="+1-555-0007"
    )
    db_session.add(customer)
    db_session.commit()

    user = User(
        email="diana@example.com",
        hashed_password="hashedpassword",
        role=UserRole.CUSTOMER,
        customer_id=customer.id,
        is_active=True
    )
    db_session.add(user)
    db_session.commit()

    # 2. Create lead in CONTACTED status
    lead = Lead(
        customer_id=customer.id,
        customer_name="Diana Prince",
        customer_email="diana@example.com",
        customer_phone="+1-555-0007",
        service_name="Precision Haircut",
        status=LeadStatus.CONTACTED,
        lead_score=60
    )
    db_session.add(lead)

    # 3. Create active notification for this lead follow-up
    notif = Notification(
        user_id=user.id,
        title="Unfinished Booking Reminder",
        message="You have an unfinished booking for Precision Haircut. Click 'Continue' to complete.",
        is_read=False,
        is_cleared=False
    )
    db_session.add(notif)
    db_session.commit()

    # 4. Trigger dismissal route logic
    from routes.lead_routes import dismiss_active_lead
    res = dismiss_active_lead(current_user=user, db=db_session)
    assert res["success"] is True

    # 5. Check lead status is now LOST
    db_session.refresh(lead)
    assert lead.status == LeadStatus.LOST

    # 6. Check notification is now read and cleared
    db_session.refresh(notif)
    assert notif.is_read is True
    assert notif.is_cleared is True


