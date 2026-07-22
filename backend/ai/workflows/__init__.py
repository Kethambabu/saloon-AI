"""
Workflows Layer — Orchestrates multi-step business transactions for agents.

Exports:
  - Legacy workflow functions (backward-compatible, used by existing agents)
  - Phase 1 Workflow Classes (AppointmentWorkflow, CRMWorkflow, etc.)
"""

# ---------------------------------------------------------------------------
# Legacy workflow functions — BACKWARD COMPATIBLE
# ---------------------------------------------------------------------------
from ai.workflows.booking_workflow import (
    book_appointment_workflow,
    cancel_appointment_workflow,
    reschedule_appointment_workflow,
    check_availability_workflow,
)

from ai.workflows.lead_workflow import (
    create_lead_workflow,
    advance_lead_status_workflow,
    create_followup_reminder_workflow,
    generate_followup_message_workflow,
    detect_abandoned_bookings_workflow,
)

from ai.workflows.review_workflow import (
    respond_to_review_workflow,
    escalate_review_workflow,
)

from ai.workflows.upsell_workflow import (
    get_customer_recommendations_workflow,
    accept_recommendation_workflow,
    reject_recommendation_workflow,
    get_upsell_analytics_workflow,
)

from ai.workflows.notification_workflow import (
    create_notification_workflow,
    clear_user_notifications_workflow,
)

# ---------------------------------------------------------------------------
# Phase 1 Workflow Classes
# ---------------------------------------------------------------------------
from ai.workflows.appointment_workflow import AppointmentWorkflow
from ai.workflows.crm_workflow import CRMWorkflow
from ai.workflows.recommendation_workflow import RecommendationWorkflow
from ai.workflows.review_workflow import ReviewWorkflow
from ai.workflows.staff_workflow import StaffWorkflow
from ai.workflows.analytics_workflow import AnalyticsWorkflow

__all__ = [
    # Legacy booking functions (backward-compatible)
    "book_appointment_workflow",
    "cancel_appointment_workflow",
    "reschedule_appointment_workflow",
    "check_availability_workflow",

    # Legacy lead functions (backward-compatible)
    "create_lead_workflow",
    "advance_lead_status_workflow",
    "create_followup_reminder_workflow",
    "generate_followup_message_workflow",
    "detect_abandoned_bookings_workflow",

    # Legacy review functions (backward-compatible)
    "respond_to_review_workflow",
    "escalate_review_workflow",

    # Legacy upsell functions (backward-compatible)
    "get_customer_recommendations_workflow",
    "accept_recommendation_workflow",
    "reject_recommendation_workflow",
    "get_upsell_analytics_workflow",

    # Notifications
    "create_notification_workflow",
    "clear_user_notifications_workflow",

    # Phase 1 Workflow Classes
    "AppointmentWorkflow",
    "CRMWorkflow",
    "RecommendationWorkflow",
    "ReviewWorkflow",
    "StaffWorkflow",
    "AnalyticsWorkflow",
]

