"""
Lead Workflows — Orchestrating lead follow-ups, acquisition, and CRM pipeline changes.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from application.services.lead_service import (
    create_lead,
    update_lead_status,
    create_followup_reminder,
    generate_followup_message,
    detect_abandoned_bookings,
)

logger = logging.getLogger(__name__)


def create_lead_workflow(
    first_name: str,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    last_name: Optional[str] = None,
    source: Optional[str] = None,
    branch_id: Optional[Any] = None,
    notes: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Workflow to register a new CRM lead."""
    return create_lead(
        first_name=first_name,
        email=email,
        phone=phone,
        last_name=last_name,
        source=source,
        branch_id=branch_id,
        notes=notes,
    )


def advance_lead_status_workflow(
    lead_id: Any,
    new_status: str,
    notes: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Workflow to move a lead forward in the CRM status pipeline."""
    return update_lead_status(
        lead_id=lead_id,
        new_status=new_status,
        notes=notes,
    )


def create_followup_reminder_workflow(
    lead_id: Any,
    channel: str,
    message: str,
    scheduled_at: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Workflow to schedule a lead outreach task."""
    return create_followup_reminder(
        lead_id=lead_id,
        channel=channel,
        message=message,
        scheduled_at=scheduled_at,
    )


def generate_followup_message_workflow(
    customer_id: Optional[Any] = None,
    lead_id: Optional[Any] = None,
    channel: str = "email",
    tone: str = "warm",
    **kwargs: Any,
) -> Dict[str, Any]:
    """Workflow to draft a personalized follow-up message."""
    return generate_followup_message(
        customer_id=customer_id,
        lead_id=lead_id,
        channel=channel,
        tone=tone,
    )


def detect_abandoned_bookings_workflow(
    branch_id: Optional[Any] = None,
    lookback_days: int = 30,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Workflow to detect abandoned bookings."""
    return detect_abandoned_bookings(
        branch_id=branch_id,
        lookback_days=lookback_days,
    )

