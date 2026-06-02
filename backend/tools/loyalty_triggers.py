"""
Loyalty Points Update Triggers
This module ensures loyalty points are refreshed whenever key business events occur
"""

from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session

from db.models import Appointment, AppointmentStatus
from tools.loyalty_service import (
    on_appointment_completed,
    on_appointment_cancelled,
    on_review_submitted,
)


def trigger_loyalty_update_on_completion(
    db: Session,
    appointment_id: UUID,
    customer_id: UUID,
) -> bool:
    """
    Trigger loyalty points update when appointment is marked as COMPLETED
    Called from appointment status update endpoints
    """
    try:
        on_appointment_completed(db, appointment_id, customer_id)
        return True
    except Exception as e:
        print(f"Error updating loyalty on completion: {e}")
        return False


def trigger_loyalty_update_on_cancellation(
    db: Session,
    appointment_id: UUID,
    customer_id: UUID,
) -> bool:
    """
    Trigger loyalty points update when appointment is CANCELLED
    Called from appointment cancellation endpoints
    """
    try:
        on_appointment_cancelled(db, appointment_id, customer_id)
        return True
    except Exception as e:
        print(f"Error updating loyalty on cancellation: {e}")
        return False


def trigger_loyalty_update_on_review(
    db: Session,
    review_id: UUID,
    customer_id: UUID,
) -> bool:
    """
    Trigger loyalty points update when review is SUBMITTED
    Called from review creation endpoints
    """
    try:
        on_review_submitted(db, review_id, customer_id)
        return True
    except Exception as e:
        print(f"Error updating loyalty on review: {e}")
        return False
