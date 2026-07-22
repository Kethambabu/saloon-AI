"""
Comprehensive 20-Sample Query Evaluation Test Suite for Clara the AI Receptionist Assistant.
Tests end-to-end functionality across Booking, Cancellation, Rescheduling, Availability,
Policy/FAQ, Customer Memory, Tab/Quote formatting, and Multi-turn State Machine workflows.
"""

import os
import sys
import pytest
import asyncio
from datetime import datetime, timezone, timedelta, date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from infrastructure.db.database import SessionLocal
from infrastructure.db import Branch, Staff, Customer, Service, Appointment, AppointmentStatus
from ai.agents.receptionist_agent import ReceptionistAgent
from application.services.conversation_state_service import get_state_service, BookingState


@pytest.fixture(name="setup_20_db", scope="function")
def fixture_setup_20_db():
    db = SessionLocal()

    # Get or seed branch
    branch = db.query(Branch).filter(Branch.name == "Main Salon").first()
    if not branch:
        branch = Branch(name="Main Salon", code="BR-MAIN-20", address="100 Main St", city="Metropolis", is_active=True)
        db.add(branch)
        db.commit()

    # Get or seed service
    service = db.query(Service).filter(Service.name == "Hair Spa").first()
    if not service:
        service = Service(name="Hair Spa", price=85.00, duration_minutes=45, is_active=True)
        db.add(service)
        db.commit()

    # Get or seed staff
    marcus = db.query(Staff).filter(Staff.first_name == "Marcus", Staff.last_name == "Johnson").first()
    if not marcus:
        marcus = Staff(branch_id=branch.id, first_name="Marcus", last_name="Johnson", email="marcus.20@salon.com", role="Stylist", is_active=True)
        db.add(marcus)
        db.commit()

    # Get or seed customer
    customer = db.query(Customer).filter(Customer.email == "alice.20@example.com").first()
    if not customer:
        customer = Customer(first_name="Alice", last_name="Walker", email="alice.20@example.com", phone="555-0199", is_active=True)
        db.add(customer)
        db.commit()

    # Seed staff leave for Marcus Johnson on 2026-07-24
    from infrastructure.db.models import StaffLeave
    m_leave = db.query(StaffLeave).filter(StaffLeave.staff_id == marcus.id, StaffLeave.leave_date == date(2026, 7, 24)).first()
    if not m_leave:
        db.add(StaffLeave(staff_id=marcus.id, leave_date=date(2026, 7, 24), reason="Vacation"))
        db.commit()

    try:
        yield {
            "db": db,
            "branch": branch,
            "service": service,
            "marcus": marcus,
            "customer": customer,
        }
    finally:
        db.close()


@pytest.mark.asyncio
async def test_20_sample_queries_suite(setup_20_db):
    agent = ReceptionistAgent()
    base_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cust_id = str(setup_20_db["customer"].id)

    # Context header
    context_header = (
        f"[SYSTEM TIME CONTEXT: Current system time is {base_date} 10:00:00]\n"
        f"[SYSTEM CUSTOMER CONTEXT: ID: {cust_id}, Email: alice.20@example.com]"
    )
    ReceptionistAgent.CURRENT_QUERY_CONTEXT = context_header
    session_id = "session-20-queries-test"

    # Query 1: Direct complete booking request on available date (2026-07-25)
    q1 = f'book an appoitment for "Hair Spa\tMain Salon\tMarcus Johnson" 12pm slot on 2026-07-25'
    res1 = await agent.process({"query": f"{context_header}\n{q1}", "latest_message": q1, "session_id": session_id})
    assert res1["success"] is True
    assert "Booking Summary" in res1["response"] or "confirm" in res1["response"].lower()
    assert "Hair Spa" in res1["response"]
    assert "Marcus Johnson" in res1["response"]

    # Query 2: Confirmation of Q1 booking
    q2 = "Yes, please confirm this booking"
    res2 = await agent.process({"query": f"{context_header}\n{q2}", "latest_message": q2, "session_id": session_id})
    assert res2["success"] is True
    assert "Confirmed" in res2["response"] or "Appointment Summary" in res2["response"]

    # Query 3: Past date booking rejection
    q3 = "book a Hair Spa for yesterday at 2pm"
    res3 = await agent.process({"query": f"{context_header}\n{q3}", "latest_message": q3, "session_id": "session-q3"})
    assert res3["success"] is True
    assert "past" in res3["response"].lower() or "cannot be booked" in res3["response"].lower()

    # Query 4: Cancellation request
    q4 = "Cancel my appointment"
    res4 = await agent.process({"query": f"{context_header}\n{q4}", "latest_message": q4, "session_id": session_id})
    assert res4["success"] is True
    assert "sure you want to cancel" in res4["response"].lower()

    # Query 5: Cancellation confirmation
    q5 = "Yes, cancel it"
    res5 = await agent.process({"query": f"{context_header}\n{q5}", "latest_message": q5, "session_id": session_id})
    assert res5["success"] is True
    assert "cancelled" in res5["response"].lower()

    # Query 6: Booking with missing time
    q6 = "Book a Hair Spa with Marcus Johnson at Main Salon tomorrow"
    res6 = await agent.process({"query": f"{context_header}\n{q6}", "latest_message": q6, "session_id": "session-q6"})
    assert res6["success"] is True
    assert "time" in res6["response"].lower() or "what time" in res6["response"].lower()

    # Query 7: Providing missing time for Q6
    q7 = "3:00 PM"
    res7 = await agent.process({"query": f"{context_header}\n{q7}", "latest_message": q7, "session_id": "session-q6"})
    assert res7["success"] is True
    assert "Booking Summary" in res7["response"]
    assert "3:00 PM" in res7["response"] or "15:00" in res7["response"]

    # Query 8: Confirmation for Q7
    q8 = "Confirm"
    res8 = await agent.process({"query": f"{context_header}\n{q8}", "latest_message": q8, "session_id": "session-q6"})
    assert res8["success"] is True
    assert "Confirmed" in res8["response"]

    # Query 9: Rescheduling request
    q9 = "Reschedule my appointment to 2026-07-25 at 4pm"
    res9 = await agent.process({"query": f"{context_header}\n{q9}", "latest_message": q9, "session_id": "session-q6"})
    assert res9["success"] is True
    assert "Rescheduling Summary" in res9["response"] or "Old Appointment" in res9["response"]

    # Query 10: Rescheduling confirmation
    q10 = "Yes proceed"
    res10 = await agent.process({"query": f"{context_header}\n{q10}", "latest_message": q10, "session_id": "session-q6"})
    assert res10["success"] is True
    assert "rescheduled" in res10["response"].lower() or "success" in res10["response"].lower()

    # Query 11: Multi-turn date correction with leading quote
    q11_a = "book a Hair Spa with Marcus Johnson at Main Salon for 2pm"
    res11_a = await agent.process({"query": f"{context_header}\n{q11_a}", "latest_message": q11_a, "session_id": "session-q11"})
    q11_b = 'no i want this date "2026-07-26'
    res11_b = await agent.process({"query": f"{context_header}\n{q11_b}", "latest_message": q11_b, "session_id": "session-q11"})
    assert res11_b["success"] is True
    assert "2026-07-26" in res11_b["response"]

    # Query 12: Availability check query
    q12 = "Is Marcus available on 2026-07-27?"
    res12 = await agent.process({"query": f"{context_header}\n{q12}", "latest_message": q12, "session_id": "session-q12"})
    assert res12["success"] is True
    assert "available" in res12["response"].lower() or "slots" in res12["response"].lower()

    # Query 13: Customer history lookup
    q13 = "What appointments do I have?"
    res13 = await agent.process({"query": f"{context_header}\n{q13}", "latest_message": q13, "session_id": "session-q13"})
    assert res13["success"] is True

    # Query 14: Discovery query for services
    q14 = "List services"
    res14 = await agent.process({"query": f"{context_header}\n{q14}", "latest_message": q14, "session_id": "session-q14"})
    assert res14["success"] is True

    # Query 15: Discovery query for branches
    q15 = "List branches"
    res15 = await agent.process({"query": f"{context_header}\n{q15}", "latest_message": q15, "session_id": "session-q15"})
    assert res15["success"] is True

    # Query 16: Discovery query for staff
    q16 = "List staff"
    res16 = await agent.process({"query": f"{context_header}\n{q16}", "latest_message": q16, "session_id": "session-q16"})
    assert res16["success"] is True

    # Query 17: Greeting fast-path check
    q17 = "Hello Clara!"
    res17 = await agent.process({"query": f"{context_header}\n{q17}", "latest_message": q17, "session_id": "session-q17"})
    assert res17["success"] is True

    # Query 18: Thanks fast-path check
    q18 = "Thank you very much"
    res18 = await agent.process({"query": f"{context_header}\n{q18}", "latest_message": q18, "session_id": "session-q18"})
    assert res18["success"] is True

    # Query 19: Farewell check
    q19 = "Goodbye"
    res19 = await agent.process({"query": f"{context_header}\n{q19}", "latest_message": q19, "session_id": "session-q19"})
    assert res19["success"] is True

    # Query 20: Repeat booking request
    q20 = "Book the same service as my last appointment for 2026-07-28 at 10am"
    res20 = await agent.process({"query": f"{context_header}\n{q20}", "latest_message": q20, "session_id": "session-q20"})
    assert res20["success"] is True
    assert "Booking Summary" in res20["response"] or "10:00" in res20["response"]


@pytest.mark.asyncio
async def test_marcus_johnson_leave_on_2026_07_24_rejected(setup_20_db):
    """Verify that booking Marcus Johnson on 2026-07-24 (leave date) is strictly rejected."""
    agent = ReceptionistAgent()
    base_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cust_id = str(setup_20_db["customer"].id)
    context_header = f"[SYSTEM TIME CONTEXT: Current system time is {base_date} 10:00:00]\n[SYSTEM CUSTOMER CONTEXT: ID: {cust_id}, Email: alice.20@example.com]"

    q = 'book a Hair Spa with Marcus Johnson at Main Salon on 2026-07-24 at 12pm'
    res = await agent.process({"query": f"{context_header}\n{q}", "latest_message": q, "session_id": "session-marcus-leave-test"})
    assert res["success"] is True
    assert "on leave" in res["response"].lower() or "unavailable" in res["response"].lower()
    assert "2026-07-24" in res["response"]
