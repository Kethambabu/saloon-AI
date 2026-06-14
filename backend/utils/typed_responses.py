"""
Typed Agent Response Models — SalonAI Workforce Platform.

Every tool and workflow must return one of these typed payloads.
The Response Renderer in utils/renderer.py converts them to final user-facing text.

Never infer the response type from text content — always use an explicit type.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────
# Response Type Enum strings (kept as literals for ease of use)
# ─────────────────────────────────────────────
BOOKING_CONFIRMATION    = "booking_confirmation"
APPOINTMENT_HISTORY     = "appointment_history"
CANCELLATION_SUCCESS    = "cancellation_success"
RESCHEDULE_SUCCESS      = "reschedule_success"
AVAILABILITY_SLOTS      = "availability_slots"
FAQ_ANSWER              = "faq_answer"
CLARIFICATION_NEEDED    = "clarification_needed"
GENERAL_CHAT            = "general_chat"
GENERAL_ERROR           = "general_error"
UPSELL_RECOMMENDATION   = "upsell_recommendation"
REVIEW_SUBMITTED        = "review_submitted"
REVIEW_ESCALATED        = "review_escalated"
LEAD_CREATED            = "lead_created"
LEAD_STATUS_ADVANCED    = "lead_status_advanced"


class TypedAgentResponse(BaseModel):
    """
    Standard structured response returned by every tool / workflow.

    The `response_type` field drives how the Response Renderer formats the
    final user-facing message.  The `text` field is an optional pre-formatted
    fallback (used when the renderer has no template for the type).
    """

    response_type: str = Field(
        ...,
        description=(
            "One of the RESPONSE_TYPE_* constants above. "
            "Used by render_response() to select the correct formatter."
        ),
    )
    text: Optional[str] = Field(
        default=None,
        description="Pre-formatted human-readable message (fallback if renderer has no template).",
    )
    data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Structured payload consumed by the renderer (appointment details, slots, etc.).",
    )
    success: bool = Field(default=True)
    error: Optional[str] = Field(default=None)

    # ── Convenience constructors ──────────────────────────────────────────────

    @classmethod
    def booking_confirmation(cls, data: Dict[str, Any]) -> "TypedAgentResponse":
        return cls(response_type=BOOKING_CONFIRMATION, data=data, success=True)

    @classmethod
    def appointment_history(cls, records: List[Dict[str, Any]]) -> "TypedAgentResponse":
        return cls(response_type=APPOINTMENT_HISTORY, data={"records": records}, success=True)

    @classmethod
    def cancellation_success(cls, data: Dict[str, Any]) -> "TypedAgentResponse":
        return cls(response_type=CANCELLATION_SUCCESS, data=data, success=True)

    @classmethod
    def reschedule_success(cls, data: Dict[str, Any]) -> "TypedAgentResponse":
        return cls(response_type=RESCHEDULE_SUCCESS, data=data, success=True)

    @classmethod
    def availability_slots(cls, slots: List[Dict[str, Any]], date: str) -> "TypedAgentResponse":
        return cls(response_type=AVAILABILITY_SLOTS, data={"slots": slots, "date": date}, success=True)

    @classmethod
    def faq_answer(cls, answer: str) -> "TypedAgentResponse":
        return cls(response_type=FAQ_ANSWER, text=answer, success=True)

    @classmethod
    def clarification_needed(cls, question: str, confidence: float = 0.0) -> "TypedAgentResponse":
        return cls(
            response_type=CLARIFICATION_NEEDED,
            text=question,
            data={"confidence": confidence},
            success=True,
        )

    @classmethod
    def general_chat(cls, message: str) -> "TypedAgentResponse":
        return cls(response_type=GENERAL_CHAT, text=message, success=True)

    @classmethod
    def general_error(cls, error: str) -> "TypedAgentResponse":
        return cls(response_type=GENERAL_ERROR, text=error, success=False, error=error)

    def to_agent_dict(self) -> Dict[str, Any]:
        """Convert to the dict format expected by agent routes and orchestrator."""
        return {
            "success": self.success,
            "response_type": self.response_type,
            "response": self.text or "",
            "data": self.data,
            "error": self.error,
        }
