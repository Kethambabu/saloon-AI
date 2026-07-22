import os
import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from application.services.conversation_state_service import (
    get_state_service,
    BookingState,
    SessionState,
)
from ai.agents.receptionist_agent import (
    ReceptionistAgent,
    is_cancellation_request,
    is_correction_request,
)


@pytest.fixture(name="agent")
def fixture_agent():
    return ReceptionistAgent(name="ClaraTest")


def test_is_cancellation_request():
    assert is_cancellation_request("Cancel my appointment") is True
    assert is_cancellation_request("Please cancel booking") is True
    assert is_cancellation_request("cancel") is True

    # Corrections should NOT be classified as cancellation
    assert is_cancellation_request("No, I want 18 Jul 2026 10 AM") is False
    assert is_cancellation_request("Actually make it tomorrow") is False
    assert is_cancellation_request("Instead change stylist to Marcus") is False


def test_is_correction_request():
    assert is_correction_request("No, I want 18 Jul 2026 10 AM") is True
    assert is_correction_request("Actually 2 PM") is True
    assert is_correction_request("I meant Main Salon") is True
    assert is_correction_request("Instead book with Marcus") is True
    assert is_correction_request("Change to tomorrow") is True

    assert is_correction_request("Book Hair Spa for tomorrow at 12 PM") is False
    assert is_correction_request("Cancel my appointment") is False


def test_state_machine_transitions():
    state_svc = get_state_service()
    session = state_svc.get_or_create("test-sm-session-123")
    
    assert session.booking_state == BookingState.IDLE
    
    session.set_booking_state(BookingState.COLLECTING)
    assert session.booking_state == BookingState.COLLECTING

    session.set_booking_state(BookingState.VALIDATING)
    assert session.booking_state == BookingState.VALIDATING

    session.set_booking_state(BookingState.AVAILABILITY)
    assert session.booking_state == BookingState.AVAILABILITY

    session.set_booking_state(BookingState.BOOKING)
    assert session.booking_state == BookingState.BOOKING

    session.set_booking_state(BookingState.CONFIRMED)
    assert session.booking_state == BookingState.CONFIRMED

    session.clear_pending_booking()
    assert session.booking_state == BookingState.CLOSED
    assert session.pending_booking == {}


@pytest.mark.asyncio
async def test_past_date_rejection_in_conversation_flow(agent, monkeypatch):
    """
    User requests:
    1. Book Hair Spa, Main Salon, Marcus Johnson, 22 Jul 12 PM (future)
    2. "No, I want 18 Jul 2026 10 AM." (past date)
    
    Expected:
    Rejects immediately with past date error message. Zero DB/availability queries.
    """
    session_id = "test-past-date-convo-999"
    state_svc = get_state_service()
    state_svc.delete_session(session_id)

    # Fixed system time: 2026-07-21 10:00:00 UTC
    fixed_now = datetime(2026, 7, 21, 10, 0, tzinfo=timezone.utc)
    monkeypatch.setattr("ai.agents.receptionist_agent.get_query_system_datetime", lambda: fixed_now)

    # 1. First turn: valid future booking params
    turn1_payload = {
        "query": "Book Hair Spa at Main Salon with Marcus Johnson on 2026-07-22 at 12:00 PM.",
        "latest_message": "Book Hair Spa at Main Salon with Marcus Johnson on 2026-07-22 at 12:00 PM.",
        "session_id": session_id,
        "user_role": "CUSTOMER",
    }

    with patch("ai.agents.receptionist_agent.check_stylist_availability") as mock_avail, \
         patch("ai.agents.receptionist_agent.book_new_appointment") as mock_book, \
         patch("ai.agents.receptionist_agent.repair_branch", return_value="b1"), \
         patch("ai.agents.receptionist_agent.repair_service", return_value="s1"), \
         patch("ai.agents.receptionist_agent.repair_staff", return_value="st1"), \
         patch("ai.agents.receptionist_agent.repair_customer", return_value="c1"):
        
        mock_avail.return_value = '{"success": true, "slots": [{"start_time": "2026-07-22T12:00:00Z"}]}'
        mock_book.return_value = '{"success": true, "appointment_id": "app-111"}'
        
        res1 = await agent.process(turn1_payload)
        assert res1["success"] is True
        assert "Confirmed" in res1["response"] or "Summary" in res1["response"]

    # 2. Second turn: User says "No, I want 18 Jul 2026 10 AM." (past date)
    turn2_payload = {
        "query": "No, I want 18 Jul 2026 10 AM.",
        "latest_message": "No, I want 18 Jul 2026 10 AM.",
        "session_id": session_id,
        "user_role": "CUSTOMER",
    }

    with patch("ai.agents.receptionist_agent.check_stylist_availability") as mock_avail2, \
         patch("ai.agents.receptionist_agent.book_new_appointment") as mock_book2, \
         patch("ai.agents.receptionist_agent.repair_branch") as mock_rep_b:
        
        res2 = await agent.process(turn2_payload)

        assert res2["success"] is True
        # Must contain past date rejection message
        assert "appointments cannot be booked for past dates" in res2["response"] or "has already passed" in res2["response"]
        
        # Zero DB / availability calls!
        mock_avail2.assert_not_called()
        mock_book2.assert_not_called()
        mock_rep_b.assert_not_called()


@pytest.mark.asyncio
async def test_future_correction_remains_booking(agent, monkeypatch):
    """
    User requests:
    "No, I want 22 Jul 2026 2 PM."
    
    Expected:
    Stays in BOOKING flow and does NOT trigger cancellation.
    """
    session_id = "test-future-corr-111"
    state_svc = get_state_service()
    state_svc.delete_session(session_id)

    fixed_now = datetime(2026, 7, 21, 10, 0, tzinfo=timezone.utc)
    monkeypatch.setattr("ai.agents.receptionist_agent.get_query_system_datetime", lambda: fixed_now)

    payload = {
        "query": "No, I want Hair Spa at Main Salon on 22 Jul 2026 at 2 PM.",
        "latest_message": "No, I want Hair Spa at Main Salon on 22 Jul 2026 at 2 PM.",
        "session_id": session_id,
        "user_role": "CUSTOMER",
    }

    with patch("ai.agents.receptionist_agent.cancel_existing_appointment") as mock_cancel, \
         patch("ai.agents.receptionist_agent.check_stylist_availability") as mock_avail, \
         patch("ai.agents.receptionist_agent.book_new_appointment") as mock_book, \
         patch("ai.agents.receptionist_agent.repair_branch", return_value="b1"), \
         patch("ai.agents.receptionist_agent.repair_service", return_value="s1"), \
         patch("ai.agents.receptionist_agent.repair_staff", return_value="st1"), \
         patch("ai.agents.receptionist_agent.repair_customer", return_value="c1"):
        
        mock_avail.return_value = '{"success": true, "slots": [{"start_time": "2026-07-22T14:00:00Z"}]}'
        mock_book.return_value = '{"success": true, "appointment_id": "app-222"}'

        res = await agent.process(payload)
        
        assert res["success"] is True
        mock_cancel.assert_not_called()
        mock_avail.assert_called_once()
        mock_book.assert_not_called()
        assert "booking summary" in res["response"].lower() or "summary" in res["response"].lower()
        assert "would you like me to confirm" in res["response"].lower()
