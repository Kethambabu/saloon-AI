"""
Booking Workflows — Orchestrating appointment bookings, cancellations, and reschedules.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from application.services.appointment_service import (
    create_appointment,
    cancel_appointment,
    reschedule_appointment,
    get_available_slots,
)
from core.typed_responses import TypedAgentResponse

logger = logging.getLogger(__name__)


def book_appointment_workflow(
    customer_id: Any,
    branch_id: Any,
    service_id: Any,
    start_time: Any,
    staff_id: Optional[Any] = None,
    notes: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Workflow to book a new salon appointment.
    Coordinates validation, slot checking, creation, and notifications.
    """
    logger.info("[Workflow] Starting book_appointment_workflow for customer=%s", customer_id)
    result = create_appointment(
        customer_id=customer_id,
        branch_id=branch_id,
        service_id=service_id,
        start_time=start_time,
        staff_id=staff_id,
        notes=notes,
    )
    logger.info("[Workflow] book_appointment_workflow completed: success=%s", result.get("success"))
    if result.get("success"):
        return TypedAgentResponse.booking_confirmation(result).to_agent_dict()
    else:
        return TypedAgentResponse.general_error(result.get("error", "Failed to book appointment")).to_agent_dict()


def cancel_appointment_workflow(
    appointment_id: Any,
    customer_id: Optional[Any] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Workflow to cancel an existing appointment.
    Coordinates cancellation window validation and loyalty updates.
    """
    logger.info("[Workflow] Starting cancel_appointment_workflow for appointment=%s", appointment_id)
    result = cancel_appointment(
        appointment_id=appointment_id,
        customer_id=customer_id,
    )
    logger.info("[Workflow] cancel_appointment_workflow completed: success=%s", result.get("success"))
    if result.get("success"):
        return TypedAgentResponse.cancellation_success(result).to_agent_dict()
    else:
        return TypedAgentResponse.general_error(result.get("error", "Failed to cancel appointment")).to_agent_dict()


def reschedule_appointment_workflow(
    appointment_id: Any,
    new_start_time: Any,
    new_staff_id: Optional[Any] = None,
    customer_id: Optional[Any] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Workflow to reschedule an existing appointment.
    Coordinates slot checking, overlap validation, and rescheduling updates.
    """
    logger.info("[Workflow] Starting reschedule_appointment_workflow for appointment=%s", appointment_id)
    result = reschedule_appointment(
        appointment_id=appointment_id,
        new_start_time=new_start_time,
        customer_id=customer_id,
    )
    logger.info("[Workflow] reschedule_appointment_workflow completed: success=%s", result.get("success"))
    if result.get("success"):
        return TypedAgentResponse.reschedule_success(result).to_agent_dict()
    else:
        return TypedAgentResponse.general_error(result.get("error", "Failed to reschedule appointment")).to_agent_dict()


def check_availability_workflow(
    branch_id: Any,
    date_str: str,
    staff_id: Optional[Any] = None,
    service_id: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Workflow to check available booking slots.
    """
    logger.info("[Workflow] Starting check_availability_workflow for branch=%s, date=%s", branch_id, date_str)
    result = get_available_slots(
        branch_id=branch_id,
        date_str=date_str,
        staff_id=staff_id,
        service_id=service_id,
    )
    if result.get("success"):
        return TypedAgentResponse.availability_slots(
            slots=result.get("slots", []),
            date=result.get("date", date_str)
        ).to_agent_dict()
    elif result.get("staff_on_leave"):
        res_dict = TypedAgentResponse.general_error(result.get("error")).to_agent_dict()
        res_dict["staff_on_leave"] = True
        res_dict["staff_name"] = result.get("staff_name")
        res_dict["date"] = result.get("date")
        res_dict["slots"] = result.get("slots")
        return res_dict
    else:
        return TypedAgentResponse.general_error(result.get("error", "Failed to get available slots")).to_agent_dict()


