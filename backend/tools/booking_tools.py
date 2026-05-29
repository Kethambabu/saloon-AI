"""
Booking Business Tools for SalonAI Workforce Platform.
Provides robust transactional functions for creating, canceling, rescheduling,
checking availability, and retrieving customer history with complete validation and logging.

Uses universal entity resolver for intelligent identifier handling.
Supports UUID and human-readable names/codes for all entities.
"""

import logging
from datetime import datetime, time, timedelta, timezone
from typing import Dict, Any, List, Optional

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
        if staff_id:
            try:
                st_id = resolve_staff(staff_id, session, branch_id=b_id, raise_on_missing=True)
                st = session.query(Staff).filter(Staff.id == st_id, Staff.is_active == True).first()
                if not st:
                    return {"success": False, "error": f"Staff member not found or inactive"}
                staff_list = [st]
            except ValueError as e:
                return {"success": False, "error": str(e)}
        else:
            # Check slots against all active staff in this branch
            staff_list = session.query(Staff).filter(Staff.branch_id == b_id, Staff.is_active == True).all()
            if not staff_list:
                return {"success": True, "slots": [], "message": "No active staff members assigned to this branch."}

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
        now_utc = datetime.now(timezone.utc)

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

            if any_staff_free:
                slots_available.append({
                    "start_time": slot_start.isoformat(),
                    "end_time": slot_end.isoformat(),
                    "available_staff_ids": free_staff_ids
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

        # Ensure booking is in the future
        if st_start < datetime.now(timezone.utc):
            return {"success": False, "error": "Appointment start time must be in the future."}

        # Get entities (all should exist after resolver)
        customer = session.query(Customer).filter(Customer.id == c_id).first()
        service = session.query(Service).filter(Service.id == s_id).first()
        
        st_end = st_start + timedelta(minutes=int(service.duration_minutes))

        # Validate Business Hours
        if not _is_within_business_hours(st_start, st_end):
            return {
                "success": False, 
                "error": f"Appointment must fit inside business hours ({BUSINESS_START_HOUR}:00 to {BUSINESS_END_HOUR}:00 UTC)."
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
                "error": f"Customer already has an appointment from {customer_overlap.start_time.strftime('%Y-%m-%d %H:%M')} to {customer_overlap.end_time.strftime('%Y-%m-%d %H:%M')} UTC."
            }

        # Staff Selection & Overlap Checking
        chosen_staff_id = None
        if st_id:
            # Validate Staff exists at branch
            staff = session.query(Staff).filter(Staff.id == st_id, Staff.is_active == True).first()
            if not staff:
                return {"success": False, "error": f"Staff member not found or inactive"}
            
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

        # Create Appointment
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

        if db:
            session.add(new_appointment)
            session.flush()
            appointment_id = str(new_appointment.id)
        else:
            with db_transaction() as tx:
                tx.add(new_appointment)
            appointment_id = str(new_appointment.id)

        logger.info(f"Appointment created: {appointment_id}")
        return {
            "success": True,
            "appointment_id": appointment_id,
            "customer_name": customer.full_name,
            "service_name": service.name,
            "assigned_staff": session.query(Staff).filter(Staff.id == chosen_staff_id).first().full_name,
            "start_time": st_start.isoformat(),
            "end_time": st_end.isoformat(),
            "status": "CONFIRMED",
            "message": "Appointment created and confirmed successfully."
        }

    except Exception as e:
        logger.error(f"Error in create_appointment: {str(e)}", exc_info=True)
        return {"success": False, "error": f"Database error: {str(e)}"}
    finally:
        if not db:
            session.close()


def cancel_appointment(appointment_id: Any, db: Optional[Session] = None) -> Dict[str, Any]:
    """
    Cancels an existing salon appointment.
    Uses entity resolver to resolve appointment identifier.
    
    Args:
        appointment_id: UUID of appointment
        db: Optional database session
    
    Returns:
        Dict with success status or error message
    """
    logger.info(f"Cancelling appointment: {appointment_id}")
    
    session = db or SessionLocal()
    
    try:
        appt_id = resolve_appointment(appointment_id, session, raise_on_missing=True)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    try:
        appointment = session.query(Appointment).filter(Appointment.id == appt_id).first()
        if not appointment:
            return {"success": False, "error": f"Appointment not found."}

        if appointment.status == AppointmentStatus.CANCELLED:
            logger.info(f"Appointment {appt_id} already cancelled")
            return {"success": True, "message": "Appointment is already cancelled."}
        
        if appointment.status == AppointmentStatus.COMPLETED:
            return {"success": False, "error": "Cannot cancel a completed appointment."}

        appointment.status = AppointmentStatus.CANCELLED
        
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
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Reschedules an existing appointment to a new start time.
    Re-validates business hours, future dates, and overlaps.
    
    Args:
        appointment_id: UUID of appointment
        new_start_time: New ISO datetime string or datetime object
        db: Optional database session
    
    Returns:
        Dict with success status or error message
    """
    logger.info(f"Rescheduling appointment {appointment_id} to {new_start_time}")
    
    session = db or SessionLocal()
    
    try:
        appt_id = resolve_appointment(appointment_id, session, raise_on_missing=True)
        new_start = _parse_datetime(new_start_time)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    if new_start < datetime.now(timezone.utc):
        return {"success": False, "error": "New appointment start time must be in the future."}

    try:
        appointment = session.query(Appointment).filter(Appointment.id == appt_id).first()
        if not appointment:
            return {"success": False, "error": f"Appointment not found."}

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
                "error": f"Customer has another booking from {customer_overlap.start_time.strftime('%Y-%m-%d %H:%M')} to {customer_overlap.end_time.strftime('%Y-%m-%d %H:%M')} UTC."
            }

        # Overlap Checking: Staff (exclude self)
        if appointment.staff_id:
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


def get_customer_history(customer_id: Any, db: Optional[Session] = None) -> Dict[str, Any]:
    """
    Retrieves all booking history for a specific customer.
    Uses entity resolver to resolve customer identifier.
    
    Args:
        customer_id: UUID or customer name/email
        db: Optional database session
    
    Returns:
        Dict with customer details and appointment history
    """
    logger.info(f"Fetching customer history: {customer_id}")
    
    session = db or SessionLocal()
    
    try:
        c_id = resolve_customer(customer_id, session, raise_on_missing=True)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    try:
        # Check Customer exists
        customer = session.query(Customer).filter(Customer.id == c_id).first()
        if not customer:
            return {"success": False, "error": f"Customer not found."}

        # Query all appointments, ordered from newest to oldest
        appointments = session.query(Appointment).filter(
            Appointment.customer_id == c_id
        ).order_by(Appointment.start_time.desc()).all()

        history_list = []
        for appt in appointments:
            branch = appt.branch
            service = appt.service
            staff = appt.staff
            review = appt.review

            history_list.append({
                "appointment_id": str(appt.id),
                "branch_name": branch.name if branch else None,
                "branch_city": branch.city if branch else None,
                "service_name": service.name if service else None,
                "service_price": float(service.price) if service else None,
                "service_duration": service.duration_minutes if service else None,
                "service": {
                    "name": service.name if service else None,
                    "price": float(service.price) if service else None,
                    "duration_minutes": service.duration_minutes if service else None,
                },
                "staff_name": staff.full_name if staff else None,
                "staff": {
                    "name": staff.full_name if staff else None,
                },
                "start_time": appt.start_time.isoformat(),
                "end_time": appt.end_time.isoformat(),
                "status": appt.status.value,
                "notes": appt.notes,
                "rating": review.rating if review else None,
                "review_comment": review.comment if review else None,
            })

        logger.info(f"Retrieved {len(history_list)} appointments for customer {c_id}")
        return {
            "success": True,
            "customer_id": str(c_id),
            "customer_name": customer.full_name,
            "email": customer.email,
            "phone": customer.phone,
            "appointment_count": len(history_list),
            "history": history_list
        }
    except Exception as e:
        logger.error(f"Error fetching customer history: {str(e)}", exc_info=True)
        return {"success": False, "error": f"Database error: {str(e)}"}
    finally:
        if not db:
            session.close()
