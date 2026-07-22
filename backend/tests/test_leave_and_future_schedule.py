import os
import sys
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from infrastructure.db import Base, Branch, Staff, Customer, Service, StaffLeave, Appointment, AppointmentStatus
from application.services.appointment_service import get_available_slots, create_appointment
from application.services.staff_service import get_schedule
from ai.agents.receptionist_agent import ReceptionistAgent
from ai.agents.staff_assistant_agent import StaffAssistantAgent

TEST_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(name="db_session", scope="function")
def fixture_db_session():
    engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    branch = Branch(name="Main Salon", code="BR-TEST-01", address="123 Salon St", city="Metropolis", is_active=True)
    db.add(branch)
    db.commit()

    service = Service(name="Bridal Makeup", price=60.00, duration_minutes=60, is_active=True)
    db.add(service)
    db.commit()

    # Stylist 1: John Doe
    stylist1 = Staff(branch_id=branch.id, first_name="John", last_name="Doe", email="john@test.com", role="Stylist", is_active=True)
    db.add(stylist1)
    
    # Stylist 2: Priya Sharma
    stylist2 = Staff(branch_id=branch.id, first_name="Priya", last_name="Sharma", email="priya@test.com", role="Stylist", is_active=True)
    db.add(stylist2)
    
    db.commit()

    customer = Customer(first_name="Jane", last_name="Smith", email="jane@gmail.com", is_active=True)
    db.add(customer)
    db.commit()
    
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

def test_get_available_slots_when_stylist_on_leave(db_session):
    branch = db_session.query(Branch).first()
    service = db_session.query(Service).first()
    john = db_session.query(Staff).filter(Staff.first_name == "John").first()
    priya = db_session.query(Staff).filter(Staff.first_name == "Priya").first()
    
    # Put John on leave tomorrow
    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    date_str = tomorrow.strftime("%Y-%m-%d")
    
    leave = StaffLeave(
        staff_id=john.id,
        leave_date=tomorrow.date(),
        reason="Vacation"
    )
    db_session.add(leave)
    db_session.commit()
    
    # Get available slots for John on his leave date
    res = get_available_slots(
        branch_id=branch.id,
        date_str=date_str,
        staff_id=john.id,
        service_id=service.id,
        db=db_session
    )
    
    assert res["success"] is False
    assert res["staff_on_leave"] is True
    assert "John Doe" in res["error"]
    
    # Verify alternative staff slots are calculated and returned (Priya is active and not on leave)
    assert len(res["slots"]) > 0
    first_slot = res["slots"][0]
    assert str(priya.id) in first_slot["available_staff_ids"]
    assert "Priya Sharma" in first_slot["available_staff_names"]

@pytest.mark.asyncio
async def test_receptionist_booking_flow_stylist_on_leave(db_session):
    # Test receptionist process when stylist is on leave
    agent = ReceptionistAgent()
    
    # Put John on leave tomorrow
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1))
    date_str = tomorrow.strftime("%Y-%m-%d")
    
    # Mock LLM intent extraction
    mock_llm_res = AsyncMock()
    mock_llm_res.content = f'{{"intent": "book", "service": "Bridal Makeup", "branch": "Main Salon", "stylist": "John Doe", "date": "{date_str}", "time": "17:00"}}'
    
    # Mock check_stylist_availability to return the leave detail
    # (Priya Sharma is available)
    mock_slots = f"{{'success': False, 'error': 'John Doe is on leave', 'staff_on_leave': True, 'staff_name': 'John Doe', 'date': '{date_str}', 'slots': [{{'start_time': '{date_str}T17:00:00Z', 'available_staff_names': ['Priya Sharma']}}]}}"
    
    with patch("core.openai_client_adapter.OpenAIChatCompletionClient.create", return_value=mock_llm_res), \
         patch("ai.agents.receptionist_agent.check_stylist_availability", return_value=mock_slots), \
         patch("ai.agents.receptionist_agent.SessionLocal", return_value=db_session):
         
        res = await agent.process({
            "query": f"book Bridal Makeup at Main Salon with John Doe tomorrow at 17:00",
            "customer_id": "some-customer-id"
        })
        
        assert res["success"] is True
        response_text = res["response"]
        assert "john doe is on leave" in response_text.lower()
        assert "priya sharma" in response_text.lower()

def test_get_schedule_for_future_date(db_session):
    john = db_session.query(Staff).filter(Staff.first_name == "John").first()
    customer = db_session.query(Customer).first()
    service = db_session.query(Service).first()
    branch = db_session.query(Branch).first()
    
    # Create an appointment for John tomorrow
    tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
    appt_time = datetime.combine(tomorrow.date(), datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=14) # 2 PM
    
    appt = Appointment(
        customer_id=customer.id,
        branch_id=branch.id,
        staff_id=john.id,
        service_id=service.id,
        start_time=appt_time,
        end_time=appt_time + timedelta(hours=1),
        status=AppointmentStatus.CONFIRMED
    )
    db_session.add(appt)
    db_session.commit()
    
    # Check schedule for tomorrow
    date_str = tomorrow.strftime("%Y-%m-%d")
    res = get_schedule(staff_id=john.id, date_str=date_str, db=db_session)
    
    assert date_str in res or tomorrow.strftime('%B %d, %Y') in res
    assert "Bridal Makeup" in res
    assert "Jane Smith" in res

