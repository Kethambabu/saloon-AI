"""
Lead & CRM Business Tools for SalonAI Workforce Platform.

Provides robust transactional functions for:
  - Detecting abandoned bookings (cancelled / no-show patterns)
  - Managing leads through the CRM pipeline (NEW → CONTACTED → CONVERTED / LOST)
  - Creating and tracking follow-up tasks with scheduling
  - Generating personalised follow-up messages
  - Tracking lead conversion analytics
  - Generating notification payloads (email / SMS / push)

All functions follow the same enterprise patterns used in booking_tools.py:
  - SQLAlchemy ORM queries with proper session management
  - UUID validation, structured JSON responses, exception handling
  - Comprehensive logging at every decision point
"""

import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, case, desc

# Project imports
from db.database import SessionLocal, db_transaction
from db.models import (
    Lead,
    LeadStatus,
    Customer,
    Appointment,
    AppointmentStatus,
    Branch,
    Service,
    Staff,
    User,
    Notification,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _parse_uuid(value: Any, name: str = "id") -> uuid.UUID:
    """Validate and parse a UUID from string or UUID input."""
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except ValueError as e:
        raise ValueError(f"Invalid UUID format for {name}: '{value}'") from e


# ---------------------------------------------------------------------------
# 1. Abandoned Booking Detection
# ---------------------------------------------------------------------------
def detect_abandoned_bookings(
    branch_id: Optional[Any] = None,
    lookback_days: int = 30,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """
    Identifies customers with cancelled or no-show appointments who have NOT
    rebooked since, signalling potential churn / abandoned intent.

    Args:
        branch_id: Optional branch UUID to scope the search. Omit for all branches.
        lookback_days: How many days back to scan (default 30).

    Returns:
        Structured JSON with a list of abandoned booking records.
    """
    logger.info(
        f"[LeadTools] Detecting abandoned bookings (branch={branch_id}, lookback={lookback_days}d)"
    )

    session = db or SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

        # Base query: cancelled or no-show appointments in the window
        q = session.query(Appointment).filter(
            Appointment.status.in_([AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW]),
            Appointment.start_time >= cutoff,
        )

        if branch_id:
            b_id = _parse_uuid(branch_id, "branch_id")
            q = q.filter(Appointment.branch_id == b_id)

        abandoned_appts = q.order_by(desc(Appointment.start_time)).all()

        # For each customer, check if they have a subsequent CONFIRMED / COMPLETED booking
        results: List[Dict[str, Any]] = []
        seen_customers = set()

        for appt in abandoned_appts:
            cid = appt.customer_id
            if cid in seen_customers:
                continue
            seen_customers.add(cid)

            # Has the customer rebooked after this appointment?
            rebooked = session.query(Appointment).filter(
                Appointment.customer_id == cid,
                Appointment.status.in_([
                    AppointmentStatus.CONFIRMED,
                    AppointmentStatus.COMPLETED,
                    AppointmentStatus.PENDING,
                ]),
                Appointment.start_time > appt.start_time,
            ).first()

            if rebooked:
                continue  # Customer already rebooked — not abandoned

            customer = session.query(Customer).filter(Customer.id == cid).first()
            service = session.query(Service).filter(Service.id == appt.service_id).first()
            branch = session.query(Branch).filter(Branch.id == appt.branch_id).first()

            results.append({
                "customer_id": str(cid),
                "customer_name": customer.full_name if customer else "Unknown",
                "email": customer.email if customer else None,
                "phone": customer.phone if customer else None,
                "last_appointment_id": str(appt.id),
                "last_status": appt.status.value,
                "last_service": service.name if service else None,
                "last_branch": branch.name if branch else None,
                "abandoned_date": appt.start_time.isoformat(),
                "days_since": (datetime.now(timezone.utc) - appt.start_time.replace(tzinfo=timezone.utc)).days,
            })

        logger.info(f"[LeadTools] Found {len(results)} abandoned booking customers")
        return {
            "success": True,
            "abandoned_count": len(results),
            "lookback_days": lookback_days,
            "records": results,
        }

    except Exception as e:
        logger.error(f"[LeadTools] Error detecting abandoned bookings: {e}", exc_info=True)
        return {"success": False, "error": f"Database error: {str(e)}"}
    finally:
        if not db:
            session.close()


# ---------------------------------------------------------------------------
# 2. Lead Pipeline Management (CRM CRUD)
# ---------------------------------------------------------------------------
def get_all_leads(
    status_filter: Optional[str] = None,
    branch_id: Optional[Any] = None,
    source_filter: Optional[str] = None,
    limit: int = 50,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """
    Retrieves leads from the CRM database with optional filtering.

    Args:
        status_filter: Filter by lead status ('NEW', 'CONTACTED', 'CONVERTED', 'LOST'). Omit for all.
        branch_id: Optional branch UUID to scope leads.
        source_filter: Filter by lead source (e.g. 'Instagram Ad', 'Website Form').
        limit: Maximum number of leads to return (default 50).

    Returns:
        Structured JSON with matching leads and summary counts.
    """
    logger.info(
        f"[LeadTools] Fetching leads (status={status_filter}, branch={branch_id}, source={source_filter})"
    )

    session = db or SessionLocal()
    try:
        q = session.query(Lead)

        if status_filter:
            try:
                status_enum = LeadStatus(status_filter.upper())
                q = q.filter(Lead.status == status_enum)
            except ValueError:
                return {"success": False, "error": f"Invalid status: '{status_filter}'. Use NEW, CONTACTED, CONVERTED, or LOST."}

        if branch_id:
            b_id = _parse_uuid(branch_id, "branch_id")
            q = q.filter(Lead.branch_id == b_id)

        if source_filter:
            q = q.filter(Lead.source.ilike(f"%{source_filter}%"))

        leads = q.order_by(desc(Lead.created_at)).limit(limit).all()

        lead_list = []
        for lead in leads:
            branch = session.query(Branch).filter(Branch.id == lead.branch_id).first() if lead.branch_id else None
            lead_list.append({
                "id": str(lead.id),
                "name": lead.full_name,
                "email": lead.email,
                "phone": lead.phone,
                "source": lead.source,
                "status": lead.status.value,
                "branch": branch.name if branch else None,
                "notes": lead.notes,
                "created_at": lead.created_at.isoformat() if lead.created_at else None,
            })

        return {
            "success": True,
            "total": len(lead_list),
            "leads": lead_list,
        }

    except Exception as e:
        logger.error(f"[LeadTools] Error fetching leads: {e}", exc_info=True)
        return {"success": False, "error": f"Database error: {str(e)}"}
    finally:
        if not db:
            session.close()


def create_lead(
    first_name: str,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    last_name: Optional[str] = None,
    source: Optional[str] = None,
    branch_id: Optional[Any] = None,
    notes: Optional[str] = None,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """
    Creates a new lead entry in the CRM pipeline.

    Args:
        first_name: Lead's first name (required).
        email: Email address.
        phone: Phone number.
        last_name: Last name.
        source: Acquisition source (e.g. 'Instagram Ad', 'Walk-in', 'Referral').
        branch_id: UUID of the interested branch location.
        notes: Free-text notes about the inquiry.

    Returns:
        Structured JSON with the created lead record.
    """
    logger.info(f"[LeadTools] Creating new lead: {first_name} {last_name or ''}")

    if not first_name or not first_name.strip():
        return {"success": False, "error": "first_name is required."}

    session = db or SessionLocal()
    try:
        b_id = None
        if branch_id:
            b_id = _parse_uuid(branch_id, "branch_id")
            branch = session.query(Branch).filter(Branch.id == b_id).first()
            if not branch:
                return {"success": False, "error": f"Branch {b_id} not found."}

        new_lead = Lead(
            first_name=first_name.strip(),
            last_name=last_name.strip() if last_name else None,
            email=email.strip().lower() if email else None,
            phone=phone.strip() if phone else None,
            source=source,
            branch_id=b_id,
            notes=notes,
            status=LeadStatus.NEW,
        )

        if db:
            session.add(new_lead)
            session.flush()
        else:
            with db_transaction() as tx:
                tx.add(new_lead)

        logger.info(f"[LeadTools] Created lead {new_lead.id}")
        return {
            "success": True,
            "lead_id": str(new_lead.id),
            "name": new_lead.full_name,
            "status": new_lead.status.value,
            "message": "Lead created successfully.",
        }

    except Exception as e:
        logger.error(f"[LeadTools] Error creating lead: {e}", exc_info=True)
        return {"success": False, "error": f"Database error: {str(e)}"}
    finally:
        if not db:
            session.close()


def update_lead_status(
    lead_id: Any,
    new_status: str,
    notes: Optional[str] = None,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """
    Advances a lead through the CRM pipeline by updating its status.

    Args:
        lead_id: UUID of the lead to update.
        new_status: New status ('NEW', 'CONTACTED', 'CONVERTED', 'LOST').
        notes: Optional additional notes to append.

    Returns:
        Structured JSON confirming the status transition.
    """
    logger.info(f"[LeadTools] Updating lead {lead_id} status → {new_status}")

    try:
        l_id = _parse_uuid(lead_id, "lead_id")
        status_enum = LeadStatus(new_status.upper())
    except ValueError as e:
        return {"success": False, "error": str(e)}

    session = db or SessionLocal()
    try:
        lead = session.query(Lead).filter(Lead.id == l_id).first()
        if not lead:
            return {"success": False, "error": f"Lead {l_id} not found."}

        old_status = lead.status.value
        lead.status = status_enum

        if notes:
            existing = lead.notes or ""
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
            lead.notes = f"{existing}\n[{timestamp}] {notes}".strip()

        if db:
            session.flush()
        else:
            session.commit()

        logger.info(f"[LeadTools] Lead {l_id} transitioned: {old_status} → {status_enum.value}")
        return {
            "success": True,
            "lead_id": str(l_id),
            "previous_status": old_status,
            "new_status": status_enum.value,
            "message": f"Lead status updated from {old_status} to {status_enum.value}.",
        }

    except Exception as e:
        logger.error(f"[LeadTools] Error updating lead status: {e}", exc_info=True)
        if not db:
            session.rollback()
        return {"success": False, "error": f"Database error: {str(e)}"}
    finally:
        if not db:
            session.close()


# ---------------------------------------------------------------------------
# 3. Follow-up Reminder Scheduling
# ---------------------------------------------------------------------------
def create_followup_reminder(
    lead_id: Any,
    channel: str,
    message: str,
    scheduled_at: Optional[str] = None,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """
    Schedules a follow-up reminder for a lead via a specified communication channel.
    Appends the follow-up action as a timestamped note on the lead record and
    returns a notification payload ready for dispatch.

    Args:
        lead_id: UUID of the target lead.
        channel: Communication channel – 'email', 'sms', or 'phone'.
        message: Personalised message content for the follow-up.
        scheduled_at: ISO datetime for when to send (default: immediately).

    Returns:
        Structured JSON with the follow-up task details and notification payload.
    """
    logger.info(f"[LeadTools] Creating follow-up for lead {lead_id} via {channel}")

    valid_channels = {"email", "sms", "phone"}
    if channel.lower() not in valid_channels:
        return {"success": False, "error": f"Invalid channel '{channel}'. Use: {', '.join(valid_channels)}"}

    if not message or not message.strip():
        return {"success": False, "error": "Follow-up message content is required."}

    try:
        l_id = _parse_uuid(lead_id, "lead_id")
    except ValueError as e:
        return {"success": False, "error": str(e)}

    send_time = datetime.now(timezone.utc)
    if scheduled_at:
        try:
            if scheduled_at.endswith("Z"):
                scheduled_at = scheduled_at[:-1] + "+00:00"
            send_time = datetime.fromisoformat(scheduled_at)
            if send_time.tzinfo is None:
                send_time = send_time.replace(tzinfo=timezone.utc)
        except ValueError:
            return {"success": False, "error": f"Invalid scheduled_at datetime: '{scheduled_at}'"}

    session = db or SessionLocal()
    try:
        lead = session.query(Lead).filter(Lead.id == l_id).first()
        if not lead:
            return {"success": False, "error": f"Lead {l_id} not found."}

        # Append follow-up action as a note
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        followup_note = f"[{timestamp}] FOLLOW-UP ({channel.upper()}): {message[:120]}"
        existing_notes = lead.notes or ""
        lead.notes = f"{existing_notes}\n{followup_note}".strip()

        # Advance status to CONTACTED if currently NEW
        status_advanced = False
        if lead.status == LeadStatus.NEW:
            lead.status = LeadStatus.CONTACTED
            status_advanced = True

        # Update Lead stats
        lead.followup_count += 1
        lead.last_contacted = datetime.now(timezone.utc)

        # Log in-app notification if customer/user exists
        from db.models import ChatLog, UserRole
        user = None
        if lead.customer_id:
            user = session.query(User).filter(User.customer_id == lead.customer_id).first()
            
        # Session ID extraction from notes to find User who initiated the chat
        session_id = None
        if not user and lead.notes and "Session ID:" in lead.notes:
            for line in lead.notes.split("\n"):
                if "Session ID:" in line:
                    session_id = line.replace("Session ID:", "").strip()
                    break
        if not user and session_id:
            log = session.query(ChatLog).filter(ChatLog.session_id == session_id).first()
            if log and log.user_id:
                user = session.query(User).filter(User.id == log.user_id).first()

        if not user and lead.customer_email:
            customer = session.query(Customer).filter(Customer.email.ilike(lead.customer_email)).first()
            if customer:
                if not lead.customer_id:
                    lead.customer_id = customer.id
                    session.flush()
                user = session.query(User).filter(User.customer_id == customer.id).first()
            if not user:
                user = session.query(User).filter(User.email.ilike(lead.customer_email)).first()
                
        if not user and lead.customer_phone:
            customer = session.query(Customer).filter(Customer.phone == lead.customer_phone).first()
            if customer:
                if not lead.customer_id:
                    lead.customer_id = customer.id
                    session.flush()
                user = session.query(User).filter(User.customer_id == customer.id).first()

        if not user:
            # Fallback to finding admin using the correct uppercase role UserRole.ADMIN
            user = session.query(User).filter(User.role == UserRole.ADMIN).first()
            if not user:
                # Fallback to first user
                user = session.query(User).first()

        if user:
            notif = Notification(
                user_id=user.id,
                title="Unfinished Booking Reminder",
                message=f"You have an unfinished booking for {lead.service_name or 'salon service'}. Click 'Continue' to complete.",
                is_read=False
            )
            session.add(notif)

        if db:
            session.flush()
        else:
            session.commit()

        # Build notification payload
        notification_payload = {
            "type": "followup_reminder",
            "channel": channel.lower(),
            "recipient": {
                "name": lead.full_name,
                "email": lead.email,
                "phone": lead.phone,
            },
            "message": message,
            "scheduled_at": send_time.isoformat(),
        }

        task_id = f"followup-{str(l_id)[:8]}-{timestamp.replace(' ', '-').replace(':', '')}"

        logger.info(f"[LeadTools] Follow-up task created: {task_id}")
        return {
            "success": True,
            "task_id": task_id,
            "lead_id": str(l_id),
            "lead_name": lead.full_name,
            "channel": channel.lower(),
            "status": "scheduled" if send_time > datetime.now(timezone.utc) else "dispatched",
            "status_advanced": status_advanced,
            "notification_payload": notification_payload,
            "message": f"Follow-up {'scheduled' if send_time > datetime.now(timezone.utc) else 'dispatched'} successfully via {channel}.",
        }

    except Exception as e:
        logger.error(f"[LeadTools] Error creating follow-up: {e}", exc_info=True)
        if not db:
            session.rollback()
        return {"success": False, "error": f"Database error: {str(e)}"}
    finally:
        if not db:
            session.close()


# ---------------------------------------------------------------------------
# 4. Personalised Follow-up Message Generation
# ---------------------------------------------------------------------------
def generate_followup_message(
    customer_id: Optional[Any] = None,
    lead_id: Optional[Any] = None,
    channel: str = "email",
    tone: str = "warm",
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """
    Generates a personalised follow-up message for a customer or lead based on
    their history, service preferences, and engagement data.

    Args:
        customer_id: UUID of an existing customer (provide this OR lead_id).
        lead_id: UUID of a lead (provide this OR customer_id).
        channel: Target channel – 'email', 'sms', or 'phone' (affects message length).
        tone: Message tone – 'warm', 'professional', 'urgent', or 'casual'.

    Returns:
        Structured JSON containing the personalised message, subject line, and metadata.
    """
    logger.info(f"[LeadTools] Generating follow-up message (customer={customer_id}, lead={lead_id}, channel={channel})")

    if not customer_id and not lead_id:
        return {"success": False, "error": "Provide either customer_id or lead_id."}

    session = db or SessionLocal()
    try:
        name = "Valued Client"
        last_service = None
        last_visit = None
        days_since = None
        contact_email = None
        contact_phone = None

        if customer_id:
            c_id = _parse_uuid(customer_id, "customer_id")
            customer = session.query(Customer).filter(Customer.id == c_id).first()
            if not customer:
                return {"success": False, "error": f"Customer {c_id} not found."}

            name = customer.full_name
            contact_email = customer.email
            contact_phone = customer.phone

            # Get most recent completed appointment
            last_appt = (
                session.query(Appointment)
                .filter(
                    Appointment.customer_id == c_id,
                    Appointment.status == AppointmentStatus.COMPLETED,
                )
                .order_by(desc(Appointment.start_time))
                .first()
            )

            if last_appt:
                service = session.query(Service).filter(Service.id == last_appt.service_id).first()
                last_service = service.name if service else None
                last_visit = last_appt.start_time.isoformat()
                days_since = (datetime.now(timezone.utc) - last_appt.start_time.replace(tzinfo=timezone.utc)).days

        elif lead_id:
            l_id = _parse_uuid(lead_id, "lead_id")
            lead = session.query(Lead).filter(Lead.id == l_id).first()
            if not lead:
                return {"success": False, "error": f"Lead {l_id} not found."}

            name = lead.full_name
            contact_email = lead.email
            contact_phone = lead.phone

        # Build personalised message based on channel and context
        first_name = name.split()[0] if name else "there"

        if channel.lower() == "sms":
            # Short SMS format (≤160 chars)
            if last_service:
                message = (
                    f"Hi {first_name}! 🌟 We miss you at SalonAI! "
                    f"Ready for another {last_service}? "
                    f"Book now & enjoy 15% off! Reply BOOK or call us."
                )
            else:
                message = (
                    f"Hi {first_name}! ✨ SalonAI would love to welcome you! "
                    f"Book your first appointment & get 20% off. "
                    f"Reply BOOK or visit us today!"
                )
            subject = None
        elif channel.lower() == "phone":
            # Phone call script
            message = (
                f"Hello, may I speak with {name}? "
                f"This is Mia from SalonAI Workforce. "
                f"{'We noticed it has been ' + str(days_since) + ' days since your last visit. ' if days_since else ''}"
                f"We have some exciting new services and a special offer I'd love to share with you. "
                f"Would you be interested in scheduling an appointment?"
            )
            subject = "Phone Call Script"
        else:
            # Full email format
            if last_service and days_since:
                subject = f"We miss you, {first_name}! ✨ Your exclusive offer inside"
                message = (
                    f"Dear {first_name},\n\n"
                    f"It's been {days_since} days since your last {last_service} with us, "
                    f"and we've been thinking about you!\n\n"
                    f"We'd love to welcome you back with a special 15% discount on your next visit. "
                    f"Our stylists have also been trained in some exciting new techniques we think you'll love.\n\n"
                    f"Book your next appointment today and let us pamper you!\n\n"
                    f"Warm regards,\nThe SalonAI Team 💇‍♀️"
                )
            else:
                subject = f"Welcome to SalonAI, {first_name}! 🎉 Your exclusive first-visit offer"
                message = (
                    f"Dear {first_name},\n\n"
                    f"Thank you for your interest in SalonAI Workforce! "
                    f"We'd love to welcome you with a special 20% discount on your first service.\n\n"
                    f"Our signature services include:\n"
                    f"• Signature Precision Haircut ($85)\n"
                    f"• Balayage & Creative Color ($220)\n"
                    f"• Hydrating Deep-Cleansing Facial ($120)\n"
                    f"• Himalayan Hot Stone Massage ($150)\n\n"
                    f"Book now to experience the SalonAI difference!\n\n"
                    f"Looking forward to meeting you,\nThe SalonAI Team ✨"
                )

        # Apply tone adjustments
        tone_label = tone.lower()
        if tone_label == "urgent":
            message = message.replace("We'd love to", "Don't miss out —")
            message = message.replace("Book now", "⏰ Limited time — Book now")

        return {
            "success": True,
            "recipient_name": name,
            "channel": channel.lower(),
            "tone": tone_label,
            "subject": subject,
            "message": message,
            "personalisation": {
                "last_service": last_service,
                "last_visit": last_visit,
                "days_since_last_visit": days_since,
            },
            "contact": {
                "email": contact_email,
                "phone": contact_phone,
            },
        }

    except Exception as e:
        logger.error(f"[LeadTools] Error generating follow-up message: {e}", exc_info=True)
        return {"success": False, "error": f"Error: {str(e)}"}
    finally:
        if not db:
            session.close()


# ---------------------------------------------------------------------------
# 5. Lead Conversion Analytics
# ---------------------------------------------------------------------------
def get_lead_conversion_analytics(
    period_days: int = 30,
    branch_id: Optional[Any] = None,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """
    Generates lead conversion analytics for the specified period, including
    pipeline distribution, conversion rates, source effectiveness, and trends.

    Args:
        period_days: Analysis window in days (default 30).
        branch_id: Optional branch UUID to scope the analytics.

    Returns:
        Structured JSON with comprehensive conversion analytics.
    """
    logger.info(f"[LeadTools] Generating conversion analytics (period={period_days}d, branch={branch_id})")

    session = db or SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=period_days)

        q = session.query(Lead).filter(Lead.created_at >= cutoff)
        if branch_id:
            b_id = _parse_uuid(branch_id, "branch_id")
            q = q.filter(Lead.branch_id == b_id)

        all_leads = q.all()
        total = len(all_leads)

        if total == 0:
            return {
                "success": True,
                "period_days": period_days,
                "total_leads": 0,
                "message": "No leads found in the specified period.",
                "pipeline": {},
                "conversion_rate": "0%",
            }

        # Pipeline distribution
        pipeline: Dict[str, int] = {"NEW": 0, "CONTACTED": 0, "CONVERTED": 0, "LOST": 0}
        source_counts: Dict[str, Dict[str, int]] = {}

        for lead in all_leads:
            status_key = lead.status.value
            pipeline[status_key] = pipeline.get(status_key, 0) + 1

            source = lead.source or "Unknown"
            if source not in source_counts:
                source_counts[source] = {"total": 0, "converted": 0}
            source_counts[source]["total"] += 1
            if lead.status == LeadStatus.CONVERTED:
                source_counts[source]["converted"] += 1

        # Conversion metrics
        converted = pipeline.get("CONVERTED", 0)
        lost = pipeline.get("LOST", 0)
        conversion_rate = (converted / total * 100) if total > 0 else 0
        loss_rate = (lost / total * 100) if total > 0 else 0

        # Source effectiveness ranking
        source_effectiveness = []
        for source, counts in source_counts.items():
            rate = (counts["converted"] / counts["total"] * 100) if counts["total"] > 0 else 0
            source_effectiveness.append({
                "source": source,
                "total_leads": counts["total"],
                "converted": counts["converted"],
                "conversion_rate": f"{rate:.1f}%",
            })
        source_effectiveness.sort(key=lambda x: x["converted"], reverse=True)

        # Calculate average time to contact (leads that moved past NEW)
        contacted_leads = [
            l for l in all_leads
            if l.status in (LeadStatus.CONTACTED, LeadStatus.CONVERTED)
        ]

        return {
            "success": True,
            "period_days": period_days,
            "total_leads": total,
            "pipeline": pipeline,
            "conversion_rate": f"{conversion_rate:.1f}%",
            "loss_rate": f"{loss_rate:.1f}%",
            "active_leads": pipeline.get("NEW", 0) + pipeline.get("CONTACTED", 0),
            "source_effectiveness": source_effectiveness,
            "recommendations": _generate_pipeline_recommendations(pipeline, total, source_effectiveness),
        }

    except Exception as e:
        logger.error(f"[LeadTools] Error generating conversion analytics: {e}", exc_info=True)
        return {"success": False, "error": f"Database error: {str(e)}"}
    finally:
        if not db:
            session.close()


def _generate_pipeline_recommendations(
    pipeline: Dict[str, int], total: int, sources: List[Dict]
) -> List[str]:
    """Generate actionable recommendations based on pipeline data."""
    recs = []

    new_pct = (pipeline.get("NEW", 0) / total * 100) if total > 0 else 0
    if new_pct > 40:
        recs.append(
            f"⚠️ {new_pct:.0f}% of leads are still NEW — consider increasing outreach cadence."
        )

    lost_pct = (pipeline.get("LOST", 0) / total * 100) if total > 0 else 0
    if lost_pct > 30:
        recs.append(
            f"🔴 High loss rate ({lost_pct:.0f}%). Review follow-up timing and messaging effectiveness."
        )

    conv_pct = (pipeline.get("CONVERTED", 0) / total * 100) if total > 0 else 0
    if conv_pct < 10:
        recs.append(
            "📉 Conversion rate below 10%. Consider A/B testing follow-up templates and offering incentives."
        )

    if sources and len(sources) > 1:
        top = sources[0]
        if top["converted"] > 0:
            recs.append(
                f"🏆 Top source: '{top['source']}' ({top['conversion_rate']} conversion). "
                f"Consider increasing investment in this channel."
            )

    if not recs:
        recs.append("✅ Pipeline looks healthy. Keep maintaining your current follow-up cadence.")

    return recs


# ---------------------------------------------------------------------------
# 6. Lead Pipeline Summary (Quick Snapshot)
# ---------------------------------------------------------------------------
def get_lead_pipeline_summary(
    branch_id: Optional[Any] = None,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """
    Returns a quick snapshot of the current lead pipeline counts per status stage.

    Args:
        branch_id: Optional branch UUID to scope the summary.

    Returns:
        Structured JSON with pipeline stage counts and conversion rate.
    """
    logger.info(f"[LeadTools] Fetching pipeline summary (branch={branch_id})")

    session = db or SessionLocal()
    try:
        q = session.query(Lead)
        if branch_id:
            b_id = _parse_uuid(branch_id, "branch_id")
            q = q.filter(Lead.branch_id == b_id)

        all_leads = q.all()
        total = len(all_leads)

        pipeline = {"NEW": 0, "CONTACTED": 0, "CONVERTED": 0, "LOST": 0}
        for lead in all_leads:
            pipeline[lead.status.value] = pipeline.get(lead.status.value, 0) + 1

        converted = pipeline.get("CONVERTED", 0)
        conversion_rate = f"{(converted / total * 100):.1f}%" if total > 0 else "0%"

        return {
            "success": True,
            "total_leads": total,
            "pipeline": pipeline,
            "conversion_rate": conversion_rate,
            "active_leads": pipeline["NEW"] + pipeline["CONTACTED"],
        }

    except Exception as e:
        logger.error(f"[LeadTools] Error fetching pipeline summary: {e}", exc_info=True)
        return {"success": False, "error": f"Database error: {str(e)}"}
    finally:
        if not db:
            session.close()


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------
__all__ = [
    "detect_abandoned_bookings",
    "get_all_leads",
    "create_lead",
    "update_lead_status",
    "create_followup_reminder",
    "generate_followup_message",
    "get_lead_conversion_analytics",
    "get_lead_pipeline_summary",
]
