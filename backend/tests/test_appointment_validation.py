import os
import sys
from datetime import datetime, date, time, timezone
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from application.services.datetime_validation import (
    validate_appointment_datetime,
    validateAppointmentDateTime,
)
from application.services.availability_service import get_available_slots
from application.services.appointment_service import create_appointment, reschedule_appointment
from ai.tools.capabilities import _dispatch
from core.handlers import HandlerContext, CheckAvailabilityHandler, BookAppointmentHandler, RescheduleAppointmentHandler
from mcp.salon_mcp_write import SalonMCPWrite
from mcp.schemas import MCPContext


# Fixed reference current datetime for tests: 21 Jul 2026 10:00 AM UTC
FIXED_NOW = datetime(2026, 7, 21, 10, 0, tzinfo=timezone.utc)


def test_validate_past_date():
    # Request: 18 Jul 2026 12:00 PM
    req_date = "2026-07-18"
    req_time = "12:00 PM"
    res = validate_appointment_datetime(req_date, req_time, current_server_datetime=FIXED_NOW)

    assert res["valid"] is False
    assert "I'm sorry, but appointments cannot be booked for past dates or times." in res["reason"]
    assert "18 July 2026 at 12:00 PM" in res["reason"]


def test_validate_past_time_today():
    # Request: 21 Jul 2026 9:00 AM (current is 10:00 AM)
    req_date = "2026-07-21"
    req_time = "9:00 AM"
    res = validate_appointment_datetime(req_date, req_time, current_server_datetime=FIXED_NOW)

    assert res["valid"] is False
    assert "The requested time (9:00 AM) has already passed today." in res["reason"]


def test_validate_future_time_today():
    # Request: 21 Jul 2026 11:00 AM (current is 10:00 AM)
    req_date = "2026-07-21"
    req_time = "11:00 AM"
    res = validate_appointment_datetime(req_date, req_time, current_server_datetime=FIXED_NOW)

    assert res["valid"] is True
    assert res["reason"] == ""


def test_validate_future_date():
    # Request: 22 Jul 2026 12:00 PM
    req_date = "2026-07-22"
    req_time = "12:00 PM"
    res = validate_appointment_datetime(req_date, req_time, current_server_datetime=FIXED_NOW)

    assert res["valid"] is True
    assert res["reason"] == ""


def test_camel_case_alias():
    res = validateAppointmentDateTime("2026-07-18", "12:00 PM", current_server_datetime=FIXED_NOW)
    assert res["valid"] is False


def test_get_available_slots_past_date_no_db_query(monkeypatch):
    mock_db = MagicMock()
    # Past date
    res = get_available_slots("branch-id", "2026-07-18", db=mock_db)
    
    assert res["success"] is False
    assert "18 July 2026" in res["error"]
    assert res["slots"] == []
    # Verify DB session was never queried
    mock_db.query.assert_not_called()


def test_create_appointment_past_date_no_db_query(monkeypatch):
    mock_db = MagicMock()
    res = create_appointment(
        customer_id="cust-123",
        branch_id="branch-123",
        service_id="serv-123",
        start_time="2026-07-18T12:00:00Z",
        db=mock_db
    )

    assert res["success"] is False
    assert "18 July 2026 at 12:00 PM" in res["error"]
    mock_db.query.assert_not_called()


def test_reschedule_appointment_past_date_no_db_query(monkeypatch):
    mock_db = MagicMock()
    res = reschedule_appointment(
        appointment_id="appt-123",
        new_start_time="2026-07-18T12:00:00Z",
        db=mock_db
    )

    assert res["success"] is False
    assert "18 July 2026 at 12:00 PM" in res["error"]
    mock_db.query.assert_not_called()


def test_capability_dispatch_past_date_rejection():
    res = _dispatch(
        workflow_name="appointment_workflow",
        action="check_availability",
        params={"date": "2026-07-18"},
        role="CUSTOMER"
    )
    assert "I'm sorry, but appointments cannot be booked for past dates or times." in res
    assert "18 July 2026" in res


def test_handlers_past_date_rejection():
    ctx_check = HandlerContext(params={"date": "2026-07-18"})
    handler_check = CheckAvailabilityHandler()
    res_check = handler_check.handle(ctx_check)
    assert res_check["success"] is False
    assert "18 July 2026" in res_check["error"]

    ctx_book = HandlerContext(params={"start_time": "2026-07-18T12:00:00Z", "service_id": "s1"})
    handler_book = BookAppointmentHandler()
    res_book = handler_book.handle(ctx_book)
    assert res_book["success"] is False
    assert "18 July 2026 at 12:00 PM" in res_book["error"]

    ctx_resched = HandlerContext(params={"appointment_id": "a1", "new_start_time": "2026-07-18T12:00:00Z"})
    handler_resched = RescheduleAppointmentHandler()
    res_resched = handler_resched.handle(ctx_resched)
    assert res_resched["success"] is False
    assert "18 July 2026 at 12:00 PM" in res_resched["error"]


def test_mcp_write_past_date_rejection():
    mcp_writer = SalonMCPWrite()
    ctx = MCPContext(user_id="user1", role="CUSTOMER")

    res = mcp_writer.execute_write(
        context=ctx,
        resource="appointments",
        operation="insert",
        data={"start_time": "2026-07-18T12:00:00Z"}
    )
    assert res.success is False
    assert res.error_code == "PAST_DATETIME_INVALID"
    assert "18 July 2026 at 12:00 PM" in res.error
