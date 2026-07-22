"""
Lead Nurturing & CRM Application Service for SalonAI Workforce Platform.
Consolidates scoring engines, abandoned booking scans, and pipeline updates.
"""

import logging
import uuid
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text, and_, or_, desc, func

from infrastructure.db.database import SessionLocal, db_transaction
from infrastructure.db.models import (
    Lead,
    LeadStatus,
    Customer,
    Appointment,
    AppointmentStatus,
    Branch,
    Staff,
    Service,
    ChatLog,
    Notification,
    User,
    UserRole
)
from infrastructure.events.event_bus import (
    get_event_bus,
    LeadCreatedEvent,
    LeadConvertedEvent,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 1. Lead Scoring Engine
# ---------------------------------------------------------------------------
def calculate_lead_score(messages: List[ChatLog], is_returning: bool = False, time_spent: float = 0) -> int:
    """
    Computes a lead score based on user engagement metrics:
    - Visited Pricing Page / Asked pricing questions: +20
    - Started Booking: +40
    - Asked AI Questions: +20
    - Returning Customer: +20
    - Time spent > 60 seconds: +20 (Bonus engagement)
    """
    score = 0
    started_booking = False
    asked_price = False
    asked_ai_questions = False
    
    for log in messages:
        if log.sender.lower() == "user":
            msg_lower = log.message.lower()
            if any(w in msg_lower for w in ["book", "appointment", "schedule", "reserve", "slot", "tomorrow", "pm", "am"]):
                started_booking = True
            if any(w in msg_lower for w in ["price", "cost", "how much", "pricing", "rate", "fee"]):
                asked_price = True
            if msg_lower.endswith("?") or any(w in msg_lower for w in ["what", "how", "why", "who", "where", "can you"]):
                asked_ai_questions = True
                
    if started_booking:
        score += 40
    if asked_price:
        score += 20
    if asked_ai_questions:
        score += 20
    if is_returning:
        score += 20
    if time_spent > 10:
        score += 20
        
    return min(score, 100)  # Max out at 100


# ---------------------------------------------------------------------------
# 2. Lead Detection Engine
# ---------------------------------------------------------------------------
def detect_abandoned_booking_engine(db: Session) -> List[Lead]:
    """Scans recent ChatLogs for abandoned intent in the last 2 hours."""
    logger.info("[LeadDetectionEngine] Scanning chat logs for abandoned bookings...")
    new_leads_created: List[Lead] = []
    
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=2)
    sessions = db.query(ChatLog.session_id).filter(ChatLog.created_at >= cutoff).distinct().all()
    
    for (session_id,) in sessions:
        # Check if we already have a lead created for this session
        existing_lead = db.query(Lead).filter(Lead.notes.like(f"%Session: {session_id}%")).first()
        if existing_lead:
            continue
            
        logs = db.query(ChatLog).filter(ChatLog.session_id == session_id).order_by(ChatLog.created_at.asc()).all()
        if not logs:
            continue
            
        # Check if this session resulted in a successful booking
        # Look for a booking confirmed in the same general window
        # For simplicity, if they completed booking they should have an appointment
        cust_id = None
        for log in logs:
            if log.customer_id:
                cust_id = log.customer_id
                break
                
        has_appointment = False
        if cust_id:
            # Check if appointment exists
            appt = db.query(Appointment).filter(
                Appointment.customer_id == cust_id,
                Appointment.created_at >= cutoff
            ).first()
            if appt:
                has_appointment = True
                
        # Expressed booking intent but no appointment
        msg_text = [l.message for l in logs if l.sender.lower() == "user"]
        started_booking = any(any(w in m.lower() for w in ["book", "appointment", "schedule", "reserve"]) for m in msg_text)
        
        if started_booking and not has_appointment:
            # Calculate lead score
            score = calculate_lead_score(logs)
            
            # Fetch user email / phone if possible
            email = None
            phone = None
            first_name = "Anonymous"
            last_name = "Client"
            
            if cust_id:
                cust = db.query(Customer).filter(Customer.id == cust_id).first()
                if cust:
                    first_name = cust.first_name
                    last_name = cust.last_name or ""
                    email = cust.email
                    phone = cust.phone
            
            # Create a Lead
            new_lead = Lead(
                id=uuid.uuid4(),
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone=phone,
                status=LeadStatus.NEW,
                score=score,
                source="CHAT_ABANDONMENT",
                notes=f"Detected Abandoned Chat Booking. Session: {session_id}"
            )
            db.add(new_lead)
            new_leads_created.append(new_lead)
            
    if new_leads_created:
        db.commit()
        logger.info(f"[LeadDetectionEngine] Detected and created {len(new_leads_created)} abandoned chat leads.")
    return new_leads_created


# ---------------------------------------------------------------------------
# 3. LeadService (Unified Application Service)
# ---------------------------------------------------------------------------
_lead_service_instance: Optional["LeadService"] = None

class LeadService:
    """
    Application Service managing CRM Lead workflows and transactions.
    """

    def __init__(self) -> None:
        self._event_bus = get_event_bus()
        logger.info("LeadService initialized.")

    def _parse_uuid(self, value: Any, name: str = "id") -> uuid.UUID:
        if isinstance(value, uuid.UUID):
            return value
        try:
            return uuid.UUID(str(value))
        except ValueError as e:
            raise ValueError(f"Invalid UUID format for {name}: '{value}'") from e

    def create(
        self,
        first_name: str,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        last_name: Optional[str] = None,
        source: Optional[str] = None,
        branch_id: Optional[str] = None,
        notes: Optional[str] = None,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Create a new CRM lead."""
        logger.info(f"[LeadService] Creating lead: first_name={first_name}")
        session = SessionLocal()
        try:
            b_id = self._parse_uuid(branch_id, "branch_id") if branch_id else None
            
            new_lead = Lead(
                id=uuid.uuid4(),
                first_name=first_name,
                last_name=last_name or "",
                email=email,
                phone=phone,
                source=source or "DIRECT",
                status=LeadStatus.NEW,
                score=50,  # Default starter score
                branch_id=b_id,
                notes=notes or "",
            )
            
            session.add(new_lead)
            session.commit()
            
            # Publish Domain Event
            try:
                self._event_bus.publish(LeadCreatedEvent(payload={
                    "lead_id": str(new_lead.id),
                    "first_name": first_name,
                    "email": email,
                    "phone": phone,
                    "tenant_id": tenant_id
                }))
            except Exception as ev_exc:
                logger.error(f"[LeadService] Failed to publish LeadCreatedEvent: {ev_exc}")
                
            return {
                "success": True,
                "data": {
                    "lead_id": str(new_lead.id),
                    "name": new_lead.full_name,
                    "status": new_lead.status.value,
                    "message": "Lead registered successfully."
                }
            }
        except Exception as e:
            logger.error(f"[LeadService] Error creating lead: {e}", exc_info=True)
            session.rollback()
            return {"success": False, "error": f"Database error: {str(e)}"}
        finally:
            session.close()

    def advance_status(
        self,
        lead_id: str,
        new_status: str,
        notes: Optional[str] = None,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Advance a lead's pipeline stage."""
        logger.info(f"[LeadService] Advancing lead {lead_id} -> {new_status}")
        session = SessionLocal()
        try:
            l_id = self._parse_uuid(lead_id, "lead_id")
            status_enum = LeadStatus(new_status.upper())
            
            lead = session.query(Lead).filter(Lead.id == l_id).first()
            if not lead:
                return {"success": False, "error": f"Lead {l_id} not found."}
                
            old_status = lead.status.value
            lead.status = status_enum
            
            if notes:
                existing = lead.notes or ""
                timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
                lead.notes = f"{existing}\n[{timestamp}] {notes}".strip()
                
            session.commit()
            
            # Publish Domain Event if converted
            if status_enum == LeadStatus.CONVERTED:
                try:
                    self._event_bus.publish(LeadConvertedEvent(payload={
                        "lead_id": str(l_id),
                        "first_name": lead.first_name,
                        "email": lead.email,
                        "tenant_id": tenant_id
                    }))
                except Exception as ev_exc:
                    logger.error(f"[LeadService] Failed to publish LeadConvertedEvent: {ev_exc}")
                    
            return {
                "success": True,
                "data": {
                    "lead_id": str(l_id),
                    "previous_status": old_status,
                    "new_status": status_enum.value,
                    "message": f"Lead status updated to {status_enum.value}."
                }
            }
        except Exception as e:
            logger.error(f"[LeadService] Error updating lead status: {e}", exc_info=True)
            session.rollback()
            return {"success": False, "error": f"Database error: {str(e)}"}
        finally:
            session.close()

    def send_followup(
        self,
        lead_id: str,
        channel: str,
        message: str,
        scheduled_at: Optional[str] = None,
        tenant_id: str = "default",
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Schedule/send follow-up outreach reminder."""
        logger.info(f"[LeadService] Creating follow-up for lead {lead_id} via {channel}")
        valid_channels = {"email", "sms", "phone"}
        if channel.lower() not in valid_channels:
            return {"success": False, "error": f"Invalid channel '{channel}'."}
            
        session = db or SessionLocal()
        try:
            l_id = self._parse_uuid(lead_id, "lead_id")
            lead = session.query(Lead).filter(Lead.id == l_id).first()
            if not lead:
                return {"success": False, "error": f"Lead {l_id} not found."}
                
            send_time = datetime.now(timezone.utc)
            if scheduled_at:
                try:
                    if scheduled_at.endswith("Z"):
                        scheduled_at = scheduled_at[:-1] + "+00:00"
                    send_time = datetime.fromisoformat(scheduled_at)
                    if send_time.tzinfo is None:
                        send_time = send_time.replace(tzinfo=timezone.utc)
                except ValueError:
                    pass

            # Link customer if not linked
            if not lead.customer_id:
                cust = None
                if lead.customer_email:
                    cust = session.query(Customer).filter(Customer.email == lead.customer_email).first()
                if not cust and lead.customer_phone:
                    cust = session.query(Customer).filter(Customer.phone == lead.customer_phone).first()
                if cust:
                    lead.customer_id = cust.id
                    
            # Increment followup count, update status/last contacted, and log note
            lead.status = LeadStatus.CONTACTED
            lead.last_contacted = datetime.now(timezone.utc)
            lead.followup_count = (lead.followup_count or 0) + 1
            existing = lead.notes or ""
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
            lead.notes = f"{existing}\n[{timestamp}] Sent follow-up via {channel.upper()}: {message[:50]}...".strip()
            
            # Queue notification for user if customer has a User account
            if lead.customer_id:
                user = session.query(User).filter(User.customer_id == lead.customer_id).first()
                if user:
                    notif = Notification(
                        id=uuid.uuid4(),
                        user_id=user.id,
                        title="Unfinished Booking Reminder",
                        message=message,
                        is_read=False
                    )
                    session.add(notif)
            
            if not db:
                session.commit()
            else:
                session.flush()
            
            return {
                "success": True,
                "data": {
                    "lead_id": str(l_id),
                    "channel": channel.upper(),
                    "scheduled_at": send_time.isoformat(),
                    "message": "Outreach notification queued successfully."
                }
            }
        except Exception as e:
            logger.error(f"[LeadService] Error scheduling follow-up: {e}", exc_info=True)
            if not db:
                session.rollback()
            return {"success": False, "error": f"Database error: {str(e)}"}
        finally:
            if not db:
                session.close()

    def generate_message(
        self,
        customer_id: Optional[str] = None,
        lead_id: Optional[str] = None,
        channel: str = "email",
        tone: str = "warm",
    ) -> Dict[str, Any]:
        """Draft a personalized follow-up message using template rules."""
        session = SessionLocal()
        try:
            name = "Valued Client"
            service_interest = "styling session"
            
            if lead_id:
                lead = session.query(Lead).filter(Lead.id == self._parse_uuid(lead_id, "lead_id")).first()
                if lead:
                    name = lead.first_name
                    if lead.notes and "bridal" in lead.notes.lower():
                        service_interest = "bridal hair/makeup package"
                        
            elif customer_id:
                cust = session.query(Customer).filter(Customer.id == self._parse_uuid(customer_id, "customer_id")).first()
                if cust:
                    name = cust.first_name
                    
            # Basic templates
            if tone == "formal":
                msg = f"Dear {name}, we noticed you were interested in booking a {service_interest} with us. Please let us know if we can assist you with your booking."
            else:
                msg = f"Hi {name}! Hope you are having a great day. We noticed you started booking a {service_interest} and wanted to check if you need any help finding a slot!"
                
            return {
                "success": True,
                "data": {
                    "message": msg
                }
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            session.close()

    def detect_abandoned(self, branch_id: Optional[str] = None, lookback_days: int = 30) -> Dict[str, Any]:
        """Scan for abandoned bookings (cancelled/no-show with no rebookings)."""
        session = SessionLocal()
        try:
            cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
            q = session.query(Appointment).filter(
                Appointment.status.in_([AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW]),
                Appointment.start_time >= cutoff
            )
            if branch_id:
                q = q.filter(Appointment.branch_id == self._parse_uuid(branch_id, "branch_id"))
                
            cancelled = q.all()
            abandoned = []
            
            for appt in cancelled:
                # Check if customer has any upcoming booking
                has_active = session.query(Appointment).filter(
                    Appointment.customer_id == appt.customer_id,
                    Appointment.start_time > appt.start_time,
                    Appointment.status.in_([AppointmentStatus.CONFIRMED, AppointmentStatus.PENDING])
                ).first()
                
                if not has_active:
                    cust_name = appt.customer.full_name if appt.customer else "Client"
                    email = appt.customer.email if appt.customer else None
                    phone = appt.customer.phone if appt.customer else None
                    
                    abandoned.append({
                        "appointment_id": str(appt.id),
                        "customer_id": str(appt.customer_id),
                        "customer_name": cust_name,
                        "email": email,
                        "phone": phone,
                        "service_name": appt.service.name if appt.service else "Styling",
                        "status": appt.status.value,
                        "date": appt.start_time.strftime("%Y-%m-%d")
                    })
                    
            return {"success": True, "data": {"leads": abandoned}}
        except Exception as e:
            logger.error(f"[LeadService] Error scanning abandoned bookings: {e}")
            return {"success": False, "error": str(e)}
        finally:
            session.close()


def get_lead_service() -> LeadService:
    global _lead_service_instance
    if _lead_service_instance is None:
        _lead_service_instance = LeadService()
    return _lead_service_instance


# Backward-compatibility wrappers for standalone functions
def send_lead_followup(lead_id: uuid.UUID, db: Session) -> Dict[str, Any]:
    l_uuid = uuid.UUID(str(lead_id))
    lead = db.query(Lead).filter(Lead.id == l_uuid).first()
    if not lead:
        return {"success": False, "error": "Lead not found."}
    payload = {
        "subject": f"We noticed you had an unfinished booking, {lead.first_name}! 💇‍♀️",
        "message": f"Hi {lead.first_name},\n\nWe noticed you were interested in our {lead.service_name or 'your service'} booking but didn't get a chance to finish.\n\nAppointments are still available tomorrow! Would you like to continue and reserve your slot?\n\nClick the link below to resume your booking instantly:\nhttp://localhost:5173/book?resume_lead={lead.id}\n\nWarm regards,\nThe SalonAI Team ✨",
        "button_text": "Continue Booking",
        "redirect_url": f"/book?resume_lead={lead.id}"
    }
    res = get_lead_service().send_followup(
        lead_id=str(lead.id),
        channel="email",
        message=payload["message"],
        tenant_id="default",
        db=db
    )
    if res.get("success"):
        return {
            "success": True,
            "lead_id": str(lead.id),
            "recipient": lead.customer_name,
            "payload": payload
        }
    return res


def convert_lead_to_appointment(lead_id: uuid.UUID, db: Session, staff_id: Optional[uuid.UUID] = None) -> Dict[str, Any]:
    l_uuid = uuid.UUID(str(lead_id))
    lead = db.query(Lead).filter(Lead.id == l_uuid).first()
    if not lead:
        return {"success": False, "error": "Lead not found."}
        
    customer = None
    if lead.customer_id:
        customer = db.query(Customer).filter(Customer.id == lead.customer_id).first()
    if not customer:
        customer = db.query(Customer).filter(Customer.email == lead.customer_email).first()
    if not customer:
        customer = Customer(
            first_name=lead.first_name,
            last_name=lead.last_name or "Lead",
            email=lead.customer_email or f"lead_{lead.id}@example.com",
            phone=lead.customer_phone or "+1-555-0000",
            is_active=True
        )
        db.add(customer)
        db.flush()
        lead.customer_id = customer.id
        
    service = db.query(Service).filter(Service.name == lead.service_name).first()
    if not service:
        service = db.query(Service).first()
        
    assigned_staff_id = staff_id or lead.assigned_staff
    if not assigned_staff_id:
        staff = db.query(Staff).filter(Staff.branch_id == lead.branch_id).first()
        assigned_staff_id = staff.id if staff else None
        
    appt = Appointment(
        customer_id=customer.id,
        branch_id=lead.branch_id or db.query(Branch).first().id,
        staff_id=assigned_staff_id,
        service_id=service.id,
        start_time=datetime.now(timezone.utc) + timedelta(days=1),
        end_time=datetime.now(timezone.utc) + timedelta(days=1, hours=1),
        status=AppointmentStatus.CONFIRMED,
        notes=f"Converted from Lead Follow-up. Original notes: {lead.notes}"
    )
    db.add(appt)
    
    lead.status = LeadStatus.CONVERTED
    lead.converted = True
    lead.converted_at = datetime.now(timezone.utc)
    lead.notes = (lead.notes or "") + f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Converted to confirmed booking (Appointment ID: {appt.id})."
    
    db.commit()
    logger.info(f"🎉 [LeadService] Lead {lead.id} successfully converted to Appointment {appt.id}")
    
    try:
        from infrastructure.events.event_bus import get_event_bus, LeadConvertedEvent
        get_event_bus().publish(LeadConvertedEvent(payload={
            "lead_id": str(lead.id),
            "first_name": lead.first_name,
            "email": lead.customer_email,
            "tenant_id": "default"
        }))
    except Exception as ev_exc:
        logger.error(f"[LeadService] Converted event failed: {ev_exc}")

    return {
        "success": True,
        "lead_id": str(lead.id),
        "appointment_id": str(appt.id),
        "status": "CONVERTED"
    }


def process_leads():
    logger.info("⏱️ [Scheduler] Starting automated lead recovery process...")
    db = SessionLocal()
    try:
        new_leads = detect_abandoned_booking_engine(db)
        logger.info(f"[Scheduler] Detected {len(new_leads)} new abandoned booking leads.")
        new_leads_to_follow = db.query(Lead).filter(Lead.status == LeadStatus.NEW).all()
        for lead in new_leads_to_follow:
            send_lead_followup(lead.id, db)
        logger.info("[Scheduler] Automated lead recovery job completed successfully.")
    except Exception as e:
        logger.error(f"[Scheduler] Error running automated lead recovery: {e}", exc_info=True)
    finally:
        db.close()


def create_followup_reminder(
    lead_id: Any,
    channel: str,
    message: str,
    scheduled_at: Optional[str] = None,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    session = db or SessionLocal()
    try:
        l_id = uuid.UUID(str(lead_id))
        lead = session.query(Lead).filter(Lead.id == l_id).first()
        if not lead:
            return {"success": False, "error": f"Lead {l_id} not found."}
        
        # Call LeadService send_followup
        res = get_lead_service().send_followup(
            lead_id=str(l_id),
            channel=channel,
            message=message,
            scheduled_at=scheduled_at,
            db=session
        )
        
        if res.get("success"):
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M")
            notification_payload = {
                "type": "followup_reminder",
                "channel": channel.lower(),
                "recipient": {
                    "name": lead.full_name,
                    "email": lead.customer_email,
                    "phone": lead.customer_phone,
                },
                "message": message,
                "scheduled_at": scheduled_at or datetime.now(timezone.utc).isoformat(),
            }
            return {
                "success": True,
                "task_id": f"followup-{str(l_id)[:8]}-{timestamp}",
                "lead_id": str(l_id),
                "lead_name": lead.full_name,
                "channel": channel.lower(),
                "status": "scheduled",
                "status_advanced": True,
                "notification_payload": notification_payload,
                "message": f"Follow-up scheduled successfully via {channel}."
            }
        return res
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        if not db:
            session.close()


# ---------------------------------------------------------------------------
# Module-level compatibility wrappers (used by lead_workflow.py + tests)
# ---------------------------------------------------------------------------

def create_lead(
    first_name: str,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    last_name: Optional[str] = None,
    source: Optional[str] = None,
    branch_id: Optional[str] = None,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """Create a new lead record."""
    return get_lead_service().create(
        first_name=first_name,
        last_name=last_name or "",
        email=email,
        phone=phone,
        source=source,
        branch_id=branch_id,
        db=db,
    )


def update_lead_status(
    lead_id: str,
    new_status: str,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """Advance a lead to a new status."""
    return get_lead_service().advance_status(
        lead_id=lead_id,
        new_status=new_status,
        db=db,
    )


def generate_followup_message(
    lead_id: str,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """Generate a personalised follow-up message for a lead."""
    return get_lead_service().generate_message(lead_id=lead_id, db=db)


def detect_abandoned_bookings(
    branch_id: Optional[str] = None,
    lookback_days: int = 30,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """Detect leads with abandoned booking intents."""
    return get_lead_service().detect_abandoned(
        branch_id=branch_id,
        lookback_days=lookback_days,
    )
