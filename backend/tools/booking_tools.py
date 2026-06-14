"""
Booking Business Tools for SalonAI Workforce Platform.
Provides robust transactional functions for creating, canceling, rescheduling,
checking availability, and retrieving customer history with complete validation and logging.

Uses universal entity resolver for intelligent identifier handling.
Supports UUID and human-readable names/codes for all entities.
"""

import logging
from datetime import datetime, time, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple

from sqlalchemy.orm import Session

# Project imports
from db.database import SessionLocal, db_transaction
from db.models import (
    Branch,
    Staff,
    Customer,
    Service,
    Appointment,
    AppointmentStatus,
)
from utils.entity_resolver import (
    resolve_branch,
    resolve_customer,
    resolve_service,
    resolve_staff,
    resolve_appointment,
)

logger = logging.getLogger(__name__)

# Business rules configurations
BUSINESS_START_HOUR = 9  # 9:00 AM
BUSINESS_END_HOUR = 20   # 8:00 PM
SLOT_INTERVAL_MINUTES = 30

# Common placeholder values that should never be used (LLM hallucination detection)
_PLACEHOLDER_VALUES = {
    "first_branch_id", "first_service_id", "first_staff_id", "first_customer_id",
    "second_branch_id", "second_service_id", "second_staff_id", 
    "default_branch_id", "default_service_id", "default_staff_id",
    "placeholder", "first", "second", "default", "example", "test",
    "branch_id", "service_id", "staff_id", "customer_id", "appointment_id",
    "your_branch", "your_service", "your_staff", "your_customer",
    "select_branch", "select_service", "select_staff",
    "none_specified", "not_specified", "unspecified",
}


def get_system_now() -> datetime:
    """Get system current datetime, respecting SYSTEM TIME CONTEXT if present in query context."""
    try:
        from core.query_context import get_query_context
        context = get_query_context()
        if not context:
            # Fallback to receptionist agent context if contextvar got lost
            from agents.receptionist_agent import ReceptionistAgent
            context = getattr(ReceptionistAgent, "CURRENT_QUERY_CONTEXT", "")
    except ImportError:
        context = ""
        
    if "[SYSTEM TIME CONTEXT:" in context:
        try:
            parts = context.split("Current system time is ")
            if len(parts) > 1:
                tokens = parts[1].split()
                if len(tokens) > 1:
                    dt_str = f"{tokens[0]} {tokens[1].split('(')[0].split(')')[0]}"
                    # Treat faked context time as UTC
                    return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except Exception as e:
            logger.debug(f"Failed to parse faked system time in get_system_now: {e}")
            pass
    return datetime.now(timezone.utc)


def _is_placeholder_value(value: Any) -> bool:
    """
    Detect if an identifier is a placeholder/hallucinated value from LLM.
    Prevents invalid tool calls with made-up identifiers.
    
    Returns True if value appears to be a placeholder rather than real data.
    """
    if value is None or value == "":
        return False
    
    value_str = str(value).strip().lower()
    
    # Direct placeholder match
    if value_str in _PLACEHOLDER_VALUES:
        return True
    
    # Check for common patterns
    if any(pattern in value_str for pattern in [
        "first_", "second_", "default_", "select_", "example_",
        "your_", "placeholder", "xxxx", "1111", "0000"
    ]):
        return True
    
    # Check if it's just text without hyphens (UUIDs have hyphens)
    # and contains these patterns (likely placeholder)
    if "_" in value_str and "-" not in value_str:
        if "id" in value_str or "staff" in value_str or "branch" in value_str:
            return True
    
    return False


def _parse_datetime(dt_input: Any) -> datetime:
    """Helper to convert string or datetime inputs to UTC timezone-aware datetime."""
    if isinstance(dt_input, str):
        # Remove Z and replace with timezone info
        if dt_input.endswith("Z"):
            dt_input = dt_input[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(dt_input)
        except ValueError as e:
            raise ValueError(f"Invalid ISO datetime format: '{dt_input}'. Expected format: YYYY-MM-DDTHH:MM:SS") from e
    elif isinstance(dt_input, datetime):
        dt = dt_input
    else:
        raise ValueError("Datetime input must be an ISO format string or datetime object.")
    
    # Ensure it's timezone-aware, defaulting to UTC if not specified
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt


def is_staff_on_leave(staff_id: Any, date_str: str, session: Session) -> Tuple[bool, Optional[str]]:
    """Check if a staff member is on leave on a given date (Rule 7)."""
    from db.models import StaffLeave, Staff
    from uuid import UUID
    
    try:
        s_uuid = UUID(str(staff_id))
        staff = session.query(Staff).filter(Staff.id == s_uuid).first()
    except ValueError:
        staff = session.query(Staff).filter(
            (Staff.first_name + " " + Staff.last_name == str(staff_id)) |
            (Staff.email == str(staff_id))
        ).first()
        
    if not staff:
        return False, None

    # Check database leaves table first
    try:
        ld = datetime.strptime(date_str, "%Y-%m-%d").date()
        db_leave = session.query(StaffLeave).filter(
            StaffLeave.staff_id == staff.id,
            StaffLeave.leave_date == ld
        ).first()
        if db_leave:
            return True, staff.full_name
    except Exception as e:
        logger.warning(f"Error checking database leaves: {str(e)}")
    
    # Predefined leaves mapping (e.g. sick leave, holidays)
    leaves = {
        "Alexandra Chen": ["2026-06-10"],
        "Marcus Johnson": ["2026-06-12"],
        "Marcus Staff": ["2026-06-12"],
    }
    
    full_name = staff.full_name
    if full_name in leaves and date_str in leaves[full_name]:
        return True, full_name
        
    return False, None


def _is_within_business_hours(start: datetime, end: datetime) -> bool:
    """Checks if the appointment slot fits completely within daily business hours."""
    business_start = datetime.combine(start.date(), time(BUSINESS_START_HOUR, 0), tzinfo=timezone.utc)
    business_end = datetime.combine(start.date(), time(BUSINESS_END_HOUR, 0), tzinfo=timezone.utc)
    return start >= business_start and end <= business_end


def get_available_slots(
    branch_id: Any,
    date_str: str,
    staff_id: Optional[Any] = None,
    service_id: Optional[Any] = None,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Computes all available start-time slots for a given branch and date.
    Intelligently resolves branch/staff/service identifiers using entity resolver.
    
    Args:
        branch_id: UUID or branch name/code
        date_str: Target date in YYYY-MM-DD format
        staff_id: Optional UUID or staff name
        service_id: Optional UUID or service name
        db: Optional database session
    
    Returns:
        Dict with success status, list of available slots, or error message
    """
    logger.info(f"Checking available slots for branch {branch_id} on date {date_str}")
    
    # VALIDATION: Reject placeholder/hallucinated values from LLM
    if _is_placeholder_value(branch_id):
        error_msg = (
            f"Invalid branch identifier '{branch_id}'. "
            "Please provide a valid branch UUID or name."
        )
        logger.warning(f"Placeholder branch_id detected: {branch_id}")
        return {"success": False, "error": error_msg}
    
    if staff_id and _is_placeholder_value(staff_id):
        error_msg = (
            f"Invalid staff identifier '{staff_id}'. "
            "Please discover available staff first using get_available_staff() and provide a valid staff UUID or name."
        )
        logger.warning(f"Placeholder staff_id detected: {staff_id}")
        return {"success": False, "error": error_msg}
    
    if service_id and _is_placeholder_value(service_id):
        error_msg = (
            f"Invalid service identifier '{service_id}'. "
            "Please discover available services first using get_available_services() and provide a valid service UUID or name."
        )
        logger.warning(f"Placeholder service_id detected: {service_id}")
        return {"success": False, "error": error_msg}
    
    # Open connection if no session is injected
    session = db or SessionLocal()
    
    try:
        # Resolve identifiers using entity resolver
        try:
            b_id = resolve_branch(branch_id, session, raise_on_missing=True)
        except ValueError as e:
            return {"success": False, "error": str(e)}
        
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return {"success": False, "error": f"Invalid date format. Use YYYY-MM-DD format."}

        # Get branch (already validated by resolver)
        branch = session.query(Branch).filter(Branch.id == b_id).first()
        
        # Determine service duration
        duration = SLOT_INTERVAL_MINUTES
        if service_id:
            try:
                s_id = resolve_service(service_id, session, raise_on_missing=True)
                service = session.query(Service).filter(Service.id == s_id).first()
                if service and service.is_active:
                    duration = int(service.duration_minutes)
            except ValueError as e:
                return {"success": False, "error": str(e)}

        # Determine target staff members
        staff_list = []
        requested_staff_on_leave = False
        requested_staff_name = None
        if staff_id:
            try:
                st_id = resolve_staff(staff_id, session, branch_id=b_id, raise_on_missing=True)
                st = session.query(Staff).filter(Staff.id == st_id, Staff.is_active == True).first()
                if not st:
                    return {"success": False, "error": f"Staff member not found or inactive"}
                
                # Check leave
                on_leave, staff_name = is_staff_on_leave(st.id, date_str, session)
                if on_leave:
                    requested_staff_on_leave = True
                    requested_staff_name = staff_name
                
                staff_list = [st]
            except ValueError as e:
                return {"success": False, "error": str(e)}
        else:
            # Check slots against all active staff in this branch
            staff_list = session.query(Staff).filter(Staff.branch_id == b_id, Staff.is_active == True).all()
            if not staff_list:
                return {"success": True, "slots": [], "message": "No active staff members assigned to this branch."}

        # Filter out staff who are on leave (Rule 7)
        active_staff = []
        for s in staff_list:
            on_leave, _ = is_staff_on_leave(s.id, date_str, session)
            if not on_leave:
                active_staff.append(s)
        staff_list = active_staff

        if requested_staff_on_leave:
            # Find other staff members who are NOT on leave and who don't have bookings at those slots
            other_staff = session.query(Staff).filter(
                Staff.branch_id == b_id, 
                Staff.is_active == True,
                Staff.id != st_id
            ).all()
            
            active_other_staff = []
            for os in other_staff:
                os_on_leave, _ = is_staff_on_leave(os.id, date_str, session)
                if not os_on_leave:
                    active_other_staff.append(os)
            
            # Fetch all non-cancelled appointments for this branch on the target date
            day_start = datetime.combine(target_date, time(0, 0), tzinfo=timezone.utc)
            day_end = datetime.combine(target_date, time(23, 59, 59), tzinfo=timezone.utc)
            
            appointments = session.query(Appointment).filter(
                Appointment.branch_id == b_id,
                Appointment.status != AppointmentStatus.CANCELLED,
                Appointment.start_time >= day_start,
                Appointment.start_time <= day_end
            ).all()
            
            slots_available = []
            now_utc = get_system_now()
            current_time = datetime.combine(target_date, time(BUSINESS_START_HOUR, 0), tzinfo=timezone.utc)
            end_boundary = datetime.combine(target_date, time(BUSINESS_END_HOUR, 0), tzinfo=timezone.utc)
            
            while current_time + timedelta(minutes=duration) <= end_boundary:
                slot_start = current_time
                slot_end = current_time + timedelta(minutes=duration)
                
                if slot_start < now_utc:
                    current_time += timedelta(minutes=SLOT_INTERVAL_MINUTES)
                    continue
                
                free_staff_ids = []
                free_staff_names = []
                for member in active_other_staff:
                    has_overlap = False
                    for appt in appointments:
                        if appt.staff_id == member.id:
                            if slot_start < appt.end_time.replace(tzinfo=timezone.utc) and slot_end > appt.start_time.replace(tzinfo=timezone.utc):
                                has_overlap = True
                                break
                    if not has_overlap:
                        free_staff_ids.append(str(member.id))
                        free_staff_names.append(member.full_name)
                
                if free_staff_ids:
                    slots_available.append({
                        "start_time": slot_start.isoformat(),
                        "end_time": slot_end.isoformat(),
                        "available_staff_ids": free_staff_ids,
                        "available_staff_names": free_staff_names
                    })
                current_time += timedelta(minutes=SLOT_INTERVAL_MINUTES)
                
            return {
                "success": False,
                "error": f"{requested_staff_name} is on leave on {date_str}. Please choose another staff member.",
                "staff_on_leave": True,
                "staff_name": requested_staff_name,
                "date": date_str,
                "slots": slots_available
            }

        # Fetch all non-cancelled appointments for this branch on the target date
        day_start = datetime.combine(target_date, time(0, 0), tzinfo=timezone.utc)
        day_end = datetime.combine(target_date, time(23, 59, 59), tzinfo=timezone.utc)
        
        appointments = session.query(Appointment).filter(
            Appointment.branch_id == b_id,
            Appointment.status != AppointmentStatus.CANCELLED,
            Appointment.start_time >= day_start,
            Appointment.start_time <= day_end
        ).all()

        # Generate daily potential slot start-times
        slots_available = []
        now_utc = get_system_now()

        current_time = datetime.combine(target_date, time(BUSINESS_START_HOUR, 0), tzinfo=timezone.utc)
        end_boundary = datetime.combine(target_date, time(BUSINESS_END_HOUR, 0), tzinfo=timezone.utc)

        while current_time + timedelta(minutes=duration) <= end_boundary:
            slot_start = current_time
            slot_end = current_time + timedelta(minutes=duration)

            # Prevent booking past slots if checking for today
            if slot_start < now_utc:
                current_time += timedelta(minutes=SLOT_INTERVAL_MINUTES)
                continue

            # A slot is available if at least one staff member is completely free
            any_staff_free = False
            free_staff_ids = []
            free_staff_names = []

            for member in staff_list:
                has_overlap = False
                for appt in appointments:
                    if appt.staff_id == member.id:
                        if slot_start < appt.end_time.replace(tzinfo=timezone.utc) and slot_end > appt.start_time.replace(tzinfo=timezone.utc):
                            has_overlap = True
                            break
                
                if not has_overlap:
                    any_staff_free = True
                    free_staff_ids.append(str(member.id))
                    free_staff_names.append(member.full_name)

            if any_staff_free:
                slots_available.append({
                    "start_time": slot_start.isoformat(),
                    "end_time": slot_end.isoformat(),
                    "available_staff_ids": free_staff_ids,
                    "available_staff_names": free_staff_names
                })

            current_time += timedelta(minutes=SLOT_INTERVAL_MINUTES)

        return {
            "success": True,
            "branch_id": str(b_id),
            "date": date_str,
            "slot_count": len(slots_available),
            "slots": slots_available
        }
    except Exception as e:
        logger.error(f"Error checking available slots: {str(e)}", exc_info=True)
        return {"success": False, "error": f"Internal error: {str(e)}"}
    finally:
        if not db:
            session.close()


def create_appointment(
    customer_id: Any,
    branch_id: Any,
    service_id: Any,
    start_time: Any,
    staff_id: Optional[Any] = None,
    notes: Optional[str] = None,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Creates a new validated, non-overlapping salon booking appointment.
    Uses entity resolver for intelligent identifier handling.
    If no staff member is specified, automatically assigns a free staff member.
    
    Args:
        customer_id: UUID or customer name/email
        branch_id: UUID or branch name/code
        service_id: UUID or service name
        start_time: ISO datetime string or datetime object
        staff_id: Optional UUID or staff name
        notes: Optional booking notes
        db: Optional database session
    
    Returns:
        Dict with success status, appointment details, or error message
    """
    logger.info(f"Creating appointment: Customer={customer_id}, Branch={branch_id}, Service={service_id}")
    
    # VALIDATION: Reject placeholder/hallucinated values from LLM
    if _is_placeholder_value(branch_id):
        error_msg = (
            f"Invalid branch identifier '{branch_id}'. "
            "Please provide a valid branch UUID or name."
        )
        logger.warning(f"Placeholder branch_id detected: {branch_id}")
        return {"success": False, "error": error_msg}
    
    if _is_placeholder_value(service_id):
        error_msg = (
            f"Invalid service identifier '{service_id}'. "
            "Please discover available services first using get_available_services() and provide a valid service UUID or name."
        )
        logger.warning(f"Placeholder service_id detected: {service_id}")
        return {"success": False, "error": error_msg}
    
    if staff_id and _is_placeholder_value(staff_id):
        error_msg = (
            f"Invalid staff identifier '{staff_id}'. "
            "Please discover available staff first using get_available_staff() and provide a valid staff UUID or name."
        )
        logger.warning(f"Placeholder staff_id detected: {staff_id}")
        return {"success": False, "error": error_msg}
    
    session = db or SessionLocal()
    
    try:
        # Resolve all identifiers using entity resolver
        try:
            c_id = resolve_customer(customer_id, session, raise_on_missing=True)
            b_id = resolve_branch(branch_id, session, raise_on_missing=True)
            s_id = resolve_service(service_id, session, raise_on_missing=True)
        except ValueError as e:
            logger.warning(f"Entity resolution failed: {str(e)}")
            return {"success": False, "error": str(e)}
        
        st_start = _parse_datetime(start_time)
        st_id = None
        if staff_id:
            try:
                st_id = resolve_staff(staff_id, session, branch_id=b_id, raise_on_missing=True)
            except ValueError as e:
                logger.warning(f"Staff resolution failed: {str(e)}")
                return {"success": False, "error": str(e)}

        # Ensure booking is in the future — give a 6-hour grace window to account for
        # timezone differences between the user's local time and the UTC server clock.
        # e.g., "10 AM tomorrow IST" = "4:30 AM UTC" which would incorrectly fail without grace.
        if st_start < (get_system_now() - timedelta(hours=6)):
            return {"success": False, "error": "Appointments must be in the future."}

        # Get entities (all should exist after resolver)
        customer = session.query(Customer).filter(Customer.id == c_id).first()
        branch = session.query(Branch).filter(Branch.id == b_id).first()
        service = session.query(Service).filter(Service.id == s_id).first()
        
        st_end = st_start + timedelta(minutes=int(service.duration_minutes))

        # Validate Business Hours — appointment must be within 9:00–20:00 of the REQUESTED local time
        # (We treat the input time as local/wall-clock; the Z suffix just marks no explicit offset)
        if not _is_within_business_hours(st_start, st_end):
            req_hour = st_start.hour
            req_end_hour = st_end.hour
            return {
                "success": False, 
                "error": f"Appointment must fit inside business hours (9:00 AM to 8:00 PM). Requested: {req_hour}:00–{req_end_hour}:{st_end.minute:02d}."
            }

        # Enforce Customer Booking Limits (Item 11) — only count future bookings as active.
        # Aligned with the 6-hour timezone grace window. Exclude linked add-on appointments.
        from sqlalchemy import or_
        active_bookings_count = session.query(Appointment).filter(
            Appointment.customer_id == c_id,
            Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED]),
            Appointment.start_time > (get_system_now() - timedelta(hours=6)),
            or_(
                Appointment.notes.is_(None),
                ~Appointment.notes.like("Linked Add-on from Appointment%")
            )
        ).count()
        if active_bookings_count >= 3:
            return {
                "success": False,
                "error": "You have reached the maximum limit of 3 active bookings. Please cancel or complete an existing booking first."
            }

        # Duplicate Appointment Detection (Rule 5)
        duplicate_query = session.query(Appointment).filter(
            Appointment.customer_id == c_id,
            Appointment.service_id == s_id,
            Appointment.start_time == st_start,
            Appointment.status != AppointmentStatus.CANCELLED
        )
        if st_id:
            duplicate_query = duplicate_query.filter(Appointment.staff_id == st_id)
        
        duplicate = duplicate_query.first()
        if duplicate:
            return {
                "success": False,
                "error": "Duplicate appointment detected. You already have this exact appointment scheduled."
            }

        # Overlap Checking: Customer
        customer_overlap = session.query(Appointment).filter(
            Appointment.customer_id == c_id,
            Appointment.status != AppointmentStatus.CANCELLED,
            Appointment.start_time < st_end,
            Appointment.end_time > st_start
        ).first()

        if customer_overlap:
            logger.warning(f"Customer overlap detected: {customer_overlap.start_time} to {customer_overlap.end_time}")
            return {
                "success": False,
                "error": "You already have an appointment scheduled at that time."
            }

        # Staff Selection & Overlap Checking
        chosen_staff_id = None
        if st_id:
            # Validate Staff exists at branch
            staff = session.query(Staff).filter(Staff.id == st_id, Staff.is_active == True).first()
            if not staff:
                return {"success": False, "error": f"Staff member not found or inactive"}
            
            # Check Staff leave (Rule 7)
            date_str = st_start.strftime("%Y-%m-%d")
            on_leave, staff_name = is_staff_on_leave(st_id, date_str, session)
            if on_leave:
                return {
                    "success": False,
                    "error": f"{staff_name} is unavailable on {date_str}."
                }
            
            # Check Staff overlap
            staff_overlap = session.query(Appointment).filter(
                Appointment.staff_id == st_id,
                Appointment.status != AppointmentStatus.CANCELLED,
                Appointment.start_time < st_end,
                Appointment.end_time > st_start
            ).first()

            if staff_overlap:
                logger.warning(f"Staff overlap detected for {staff.full_name}")
                return {
                    "success": False,
                    "error": f"Staff member '{staff.full_name}' is already booked from {staff_overlap.start_time.strftime('%Y-%m-%d %H:%M')} to {staff_overlap.end_time.strftime('%Y-%m-%d %H:%M')} UTC."
                }
            chosen_staff_id = st_id
        else:
            # Dispatcher: Find a free staff member
            all_staff = session.query(Staff).filter(Staff.branch_id == b_id, Staff.is_active == True).all()
            if not all_staff:
                return {"success": False, "error": f"No active staff members available."}

            for member in all_staff:
                # Check leave (Rule 7)
                date_str = st_start.strftime("%Y-%m-%d")
                on_leave, _ = is_staff_on_leave(member.id, date_str, session)
                if on_leave:
                    continue

                overlap = session.query(Appointment).filter(
                    Appointment.staff_id == member.id,
                    Appointment.status != AppointmentStatus.CANCELLED,
                    Appointment.start_time < st_end,
                    Appointment.end_time > st_start
                ).first()
                
                if not overlap:
                    chosen_staff_id = member.id
                    logger.info(f"Auto-assigned staff: {member.full_name}")
                    break
            
            if not chosen_staff_id:
                return {"success": False, "error": "No available staff members for the requested time slot."}

        # Create Appointment — status is CONFIRMED immediately so it shows in customer UI
        new_appointment = Appointment(
            customer_id=c_id,
            branch_id=b_id,
            staff_id=chosen_staff_id,
            service_id=s_id,
            start_time=st_start,
            end_time=st_end,
            status=AppointmentStatus.CONFIRMED,
            notes=notes
        )

        appointment_id = None
        assigned_staff_name = None
        
        session.add(new_appointment)
        session.flush()
        appointment_id = str(new_appointment.id)
        assigned_staff = session.query(Staff).filter(Staff.id == chosen_staff_id).first()
        assigned_staff_name = assigned_staff.full_name if assigned_staff else "Unknown"
        
        if not db:
            session.commit()

        # Dispatch notification to user dynamically
        try:
            from db.models import User, Notification
            user = session.query(User).filter(User.customer_id == c_id).first()
            if user:
                import uuid
                notif = Notification(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    title="Appointment Confirmed",
                    message=f"Your appointment for {service.name} has been confirmed and is ready.",
                    is_read=False
                )
                session.add(notif)
                if db:
                    session.flush()
                else:
                    session.commit()
        except Exception as notif_err:
            logger.error(f"Error creating booking notification: {notif_err}")

        # Mark active leads as converted
        try:
            from db.models import Lead, LeadStatus
            active_leads = session.query(Lead).filter(
                Lead.customer_id == c_id,
                Lead.status.in_([LeadStatus.NEW, LeadStatus.CONTACTED])
            ).all()
            for lead in active_leads:
                lead.status = LeadStatus.CONVERTED
                lead.converted = True
                lead.converted_at = datetime.now(timezone.utc)
                lead.notes = (lead.notes or "") + f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Converted to confirmed booking (Appointment ID: {appointment_id})."
            if db:
                session.flush()
            else:
                session.commit()
            logger.info(f"Converted {len(active_leads)} active leads for customer {c_id}")
        except Exception as lead_err:
            logger.error(f"Error converting lead on appointment creation: {lead_err}")

        # Mark matching recommendations as accepted
        try:
            from db.models import CustomerRecommendation
            matching_recs = session.query(CustomerRecommendation).filter(
                CustomerRecommendation.customer_id == c_id,
                CustomerRecommendation.recommended_service_id == s_id,
                CustomerRecommendation.accepted == False
            ).all()
            for r in matching_recs:
                r.accepted = True
                r.appointment_id = new_appointment.id
            if db:
                session.flush()
            else:
                session.commit()
            if matching_recs:
                logger.info(f"Marked {len(matching_recs)} customer recommendations as accepted for customer {c_id}")
        except Exception as rec_err:
            logger.error(f"Error converting recommendation on appointment creation: {rec_err}")

        branch_name = branch.name if branch else "Our Salon"
        service_price = service.price if service else None

        logger.info(f"Appointment created: {appointment_id}")
        return {
            "success": True,
            "appointment_id": appointment_id,
            "customer_name": customer.full_name,
            "service_name": service.name,
            "branch_name": branch_name,
            "stylist_name": assigned_staff_name,
            "start_time": st_start.isoformat(),
            "end_time": st_end.isoformat(),
            "status": "CONFIRMED",
            "price": str(service_price) if service_price is not None else None,
            "message": "Appointment confirmed successfully."
        }

    except Exception as e:
        logger.error(f"Error in create_appointment: {str(e)}", exc_info=True)
        return {"success": False, "error": f"Database error: {str(e)}"}
    finally:
        if not db:
            session.close()


def cancel_appointment(appointment_id: Any, customer_id: Optional[Any] = None, db: Optional[Session] = None) -> Dict[str, Any]:
    """
    Cancels an existing salon appointment.
    Uses entity resolver to resolve appointment identifier.
    
    Args:
        appointment_id: UUID of appointment
        customer_id: Optional customer UUID or name/email for ownership validation
        db: Optional database session
    
    Returns:
        Dict with success status or error message
    """
    logger.info(f"Cancelling appointment: {appointment_id}")
    
    # VALIDATION: Reject placeholder/hallucinated values from LLM
    if _is_placeholder_value(appointment_id):
        error_msg = (
            f"Invalid appointment identifier '{appointment_id}'. "
            "Please provide a valid appointment UUID."
        )
        logger.warning(f"Placeholder appointment_id detected: {appointment_id}")
        return {"success": False, "error": error_msg}
    
    session = db or SessionLocal()
    
    try:
        appt_id = resolve_appointment(appointment_id, session, raise_on_missing=True)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    try:
        appointment = session.query(Appointment).filter(Appointment.id == appt_id).first()
        if not appointment:
            return {"success": False, "error": f"Appointment not found."}

        if customer_id:
            try:
                c_id = resolve_customer(customer_id, session, raise_on_missing=True)
                if appointment.customer_id != c_id:
                    return {"success": False, "error": "You are not authorized to cancel this appointment."}
            except Exception as e:
                return {"success": False, "error": f"Customer resolution failed: {str(e)}"}

        if appointment.status == AppointmentStatus.CANCELLED:
            logger.info(f"Appointment {appt_id} already cancelled")
            return {"success": True, "message": "Appointment is already cancelled."}
        
        if appointment.status == AppointmentStatus.COMPLETED:
            return {"success": False, "error": "Cannot cancel a completed appointment."}

        # Validate Cancellation Window (Rule 10)
        from datetime import datetime, timezone
        now = get_system_now()
        appt_start = appointment.start_time
        if appt_start.tzinfo is None:
            appt_start = appt_start.replace(tzinfo=timezone.utc)
        else:
            appt_start = appt_start.astimezone(timezone.utc)
            
        if now >= appt_start:
            return {"success": False, "error": "Cannot cancel an appointment after the service has already started."}
            
        time_diff = appt_start - now
        if time_diff.total_seconds() < 1800: # 30 minutes
            return {"success": False, "error": "Cannot cancel an appointment within 30 minutes of its start time."}

        appointment.status = AppointmentStatus.CANCELLED
        
        # Trigger loyalty points deduction
        try:
            from tools.loyalty_triggers import trigger_loyalty_update_on_cancellation
            trigger_loyalty_update_on_cancellation(session, appointment.id, appointment.customer_id)
        except Exception as loyalty_err:
            logger.error(f"Error triggering loyalty update on cancellation: {loyalty_err}")

        # Dispatch notification to user dynamically
        try:
            from db.models import User, Notification
            import uuid
            user = session.query(User).filter(User.customer_id == appointment.customer_id).first()
            if user:
                service_name = appointment.service.name if appointment.service else "Styling Treatment"
                notif = Notification(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    title="Appointment Cancelled",
                    message=f"Your appointment for {service_name} has been cancelled successfully.",
                    is_read=False
                )
                session.add(notif)
        except Exception as notif_err:
            logger.error(f"Error creating cancellation notification: {notif_err}")

        # Check waitlist notifications (Rule 16)
        try:
            appt_date = appointment.start_time.strftime("%Y-%m-%d")
            appt_time = appointment.start_time.strftime("%H:%M")
            
            from db.models import Waitlist, User, Notification
            import uuid
            
            waitlists = session.query(Waitlist).filter(
                Waitlist.branch_id == appointment.branch_id,
                Waitlist.service_id == appointment.service_id,
                Waitlist.date_str == appt_date,
                Waitlist.time_str == appt_time,
                Waitlist.is_notified == False
            ).all()
            
            for wl in waitlists:
                wl_user = session.query(User).filter(User.customer_id == wl.customer_id).first()
                if wl_user:
                    branch_name = appointment.branch.name if appointment.branch else "Salon"
                    service_name = appointment.service.name if appointment.service else "Styling Treatment"
                    title = "Waitlist Slot Available!"
                    msg = f"Good news! The {appt_time} slot on {appt_date} for {service_name} at our {branch_name} branch is now available. Book it now!"
                    
                    notif = Notification(
                        id=uuid.uuid4(),
                        user_id=wl_user.id,
                        title=title,
                        message=msg,
                        is_read=False
                    )
                    session.add(notif)
                    wl.is_notified = True
        except Exception as wl_err:
            logger.error(f"Error notifying waitlist: {wl_err}")

        if db:
            session.flush()
        else:
            session.commit()
            
        logger.info(f"Appointment {appt_id} cancelled")
        return {
            "success": True,
            "appointment_id": str(appt_id),
            "status": "CANCELLED",
            "message": "Appointment has been cancelled successfully."
        }
    except Exception as e:
        logger.error(f"Error cancelling appointment: {str(e)}", exc_info=True)
        if not db:
            session.rollback()
        return {"success": False, "error": f"Database error: {str(e)}"}
    finally:
        if not db:
            session.close()


def reschedule_appointment(
    appointment_id: Any,
    new_start_time: Any,
    customer_id: Optional[Any] = None,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Reschedules an existing appointment to a new start time.
    Re-validates business hours, future dates, and overlaps.
    
    Args:
        appointment_id: UUID of appointment
        new_start_time: New ISO datetime string or datetime object
        customer_id: Optional customer UUID or name/email for ownership validation
        db: Optional database session
    
    Returns:
        Dict with success status or error message
    """
    logger.info(f"Rescheduling appointment {appointment_id} to {new_start_time}")
    
    # VALIDATION: Reject placeholder/hallucinated values from LLM
    if _is_placeholder_value(appointment_id):
        error_msg = (
            f"Invalid appointment identifier '{appointment_id}'. "
            "Please provide a valid appointment UUID."
        )
        logger.warning(f"Placeholder appointment_id detected: {appointment_id}")
        return {"success": False, "error": error_msg}
    
    session = db or SessionLocal()
    
    try:
        appt_id = resolve_appointment(appointment_id, session, raise_on_missing=True)
        new_start = _parse_datetime(new_start_time)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    if new_start < get_system_now():
        return {"success": False, "error": "Appointments must be in the future."}

    try:
        appointment = session.query(Appointment).filter(Appointment.id == appt_id).first()
        if not appointment:
            return {"success": False, "error": f"Appointment not found."}

        if customer_id:
            try:
                c_id = resolve_customer(customer_id, session, raise_on_missing=True)
                if appointment.customer_id != c_id:
                    return {"success": False, "error": "You are not authorized to reschedule this appointment."}
            except Exception as e:
                return {"success": False, "error": f"Customer resolution failed: {str(e)}"}

        if appointment.status == AppointmentStatus.CANCELLED:
            return {"success": False, "error": "Cannot reschedule a cancelled appointment."}
        if appointment.status == AppointmentStatus.COMPLETED:
            return {"success": False, "error": "Cannot reschedule a completed appointment."}

        # Get service to calculate duration
        service = session.query(Service).filter(Service.id == appointment.service_id).first()
        if not service:
            return {"success": False, "error": "Associated service not found."}

        new_end = new_start + timedelta(minutes=int(service.duration_minutes))

        # Validate Business Hours
        if not _is_within_business_hours(new_start, new_end):
            return {
                "success": False,
                "error": f"New slot must fit inside business hours ({BUSINESS_START_HOUR}:00 to {BUSINESS_END_HOUR}:00 UTC)."
            }

        # Overlap Checking: Customer (exclude self)
        customer_overlap = session.query(Appointment).filter(
            Appointment.customer_id == appointment.customer_id,
            Appointment.id != appt_id,
            Appointment.status != AppointmentStatus.CANCELLED,
            Appointment.start_time < new_end,
            Appointment.end_time > new_start
        ).first()

        if customer_overlap:
            return {
                "success": False,
                "error": "You already have an appointment scheduled at that time."
            }

        # Overlap Checking: Staff (exclude self)
        if appointment.staff_id:
            # Check Staff leave
            date_str = new_start.strftime("%Y-%m-%d")
            on_leave, staff_name = is_staff_on_leave(appointment.staff_id, date_str, session)
            if on_leave:
                return {
                    "success": False,
                    "error": f"{staff_name} is unavailable on {date_str} due to scheduled leave."
                }

            staff_overlap = session.query(Appointment).filter(
                Appointment.staff_id == appointment.staff_id,
                Appointment.id != appt_id,
                Appointment.status != AppointmentStatus.CANCELLED,
                Appointment.start_time < new_end,
                Appointment.end_time > new_start
            ).first()

            if staff_overlap:
                staff = session.query(Staff).filter(Staff.id == appointment.staff_id).first()
                staff_name = staff.full_name if staff else "Stylist"
                return {
                    "success": False,
                    "error": f"Staff member '{staff_name}' is already booked from {staff_overlap.start_time.strftime('%Y-%m-%d %H:%M')} to {staff_overlap.end_time.strftime('%Y-%m-%d %H:%M')} UTC."
                }

        # Apply changes
        appointment.start_time = new_start
        appointment.end_time = new_end
        appointment.status = AppointmentStatus.CONFIRMED

        # Dispatch notification to user dynamically
        try:
            from db.models import User, Notification
            import uuid
            user = session.query(User).filter(User.customer_id == appointment.customer_id).first()
            if user:
                service_name = appointment.service.name if appointment.service else "Styling Treatment"
                formatted_time = new_start.strftime("%Y-%m-%d at %I:%M %p")
                notif = Notification(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    title="Appointment Rescheduled",
                    message=f"Your appointment request for {service_name} has been rescheduled to {formatted_time}.",
                    is_read=False
                )
                session.add(notif)
        except Exception as notif_err:
            logger.error(f"Error creating reschedule notification: {notif_err}")

        if db:
            session.flush()
        else:
            session.commit()

        logger.info(f"Appointment {appt_id} rescheduled to {new_start.isoformat()}")
        return {
            "success": True,
            "appointment_id": str(appt_id),
            "start_time": new_start.isoformat(),
            "end_time": new_end.isoformat(),
            "status": "CONFIRMED",
            "message": "Appointment rescheduled successfully."
        }

    except Exception as e:
        logger.error(f"Error rescheduling appointment: {str(e)}", exc_info=True)
        if not db:
            session.rollback()
        return {"success": False, "error": f"Database error: {str(e)}"}
    finally:
        if not db:
            session.close()



def add_to_waitlist(
    customer_id: Any,
    branch_id: Any,
    service_id: Any,
    date_str: str,
    time_str: str,
    staff_id: Optional[Any] = None,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Adds a customer to the waitlist for a booked-out slot (Rule 16).
    """
    session = db or SessionLocal()
    try:
        c_id = resolve_customer(customer_id, session, raise_on_missing=True)
        b_id = resolve_branch(branch_id, session, raise_on_missing=True)
        s_id = resolve_service(service_id, session, raise_on_missing=True)
        st_id = None
        if staff_id and not _is_placeholder_value(staff_id):
            st_id = resolve_staff(staff_id, session, branch_id=b_id, raise_on_missing=True)
            
        from db.models import Waitlist
        import uuid
        
        # Check if already on waitlist
        exists = session.query(Waitlist).filter(
            Waitlist.customer_id == c_id,
            Waitlist.branch_id == b_id,
            Waitlist.service_id == s_id,
            Waitlist.date_str == date_str,
            Waitlist.time_str == time_str
        ).first()
        
        if exists:
            return {"success": True, "message": "You are already on the waitlist for this slot."}
            
        wl = Waitlist(
            id=uuid.uuid4(),
            customer_id=c_id,
            branch_id=b_id,
            service_id=s_id,
            staff_id=st_id,
            date_str=date_str,
            time_str=time_str,
            is_notified=False
        )
        
        session.add(wl)
        if not db:
            session.commit()
        else:
            session.flush()
            
        return {"success": True, "message": "Successfully joined the waitlist! We will notify you if this slot opens up."}
    except Exception as e:
        logger.error(f"Error adding to waitlist: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
    finally:
        if not db:
            session.close()


def send_appointment_reminders(customer_id: Any, db: Session) -> int:
    """
    Scans customer's upcoming appointments and generates lazy reminders in the notification table
    for 24-hour, 2-hour, and 30-minute horizons (Rule 11).
    """
    from db.models import User, Appointment, AppointmentStatus, Notification
    import uuid
    from datetime import datetime, timezone
    
    # Resolve customer id
    try:
        c_id = resolve_customer(customer_id, db, raise_on_missing=True)
    except ValueError:
        return 0
        
    # Get user account for customer
    user = db.query(User).filter(User.customer_id == c_id).first()
    if not user:
        return 0
        
    # Get active upcoming appointments
    now = datetime.now(timezone.utc)
    appts = db.query(Appointment).filter(
        Appointment.customer_id == c_id,
        Appointment.status == AppointmentStatus.CONFIRMED,
        Appointment.start_time > now
    ).all()
    
    notifications_created = 0
    for appt in appts:
        appt_start = appt.start_time
        if appt_start.tzinfo is None:
            appt_start = appt_start.replace(tzinfo=timezone.utc)
        else:
            appt_start = appt_start.astimezone(timezone.utc)
            
        time_diff = appt_start - now
        diff_seconds = time_diff.total_seconds()
        
        # 30-minute reminder (within 30 minutes, i.e. 1800 seconds)
        if 0 < diff_seconds <= 1800:
            title = f"Upcoming Appointment in 30 Minutes"
            msg = f"Reminder: Your appointment for {appt.service.name} with {appt.staff.full_name} is scheduled in less than 30 minutes (at {appt_start.strftime('%I:%M %p')})."
            # Avoid duplicate
            exists = db.query(Notification).filter(
                Notification.user_id == user.id,
                Notification.title == title
            ).first()
            if not exists:
                new_notif = Notification(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    title=title,
                    message=msg,
                    is_read=False
                )
                db.add(new_notif)
                notifications_created += 1
                
        # 2-hour reminder (within 2 hours, i.e. 7200 seconds)
        elif 1800 < diff_seconds <= 7200:
            title = f"Upcoming Appointment in 2 Hours"
            msg = f"Reminder: Your appointment for {appt.service.name} with {appt.staff.full_name} is scheduled in 2 hours (at {appt_start.strftime('%I:%M %p')})."
            exists = db.query(Notification).filter(
                Notification.user_id == user.id,
                Notification.title == title
            ).first()
            if not exists:
                new_notif = Notification(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    title=title,
                    message=msg,
                    is_read=False
                )
                db.add(new_notif)
                notifications_created += 1
                
        # 24-hour reminder (within 24 hours, i.e. 86400 seconds)
        elif 7200 < diff_seconds <= 86400:
            title = f"Upcoming Appointment Tomorrow"
            msg = f"Reminder: Your appointment for {appt.service.name} with {appt.staff.full_name} is scheduled tomorrow at {appt_start.strftime('%I:%M %p')}."
            exists = db.query(Notification).filter(
                Notification.user_id == user.id,
                Notification.title == title
            ).first()
            if not exists:
                new_notif = Notification(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    title=title,
                    message=msg,
                    is_read=False
                )
                db.add(new_notif)
                notifications_created += 1
                
    if notifications_created > 0:
        db.commit()
        
    return notifications_created


def auto_cancel_past_customer_appointments(customer_id: Any, db: Session) -> int:
    """
    Finds all PENDING or CONFIRMED appointments for a customer that are in the past,
    marks them as CANCELLED, and commits the transaction.
    """
    from datetime import datetime, timezone
    from db.models import Appointment, AppointmentStatus
    from utils.entity_resolver import resolve_customer
    
    try:
        c_id = resolve_customer(customer_id, db, raise_on_missing=True)
    except ValueError:
        return 0
        
    now = datetime.now(timezone.utc)
    past_appts = db.query(Appointment).filter(
        Appointment.customer_id == c_id,
        Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED]),
        Appointment.start_time < now
    ).all()
    
    if past_appts:
        for appt in past_appts:
            appt.status = AppointmentStatus.CANCELLED
            logger.info(f"Auto-cancelled past customer appointment {appt.id} (scheduled for {appt.start_time})")
        db.commit()
        return len(past_appts)
    return 0


def auto_cancel_past_staff_appointments(staff_id: Any, db: Session) -> int:
    """
    Finds all PENDING or CONFIRMED appointments for a staff member that are in the past,
    marks them as CANCELLED, and commits the transaction.
    """
    from datetime import datetime, timezone
    from db.models import Appointment, AppointmentStatus
    from utils.entity_resolver import resolve_staff
    
    try:
        s_id = resolve_staff(staff_id, db, raise_on_missing=True)
    except ValueError:
        return 0
        
    now = datetime.now(timezone.utc)
    past_appts = db.query(Appointment).filter(
        Appointment.staff_id == s_id,
        Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED]),
        Appointment.start_time < now
    ).all()
    
    if past_appts:
        for appt in past_appts:
            appt.status = AppointmentStatus.CANCELLED
            logger.info(f"Auto-cancelled past staff appointment {appt.id} (scheduled for {appt.start_time})")
        db.commit()
        return len(past_appts)
    return 0

