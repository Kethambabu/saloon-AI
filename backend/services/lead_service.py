"""
Lead Nurturing & Follow-up Service for SalonAI Workforce Platform.
Implements the Lead Detection Engine, Lead Scoring, and CRM actions.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text, and_, or_, desc

from db.database import SessionLocal, db_transaction
from db.models import (
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
    User
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
    if time_spent > 60:
        score += 20
        
    return min(score, 100)  # Max out at 100


# ---------------------------------------------------------------------------
# 2. Lead Detection Engine
# ---------------------------------------------------------------------------
def detect_abandoned_bookings(db: Session) -> List[Lead]:
    """
    Scans recent ChatLogs for abandoned intent in the last 2 hours.
    Rules:
    - Rule 1: booking_started == True and booking_completed == False (expressed booking intent but no appointment)
    - Rule 2: time_spent > 60 seconds (active chat duration > 60s)
    - Rule 3: Customer asks price ("Hair Spa Price?") but leaves without booking
    """
    logger.info("[LeadDetectionEngine] Scanning chat logs for abandoned bookings...")
    new_leads_created: List[Lead] = []
    
    # Define timeframe: chats in the last 2 hours
    cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
    
    # Get all active sessions in the cutoff window
    sessions = db.query(ChatLog.session_id).filter(
        ChatLog.created_at >= cutoff
    ).distinct().all()
    
    for (session_id,) in sessions:
        # Check if we already have a lead created for this session
        existing_lead = db.query(Lead).filter(Lead.notes.like(f"%Session ID: {session_id}%")).first()
        if existing_lead:
            continue
            
        # Get all logs for this session sorted chronologically
        logs = db.query(ChatLog).filter(ChatLog.session_id == session_id).order_by(ChatLog.created_at).all()
        if not logs:
            continue
            
        # Analyze session metadata
        first_msg = logs[0]
        last_msg = logs[-1]
        time_spent = (last_msg.created_at - first_msg.created_at).total_seconds()
        
        # Determine customer information
        customer_id = None
        customer_name = "Guest Client"
        customer_email = None
        customer_phone = None
        is_returning = False
        
        # Check if logs link to an authenticated user / customer
        for log in logs:
            if log.customer_id:
                customer_id = log.customer_id
                cust = db.query(Customer).filter(Customer.id == customer_id).first()
                if cust:
                    customer_name = cust.full_name
                    customer_email = cust.email
                    customer_phone = cust.phone
                    is_returning = True
                break
                
        # If still guest, try to extract email or phone from messages (simplified regex)
        if not customer_email:
            for log in logs:
                if log.sender.lower() == "user":
                    words = log.message.split()
                    for word in words:
                        if "@" in word and "." in word:
                            customer_email = word.strip(".,!?")
                        if len(word) >= 10 and word.isdigit():
                            customer_phone = word.strip(".,!?")
                            
        # Check if an appointment was successfully completed/confirmed for this session or customer
        # in the last 2 hours
        appt_completed = False
        if customer_id:
            appt = db.query(Appointment).filter(
                Appointment.customer_id == customer_id,
                Appointment.status.in_([AppointmentStatus.CONFIRMED, AppointmentStatus.COMPLETED]),
                Appointment.created_at >= cutoff
            ).first()
            if appt:
                appt_completed = True
                
        # Apply Rules
        rule_1_match = False  # booking_started == True and booking_completed == False
        rule_2_match = False  # time_spent > 60 seconds
        rule_3_match = False  # asks pricing but leaves
        
        # Assess rule conditions
        started_booking = any(
            any(w in log.message.lower() for w in ["book", "appointment", "schedule", "reserve"])
            for log in logs if log.sender.lower() == "user"
        )
        asked_price = any(
            any(w in log.message.lower() for w in ["price", "cost", "how much", "pricing", "rate", "fee"])
            for log in logs if log.sender.lower() == "user"
        )
        
        if started_booking and not appt_completed:
            rule_1_match = True
        if time_spent > 60 and not appt_completed:
            rule_2_match = True
        if asked_price and not appt_completed:
            rule_3_match = True
            
        # If any rule is triggered, generate a Lead!
        if (rule_1_match or rule_2_match or rule_3_match) and not appt_completed:
            # Extract preferred service
            inferred_service = "General Inquiry"
            for log in logs:
                msg = log.message.lower()
                if "haircut" in msg or "hair cut" in msg:
                    inferred_service = "Signature Precision Haircut"
                elif "balayage" in msg or "color" in msg:
                    inferred_service = "Balayage & Creative Color"
                elif "facial" in msg or "skin" in msg:
                    inferred_service = "Hydrating Deep-Cleansing Facial"
                elif "massage" in msg or "stone" in msg:
                    inferred_service = "Himalayan Hot Stone Massage"
                    
            # Branch mapping (default to first active branch if unspecified)
            branch = db.query(Branch).filter(Branch.is_active == True).first()
            branch_id = branch.id if branch else None
            
            # Calculate Lead Score
            lead_score = calculate_lead_score(logs, is_returning, time_spent)
            
            # Formulate notes
            notes_lines = [
                f"Session ID: {session_id}",
                f"Time spent in chat: {time_spent:.1f}s",
                "Triggered Rules: " + ", ".join(
                    [r for r, m in [("Rule 1 (Booking Abandoned)", rule_1_match), 
                                    ("Rule 2 (Spent >60s)", rule_2_match), 
                                    ("Rule 3 (Price Inquired)", rule_3_match)] if m]
                )
            ]
            
            lead = Lead(
                customer_id=customer_id,
                customer_name=customer_name,
                customer_email=customer_email or f"guest_{session_id[:8]}@example.com",
                customer_phone=customer_phone or "+1-555-0000",
                service_name=inferred_service,
                preferred_date=(datetime.now() + timedelta(days=1)).date(),
                preferred_time=datetime.now().time(),
                branch_id=branch_id,
                source="AI Receptionist Chat",
                status=LeadStatus.NEW,
                lead_score=lead_score,
                notes="\n".join(notes_lines),
                converted=False
            )
            db.add(lead)
            new_leads_created.append(lead)
            logger.info(f"⚡ [LeadDetectionEngine] Lead created for {customer_name} (Score: {lead_score})")
            
    if new_leads_created:
        db.commit()
        
    return new_leads_created


# ---------------------------------------------------------------------------
# 3. Follow-up Message & Automation Engine
# ---------------------------------------------------------------------------
def generate_followup_payload(lead: Lead) -> Dict[str, Any]:
    """Generates the outreach follow-up template for a lead."""
    first_name = lead.first_name or "there"
    service = lead.service_name or "your service"
    
    subject = f"We noticed you had an unfinished booking, {first_name}! 💇‍♀️"
    message = (
        f"Hi {first_name},\n\n"
        f"We noticed you were interested in our {service} booking but didn't get a chance to finish.\n\n"
        f"Appointments are still available tomorrow! Would you like to continue and reserve your slot?\n\n"
        f"Click the link below to resume your booking instantly:\n"
        f"http://localhost:5173/book?resume_lead={lead.id}\n\n"
        f"Warm regards,\nThe SalonAI Team ✨"
    )
    
    return {
        "subject": subject,
        "message": message,
        "button_text": "Continue Booking",
        "redirect_url": f"/book?resume_lead={lead.id}"
    }


def send_lead_followup(lead_id: uuid.UUID, db: Session) -> Dict[str, Any]:
    """
    Sends a follow-up notification (in-app, email, SMS simulated) to a lead.
    Advances status from NEW to CONTACTED.
    """
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        return {"success": False, "error": "Lead not found."}
        
    payload = generate_followup_payload(lead)
    
    # Log in-app notification if customer/user exists
    user = None
    if lead.customer_id:
        user = db.query(User).filter(User.customer_id == lead.customer_id).first()
        
    if not user:
        # Fallback to finding admin or creating a general notification
        user = db.query(User).filter(User.role == "Admin").first()
        
    if user:
        # Create a notification that the Customer will see in their dashboard
        notif = Notification(
            user_id=user.id,
            title="Unfinished Booking Reminder",
            message=f"You have an unfinished booking for {lead.service_name or 'salon service'}. Click 'Continue' to complete.",
            is_read=False
        )
        db.add(notif)
        
    # Update Lead state
    lead.status = LeadStatus.CONTACTED
    lead.followup_count += 1
    lead.last_contacted = datetime.now(timezone.utc)
    lead.notes = (lead.notes or "") + f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Sent follow-up email/notification."
    
    db.commit()
    logger.info(f"📨 [LeadService] Follow-up sent to lead {lead.id} ({lead.customer_name})")
    
    return {
        "success": True,
        "lead_id": str(lead.id),
        "recipient": lead.customer_name,
        "payload": payload
    }


def convert_lead_to_appointment(lead_id: uuid.UUID, db: Session, staff_id: Optional[uuid.UUID] = None) -> Dict[str, Any]:
    """
    Converts a lead into a completed booked appointment.
    Moves status to CONVERTED.
    """
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        return {"success": False, "error": "Lead not found."}
        
    # Verify customer or create customer record
    customer = None
    if lead.customer_id:
        customer = db.query(Customer).filter(Customer.id == lead.customer_id).first()
        
    if not customer:
        # Lookup by email
        customer = db.query(Customer).filter(Customer.email == lead.customer_email).first()
        
    if not customer:
        # Create customer
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
        
    # Find service id by name
    service = db.query(Service).filter(Service.name == lead.service_name).first()
    if not service:
        # Default to first service
        service = db.query(Service).first()
        
    # Staff assignment
    assigned_staff_id = staff_id or lead.assigned_staff
    if not assigned_staff_id:
        # Assign first available staff member
        staff = db.query(Staff).filter(Staff.branch_id == lead.branch_id).first()
        assigned_staff_id = staff.id if staff else None
        
    # Create Appointment
    appt = Appointment(
        customer_id=customer.id,
        branch_id=lead.branch_id or db.query(Branch).first().id,
        staff_id=assigned_staff_id,
        service_id=service.id,
        start_time=datetime.now(timezone.utc) + timedelta(days=1),  # Tomorrow
        end_time=datetime.now(timezone.utc) + timedelta(days=1, hours=1),
        status=AppointmentStatus.CONFIRMED,
        notes=f"Converted from Lead Follow-up. Original notes: {lead.notes}"
    )
    db.add(appt)
    
    # Update Lead
    lead.status = LeadStatus.CONVERTED
    lead.converted = True
    lead.converted_at = datetime.now(timezone.utc)
    lead.notes = (lead.notes or "") + f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Converted to confirmed booking (Appointment ID: {appt.id})."
    
    db.commit()
    logger.info(f"🎉 [LeadService] Lead {lead.id} successfully converted to Appointment {appt.id}")
    
    return {
        "success": True,
        "lead_id": str(lead.id),
        "appointment_id": str(appt.id),
        "status": "CONVERTED"
    }


# ---------------------------------------------------------------------------
# 4. Automated Scheduler Job
# ---------------------------------------------------------------------------
def process_leads():
    """
    Main job executed by background scheduler every 30 minutes.
    1. Runs Lead Detection Engine to identify abandoned sessions and create new leads.
    2. Runs Follow-up triggers to send outreach reminders for new leads.
    """
    logger.info("⏱️ [Scheduler] Starting automated lead recovery process...")
    db = SessionLocal()
    try:
        # 1. Detect new leads
        new_leads = detect_abandoned_bookings(db)
        logger.info(f"[Scheduler] Detected {len(new_leads)} new abandoned booking leads.")
        
        # 2. Automated follow-up dispatch for NEW leads
        new_leads_to_follow = db.query(Lead).filter(Lead.status == LeadStatus.NEW).all()
        for lead in new_leads_to_follow:
            send_lead_followup(lead.id, db)
            
        logger.info("[Scheduler] Automated lead recovery job completed successfully.")
    except Exception as e:
        logger.error(f"[Scheduler] Error running automated lead recovery: {e}", exc_info=True)
    finally:
        db.close()
