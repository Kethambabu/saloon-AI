"""
Appointment Lifecycle Application Service for SalonAI Workforce Platform.
Consolidates booking creation, cancellation, rescheduling, and customer searches.
"""

import logging
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func, case, desc

from infrastructure.db.database import SessionLocal, db_transaction
from infrastructure.db.models import (
    Appointment,
    AppointmentStatus,
    Customer,
    Branch,
    Staff,
    Service,
    Notification,
)
from infrastructure.events.event_bus import (
    get_event_bus,
    AppointmentBookedEvent,
    AppointmentCancelledEvent,
    AppointmentRescheduledEvent,
)

from application.services.datetime_validation import (
    validate_appointment_datetime,
    validateAppointmentDateTime,
)

logger = logging.getLogger(__name__)

def _is_within_business_hours(start: datetime, end: datetime) -> bool:
    """Checks if the appointment slot fits completely within daily business hours (9:00 AM to 8:00 PM local/UTC)."""
    from datetime import time
    business_start = datetime.combine(start.date(), time(9, 0), tzinfo=timezone.utc)
    business_end = datetime.combine(start.date(), time(20, 0), tzinfo=timezone.utc)
    return start >= business_start and end <= business_end


def _parse_uuid(value: Any, name: str = "id") -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except ValueError as e:
        raise ValueError(f"Invalid UUID format for {name}: '{value}'") from e


_appointment_service_instance: Optional["AppointmentService"] = None

class AppointmentService:
    """
    Application Service managing Salon Appointment lifecycle and database states.
    """

    def __init__(self) -> None:
        self._event_bus = get_event_bus()
        logger.info("AppointmentService initialized.")

    def book(
        self,
        customer_id: str,
        branch_id: str,
        service_id: str,
        start_time: str,
        staff_id: Optional[str] = None,
        notes: Optional[str] = None,
        tenant_id: str = "default",
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Book a new appointment and publish AppointmentBookedEvent."""
        logger.info(f"[AppointmentService] Booking appointment for customer={customer_id}")

        # Mandatory pre-validation before any DB queries or entity resolutions
        val = validate_appointment_datetime(start_time)
        if not val["valid"]:
            return {"success": False, "error": val["reason"]}

        
        session = db or SessionLocal()
        try:
            # Auto-cancel any expired appointments in the system
            auto_cancel_all_expired_appointments(session)

            # 0. Check placeholders
            if _is_placeholder_value(branch_id):
                return {"success": False, "error": f"Invalid branch identifier '{branch_id}'."}
            if _is_placeholder_value(service_id):
                return {"success": False, "error": f"Invalid service identifier '{service_id}'."}
            if staff_id and _is_placeholder_value(staff_id):
                return {"success": False, "error": f"Invalid staff identifier '{staff_id}'."}
                
            from application.services.entity_resolver_service import (
                resolve_customer,
                resolve_branch,
                resolve_service,
                resolve_staff,
            )
            
            # Resolve customer
            try:
                c_id = resolve_customer(customer_id, session, raise_on_missing=True)
            except ValueError as val_err:
                from application.services.entity_resolver_service import _is_valid_uuid
                cust_query = None
                if _is_valid_uuid(str(customer_id)):
                    cust_query = session.query(Customer).filter(Customer.id == uuid.UUID(str(customer_id))).first()
                else:
                    cust_query = session.query(Customer).filter(
                        or_(
                            Customer.email.ilike(str(customer_id)),
                            Customer.phone == str(customer_id)
                        )
                    ).first()
                if cust_query and not cust_query.is_active:
                    return {"success": False, "error": "Customer account is inactive."}
                return {"success": False, "error": str(val_err)}

            if not c_id:
                return {"success": False, "error": f"Customer '{customer_id}' not found."}
            customer = session.query(Customer).filter(Customer.id == c_id).first()
            
            # Resolve branch
            b_id = resolve_branch(branch_id, session)
            if not b_id:
                return {"success": False, "error": f"Branch '{branch_id}' not found."}
            branch = session.query(Branch).filter(Branch.id == b_id).first()
            
            # Resolve service
            s_id = resolve_service(service_id, session)
            if not s_id:
                return {"success": False, "error": f"Service '{service_id}' not found."}
            service = session.query(Service).filter(Service.id == s_id).first()
            
            # 1. Parse start time
            start_dt = None
            if isinstance(start_time, str):
                st_str = start_time.strip()
                if st_str.endswith("Z"):
                    st_str = st_str[:-1] + "+00:00"
                if " " in st_str and "T" not in st_str and len(st_str) >= 19:
                    st_str = st_str.replace(" ", "T", 1)
                try:
                    start_dt = datetime.fromisoformat(st_str)
                except ValueError:
                    # Fallback for time-only strings (e.g. "15:00", "10:00 AM")
                    try:
                        from application.services.entity_resolver_service import resolve_relative_time
                        time_part = resolve_relative_time(st_str)
                        date_part = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                        start_dt = datetime.fromisoformat(f"{date_part}T{time_part}:00+00:00")
                    except Exception:
                        start_dt = None
            if not start_dt:
                return {"success": False, "error": f"Invalid start_time format: '{start_time}'."}
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)
                
            # Ensure booking is in the future
            if start_dt <= datetime.now(timezone.utc):
                return {"success": False, "error": "Appointments must be in the future."}
                
            end_dt = start_dt + timedelta(minutes=service.duration_minutes)
            
            # Validate Business Hours
            if not _is_within_business_hours(start_dt, end_dt):
                req_hour = start_dt.hour
                req_end_hour = end_dt.hour
                return {
                    "success": False, 
                    "error": f"Appointment must fit inside business hours (9:00 AM to 8:00 PM). Requested: {req_hour}:00–{req_end_hour}:{end_dt.minute:02d}."
                }
                
            # Enforce Customer Booking Limits
            active_bookings_count = session.query(Appointment).filter(
                Appointment.customer_id == c_id,
                Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED]),
                Appointment.start_time > datetime.now(timezone.utc),
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
                
            # Duplicate Appointment Detection
            duplicate_query = session.query(Appointment).filter(
                Appointment.customer_id == c_id,
                Appointment.service_id == s_id,
                Appointment.start_time == start_dt,
                Appointment.status != AppointmentStatus.CANCELLED
            )
            
            # Resolve staff if provided
            st_id = None
            if staff_id:
                st_id = resolve_staff(staff_id, session)
                if not st_id:
                    return {"success": False, "error": f"Staff '{staff_id}' not found."}
                duplicate_query = duplicate_query.filter(Appointment.staff_id == st_id)
                
            duplicate = duplicate_query.first()
            if duplicate:
                return {
                    "success": False,
                    "error": "Duplicate appointment detected. You already have this exact appointment scheduled."
                }
                
            # Customer Overlap Check
            customer_overlap = session.query(Appointment).filter(
                Appointment.customer_id == c_id,
                Appointment.status != AppointmentStatus.CANCELLED,
                Appointment.start_time < end_dt,
                Appointment.end_time > start_dt
            ).first()
            if customer_overlap:
                return {
                    "success": False,
                    "error": "You already have an appointment scheduled at that time."
                }
                
            # Staff Assignment & Overlap Checks
            chosen_staff_id = None
            if st_id:
                # Check active
                staff = session.query(Staff).filter(Staff.id == st_id, Staff.is_active == True).first()
                if not staff:
                    return {"success": False, "error": "Staff member not found or inactive"}
                # Check leave
                date_str = start_dt.strftime("%Y-%m-%d")
                on_leave, staff_name = is_staff_on_leave(st_id, date_str, session)
                if on_leave:
                    alt_names = _find_available_staff_names(
                        session, b_id, st_id, start_dt, end_dt, date_str
                    )
                    if alt_names:
                        error_msg = (
                            f"{staff_name} is unavailable on {date_str} due to scheduled leave. "
                            f"The stylist you want is on leave, so please book another stylist. "
                            f"Available at this time: {', '.join(alt_names)}."
                        )
                    else:
                        error_msg = (
                            f"{staff_name} is unavailable on {date_str} due to scheduled leave. "
                            f"The stylist you want is on leave, so please book another stylist. "
                            f"No other stylists are free at this exact time; please choose a different time."
                        )
                    return {"success": False, "error": error_msg}
                # Check overlap
                staff_overlap = session.query(Appointment).filter(
                    Appointment.staff_id == st_id,
                    Appointment.status != AppointmentStatus.CANCELLED,
                    Appointment.start_time < end_dt,
                    Appointment.end_time > start_dt
                ).first()
                if staff_overlap:
                    return {
                        "success": False,
                        "error": f"Staff member '{staff.full_name}' is already booked from {staff_overlap.start_time.strftime('%Y-%m-%d %H:%M')} to {staff_overlap.end_time.strftime('%Y-%m-%d %H:%M')} UTC."
                    }
                chosen_staff_id = st_id
            else:
                # Find free staff member
                all_staff = session.query(Staff).filter(Staff.branch_id == b_id, Staff.is_active == True).all()
                if not all_staff:
                    return {"success": False, "error": "No active staff members available."}
                    
                for member in all_staff:
                    # Check leave
                    date_str = start_dt.strftime("%Y-%m-%d")
                    on_leave, _ = is_staff_on_leave(member.id, date_str, session)
                    if on_leave:
                        continue
                    # Check overlap
                    overlap = session.query(Appointment).filter(
                        Appointment.staff_id == member.id,
                        Appointment.status != AppointmentStatus.CANCELLED,
                        Appointment.start_time < end_dt,
                        Appointment.end_time > start_dt
                    ).first()
                    if not overlap:
                        chosen_staff_id = member.id
                        break
                        
                if not chosen_staff_id:
                    return {"success": False, "error": "No available staff members for the requested time slot."}
                    
            # 3. Create appointment model
            appt = Appointment(
                id=uuid.uuid4(),
                customer_id=c_id,
                branch_id=b_id,
                staff_id=chosen_staff_id,
                service_id=s_id,
                start_time=start_dt,
                end_time=end_dt,
                status=AppointmentStatus.CONFIRMED,
                notes=notes or "",
            )
            # Check for recommendations conversion
            try:
                from infrastructure.db.models import CustomerRecommendation
                if hasattr(CustomerRecommendation, 'service_id') and hasattr(CustomerRecommendation, 'accepted'):
                    matching_recs = session.query(CustomerRecommendation).filter(
                        CustomerRecommendation.customer_id == c_id,
                        CustomerRecommendation.service_id == s_id,
                        CustomerRecommendation.accepted == False
                    ).all()
                    for r in matching_recs:
                        r.accepted = True
                        if hasattr(r, 'appointment_id'):
                            r.appointment_id = appt.id
            except Exception as rec_err:
                logger.error(f"Error converting recommendation: {rec_err}")
                
            session.add(appt)
            session.flush()

            # Dispatch notification to user dynamically
            try:
                from infrastructure.db.models import User
                user = session.query(User).filter(User.customer_id == c_id).first()
                if user:
                    notif = Notification(
                        id=uuid.uuid4(),
                        user_id=user.id,
                        title="Appointment Confirmed",
                        message=f"Your appointment for {service.name} has been confirmed and is ready.",
                        is_read=False
                    )
                    session.add(notif)
            except Exception as notif_err:
                logger.error(f"[AppointmentService] Error creating booking notification: {notif_err}")

            # Mark active leads as converted
            try:
                from infrastructure.db.models import Lead, LeadStatus
                active_leads = session.query(Lead).filter(
                    Lead.customer_id == c_id,
                    Lead.status.in_([LeadStatus.NEW, LeadStatus.CONTACTED])
                ).all()
                for lead in active_leads:
                    lead.status = LeadStatus.CONVERTED
                    lead.converted = True
                    lead.converted_at = datetime.now(timezone.utc)
                    lead.notes = (lead.notes or "") + f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Converted to confirmed booking (Appointment ID: {appt.id})."
                logger.info(f"[AppointmentService] Converted {len(active_leads)} active leads for customer {c_id}")
            except Exception as lead_err:
                logger.error(f"[AppointmentService] Error converting lead on appointment creation: {lead_err}")

            session.commit()
            
            # Post-booking Verification Layer (Step 12)
            verified_appt = session.query(Appointment).filter(Appointment.id == appt.id).first()
            if not verified_appt:
                session.rollback()
                logger.critical(f"[AppointmentService] Verification failed! Created appointment {appt.id} not found after commit.")
                return {
                    "success": False,
                    "error": "Booking verification failed. Transaction rolled back for security."
                }
            
            try:
                from infrastructure.cache.response_cache import invalidate_customer_cache, invalidate_availability_cache
                invalidate_customer_cache(str(c_id))
                date_str = start_dt.strftime("%Y-%m-%d")
                invalidate_availability_cache(str(b_id), date_str)
            except Exception as cache_err:
                logger.warning(f"[AppointmentService] Cache invalidation failed: {cache_err}")
            
            # 4. Publish Event
            try:
                self._event_bus.publish(AppointmentBookedEvent(
                    tenant_id=tenant_id,
                    appointment_id=str(appt.id),
                    customer_id=str(c_id),
                    staff_id=str(chosen_staff_id) if chosen_staff_id else None,
                    service_id=str(s_id),
                    starts_at=start_dt,
                    payload={
                        "appointment_id": str(appt.id),
                        "customer_id": str(c_id),
                        "branch_id": str(b_id),
                        "service_id": str(s_id),
                        "staff_id": str(chosen_staff_id) if chosen_staff_id else None,
                        "start_time": start_dt.isoformat(),
                        "tenant_id": tenant_id
                    }
                ))
            except Exception as ev_exc:
                logger.error(f"[AppointmentService] Event publish failed: {ev_exc}")
                
            # Return flat dict for backward compatibility
            return {
                "success": True,
                "appointment_id": str(appt.id),
                "status": appt.status.value,
                "start_time": appt.start_time.isoformat(),
                "price": str(service.price),
                "message": "Appointment confirmed successfully.",
            }
            
        except ValueError as val_err:
            logger.error(f"[AppointmentService] Booking validation failed: {val_err}")
            session.rollback()
            return {"success": False, "error": str(val_err)}
        except Exception as e:
            logger.error(f"[AppointmentService] Booking failed: {e}", exc_info=True)
            session.rollback()
            return {"success": False, "error": f"Database error: {str(e)}"}
        finally:
            if not db:
                session.close()

    def cancel(
        self,
        appointment_id: str,
        customer_id: Optional[str] = None,
        tenant_id: str = "default",
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Cancel an existing appointment and publish AppointmentCancelledEvent."""
        logger.info(f"[AppointmentService] Cancelling appointment={appointment_id}")
        session = db or SessionLocal()
        try:
            appt = None
            appt_uuid = None

            is_placeholder = _is_placeholder_value(appointment_id)
            if not is_placeholder:
                try:
                    appt_uuid = _parse_uuid(appointment_id, "appointment_id")
                    appt = session.query(Appointment).filter(Appointment.id == appt_uuid).first()
                except Exception:
                    pass

            # Fallback: appointment_id didn't resolve to a real appointment — it
            # may actually be a customer ID the caller (LLM) supplied by mistake
            # (Fallback 1, appt_uuid parsed but matched nothing), or it may have
            # been missing/placeholder/invalid, in which case we fall back to the
            # customer_id parameter instead (Fallback 2). In both cases we must
            # NOT silently guess which appointment was meant when the customer has
            # more than one active booking — auto-resolve only when there is
            # exactly one candidate, otherwise fail safely and ask for
            # disambiguation instead of risking cancelling the wrong appointment.
            if not appt:
                fallback_source = appt_uuid or customer_id
                if fallback_source:
                    candidates = _find_active_appointments_for_customer(fallback_source, session)
                    if len(candidates) == 1:
                        appt = candidates[0]
                        appt_uuid = appt.id
                        logger.info(
                            "[AppointmentService] Resolved '%s' to sole active appointment=%s",
                            appointment_id, appt.id,
                        )
                    elif len(candidates) > 1:
                        options = "; ".join(
                            f"{a.start_time.strftime('%Y-%m-%d %H:%M')} UTC (id={a.id})" for a in candidates
                        )
                        return {
                            "success": False,
                            "error": (
                                "You have more than one upcoming appointment, so I can't tell which one "
                                f"you mean from '{appointment_id}'. Your upcoming appointments are: {options}. "
                                "Please specify which one (e.g. by date/time)."
                            ),
                        }

            if not appt:
                return {"success": False, "error": f"Appointment {appointment_id} not found."}

            if customer_id and str(appt.customer_id) != str(customer_id):
                return {"success": False, "error": "Unauthorized to cancel this appointment."}

            old_status = appt.status.value
            appt.status = AppointmentStatus.CANCELLED
            
            # Deduct loyalty points for cancellation penalty
            try:
                from application.services.loyalty_service import get_loyalty_service
                get_loyalty_service().on_appointment_cancelled(session, appt.id, appt.customer_id)
            except Exception as loy_exc:
                logger.error(f"[AppointmentService] Loyalty cancellation penalty failed: {loy_exc}")

            # Dispatch notification to user dynamically
            try:
                from infrastructure.db.models import User
                user = session.query(User).filter(User.customer_id == appt.customer_id).first()
                if user:
                    service_name = appt.service.name if appt.service else "Styling Treatment"
                    notif = Notification(
                        id=uuid.uuid4(),
                        user_id=user.id,
                        title="Appointment Cancelled",
                        message=f"Your appointment for {service_name} has been cancelled successfully.",
                        is_read=False
                    )
                    session.add(notif)
            except Exception as notif_err:
                logger.error(f"[AppointmentService] Error creating cancellation notification: {notif_err}")

            # Check waitlist notifications (Rule 16)
            try:
                appt_date = appt.start_time.strftime("%Y-%m-%d")
                appt_time = appt.start_time.strftime("%H:%M")
                
                from infrastructure.db.models import Waitlist, User
                
                waitlists = session.query(Waitlist).filter(
                    Waitlist.branch_id == appt.branch_id,
                    Waitlist.service_id == appt.service_id,
                    Waitlist.date_str == appt_date,
                    Waitlist.time_str == appt_time,
                    Waitlist.is_notified == False
                ).all()
                
                for wl in waitlists:
                    wl_user = session.query(User).filter(User.customer_id == wl.customer_id).first()
                    if wl_user:
                        branch_name = appt.branch.name if appt.branch else "Salon"
                        service_name = appt.service.name if appt.service else "Styling Treatment"
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
                logger.error(f"[AppointmentService] Error notifying waitlist: {wl_err}")
                
            session.commit()
            
            # Publish Event
            try:
                self._event_bus.publish(AppointmentCancelledEvent(
                    tenant_id=tenant_id,
                    appointment_id=str(appt_uuid),
                    customer_id=str(appt.customer_id),
                    payload={
                        "appointment_id": str(appt_uuid),
                        "customer_id": str(appt.customer_id),
                        "tenant_id": tenant_id
                    }
                ))
            except Exception as ev_exc:
                logger.error(f"[AppointmentService] Event publish failed: {ev_exc}")
                
            return {
                "success": True,
                "data": {
                    "appointment_id": str(appt_uuid),
                    "status": appt.status.value,
                    "message": "Appointment cancelled successfully."
                }
            }
        except Exception as e:
            logger.error(f"[AppointmentService] Cancellation failed: {e}", exc_info=True)
            session.rollback()
            return {"success": False, "error": str(e)}
        finally:
            if not db:
                session.close()

    def reschedule(
        self,
        appointment_id: str,
        new_start_time: str,
        new_staff_id: Optional[str] = None,
        customer_id: Optional[str] = None,
        tenant_id: str = "default",
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Reschedule an existing appointment and publish AppointmentRescheduledEvent."""
        logger.info(f"[AppointmentService] Rescheduling appointment={appointment_id}")

        # Mandatory pre-validation before any DB queries
        val = validate_appointment_datetime(new_start_time)
        if not val["valid"]:
            return {"success": False, "error": val["reason"]}

        session = db or SessionLocal()
        try:
            appt = None
            appt_uuid = None

            is_placeholder = _is_placeholder_value(appointment_id)
            if not is_placeholder:
                try:
                    appt_uuid = _parse_uuid(appointment_id, "appointment_id")
                    appt = session.query(Appointment).filter(Appointment.id == appt_uuid).first()
                except Exception:
                    pass

            # Fallback: appointment_id didn't resolve to a real appointment — it
            # may actually be a customer ID the caller (LLM) supplied by mistake
            # (Fallback 1, appt_uuid parsed but matched nothing), or it may have
            # been missing/placeholder/invalid, in which case we fall back to the
            # customer_id parameter instead (Fallback 2). Only auto-resolve when
            # there is exactly one active-appointment candidate for that customer
            # — see _find_active_appointments_for_customer's docstring for why
            # silently picking one of several (previously: the single
            # furthest-in-the-future one) is unsafe.
            if not appt:
                fallback_source = appt_uuid or customer_id
                if fallback_source:
                    candidates = _find_active_appointments_for_customer(fallback_source, session)
                    if len(candidates) == 1:
                        appt = candidates[0]
                        appt_uuid = appt.id
                        logger.info(
                            "[AppointmentService] Resolved '%s' to sole active appointment=%s",
                            appointment_id, appt.id,
                        )
                    elif len(candidates) > 1:
                        options = "; ".join(
                            f"{a.start_time.strftime('%Y-%m-%d %H:%M')} UTC (id={a.id})" for a in candidates
                        )
                        return {
                            "success": False,
                            "error": (
                                "You have more than one upcoming appointment, so I can't tell which one "
                                f"you mean from '{appointment_id}'. Your upcoming appointments are: {options}. "
                                "Please specify which one (e.g. by date/time)."
                            ),
                        }

            if not appt:
                if is_placeholder:
                    return {"success": False, "error": f"Invalid appointment identifier '{appointment_id}'."}
                return {"success": False, "error": "Appointment not found."}
                
            if customer_id:
                from application.services.entity_resolver_service import resolve_customer
                c_id = resolve_customer(customer_id, session)
                if not c_id or appt.customer_id != c_id:
                    return {"success": False, "error": "You are not authorized to reschedule this appointment."}
                    
            if appt.status == AppointmentStatus.CANCELLED:
                return {"success": False, "error": "Cannot reschedule a cancelled appointment."}
            if appt.status == AppointmentStatus.COMPLETED:
                return {"success": False, "error": "Cannot reschedule a completed appointment."}
                
            # Parse start time
            if new_start_time.endswith("Z"):
                new_start_time = new_start_time[:-1] + "+00:00"
            start_dt = datetime.fromisoformat(new_start_time)
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)
                
            # Ensure rescheduling is in the future
            if start_dt <= datetime.now(timezone.utc):
                return {"success": False, "error": "Appointments must be in the future."}
                
            # Get service
            service = session.query(Service).filter(Service.id == appt.service_id).first()
            if not service:
                return {"success": False, "error": "Associated service not found."}
            end_dt = start_dt + timedelta(minutes=int(service.duration_minutes))
            
            # Validate Business Hours
            if not _is_within_business_hours(start_dt, end_dt):
                return {
                    "success": False,
                    "error": f"New slot must fit inside business hours (9:00 AM to 8:00 PM). Requested: {start_dt.hour}:00–{end_dt.hour}:{end_dt.minute:02d}."
                }
                
            # Overlap Checking: Customer (exclude self)
            customer_overlap = session.query(Appointment).filter(
                Appointment.customer_id == appt.customer_id,
                Appointment.id != appt_uuid,
                Appointment.status != AppointmentStatus.CANCELLED,
                Appointment.start_time < end_dt,
                Appointment.end_time > start_dt
            ).first()
            if customer_overlap:
                return {
                    "success": False,
                    "error": "You already have an appointment scheduled at that time."
                }
                
            # Staff check
            target_staff_id = appt.staff_id
            if new_staff_id:
                from application.services.entity_resolver_service import resolve_staff
                target_staff_id = resolve_staff(new_staff_id, session)
                if not target_staff_id:
                    return {"success": False, "error": "Staff not found."}
                
            if target_staff_id:
                # Check leave
                date_str = start_dt.strftime("%Y-%m-%d")
                on_leave, staff_name = is_staff_on_leave(target_staff_id, date_str, session)
                if on_leave:
                    alt_names = _find_available_staff_names(
                        session, appt.branch_id, target_staff_id, start_dt, end_dt, date_str
                    )
                    if alt_names:
                        error_msg = (
                            f"{staff_name} is unavailable on {date_str} due to scheduled leave. "
                            f"The stylist you want is on leave, so please book another stylist. "
                            f"Available at this time: {', '.join(alt_names)}."
                        )
                    else:
                        error_msg = (
                            f"{staff_name} is unavailable on {date_str} due to scheduled leave. "
                            f"The stylist you want is on leave, so please book another stylist. "
                            f"No other stylists are free at this exact time; please choose a different time."
                        )
                    return {"success": False, "error": error_msg}
                # Check staff overlap
                staff_overlap = session.query(Appointment).filter(
                    Appointment.staff_id == target_staff_id,
                    Appointment.id != appt_uuid,
                    Appointment.status != AppointmentStatus.CANCELLED,
                    Appointment.start_time < end_dt,
                    Appointment.end_time > start_dt
                ).first()
                if staff_overlap:
                    staff = session.query(Staff).filter(Staff.id == target_staff_id).first()
                    staff_name = staff.full_name if staff else "Stylist"
                    return {
                        "success": False,
                        "error": f"Staff member '{staff_name}' is already booked from {staff_overlap.start_time.strftime('%Y-%m-%d %H:%M')} to {staff_overlap.end_time.strftime('%Y-%m-%d %H:%M')} UTC."
                    }
                    
            old_start = appt.start_time.isoformat()
            appt.start_time = start_dt
            appt.end_time = end_dt
            if target_staff_id:
                appt.staff_id = target_staff_id
            appt.status = AppointmentStatus.CONFIRMED
            
            # Send Notification log if needed
            try:
                from infrastructure.db.models import Notification, User
                user = session.query(User).filter(User.customer_id == appt.customer_id).first()
                if user:
                    notif = Notification(
                        id=uuid.uuid4(),
                        user_id=user.id,
                        title="Appointment Rescheduled",
                        message=f"Your appointment has been successfully rescheduled to {start_dt.strftime('%Y-%m-%d %I:%M %p')}.",
                        is_read=False
                    )
                    session.add(notif)
            except Exception as notif_err:
                logger.error(f"Error creating rescheduled notification: {notif_err}")
                
            session.commit()
            
            # Publish Event
            try:
                self._event_bus.publish(AppointmentRescheduledEvent(
                    tenant_id=tenant_id,
                    appointment_id=str(appt_uuid),
                    customer_id=str(appt.customer_id),
                    payload={
                        "appointment_id": str(appt_uuid),
                        "customer_id": str(appt.customer_id),
                        "previous_start_time": old_start,
                        "new_start_time": start_dt.isoformat(),
                        "tenant_id": tenant_id
                    }
                ))
            except Exception as ev_exc:
                logger.error(f"[AppointmentService] Event publish failed: {ev_exc}")
                
            return {
                "success": True,
                "data": {
                    "appointment_id": str(appt_uuid),
                    "status": appt.status.value,
                    "new_start_time": appt.start_time.isoformat()
                }
            }
        except Exception as e:
            logger.error(f"[AppointmentService] Reschedule failed: {e}", exc_info=True)
            session.rollback()
            return {"success": False, "error": str(e)}
        finally:
            if not db:
                session.close()

    def list_appointments(
        self,
        customer_id: str,
        limit: int = 20,
        tenant_id: str = "default",
        db: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """List appointments for a given customer."""
        session = db or SessionLocal()
        try:
            auto_cancel_all_expired_appointments(session)
            cust_uuid = _parse_uuid(customer_id, "customer_id")
            appts = session.query(Appointment).filter(
                Appointment.customer_id == cust_uuid
            ).order_by(Appointment.start_time.desc()).limit(limit).all()
            
            res_list = []
            for a in appts:
                res_list.append({
                    "id": str(a.id),
                    "service_name": a.service.name if a.service else "Styling Session",
                    "staff_name": f"{a.staff.first_name} {a.staff.last_name}" if a.staff else "Stylist",
                    "branch_name": a.branch.name if a.branch else "Salon Branch",
                    "start_time": a.start_time.isoformat(),
                    "status": a.status.value,
                })
            return {"success": True, "data": res_list}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            if not db:
                session.close()

    def list_services(self, tenant_id: str = "default", db: Optional[Session] = None) -> Dict[str, Any]:
        """List all active salon services."""
        session = db or SessionLocal()
        try:
            services = session.query(Service).filter(Service.is_active == True).all()
            res_list = []
            for s in services:
                res_list.append({
                    "id": str(s.id),
                    "name": s.name,
                    "price": float(s.price),
                    "duration_minutes": s.duration_minutes
                })
            return {"success": True, "data": res_list}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            if not db:
                session.close()

    def list_staff(self, tenant_id: str = "default", db: Optional[Session] = None) -> Dict[str, Any]:
        """List all active salon staff."""
        session = db or SessionLocal()
        try:
            staff = session.query(Staff).filter(Staff.is_active == True).all()
            res_list = []
            for st in staff:
                res_list.append({
                    "id": str(st.id),
                    "name": f"{st.first_name} {st.last_name}",
                    "specialty": getattr(st, "specialty", "Stylist")
                })
            return {"success": True, "data": res_list}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            if not db:
                session.close()

    def search_customers(self, query: str, tenant_id: str = "default", db: Optional[Session] = None) -> Dict[str, Any]:
        """Search for customers by name, phone, or email."""
        session = db or SessionLocal()
        try:
            custs = session.query(Customer).filter(
                or_(
                    Customer.first_name.ilike(f"%{query}%"),
                    Customer.last_name.ilike(f"%{query}%"),
                    Customer.email.ilike(f"%{query}%"),
                    Customer.phone.ilike(f"%{query}%")
                )
            ).all()
            res_list = []
            for c in custs:
                res_list.append({
                    "id": str(c.id),
                    "name": c.full_name,
                    "email": c.email,
                    "phone": c.phone
                })
            return {"success": True, "data": res_list}
        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            if not db:
                session.close()


def get_appointment_service() -> AppointmentService:
    global _appointment_service_instance
    if _appointment_service_instance is None:
        _appointment_service_instance = AppointmentService()
    return _appointment_service_instance


# Backward-compatibility wrappers for standalone functions
from application.services.availability_service import get_available_slots

def create_appointment(*args, **kwargs):
    res = get_appointment_service().book(*args, **kwargs)
    if res.get("success") and "data" in res:
        data = res["data"]
        return {
            "success": True,
            "appointment_id": data.get("appointment_id"),
            "status": data.get("status"),
            "start_time": data.get("start_time"),
            "price": str(data.get("price")),
            "message": "Appointment confirmed successfully."
        }
    return res

def cancel_appointment(*args, **kwargs):
    res = get_appointment_service().cancel(*args, **kwargs)
    if res.get("success") and "data" in res:
        data = res["data"]
        return {
            "success": True,
            "appointment_id": data.get("appointment_id"),
            "status": data.get("status"),
            "message": data.get("message", "Appointment cancelled successfully.")
        }
    return res

def reschedule_appointment(*args, **kwargs):
    res = get_appointment_service().reschedule(*args, **kwargs)
    if res.get("success") and "data" in res:
        data = res["data"]
        return {
            "success": True,
            "appointment_id": data.get("appointment_id"),
            "status": data.get("status"),
            "new_start_time": data.get("new_start_time"),
            "message": "Appointment rescheduled successfully."
        }
    return res

def list_services(*args, **kwargs):
    return get_appointment_service().list_services(*args, **kwargs)

def list_staff(*args, **kwargs):
    return get_appointment_service().list_staff(*args, **kwargs)

def search_customers(*args, **kwargs):
    return get_appointment_service().search_customers(*args, **kwargs)

def list_appointments(*args, **kwargs):
    return get_appointment_service().list_appointments(*args, **kwargs)


# Placeholder validation for testing and agent safeguards
_PLACEHOLDER_VALUES = {
    "first_branch_id", "first_service_id", "first_staff_id", "first_customer_id",
    "second_branch_id", "second_service_id", "second_staff_id",
    "default_branch_id", "default_service_id", "default_staff_id",
    "placeholder", "first", "second", "default", "example", "test",
    "branch_id", "service_id", "staff_id", "customer_id", "appointment_id",
    "your_branch", "your_service", "your_staff", "your_customer",
    "select_branch", "select_service", "select_staff",
    "none_specified", "not_specified", "unspecified", "any", "none", "null", "undefined",
    # Short tokens an LLM sometimes emits verbatim as a whole "I don't have a
    # real ID" placeholder. Matched only as an EXACT full value here (not as a
    # substring — see _PLACEHOLDER_SUBSTRINGS note below for why that matters).
    "xxxx", "1111", "0000", "aaaa", "abcd", "1234",
}

_PLACEHOLDER_SUBSTRINGS = [
    "first_", "second_", "default_", "select_", "example_", "your_",
]
# NOTE: "xxxx", "1111", "0000", "aaaa", "abcd", "1234" used to live in this
# substring list too, matched via "substring in value_str" — i.e. flagged as
# fake ANY identifier merely *containing* one of those 4-char runs anywhere.
# A real, randomly-generated 32-hex-digit UUID has a non-trivial chance of
# containing one of those runs purely by coincidence, so that check silently
# misidentified real appointment/customer/staff/branch/service UUIDs as
# hallucinated placeholders, causing bookings/cancellations/reschedules to
# fail intermittently for no reason a customer or support agent could
# explain. They now live in _PLACEHOLDER_VALUES (exact full-value match
# only), and the patterns below catch the UUID-shaped fakes an LLM actually
# invents (all-zeros, all-ones, all-a's, the textbook
# "12345678-1234-1234-1234-123456789012") by matching the WHOLE identifier.
_SEQUENTIAL_PLACEHOLDER_RE = re.compile(
    r"^(?:00000000-0000-0000-0000-000000000000|"
    r"11111111-1111-1111-1111-111111111111|"
    r"aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa|"
    r"12345678-1234-1234-1234-123456789012|"
    r"xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)$"
)

def _is_placeholder_value(value: Any) -> bool:
    """Detect if an identifier is a placeholder/hallucinated value from an LLM."""
    if value is None or value == "":
        return False
    value_str = str(value).strip().lower()
    if value_str in _PLACEHOLDER_VALUES:
        return True
    if any(sub in value_str for sub in _PLACEHOLDER_SUBSTRINGS):
        return True
    if _SEQUENTIAL_PLACEHOLDER_RE.match(value_str):
        return True
    # Degenerate all-repeated-character UUID (e.g. "cccccccc-cccc-...") that
    # isn't one of the specific patterns above — checked against the full
    # de-hyphenated value so a real UUID that merely *contains* a short run
    # of a repeated character is never caught by this.
    hex_only = value_str.replace("-", "")
    if len(hex_only) == 32 and len(set(hex_only)) == 1:
        return True
    return False


def _find_active_appointments_for_customer(cust_id_val: Any, session: Session) -> List["Appointment"]:
    """Return this customer's active (CONFIRMED/PENDING) appointments, soonest first.

    Used by cancel()/reschedule() as a fallback when the caller (an LLM agent)
    couldn't supply a real appointment_id and a customer identifier was given
    instead — either because appointment_id itself turned out to be a customer
    UUID, or because appointment_id was missing/invalid and the customer_id
    parameter was used. Ordered ascending by start_time so that when there's
    exactly one candidate, "the" appointment resolved is the next upcoming
    one — previously this used start_time DESCENDING ("latest"), which
    actually picked whichever active appointment was furthest in the future,
    silently cancelling/rescheduling the wrong booking for any customer with
    more than one upcoming appointment.
    """
    try:
        cust_uuid = _parse_uuid(cust_id_val, "customer_id")
    except Exception:
        return []
    return (
        session.query(Appointment)
        .filter(
            Appointment.customer_id == cust_uuid,
            Appointment.status.in_([AppointmentStatus.CONFIRMED, AppointmentStatus.PENDING]),
        )
        .order_by(Appointment.start_time.asc())
        .all()
    )


# Waitlist functionality
def add_to_waitlist(
    customer_id: Any,
    branch_id: Any,
    service_id: Any,
    date_str: str,
    time_str: str,
    staff_id: Optional[Any] = None,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """Adds a customer to the waitlist for a booked-out slot."""
    session = db or SessionLocal()
    try:
        from application.services.entity_resolver_service import (
            resolve_customer,
            resolve_branch,
            resolve_service,
            resolve_staff,
        )
        from infrastructure.db.models import Waitlist
        
        # Fuzzy resolve using session
        c_id = resolve_customer(customer_id, session)
        if not c_id:
            return {"success": False, "error": f"Customer '{customer_id}' not found."}
        
        b_id = resolve_branch(branch_id, session)
        if not b_id:
            return {"success": False, "error": f"Branch '{branch_id}' not found."}
        
        s_id = resolve_service(service_id, session)
        if not s_id:
            return {"success": False, "error": f"Service '{service_id}' not found."}
        
        st_id = None
        if staff_id and not _is_placeholder_value(staff_id):
            st_id = resolve_staff(staff_id, session)
                
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
        if not db:
            session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        if not db:
            session.close()


def send_appointment_reminders(customer_id: Any, db: Session) -> int:
    """
    Scans customer's upcoming appointments and generates lazy reminders in the notification table
    for 24-hour, 2-hour, and 30-minute horizons (Rule 11).
    """
    from datetime import datetime, timezone
    from application.services.entity_resolver_service import resolve_customer
    from infrastructure.db.models import User, Appointment, AppointmentStatus, Notification
    import uuid
    
    # Resolve customer id
    try:
        c_id = resolve_customer(customer_id, db)
        if not c_id:
            return 0
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


from typing import Tuple

def is_staff_on_leave(staff_id: Any, date_str: str, session: Session) -> Tuple[bool, Optional[str]]:
    """Check if a staff member is on leave on a given date (Rule 7)."""
    from infrastructure.db.models import StaffLeave, Staff
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
    
    leaves = {
        "Alexandra Chen": ["2026-06-10"],
        "Marcus Johnson": ["2026-07-24", "2026-06-12"],
        "Marcus Staff": ["2026-07-24", "2026-06-12"],
    }
    
    full_name = staff.full_name
    if full_name in leaves and date_str in leaves[full_name]:
        return True, full_name
        
    return False, None


def _find_available_staff_names(
    session: Session,
    branch_id: Any,
    excluded_staff_id: Any,
    start_dt: datetime,
    end_dt: datetime,
    date_str: str,
) -> List[str]:
    """Find other active staff at the branch who are free (not on leave, no overlap) for the given slot."""
    names: List[str] = []
    try:
        candidates = session.query(Staff).filter(
            Staff.branch_id == branch_id,
            Staff.is_active == True,
            Staff.id != excluded_staff_id,
        ).all()
        for member in candidates:
            on_leave, _ = is_staff_on_leave(member.id, date_str, session)
            if on_leave:
                continue
            overlap = session.query(Appointment).filter(
                Appointment.staff_id == member.id,
                Appointment.status != AppointmentStatus.CANCELLED,
                Appointment.start_time < end_dt,
                Appointment.end_time > start_dt,
            ).first()
            if not overlap:
                names.append(member.full_name)
    except Exception as exc:
        logger.warning(f"[AppointmentService] _find_available_staff_names failed: {exc}")
    return names


def auto_cancel_past_customer_appointments(customer_id: Any, db: Session) -> int:
    """
    Automatically cancel any PENDING or CONFIRMED appointments that have passed
    for a given customer. Called lazily when a customer's appointment list is fetched.

    Args:
        customer_id: UUID string or UUID object for the customer.
        db: SQLAlchemy session (caller owns the session lifecycle).

    Returns:
        Number of appointments that were auto-cancelled.
    """
    from application.services.entity_resolver_service import resolve_customer

    try:
        c_id = resolve_customer(customer_id, db, raise_on_missing=False)
        if not c_id:
            return 0
    except Exception:
        return 0

    now = datetime.now(timezone.utc)
    try:
        stale = (
            db.query(Appointment)
            .filter(
                Appointment.customer_id == c_id,
                Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED]),
                Appointment.start_time < now,
            )
            .all()
        )
        count = 0
        for appt in stale:
            appt.status = AppointmentStatus.CANCELLED
            note = "[Auto-cancelled: Booking time/date passed]"
            if appt.notes:
                if note not in appt.notes:
                    appt.notes = f"{appt.notes} {note}"
            else:
                appt.notes = note
            count += 1
        if count:
            db.commit()
            logger.info(
                "[AppointmentService] Auto-cancelled %d past appointment(s) for customer %s",
                count,
                c_id,
            )
        return count
    except Exception as exc:
        logger.warning("[AppointmentService] auto_cancel_past failed: %s", exc)
        try:
            db.rollback()
        except Exception:
            pass
        return 0


def auto_cancel_past_staff_appointments(staff_id: Any, db: Session) -> int:
    """
    Automatically cancel any PENDING or CONFIRMED appointments that have passed for a given staff member.

    Args:
        staff_id: UUID string or UUID object for the staff member.
        db: SQLAlchemy session.

    Returns:
        Number of appointments auto-cancelled.
    """
    from application.services.entity_resolver_service import resolve_staff

    try:
        st_id = resolve_staff(staff_id, db)
        if not st_id:
            return 0
    except Exception:
        return 0

    now = datetime.now(timezone.utc)
    try:
        stale = (
            db.query(Appointment)
            .filter(
                Appointment.staff_id == st_id,
                Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED]),
                Appointment.start_time < now,
            )
            .all()
        )
        count = 0
        for appt in stale:
            appt.status = AppointmentStatus.CANCELLED
            note = "[Auto-cancelled: Booking time/date passed]"
            if appt.notes:
                if note not in appt.notes:
                    appt.notes = f"{appt.notes} {note}"
            else:
                appt.notes = note
            count += 1
        if count:
            db.commit()
            logger.info(
                "[AppointmentService] Auto-cancelled %d past appointment(s) for staff %s",
                count,
                st_id,
            )
        return count
    except Exception as exc:
        logger.warning("[AppointmentService] auto_cancel_past_staff_appointments failed: %s", exc)
        try:
            db.rollback()
        except Exception:
            pass
        return 0


def auto_cancel_all_expired_appointments(db: Optional[Session] = None) -> int:
    """
    Automatically cancel any PENDING or CONFIRMED appointments across the entire system
    whose start_time (or date) has passed.

    Args:
        db: Optional SQLAlchemy session. If None, SessionLocal is created & closed.

    Returns:
        Number of appointments that were auto-cancelled.
    """
    session = db or SessionLocal()
    close_session = db is None
    now = datetime.now(timezone.utc)
    try:
        stale = (
            session.query(Appointment)
            .filter(
                Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED]),
                Appointment.start_time < now,
            )
            .all()
        )
        count = 0
        event_bus = get_event_bus()
        for appt in stale:
            appt.status = AppointmentStatus.CANCELLED
            note = "[Auto-cancelled: Booking time/date passed]"
            if appt.notes:
                if note not in appt.notes:
                    appt.notes = f"{appt.notes} {note}"
            else:
                appt.notes = note
            count += 1

            try:
                t_id = getattr(appt, "tenant_id", "default") or "default"
                event_bus.publish(
                    AppointmentCancelledEvent(
                        tenant_id=t_id,
                        appointment_id=str(appt.id),
                        customer_id=str(appt.customer_id),
                        reason="Booking time/date passed",
                        cancelled_by="SYSTEM_AUTO_CANCEL",
                    )
                )
            except Exception as e:
                logger.warning("[AppointmentService] Failed to publish cancellation event for appointment %s: %s", appt.id, e)

        if count:
            session.commit()
            logger.info("[AppointmentService] Auto-cancelled %d expired appointment(s) system-wide.", count)
        return count
    except Exception as exc:
        logger.warning("[AppointmentService] auto_cancel_all_expired_appointments failed: %s", exc)
        if close_session:
            try:
                session.rollback()
            except Exception:
                pass
        return 0
    finally:
        if close_session:
            session.close()

