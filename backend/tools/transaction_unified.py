"""
Unified Write-Transaction Dispatcher Tool for SalonAI Workforce Platform.
Consolidates all state-changing mutations and transactional workflows under a single schema.
"""

import logging
from typing import Dict, Any, Optional, Union

logger = logging.getLogger(__name__)

def execute_transaction(action: str, parameters: Union[Dict[str, Any], str]) -> str:
    """
    Execute a state-changing write transaction or database workflow.

    Args:
        action: The name of the transactional action to execute. Must be one of:
            - 'book_appointment': Create a new appointment booking.
            - 'cancel_appointment': Cancel an existing booking.
            - 'reschedule_appointment': Reschedule a booking to a new time.
            - 'register_lead': Register a prospect client in CRM.
            - 'advance_lead_status': Advance a CRM lead stage.
            - 'send_followup': Send/schedule an outreach reminder to a lead.
            - 'draft_review_response': Respond to a customer review.
            - 'escalate_review': Escalate a negative customer review.
            - 'create_leave_request': Stylist leave logging.
            - 'send_customer_reminders': Dispatch notifications to stylist's clients.
            - 'accept_upsell_recommendation': Record accepted add-on service.
            - 'reject_upsell_recommendation': Record rejected upsell offer.
        parameters: A key-value dictionary containing the parameters required for the specific action.
    """
    action_lower = str(action).strip().lower()
    params = parameters or {}
    if isinstance(params, str) and params.strip():
        try:
            import json
            params = json.loads(params)
        except Exception:
            params = {}
    if not isinstance(params, dict):
        params = {}
    
    logger.info(f"[TransactionUnified] Executing transaction: action='{action_lower}', params={list(params.keys())}")

    try:
        # Booking transactions
        if action_lower == "book_appointment":
            from agents.receptionist_agent import book_new_appointment
            return book_new_appointment(
                customer_id=params.get("customer_id"),
                branch_id=params.get("branch_id"),
                service_id=params.get("service_id"),
                start_time=params.get("start_time"),
                staff_id=params.get("staff_id"),
                notes=params.get("notes"),
            )

        elif action_lower == "cancel_appointment":
            from agents.receptionist_agent import cancel_existing_appointment
            return cancel_existing_appointment(
                appointment_id=params.get("appointment_id"),
            )

        elif action_lower == "reschedule_appointment":
            from agents.receptionist_agent import reschedule_existing_appointment
            return reschedule_existing_appointment(
                appointment_id=params.get("appointment_id"),
                new_start_time=params.get("new_start_time"),
            )

        # CRM & Lead transactions
        elif action_lower == "register_lead":
            from agents.lead_followup_agent import register_new_lead
            return register_new_lead(
                first_name=params.get("first_name"),
                email=params.get("email"),
                phone=params.get("phone"),
                last_name=params.get("last_name"),
                source=params.get("source"),
                branch_id=params.get("branch_id"),
                notes=params.get("notes"),
            )

        elif action_lower == "advance_lead_status":
            from agents.lead_followup_agent import advance_lead_status
            return advance_lead_status(
                lead_id=params.get("lead_id"),
                new_status=params.get("new_status"),
                notes=params.get("notes"),
            )

        elif action_lower == "send_followup":
            from agents.lead_followup_agent import send_followup_reminder
            return send_followup_reminder(
                lead_id=params.get("lead_id"),
                channel=params.get("channel"),
                message=params.get("message"),
                scheduled_at=params.get("scheduled_at"),
            )

        # Review & Reputation transactions
        elif action_lower == "draft_review_response":
            from agents.reputation_agent import draft_review_response
            return draft_review_response(
                review_id=params.get("review_id"),
                custom_response=params.get("custom_response"),
            )

        elif action_lower == "escalate_review":
            from agents.reputation_agent import escalate_customer_review
            return escalate_customer_review(
                review_id=params.get("review_id"),
            )

        # Staff productivity transactions
        elif action_lower == "create_leave_request":
            from tools.staff_tools import create_leave_request
            return create_leave_request(
                staff_id=params.get("staff_id"),
                leave_date=params.get("leave_date"),
                reason=params.get("reason"),
            )

        elif action_lower == "send_customer_reminders":
            from tools.staff_tools import send_customer_reminders
            return send_customer_reminders(
                staff_id=params.get("staff_id"),
            )

        # Upsell transactions
        elif action_lower == "accept_upsell_recommendation":
            from agents.upsell_agent import accept_recommendation
            return accept_recommendation(
                customer_id=params.get("customer_id"),
                service_id=params.get("service_id"),
                appointment_id=params.get("appointment_id"),
            )

        elif action_lower == "reject_upsell_recommendation":
            from agents.upsell_agent import reject_recommendation
            return reject_recommendation(
                customer_id=params.get("customer_id"),
                service_id=params.get("service_id"),
                appointment_id=params.get("appointment_id"),
            )

        else:
            supported = [
                "book_appointment", "cancel_appointment", "reschedule_appointment",
                "register_lead", "advance_lead_status", "send_followup",
                "draft_review_response", "escalate_review", "create_leave_request",
                "send_customer_reminders", "accept_upsell_recommendation",
                "reject_upsell_recommendation"
            ]
            return f"Error: Unknown transaction action '{action_lower}'. Supported actions: {', '.join(supported)}"

    except Exception as e:
        logger.error(f"Error executing write transaction '{action_lower}': {str(e)}", exc_info=True)
        return f"Error executing write transaction: {str(e)}"
