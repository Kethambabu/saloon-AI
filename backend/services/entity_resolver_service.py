"""
Entity Resolver Service for SalonAI Workforce Platform.

Phase 1 Architecture — Layer between LLM agent output and MCP calls.

Normalizes:
  - service names   (fuzzy match → canonical UUID)
  - staff names     (fuzzy match → canonical UUID)
  - customer names  (fuzzy match → canonical UUID)
  - relative dates  (today / tomorrow / next-monday → YYYY-MM-DD)

All resolution methods return the UUID string on success, or None when
no match can be found, allowing callers to gracefully handle mismatches.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Date Resolution
# ---------------------------------------------------------------------------

def resolve_relative_date(date_input: Any, base_date: Optional[datetime] = None) -> str:
    """
    Normalize relative date keywords and absolute date strings to YYYY-MM-DD.

    Supported inputs:
      - 'today', 'tomorrow', 'day after tomorrow'
      - 'next week', 'monday' … 'sunday'
      - 'June 8th 2026', 'June 8, 2026', '08-06-2026', '8/6/2026'
      - Already-formatted 'YYYY-MM-DD'

    Returns:
        str: Date in 'YYYY-MM-DD' format.
    """
    if base_date is None:
        base_date = datetime.utcnow()

    if not date_input:
        return base_date.strftime("%Y-%m-%d")

    date_str = str(date_input).strip()

    # Already ISO format
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        return date_str

    date_clean = date_str.lower()

    # Relative keywords
    if "today" in date_clean:
        return base_date.strftime("%Y-%m-%d")
    if "day after tomorrow" in date_clean:
        return (base_date + timedelta(days=2)).strftime("%Y-%m-%d")
    if "tomorrow" in date_clean:
        return (base_date + timedelta(days=1)).strftime("%Y-%m-%d")
    if "next week" in date_clean:
        return (base_date + timedelta(days=7)).strftime("%Y-%m-%d")

    # Weekday names
    weekdays = {
        "monday": 0, "tuesday": 1, "wednesday": 2,
        "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
    }
    for day_name, day_idx in weekdays.items():
        if day_name in date_clean:
            days_ahead = day_idx - base_date.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            return (base_date + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    # Month name patterns: "June 8th 2026", "Jun 8, 2026"
    months = {
        "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
        "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7,
        "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }
    for m_name, m_val in months.items():
        if re.search(r"\b" + re.escape(m_name) + r"\b", date_clean):
            text_without_month = re.sub(r"\b" + re.escape(m_name) + r"\b", "", date_clean)
            digits = re.findall(r"\d+", text_without_month)
            day, year = None, base_date.year
            for d in digits:
                val = int(d)
                if 1 <= val <= 31 and day is None:
                    day = val
                elif val > 1900:
                    year = val
            if day is not None:
                return f"{year:04d}-{m_val:02d}-{day:02d}"

    # Numeric patterns: "08-06-2026", "8/6/2026"
    num_str = re.sub(r"\s+", "", date_clean)
    m = re.match(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$", num_str)
    if m:
        d, mo, yr = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return f"{yr:04d}-{mo:02d}-{d:02d}"
    m = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$", num_str)
    if m:
        yr, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return f"{yr:04d}-{mo:02d}-{d:02d}"

    logger.warning("[EntityResolver] Could not parse date '%s', defaulting to today.", date_input)
    return base_date.strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Time Resolution
# ---------------------------------------------------------------------------

def resolve_relative_time(time_input: Any) -> str:
    """
    Convert relative time slots (e.g. '5pm', '3-4pm', '3pm-4pm') to HH:MM.

    Returns:
        str: Time in 'HH:MM' format.
    """
    if not time_input:
        return "10:00"

    time_str = str(time_input).strip()

    # Strip YYYY-MM-DD or DD-MM-YYYY date patterns if present to avoid hyphen-splitting issues
    time_str = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "", time_str)
    time_str = re.sub(r"\b\d{2}-\d{2}-\d{4}\b", "", time_str)

    # Already HH:MM
    if re.match(r"^\d{2}:\d{2}$", time_str):
        return time_str
    if re.match(r"^\d{2}:\d{2}:\d{2}$", time_str):
        return time_str[:5]

    time_clean = time_str.lower().replace(" ", "")
    is_pm = "pm" in time_clean
    is_am = "am" in time_clean

    # Strip text chars; keep digits, colon, dash
    time_no_text = re.sub(r"[^0-9:\-]", "", time_clean)

    # Take start portion only (e.g. "3-4pm" → "3")
    start_part = time_no_text.split("-")[0]
    digits = "".join(c for c in start_part if c.isdigit() or c == ":")

    if ":" in digits:
        parts = digits.split(":")
        try:
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
        except ValueError:
            hour, minute = 10, 0
    else:
        try:
            hour = int(digits) if digits else 10
            minute = 0
        except ValueError:
            hour, minute = 10, 0

    if is_pm and hour < 12:
        hour += 12
    elif is_am and hour == 12:
        hour = 0

    hour = max(0, min(23, hour))
    minute = max(0, min(59, minute))
    return f"{hour:02d}:{minute:02d}"


# ---------------------------------------------------------------------------
# Database-Backed Entity Resolution
# ---------------------------------------------------------------------------

def _fuzzy_score(candidate: str, query: str) -> int:
    """Simple substring / word-overlap score for fuzzy matching."""
    candidate_l = candidate.lower()
    query_l = query.lower()
    if query_l == candidate_l:
        return 100
    if query_l in candidate_l:
        return 80
    # Partial word overlap
    q_words = set(query_l.split())
    c_words = set(candidate_l.split())
    overlap = len(q_words & c_words)
    if overlap:
        return 50 + overlap * 10
    return 0


def resolve_service_name(name_or_id: str, db=None) -> Optional[str]:
    """
    Resolve a service name or UUID to the canonical service UUID.

    Args:
        name_or_id: Raw name (e.g. 'haircut', 'balayage color') or UUID.
        db: Optional SQLAlchemy session. Will open one if not provided.

    Returns:
        UUID string or None.
    """
    if not name_or_id:
        return None

    close_db = False
    if db is None:
        try:
            from db.database import SessionLocal
            db = SessionLocal()
            close_db = True
        except Exception as exc:
            logger.error("[EntityResolver] Cannot open DB session: %s", exc)
            return None

    try:
        from utils.entity_resolver import resolve_service as _resolve_svc
        result = _resolve_svc(name_or_id, db, raise_on_missing=False)
        if result:
            return str(result)

        # Fuzzy fallback — load all services and score
        from db.database import SessionLocal as _SL
        from db import Service
        services = db.query(Service).filter(Service.is_active == True).all()  # noqa: E712
        best_id, best_score = None, 0
        for svc in services:
            score = _fuzzy_score(svc.name, name_or_id)
            if score > best_score:
                best_score = score
                best_id = str(svc.id)
        if best_score >= 50:
            logger.info(
                "[EntityResolver] Fuzzy-matched service '%s' → id=%s (score=%d)",
                name_or_id, best_id, best_score
            )
            return best_id

        logger.warning("[EntityResolver] Could not resolve service '%s'.", name_or_id)
        return None
    except Exception as exc:
        logger.error("[EntityResolver] resolve_service_name error: %s", exc)
        return None
    finally:
        if close_db:
            db.close()


def resolve_staff_name(name_or_id: str, db=None) -> Optional[str]:
    """
    Resolve a staff name or UUID to the canonical staff UUID.

    Args:
        name_or_id: Raw name (e.g. 'James', 'Priya Sharma') or UUID.
        db: Optional SQLAlchemy session.

    Returns:
        UUID string or None.
    """
    if not name_or_id:
        return None
    if name_or_id.lower() in {"any", "none", "auto", "default", "no preference"}:
        return None

    close_db = False
    if db is None:
        try:
            from db.database import SessionLocal
            db = SessionLocal()
            close_db = True
        except Exception as exc:
            logger.error("[EntityResolver] Cannot open DB session: %s", exc)
            return None

    try:
        from utils.entity_resolver import resolve_staff as _resolve_staff
        result = _resolve_staff(name_or_id, db, raise_on_missing=False)
        if result:
            return str(result)

        # Fuzzy fallback
        from db import Staff
        staff_list = db.query(Staff).filter(Staff.is_active == True).all()  # noqa: E712
        best_id, best_score = None, 0
        for s in staff_list:
            full_name = f"{s.first_name} {s.last_name}"
            score = max(_fuzzy_score(full_name, name_or_id), _fuzzy_score(s.first_name, name_or_id))
            if score > best_score:
                best_score = score
                best_id = str(s.id)
        if best_score >= 50:
            logger.info(
                "[EntityResolver] Fuzzy-matched staff '%s' → id=%s (score=%d)",
                name_or_id, best_id, best_score
            )
            return best_id

        logger.warning("[EntityResolver] Could not resolve staff '%s'.", name_or_id)
        return None
    except Exception as exc:
        logger.error("[EntityResolver] resolve_staff_name error: %s", exc)
        return None
    finally:
        if close_db:
            db.close()


def resolve_customer_name(name_or_id: str, db=None) -> Optional[str]:
    """
    Resolve a customer name or UUID to the canonical customer UUID.

    Args:
        name_or_id: Raw name (e.g. 'John Doe') or UUID.
        db: Optional SQLAlchemy session.

    Returns:
        UUID string or None.
    """
    if not name_or_id:
        return None

    close_db = False
    if db is None:
        try:
            from db.database import SessionLocal
            db = SessionLocal()
            close_db = True
        except Exception as exc:
            logger.error("[EntityResolver] Cannot open DB session: %s", exc)
            return None

    try:
        from utils.entity_resolver import resolve_customer as _resolve_cust
        result = _resolve_cust(name_or_id, db, raise_on_missing=False)
        if result:
            return str(result)

        # Fuzzy fallback
        from db import Customer
        customers = db.query(Customer).filter(Customer.is_active == True).all()  # noqa: E712
        best_id, best_score = None, 0
        for c in customers:
            full_name = f"{c.first_name} {c.last_name}"
            score = max(_fuzzy_score(full_name, name_or_id), _fuzzy_score(c.first_name, name_or_id))
            if score > best_score:
                best_score = score
                best_id = str(c.id)
        if best_score >= 50:
            logger.info(
                "[EntityResolver] Fuzzy-matched customer '%s' → id=%s (score=%d)",
                name_or_id, best_id, best_score
            )
            return best_id

        logger.warning("[EntityResolver] Could not resolve customer '%s'.", name_or_id)
        return None
    except Exception as exc:
        logger.error("[EntityResolver] resolve_customer_name error: %s", exc)
        return None
    finally:
        if close_db:
            db.close()


def resolve_branch_name(name_or_id: str, db=None) -> Optional[str]:
    """
    Resolve a branch name or UUID to the canonical branch UUID.

    Args:
        name_or_id: Raw name (e.g. 'downtown', 'main branch') or UUID.
        db: Optional SQLAlchemy session.

    Returns:
        UUID string or None.
    """
    if not name_or_id:
        return None

    close_db = False
    if db is None:
        try:
            from db.database import SessionLocal
            db = SessionLocal()
            close_db = True
        except Exception as exc:
            logger.error("[EntityResolver] Cannot open DB session: %s", exc)
            return None

    try:
        from utils.entity_resolver import resolve_branch as _resolve_branch
        result = _resolve_branch(name_or_id, db, raise_on_missing=False)
        if result:
            return str(result)

        # Fuzzy fallback
        from db import Branch
        branches = db.query(Branch).filter(Branch.is_active == True).all()  # noqa: E712
        best_id, best_score = None, 0
        for b in branches:
            score = _fuzzy_score(b.name, name_or_id)
            if score > best_score:
                best_score = score
                best_id = str(b.id)
        if best_score >= 50:
            logger.info(
                "[EntityResolver] Fuzzy-matched branch '%s' → id=%s (score=%d)",
                name_or_id, best_id, best_score
            )
            return best_id

        logger.warning("[EntityResolver] Could not resolve branch '%s'.", name_or_id)
        return None
    except Exception as exc:
        logger.error("[EntityResolver] resolve_branch_name error: %s", exc)
        return None
    finally:
        if close_db:
            db.close()


# ---------------------------------------------------------------------------
# Datetime Resolution
# ---------------------------------------------------------------------------

def resolve_relative_datetime(datetime_input: Any, base_date: Optional[datetime] = None) -> str:
    """
    Normalize relative datetime strings or full datetimes to YYYY-MM-DDTHH:MM:SSZ format.
    """
    if not datetime_input:
        return ""
    
    input_clean = str(datetime_input).strip()
    
    # Check if already ISO format with date and time
    if re.match(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}", input_clean):
        normalized = input_clean.replace(" ", "T")
        if not normalized.endswith("Z") and not "+" in normalized and not "-" in normalized[10:]:
            normalized += "Z"
        return normalized
        
    # Otherwise split/resolve separately
    resolved_date = resolve_relative_date(input_clean, base_date)
    resolved_time = resolve_relative_time(input_clean)
    
    return f"{resolved_date}T{resolved_time}:00Z"


# ---------------------------------------------------------------------------
# Batch resolver — normalize a full entity context dict in one call
# ---------------------------------------------------------------------------

def resolve_entity_context(
    raw: Dict[str, Any],
    base_date: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Normalize an entity context dictionary in a single call.

    Input keys recognized:
      service, service_id, service_name → resolved to service_id UUID
      staff, staff_id, staff_name, stylist → resolved to staff_id UUID
      customer, customer_id, customer_name → resolved to customer_id UUID
      branch, branch_id, branch_name → resolved to branch_id UUID
      date → resolved to YYYY-MM-DD
      time, start_time → resolved to HH:MM

    The original raw dict is left intact; resolved values are added/overwritten
    only when a resolution succeeds (non-None).

    Returns:
        A new dict with resolved values merged in.
    """
    resolved = dict(raw)

    # Date
    for key in ("date", "booking_date"):
        if key in raw and raw[key]:
            resolved[key] = resolve_relative_date(raw[key], base_date)

    # Time
    for key in ("time", "booking_time"):
        if key in raw and raw[key]:
            resolved[key] = resolve_relative_time(raw[key])

    # Datetime
    for key in ("start_time", "new_start_time"):
        if key in raw and raw[key]:
            resolved[key] = resolve_relative_datetime(raw[key], base_date)

    # Service
    svc_raw = raw.get("service") or raw.get("service_name") or raw.get("service_id")
    if svc_raw:
        svc_id = resolve_service_name(str(svc_raw))
        if svc_id:
            resolved["service_id"] = svc_id

    # Staff
    staff_raw = raw.get("staff") or raw.get("staff_name") or raw.get("stylist") or raw.get("staff_id")
    if staff_raw:
        staff_id = resolve_staff_name(str(staff_raw))
        if staff_id:
            resolved["staff_id"] = staff_id

    # Customer
    cust_raw = raw.get("customer") or raw.get("customer_name") or raw.get("customer_id")
    if cust_raw:
        cust_id = resolve_customer_name(str(cust_raw))
        if cust_id:
            resolved["customer_id"] = cust_id

    # Branch
    branch_raw = raw.get("branch") or raw.get("branch_name") or raw.get("branch_id")
    if branch_raw:
        branch_id = resolve_branch_name(str(branch_raw))
        if branch_id:
            resolved["branch_id"] = branch_id

    return resolved
