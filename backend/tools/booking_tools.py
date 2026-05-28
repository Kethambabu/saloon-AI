"""
Booking Business Tools for SalonAI Workforce Platform.
Provides robust transactional functions for creating, canceling, rescheduling,
checking availability, and retrieving customer history with complete validation and logging.
"""

import logging
import uuid
from datetime import datetime, time, timedelta, timezone
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

# Project imports
from db.database import SessionLocal, db_transaction
from db.models import (
    Branch,
    Staff,
    Customer,
    Service,
    Appointment,
    AppointmentStatus,
    Review
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


def _parse_uuid(uuid_input: Any, name: str = "id", db: Optional[Session] = None) -> uuid.UUID:
    """
    Helper to validate and parse UUIDs.
    Tries UUID parsing first, then falls back to name/code lookup if needed.
    """
    if isinstance(uuid_input, uuid.UUID):
        return uuid_input
    
    # Try to parse as UUID string
    str_input = str(uuid_input).strip()
    try:
        return uuid.UUID(str_input)
    except ValueError:
        pass
    
    # If UUID parsing fails and we have a DB session, try to look up by name/code
    if db:
        # Map field names to lookup strategies
        if name == "branch_id":
            # Look up by branch name or code
            branch = db.query(Branch).filter(
                or_(Branch.name.ilike(str_input), Branch.code.ilike(str_input))
            ).first()
            if branch:
                logger.info(f"Resolved branch_id '{str_input}' to UUID: {branch.id}")
                return branch.id
        
        elif name == "customer_id":
            # Look up by customer name or email
            customer = db.query(Customer).filter(
                or_(
                    Customer.full_name.ilike(f"%{str_input}%"),
                    Customer.email.ilike(str_input)
                )
            ).first()
            if customer:
                logger.info(f"Resolved customer_id '{str_input}' to UUID: {customer.id}")
                return customer.id
        
        elif name == "service_id":
            # Look up by service name
            service = db.query(Service).filter(Service.name.ilike(f"%{str_input}%")).first()
            if service:
                logger.info(f"Resolved service_id '{str_input}' to UUID: {service.id}")
                return service.id
        
        elif name == "staff_id":
            # Look up by staff name
            staff = db.query(Staff).filter(Staff.full_name.ilike(f"%{str_input}%")).first()
            if staff:
                logger.info(f"Resolved staff_id '{str_input}' to UUID: {staff.id}")
                return staff.id
    
    # If all lookups fail, raise error
    raise ValueError(f"Invalid UUID format or unknown identifier for {name}: '{uuid_input}'")


def _is_within_business_hours(start: datetime, end: datetime) -> bool:
    """Checks if the appointment slot fits completely within daily business hours."""
    # Convert to local/target date time comparison or check hour bounds
    # For a unified standard, we check the hour boundaries of the date of the appointment
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
    Optionally filters by staff (to check their specific calendar) and service (to verify slot duration).
    """
    logger.info(f"Checking available slots for branch {branch_id} on date {date_str} (Staff: {staff_id}, Service: {service_id})")
    
    # Open connection if no session is injected
    session = db or SessionLocal()
    
    try:
        b_id = _parse_uuid(branch_id, "branch_id", session)
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError as e:
        logger.warning(f"Validation failed in get_available_slots: {str(e)}")
        return {"success": False, "error": str(e)}

    try:
        # 1. Validate Branch exists
        branch = session.query(Branch).filter(Branch.id == b_id, Branch.is_active == True).first()
        if not branch:
            return {"success": False, "error": f"Active Branch with ID {b_id} not found"}

        # 2. Determine service duration
        duration = SLOT_INTERVAL_MINUTES
        if service_id:
            try:
                s_id = _parse_uuid(service_id, "service_id", session)
                service = session.query(Service).filter(Service.id == s_id, Service.is_active == True).first()
                if not service:
                    return {"success": False, "error": f"Active Service with ID {s_id} not found"}
                duration = int(service.duration_minutes)
            except ValueError as e:
                return {"success": False, "error": str(e)}

        # 3. Determine target staff members
        staff_list = []
        if staff_id:
            try:
                st_id = _parse_uuid(staff_id, "staff_id", session)
                st = session.query(Staff).filter(Staff.id == st_id, Staff.branch_id == b_id, Staff.is_active == True).first()
                if not st:
                    return {"success": False, "error": f"Active Staff member {st_id} not found at branch {b_id}"}
                staff_list = [st]
            except ValueError as e:
                return {"success": False, "error": str(e)}
        else:
            # Check slots against all active staff in this branch
            staff_list = session.query(Staff).filter(Staff.branch_id == b_id, Staff.is_active == True).all()
            if not staff_list:
                return {"success": True, "slots": [], "message": "No active staff members assigned to this branch."}

        # 4. Fetch all non-cancelled appointments for this branch on the target date
        day_start = datetime.combine(target_date, time(0, 0), tzinfo=timezone.utc)
        day_end = datetime.combine(target_date, time(23, 59, 59), tzinfo=timezone.utc)
        
        appointments = session.query(Appointment).filter(
            Appointment.branch_id == b_id,
            Appointment.status != AppointmentStatus.CANCELLED,
            Appointment.start_time >= day_start,
            Appointment.start_time <= day_end
        ).all()

        # 5. Generate daily potential slot start-times
        slots_available = []
        now_utc = datetime.now(timezone.utc)

        # Loop from business open to close
        current_time = datetime.combine(target_date, time(BUSINESS_START_HOUR, 0), tzinfo=timezone.utc)
        end_boundary = datetime.combine(target_date, time(BUSINESS_END_HOUR, 0), tzinfo=timezone.utc)

        while current_time + timedelta(minutes=duration) <= end_boundary:
            slot_start = current_time
            slot_end = current_time + timedelta(minutes=duration)

            # Prevent booking past slots if checking for today
            if slot_start < now_utc:
                current_time += timedelta(minutes=SLOT_INTERVAL_MINUTES)
                continue

            # A slot is available if at least one capable staff member is completely free during slot_start -> slot_end
            any_staff_free = False
            free_staff_ids = []

            for member in staff_list:
                # Check for overlaps
                has_overlap = False
                for appt in appointments:
                    if appt.staff_id == member.id:
                        # Two intervals [S1, E1] and [S2, E2] overlap if S1 < E2 and E1 > S2
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
            "slots": slots_available
        }
    except Exception as e:
        logger.error(f"Error checking available slots: {str(e)}", exc_info=True)
        return {"success": False, "error": f"Internal database error: {str(e)}"}
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
    If no staff member is specified, automatically assigns a free staff member.
    """
    logger.info(f"Creating appointment for Customer: {customer_id}, Branch: {branch_id}, Service: {service_id}, Start: {start_time}")
    
    # Open connection if no session is injected
    session = db or SessionLocal()
    
    try:
        c_id = _parse_uuid(customer_id, "customer_id", session)
        b_id = _parse_uuid(branch_id, "branch_id", session)
        s_id = _parse_uuid(service_id, "service_id", session)
        st_start = _parse_datetime(start_time)
        st_id = _parse_uuid(staff_id, "staff_id", session) if staff_id else None
    except ValueError as e:
        logger.warning(f"Validation failed in create_appointment: {str(e)}")
        return {"success": False, "error": str(e)}

    # Ensure booking is in the future
    if st_start < datetime.now(timezone.utc):
        return {"success": False, "error": "Appointment start time must be in the future."}

    try:
        # 1. Validate Customer
        customer = session.query(Customer).filter(Customer.id == c_id, Customer.is_active == True).first()
        if not customer:
            return {"success": False, "error": f"Active Customer with ID {c_id} not found"}

        # 2. Validate Branch
        branch = session.query(Branch).filter(Branch.id == b_id, Branch.is_active == True).first()
        if not branch:
            return {"success": False, "error": f"Active Branch with ID {b_id} not found"}

        # 3. Validate Service and calculate end time
        service = session.query(Service).filter(Service.id == s_id, Service.is_active == True).first()
        if not service:
            return {"success": False, "error": f"Active Service with ID {s_id} not found"}
        
        st_end = st_start + timedelta(minutes=int(service.duration_minutes))

        # 4. Validate Business Hours
        if not _is_within_business_hours(st_start, st_end):
            return {
                "success": False, 
                "error": f"Appointment must fit inside business hours ({BUSINESS_START_HOUR}:00 to {BUSINESS_END_HOUR}:00 UTC)."
            }

        # 5. Overlap Checking: Check Customer overlap
        customer_overlap = session.query(Appointment).filter(
            Appointment.customer_id == c_id,
            Appointment.status != AppointmentStatus.CANCELLED,
            Appointment.start_time < st_end,
            Appointment.end_time > st_start
        ).first()

        if customer_overlap:
            return {
                "success": False,
                "error": f"Customer already has an appointment booking from {customer_overlap.start_time} to {customer_overlap.end_time}."
            }

        # 6. Staff Selection & Overlap Checking
        chosen_staff_id = None
        if st_id:
            # Validate Staff
            staff = session.query(Staff).filter(Staff.id == st_id, Staff.branch_id == b_id, Staff.is_active == True).first()
            if not staff:
                return {"success": False, "error": f"Active Staff member with ID {st_id} not found at Branch {b_id}"}
            
            # Check Staff overlap
            staff_overlap = session.query(Appointment).filter(
                Appointment.staff_id == st_id,
                Appointment.status != AppointmentStatus.CANCELLED,
                Appointment.start_time < st_end,
                Appointment.end_time > st_start
            ).first()

            if staff_overlap:
                return {
                    "success": False,
                    "error": f"Staff member '{staff.full_name}' is already booked from {staff_overlap.start_time} to {staff_overlap.end_time}."
                }
            chosen_staff_id = st_id
        else:
            # Dispatcher: Find an active staff member who is completely free
            all_staff = session.query(Staff).filter(Staff.branch_id == b_id, Staff.is_active == True).all()
            if not all_staff:
                return {"success": False, "error": f"No active staff members available at Branch {b_id}."}

            for member in all_staff:
                # Check overlap for this member
                overlap = session.query(Appointment).filter(
                    Appointment.staff_id == member.id,
                    Appointment.status != AppointmentStatus.CANCELLED,
                    Appointment.start_time < st_end,
                    Appointment.end_time > st_start
                ).first()
                
                if not overlap:
                    chosen_staff_id = member.id
                    logger.info(f"Automatically assigned staff member '{member.full_name}' to appointment.")
                    break
            
            if not chosen_staff_id:
                return {
                    "success": False,
                    "error": "No available staff members are free during the requested time slot."
                }

        # 7. Create Appointment under atomic transaction block
        new_appointment = Appointment(
            customer_id=c_id,
            branch_id=b_id,
            staff_id=chosen_staff_id,
            service_id=s_id,
            start_time=st_start,
            end_time=st_end,
            status=AppointmentStatus.CONFIRMED,  # Automatically confirmed
            notes=notes
        )

        # Write safely (with transaction handling if calling outer session or opening new)
        if db:
            session.add(new_appointment)
            session.flush()  # Populates ID
            appointment_id = str(new_appointment.id)
        else:
            with db_transaction() as tx:
                tx.add(new_appointment)
            appointment_id = str(new_appointment.id)

        logger.info(f"Successfully booked appointment: {appointment_id}")
        return {
            "success": True,
            "appointment_id": appointment_id,
            "assigned_staff_id": str(chosen_staff_id),
            "start_time": st_start.isoformat(),
            "end_time": st_end.isoformat(),
            "status": "CONFIRMED",
            "message": "Appointment created and confirmed successfully."
        }

    except Exception as e:
        logger.error(f"Error in create_appointment: {str(e)}", exc_info=True)
        return {"success": False, "error": f"Database transactional error: {str(e)}"}
    finally:
        if not db:
            session.close()


def cancel_appointment(appointment_id: Any, db: Optional[Session] = None) -> Dict[str, Any]:
    """
    Cancels an existing salon appointment by UUID.
    Updates the status to AppointmentStatus.CANCELLED.
    """
    logger.info(f"Request to cancel appointment ID: {appointment_id}")
    
    session = db or SessionLocal()
    
    try:
        appt_id = _parse_uuid(appointment_id, "appointment_id", session)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    try:
        appointment = session.query(Appointment).filter(Appointment.id == appt_id).first()
        if not appointment:
            return {"success": False, "error": f"Appointment with ID {appt_id} not found."}

        if appointment.status == AppointmentStatus.CANCELLED:
            return {"success": True, "message": "Appointment is already cancelled.", "appointment_id": str(appt_id)}
        
        if appointment.status == AppointmentStatus.COMPLETED:
            return {"success": False, "error": "Cannot cancel an appointment that has already been completed."}

        # Update status
        appointment.status = AppointmentStatus.CANCELLED
        
        if db:
            session.flush()
        else:
            session.commit()
            
        logger.info(f"Appointment {appt_id} cancelled successfully.")
        return {
            "success": True,
            "appointment_id": str(appt_id),
            "status": "CANCELLED",
            "message": "Appointment has been cancelled successfully."
        }
    except Exception as e:
        logger.error(f"Error in cancel_appointment: {str(e)}", exc_info=True)
        if not db:
            session.rollback()
        return {"success": False, "error": f"Database transaction rollback error: {str(e)}"}
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
    Re-validates business hours, future dates, and overlaps for both customer and stylist.
    """
    logger.info(f"Rescheduling appointment ID {appointment_id} to new start: {new_start_time}")
    
    session = db or SessionLocal()
    
    try:
        appt_id = _parse_uuid(appointment_id, "appointment_id", session)
        new_start = _parse_datetime(new_start_time)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    if new_start < datetime.now(timezone.utc):
        return {"success": False, "error": "New appointment start time must be in the future."}

    try:
        # 1. Fetch appointment
        appointment = session.query(Appointment).filter(Appointment.id == appt_id).first()
        if not appointment:
            return {"success": False, "error": f"Appointment with ID {appt_id} not found."}

        if appointment.status == AppointmentStatus.CANCELLED:
            return {"success": False, "error": "Cannot reschedule a cancelled appointment."}
        if appointment.status == AppointmentStatus.COMPLETED:
            return {"success": False, "error": "Cannot reschedule a completed appointment."}

        # 2. Fetch linked service to compute end time
        service = session.query(Service).filter(Service.id == appointment.service_id).first()
        if not service:
            return {"success": False, "error": "Associated service record not found."}

        new_end = new_start + timedelta(minutes=int(service.duration_minutes))

        # 3. Validate Business Hours
        if not _is_within_business_hours(new_start, new_end):
            return {
                "success": False,
                "error": f"New slot must fit inside business hours ({BUSINESS_START_HOUR}:00 to {BUSINESS_END_HOUR}:00 UTC)."
            }

        # 4. Overlap Checking: Customer (exclude CURRENT appointment)
        customer_overlap = session.query(Appointment).filter(
            Appointment.customer_id == appointment.customer_id,
            Appointment.id != appt_id,  # Exclude self!
            Appointment.status != AppointmentStatus.CANCELLED,
            Appointment.start_time < new_end,
            Appointment.end_time > new_start
        ).first()

        if customer_overlap:
            return {
                "success": False,
                "error": f"Customer already has another booking from {customer_overlap.start_time} to {customer_overlap.end_time}."
            }

        # 5. Overlap Checking: Staff (exclude CURRENT appointment)
        if appointment.staff_id:
            staff_overlap = session.query(Appointment).filter(
                Appointment.staff_id == appointment.staff_id,
                Appointment.id != appt_id,  # Exclude self!
                Appointment.status != AppointmentStatus.CANCELLED,
                Appointment.start_time < new_end,
                Appointment.end_time > new_start
            ).first()

            if staff_overlap:
                staff = session.query(Staff).filter(Staff.id == appointment.staff_id).first()
                staff_name = staff.full_name if staff else "Stylist"
                return {
                    "success": False,
                    "error": f"Staff member '{staff_name}' is already booked from {staff_overlap.start_time} to {staff_overlap.end_time}."
                }

        # 6. Apply Changes
        appointment.start_time = new_start
        appointment.end_time = new_end
        appointment.status = AppointmentStatus.CONFIRMED  # Re-confirm

        if db:
            session.flush()
        else:
            session.commit()

        logger.info(f"Appointment {appt_id} rescheduled successfully to {new_start.isoformat()}")
        return {
            "success": True,
            "appointment_id": str(appt_id),
            "start_time": new_start.isoformat(),
            "end_time": new_end.isoformat(),
            "status": "CONFIRMED",
            "message": "Appointment has been successfully rescheduled."
        }

    except Exception as e:
        logger.error(f"Error in reschedule_appointment: {str(e)}", exc_info=True)
        if not db:
            session.rollback()
        return {"success": False, "error": f"Database transaction rollback error: {str(e)}"}
    finally:
        if not db:
            session.close()


def get_customer_history(customer_id: Any, db: Optional[Session] = None) -> Dict[str, Any]:
    """
    Retrieves all booking history for a specific customer.
    Includes comprehensive details of branches, services, staff, and reviews.
    """
    logger.info(f"Fetching customer history for: {customer_id}")
    
    session = db or SessionLocal()
    
    try:
        c_id = _parse_uuid(customer_id, "customer_id", session)
    except ValueError as e:
        return {"success": False, "error": str(e)}

    try:
        # Check Customer exists
        customer = session.query(Customer).filter(Customer.id == c_id).first()
        if not customer:
            return {"success": False, "error": f"Customer with ID {c_id} not found."}

        # Query all appointments, ordered from newest to oldest
        appointments = session.query(Appointment).filter(
            Appointment.customer_id == c_id
        ).order_by(Appointment.start_time.desc()).all()

        history_list = []
        for appt in appointments:
            # Query associated objects cleanly
            branch = appt.branch
            service = appt.service
            staff = appt.staff
            review = appt.review

            history_list.append({
                "appointment_id": str(appt.id),
                "branch": {
                    "id": str(branch.id) if branch else None,
                    "name": branch.name if branch else None,
                    "city": branch.city if branch else None
                } if branch else None,
                "service": {
                    "id": str(service.id) if service else None,
                    "name": service.name if service else None,
                    "price": float(service.price) if service else None,
                    "duration_minutes": service.duration_minutes if service else None
                } if service else None,
                "staff": {
                    "id": str(staff.id) if staff else None,
                    "name": staff.full_name if staff else None,
                    "role": staff.role if staff else None
                } if staff else None,
                "start_time": appt.start_time.isoformat(),
                "end_time": appt.end_time.isoformat(),
                "status": appt.status.value,
                "notes": appt.notes,
                "review": {
                    "id": str(review.id),
                    "rating": review.rating,
                    "comment": review.comment,
                    "status": review.status.value
                } if review else None
            })

        return {
            "success": True,
            "customer_id": str(c_id),
            "customer_name": customer.full_name,
            "email": customer.email,
            "appointment_count": len(history_list),
            "history": history_list
        }
    except Exception as e:
        logger.error(f"Error in get_customer_history: {str(e)}", exc_info=True)
        return {"success": False, "error": f"Database query failure: {str(e)}"}
    finally:
        if not db:
            session.close()
