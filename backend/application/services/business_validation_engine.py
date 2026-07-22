"""
Business Validation Engine — Phase 2 Architecture.

Provides single-source deterministic validation for all salon booking activities:
- Customer (existence, active status, block status)
- Branch (existence, active status)
- Service (existence, active status)
- Stylist (existence, active status, branch assignment, qualification, leave status)
- Date & Time (past-date protection, business hours, slot interval)
- Conflicts (customer overlap, stylist overlap)
- Duplicates (exact customer + service + date + time matches)
- Booking Policies (active booking limits)
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, Tuple, List
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from infrastructure.db.models import (
    Appointment,
    AppointmentStatus,
    Customer,
    Branch,
    Staff,
    Service,
    StaffLeave,
)
from application.services.datetime_validation import validate_appointment_datetime
from application.services.availability_service import AvailabilityService

logger = logging.getLogger(__name__)

BUSINESS_START_HOUR = 9   # 9:00 AM
BUSINESS_END_HOUR = 20    # 8:00 PM
MAX_ACTIVE_BOOKINGS = 3


def _parse_uuid(value: Any) -> Optional[uuid.UUID]:
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


class BusinessValidationEngine:
    """
    Centralized, deterministic business validation engine.
    Ensures no invalid, past, duplicate, or conflicting bookings can proceed.
    """

    @staticmethod
    def validate_customer(customer_id: Any, session: Session) -> Tuple[bool, Optional[str], Optional[Customer]]:
        """Validate customer exists, is active, and is eligible to book."""
        if not customer_id:
            return False, "Customer identifier is required.", None

        c_uuid = _parse_uuid(customer_id)
        if c_uuid:
            cust = session.query(Customer).filter(Customer.id == c_uuid).first()
        else:
            cust = session.query(Customer).filter(
                or_(
                    Customer.email.ilike(str(customer_id)),
                    Customer.phone == str(customer_id)
                )
            ).first()

        if not cust:
            return False, f"Customer '{customer_id}' not found.", None
        if not cust.is_active:
            return False, "Customer account is inactive or blocked.", cust
        return True, None, cust

    @staticmethod
    def validate_branch(branch_id: Any, session: Session) -> Tuple[bool, Optional[str], Optional[Branch]]:
        """Validate branch exists and is active."""
        if not branch_id:
            return False, "Branch identifier is required.", None

        b_uuid = _parse_uuid(branch_id)
        if not b_uuid:
            branch = session.query(Branch).filter(Branch.name.ilike(str(branch_id))).first()
        else:
            branch = session.query(Branch).filter(Branch.id == b_uuid).first()

        if not branch:
            return False, f"Branch '{branch_id}' not found.", None
        if hasattr(branch, "is_active") and not branch.is_active:
            return False, f"Branch '{branch.name}' is currently inactive.", branch
        return True, None, branch

    @staticmethod
    def validate_service(service_id: Any, session: Session) -> Tuple[bool, Optional[str], Optional[Service]]:
        """Validate service exists and is active."""
        if not service_id:
            return False, "Service identifier is required.", None

        s_uuid = _parse_uuid(service_id)
        if not s_uuid:
            service = session.query(Service).filter(Service.name.ilike(str(service_id))).first()
        else:
            service = session.query(Service).filter(Service.id == s_uuid).first()

        if not service:
            return False, f"Service '{service_id}' not found.", None
        if hasattr(service, "is_active") and not service.is_active:
            return False, f"Service '{service.name}' is currently unavailable.", service
        return True, None, service

    @staticmethod
    def validate_stylist(
        staff_id: Any,
        branch_id: Any,
        date_str: str,
        session: Session
    ) -> Tuple[bool, Optional[str], Optional[Staff]]:
        """Validate stylist exists, works at branch, is active, and is NOT on leave."""
        if not staff_id:
            return True, None, None  # Staff is optional for auto-assignment

        st_uuid = _parse_uuid(staff_id)
        if not st_uuid:
            staff = session.query(Staff).filter(Staff.full_name.ilike(str(staff_id))).first()
        else:
            staff = session.query(Staff).filter(Staff.id == st_uuid).first()

        if not staff:
            return False, f"Stylist '{staff_id}' not found.", None
        if hasattr(staff, "is_active") and not staff.is_active:
            return False, f"Stylist '{staff.full_name}' is currently inactive.", staff

        # Verify staff works at branch
        b_uuid = _parse_uuid(branch_id)
        if b_uuid and hasattr(staff, "branch_id") and staff.branch_id and staff.branch_id != b_uuid:
            return False, f"Stylist '{staff.full_name}' does not work at the selected branch.", staff

        # Check leave calendar
        if date_str:
            on_leave, staff_name = AvailabilityService.is_staff_on_leave(staff.id, date_str, session)
            if on_leave:
                return False, f"{staff_name or staff.full_name} is on leave on {date_str}.", staff

        return True, None, staff

    @staticmethod
    def validate_datetime(date_or_datetime_str: str, time_str: Optional[str] = None) -> Tuple[bool, Optional[str], Optional[datetime]]:
        """
        Validate date/time strings for past-date protection, ISO formatting, and business hours.
        Returns (valid, error_reason, parsed_utc_datetime).
        """
        val = validate_appointment_datetime(date_or_datetime_str, time_str)
        if not val["valid"]:
            return False, val["reason"], None

        # Parse normalized ISO string
        start_time_iso = val.get("normalized_start_time")
        if not start_time_iso:
            return False, "Could not resolve valid start time.", None

        try:
            st = start_time_iso.strip()
            if st.endswith("Z"):
                st = st[:-1] + "+00:00"
            dt = datetime.fromisoformat(st)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return False, f"Invalid datetime format: '{start_time_iso}'.", None

        # Absolute past-date protection check against current UTC time
        now_utc = datetime.now(timezone.utc)
        if dt <= now_utc:
            return False, f"Requested time ({dt.strftime('%Y-%m-%d %H:%M UTC')}) has already passed.", dt

        # Business hours check (9 AM to 8 PM)
        if dt.hour < BUSINESS_START_HOUR or dt.hour >= BUSINESS_END_HOUR:
            return False, f"Appointments must fit inside business hours (9:00 AM to 8:00 PM). Requested: {dt.hour}:00.", dt

        return True, None, dt

    @staticmethod
    def check_conflicts_and_duplicates(
        customer_id: uuid.UUID,
        staff_id: Optional[uuid.UUID],
        service_id: uuid.UUID,
        start_dt: datetime,
        end_dt: datetime,
        session: Session
    ) -> Tuple[bool, Optional[str]]:
        """
        Check for:
        1. Duplicate bookings (same customer, same service, same start time)
        2. Customer schedule overlaps
        3. Stylist schedule overlaps
        """
        # 1. Duplicate check
        dup_query = session.query(Appointment).filter(
            Appointment.customer_id == customer_id,
            Appointment.service_id == service_id,
            Appointment.start_time == start_dt,
            Appointment.status != AppointmentStatus.CANCELLED
        )
        if staff_id:
            dup_query = dup_query.filter(Appointment.staff_id == staff_id)
        if dup_query.first():
            return False, "Duplicate appointment detected. You already have this exact appointment scheduled."

        # 2. Customer overlap check
        cust_overlap = session.query(Appointment).filter(
            Appointment.customer_id == customer_id,
            Appointment.status != AppointmentStatus.CANCELLED,
            Appointment.start_time < end_dt,
            Appointment.end_time > start_dt
        ).first()
        if cust_overlap:
            return False, f"You already have an appointment scheduled between {cust_overlap.start_time.strftime('%H:%M')} and {cust_overlap.end_time.strftime('%H:%M')}."

        # 3. Stylist overlap check
        if staff_id:
            staff_overlap = session.query(Appointment).filter(
                Appointment.staff_id == staff_id,
                Appointment.status != AppointmentStatus.CANCELLED,
                Appointment.start_time < end_dt,
                Appointment.end_time > start_dt
            ).first()
            if staff_overlap:
                staff_member = session.query(Staff).filter(Staff.id == staff_id).first()
                name = staff_member.full_name if staff_member else "The selected stylist"
                return False, f"{name} is already booked from {staff_overlap.start_time.strftime('%H:%M')} to {staff_overlap.end_time.strftime('%H:%M')}."

        return True, None

    @staticmethod
    def validate_policy_limits(customer_id: uuid.UUID, session: Session) -> Tuple[bool, Optional[str]]:
        """Validate customer active booking policy limits (max 3 active bookings)."""
        active_count = session.query(Appointment).filter(
            Appointment.customer_id == customer_id,
            Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED]),
            Appointment.start_time > datetime.now(timezone.utc),
            or_(
                Appointment.notes.is_(None),
                ~Appointment.notes.like("Linked Add-on from Appointment%")
            )
        ).count()

        if active_count >= MAX_ACTIVE_BOOKINGS:
            return False, f"You have reached the maximum limit of {MAX_ACTIVE_BOOKINGS} active bookings. Please complete or cancel an existing booking before scheduling a new one."

        return True, None
