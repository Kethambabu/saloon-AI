"""
Response Renderer — SalonAI Workforce Platform.

Converts TypedAgentResponse payloads into clean, customer-facing Markdown.
Agents should never manually construct final user-facing text — they return a
TypedAgentResponse and this module formats it.

Zenoti smart upsell injection lives here, not in receptionist_agent.py.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.typed_responses import (
    BOOKING_CONFIRMATION,
    APPOINTMENT_HISTORY,
    CANCELLATION_SUCCESS,
    RESCHEDULE_SUCCESS,
    AVAILABILITY_SLOTS,
    FAQ_ANSWER,
    CLARIFICATION_NEEDED,
    GENERAL_CHAT,
    GENERAL_ERROR,
    UPSELL_RECOMMENDATION,
    REVIEW_SUBMITTED,
    REVIEW_ESCALATED,
    LEAD_CREATED,
    LEAD_STATUS_ADVANCED,
    TypedAgentResponse,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _fmt_dt(iso_str: Optional[str]) -> str:
    """Format ISO datetime string to human-readable form."""
    if not iso_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%A, %B %d, %Y at %I:%M %p")
    except Exception:
        return iso_str


def _zenoti_upsells(service_name: str) -> str:
    """Return the Zenoti smart upsell block appropriate for the service."""
    svc = (service_name or "").lower()
    if "haircut" in svc or "hair cut" in svc:
        items = [
            "🌿 Hair Spa ($55)",
            "💆 Special Head Massage ($25)",
            "✂️ Professional Beard Styling ($35)",
        ]
    elif "massage" in svc:
        items = [
            "🧖 Luxury Facial Treatment ($120)",
            "🧂 Himalayan Sea Salt Foot Wash ($30)",
        ]
    elif "facial" in svc or "face" in svc:
        items = [
            "💆 Special Head Massage ($25)",
            "🌿 Deep Conditioning Treatment ($45)",
        ]
    else:
        items = [
            "✂️ Signature Precision Haircut ($85)",
            "💆 Special Head Massage ($25)",
        ]
    return "\n🎁 **Recommended Add-on Treatments** *(Zenoti smart upsell)*:\n" + "\n".join(f"  - {i}" for i in items)


# ─────────────────────────────────────────────────────────────────────────────
# Renderers per response_type
# ─────────────────────────────────────────────────────────────────────────────

def _render_booking_confirmation(data: Dict[str, Any]) -> str:
    service  = data.get("service_name", "Styling Session")
    branch   = data.get("branch_name", "Our Salon")
    stylist  = data.get("staff_name") or data.get("stylist_name") or "Any Available Stylist"
    date     = data.get("date") or data.get("start_time", "")[:10]
    time_raw = data.get("time") or (data.get("start_time", ""))[11:16]
    price    = data.get("price") or data.get("service_price", "")

    # Format datetime nicely if full ISO string available
    if data.get("start_time") and "T" in data.get("start_time", ""):
        nice_dt = _fmt_dt(data["start_time"])
    else:
        nice_dt = f"{date} at {time_raw}" if date else "N/A"

    lines = [
        "✅ **Appointment Confirmed!**\n",
        "| Field | Details |",
        "|-------|---------|",
        f"| **Service** | {service} |",
        f"| **Branch** | {branch} |",
        f"| **Stylist** | {stylist} |",
        f"| **Date & Time** | {nice_dt} |",
    ]
    if price:
        lines.append(f"| **Price** | ${price} |")

    lines.append("\n**Status:** Confirmed")
    lines.append(_zenoti_upsells(service))
    return "\n".join(lines)


def _render_appointment_history(data: Dict[str, Any]) -> str:
    records: List[Dict[str, Any]] = data.get("records", [])
    if not records:
        return "📋 You have no past appointments on record with us."

    lines = ["📋 **Your Appointment History:**\n"]
    for appt in records:
        svc    = appt.get("service_name", "Styling Session")
        staff  = appt.get("staff_name", "Stylist")
        branch = appt.get("branch_name", "Salon")
        status = (appt.get("status") or "CONFIRMED").upper()
        dt     = _fmt_dt(appt.get("start_time"))
        price  = appt.get("service_price") or appt.get("price", "")
        price_str = f" · ${price}" if price else ""
        lines.append(f"- **{svc}**{price_str} with {staff} at {branch} · {dt} · `{status}`")

    return "\n".join(lines)


def _render_cancellation_success(data: Dict[str, Any]) -> str:
    appt_id = data.get("appointment_id", "")
    ref     = f" (Ref: `{appt_id[:8]}...`)" if appt_id else ""
    return (
        f"❌ **Appointment Cancelled**{ref}\n\n"
        "Your booking has been successfully cancelled. "
        "We hope to see you again soon — feel free to rebook anytime!"
    )


def _render_reschedule_success(data: Dict[str, Any]) -> str:
    new_time = _fmt_dt(data.get("start_time") or data.get("new_start_time"))
    return (
        f"🔄 **Appointment Rescheduled**\n\n"
        f"Your appointment has been successfully moved to **{new_time}**.\n"
        "We look forward to seeing you!"
    )


def _render_availability_slots(data: Dict[str, Any]) -> str:
    slots: List[Dict[str, Any]] = data.get("slots", [])
    date  = data.get("date", "your selected date")

    if not slots:
        return f"🕐 Sorry, there are no available slots for **{date}**. Please try a different date."

    lines = [f"🕐 **Available Slots for {date}:**\n"]
    for slot in slots:
        start = slot.get("start_time", "")
        try:
            dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            nice = dt.strftime("%I:%M %p")
        except Exception:
            nice = start

        staff_names: List[str] = slot.get("available_staff_names", [])
        staff_str = f" · Stylists: {', '.join(staff_names)}" if staff_names else ""
        lines.append(f"  - **{nice}**{staff_str}")

    return "\n".join(lines)


def _render_faq_answer(text: str) -> str:
    # FAQ answers are already clean text from the knowledge base; just pass through
    return text or "I couldn't find that information in the salon knowledge base."


def _render_clarification_needed(text: str, data: Optional[Dict] = None) -> str:
    confidence = (data or {}).get("confidence", 0.0)
    prefix = "🤔 " if confidence < 0.70 else ""
    return f"{prefix}{text}"


def _render_general_error(text: str) -> str:
    # Sanitise technical jargon before returning to user
    sanitise_map = {
        "429": "temporary high volume",
        "rate limit": "temporary slot holds",
        "quota exceeded": "system adjustments",
        "uuid": "reference number",
        "UUID": "reference number",
        "postgresql": "system",
        "supabase": "system",
        "sqlite": "system",
        "tool execution error": "scheduling adjustment",
        "additionalproperties": "parameter alignment",
    }
    out = text or "An unexpected issue occurred. Please try again."
    for tech, clean in sanitise_map.items():
        import re
        out = re.sub(re.escape(tech), clean, out, flags=re.IGNORECASE)
    return f"⚠️ {out}"


def _render_upsell_recommendation(data: Dict[str, Any]) -> str:
    recs = data.get("recommendations", [])
    if not recs:
        return "No personalised recommendations at this time."
    lines = ["💡 **Personalised Recommendations for You:**\n"]
    for r in recs:
        rtype = r.get("type", "").capitalize()
        name  = r.get("suggested") or r.get("service") or r.get("name", "Service")
        price = r.get("price_diff") or r.get("price", "")
        reason = r.get("reason", "")
        price_str = f" · {price}" if price else ""
        reason_str = f" — _{reason}_" if reason else ""
        lines.append(f"- **{rtype}: {name}**{price_str}{reason_str}")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def render_response(payload: Dict[str, Any]) -> str:
    """
    Convert a TypedAgentResponse payload dict into a clean, customer-facing
    Markdown string.

    Parameters
    ----------
    payload : dict
        Must contain at least ``response_type``.  Typically also contains
        ``data`` (structured payload) and/or ``text`` (pre-formatted fallback).

    Returns
    -------
    str
        Customer-facing Markdown string.
    """
    if not payload:
        return "Hello! I'm Clara, your AI Salon Receptionist. How can I help you today?"

    response_type = payload.get("response_type", GENERAL_CHAT)
    data          = payload.get("data") or {}
    text          = payload.get("text") or payload.get("response") or ""

    try:
        if response_type == BOOKING_CONFIRMATION:
            return _render_booking_confirmation(data)

        if response_type == APPOINTMENT_HISTORY:
            return _render_appointment_history(data)

        if response_type == CANCELLATION_SUCCESS:
            return _render_cancellation_success(data)

        if response_type == RESCHEDULE_SUCCESS:
            return _render_reschedule_success(data)

        if response_type == AVAILABILITY_SLOTS:
            return _render_availability_slots(data)

        if response_type == FAQ_ANSWER:
            return _render_faq_answer(text)

        if response_type == CLARIFICATION_NEEDED:
            return _render_clarification_needed(text, data)

        if response_type == GENERAL_ERROR:
            return _render_general_error(text)

        if response_type == UPSELL_RECOMMENDATION:
            return _render_upsell_recommendation(data)

        if response_type in (REVIEW_SUBMITTED, REVIEW_ESCALATED):
            return text or "Your review has been processed. Thank you!"

        if response_type in (LEAD_CREATED, LEAD_STATUS_ADVANCED):
            return text or "Lead record updated successfully."

        # Fallback: general chat / unknown type
        return text or "I'm here to help! What would you like to do?"

    except Exception as exc:
        logger.error("[Renderer] Error rendering response_type='%s': %s", response_type, exc, exc_info=True)
        return text or "I'm having trouble formatting my response. Please try again."

