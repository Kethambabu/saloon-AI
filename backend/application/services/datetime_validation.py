"""
Appointment DateTime Validation Service.

Enforces strict business rules preventing appointment bookings or availability checks
for dates or times in the past.
"""

from datetime import datetime, date, time, timezone
import logging
import re

logger = logging.getLogger(__name__)

def validate_appointment_datetime(
    requested_date: str | date | datetime | None,
    requested_time: str | time | None = None,
    current_server_datetime: datetime | None = None,
) -> dict[str, bool | str]:
    """
    Validates requested appointment date and time against current server datetime.

    Returns:
        {
            "valid": bool,
            "reason": str
        }
    """
    if requested_date is None:
        return {"valid": True, "reason": ""}

    # 1. Obtain current server date/time
    if current_server_datetime is None:
        current_server_datetime = datetime.now(timezone.utc)

    if current_server_datetime.tzinfo is None:
        current_server_datetime = current_server_datetime.replace(tzinfo=timezone.utc)

    curr_date = current_server_datetime.date()
    curr_time = current_server_datetime.time()

    # 2. Parse requested appointment date & time
    req_dt: datetime | None = None
    req_date: date | None = None
    req_time: time | None = None
    time_was_specified = False

    if isinstance(requested_date, datetime):
        req_dt = requested_date
        req_date = req_dt.date()
        req_time = req_dt.time()
        time_was_specified = True
    elif isinstance(requested_date, date):
        req_date = requested_date
    elif isinstance(requested_date, str) and requested_date.strip():
        date_str = requested_date.strip()
        # Check if full ISO datetime string (e.g. 2026-07-18T12:00:00Z)
        if "T" in date_str or (" " in date_str and len(date_str) >= 16):
            try:
                st = date_str.replace("Z", "+00:00")
                req_dt = datetime.fromisoformat(st)
                req_date = req_dt.date()
                req_time = req_dt.time()
                time_was_specified = True
            except ValueError:
                pass

        if req_date is None:
            try:
                from application.services.entity_resolver_service import resolve_relative_date
                norm_date_str = resolve_relative_date(date_str, base_date=current_server_datetime)
                req_date = datetime.strptime(norm_date_str, "%Y-%m-%d").date()
            except Exception as exc:
                # A date that can't be parsed at all (garbled text, or a
                # calendar-invalid date like "Feb 30th") must be rejected
                # outright — previously this fell through to "valid" below,
                # which let unrecognizable dates silently skip validation
                # entirely instead of being caught here.
                logger.warning("[DatetimeValidation] Date parse error for '%s': %s", date_str, exc)
                return {
                    "valid": False,
                    "reason": (
                        f"I couldn't understand '{date_str}' as a valid date. "
                        "Please provide a specific date, e.g. '2026-07-24' or 'next Friday'."
                    ),
                }

    if req_date is None:
        return {"valid": True, "reason": ""}

    # Parse requested_time if provided and not already extracted
    if requested_time is not None and not time_was_specified:
        if isinstance(requested_time, time):
            req_time = requested_time
            time_was_specified = True
        elif isinstance(requested_time, str) and requested_time.strip():
            time_str = requested_time.strip()
            try:
                from application.services.entity_resolver_service import resolve_relative_time
                norm_time_str = resolve_relative_time(time_str, base_time=current_server_datetime)
                req_time = datetime.strptime(norm_time_str, "%H:%M").time()
                time_was_specified = True
            except Exception as exc:
                logger.warning("[DatetimeValidation] Time parse error for '%s': %s", time_str, exc)

    if req_dt is None:
        if req_time is not None:
            req_dt = datetime.combine(req_date, req_time, tzinfo=timezone.utc)
        else:
            req_dt = datetime.combine(req_date, time.min, tzinfo=timezone.utc)

    if req_dt.tzinfo is None:
        req_dt = req_dt.replace(tzinfo=timezone.utc)

    # 3. Compare using Date / DateTime objects
    # Case A: Requested Date is in the past
    if req_date < curr_date:
        day_str = f"{req_date.day} {req_date.strftime('%B')} {req_date.year}"
        if time_was_specified and req_time is not None:
            h12 = req_time.hour % 12
            if h12 == 0:
                h12 = 12
            ampm = "AM" if req_time.hour < 12 else "PM"
            time_formatted = f"{h12}:{req_time.minute:02d} {ampm}"
            formatted_appt = f"{day_str} at {time_formatted}"
        else:
            formatted_appt = day_str

        reason = (
            f"I'm sorry, but appointments cannot be booked for past dates or times.\n\n"
            f"The requested appointment ({formatted_appt}) has already passed.\n\n"
            f"Please choose today or a future date."
        )
        return {"valid": False, "reason": reason}

    # Case B: Requested Date is TODAY, but requested time has passed
    if req_date == curr_date:
        if time_was_specified and req_time is not None:
            if req_dt < current_server_datetime:
                h12 = req_time.hour % 12
                if h12 == 0:
                    h12 = 12
                ampm = "AM" if req_time.hour < 12 else "PM"
                time_formatted = f"{h12}:{req_time.minute:02d} {ampm}"
                reason = (
                    f"The requested time ({time_formatted}) has already passed today.\n\n"
                    f"Please choose a later available time."
                )
                return {"valid": False, "reason": reason}

    # Case C: Requested datetime is in the future
    return {
        "valid": True,
        "reason": "",
        "normalized_start_time": req_dt.isoformat()
    }


# Mandatory camelCase alias as per prompt spec
validateAppointmentDateTime = validate_appointment_datetime
