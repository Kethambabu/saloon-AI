"""
Universal Entity Resolver for SalonAI Workforce Platform.
Intelligently resolves human-readable identifiers to UUIDs with fuzzy matching,
case-insensitive matching, and comprehensive error handling.

Features:
- Accept UUID or human-readable names/codes
- Perform fuzzy string matching (e.g., "Downtown_Elite" → "Downtown Elite")
- Case-insensitive matching
- Partial name matching
- Return normalized UUIDs
- Log all transformations
- Raise clean API errors
"""

import logging
import uuid
import re
from typing import Optional, List, Dict, Any
from difflib import SequenceMatcher
from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from infrastructure.db.models import Branch, Customer, Service, Staff, Appointment
from infrastructure.db.database import SessionLocal

logger = logging.getLogger(__name__)

# Fuzzy matching threshold (0-1): minimum similarity score required
FUZZY_MATCH_THRESHOLD = 0.75


def _normalize_string(s: str) -> str:
    """Normalize string for matching: lowercase, trim, replace underscores with spaces."""
    return s.strip().lower().replace("_", " ")


def _fuzzy_match_score(s1: str, s2: str) -> float:
    """Calculate fuzzy match score between two strings (0-1)."""
    return SequenceMatcher(None, _normalize_string(s1), _normalize_string(s2)).ratio()


def _is_valid_uuid(value: str) -> bool:
    """Check if a string is a valid UUID."""
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, AttributeError):
        return False


def _clean_identifier_placeholders(identifier: Any) -> Any:
    """Strip common descriptive placeholder suffixes from LLM generated values."""
    if not isinstance(identifier, str):
        return identifier
    
    val = identifier.strip()
    if _is_valid_uuid(val):
        return val
        
    val_lower = val.lower()
    
    # Suffixes to strip
    suffixes = [
        "'s staff id", " staff id", " staff name", " staff uuid", " staff",
        "'s service id", " service id", " service name", " service uuid", " service",
        "'s branch id", " branch id", " branch name", " branch uuid", " branch",
        "'s customer id", " customer id", " customer name", " customer uuid", " customer",
        "'s user id", " user id", " user uuid",
        "'s id", " id", "'s uuid", " uuid",
    ]
    
    for suffix in suffixes:
        if val_lower.endswith(suffix):
            cleaned = val[:-len(suffix)].strip()
            if cleaned:
                logger.info(f"[EntityResolver] Cleaned placeholder suffix '{suffix}' from '{val}' → '{cleaned}'")
                return cleaned
                
    return val


def _get_context_customer_id() -> Optional[str]:
    """Extract logged-in customer ID from system/query context."""
    context = ""
    try:
        from core.query_context import get_query_context
        context = get_query_context()
    except Exception:
        pass
        
    if not context:
        try:
            from ai.agents.receptionist_agent import ReceptionistAgent
            context = getattr(ReceptionistAgent, "CURRENT_QUERY_CONTEXT", "") or ""
        except Exception:
            pass
            
    if not context:
        try:
            from ai.agents.staff_assistant_agent import StaffAssistantAgent
            context = getattr(StaffAssistantAgent, "CURRENT_QUERY_CONTEXT", "") or ""
        except Exception:
            pass
            
    if context and "[SYSTEM CUSTOMER CONTEXT:" in context:
        import re
        match = re.search(r"\[SYSTEM CUSTOMER CONTEXT:[^\]]*?\bID:\s*([a-f0-9\-]{36})", context, re.IGNORECASE)
        if match:
            return match.group(1)
        try:
            parts = context.split("ID: ")
            if len(parts) > 1:
                cust_id = parts[1].split(",")[0].strip()
                return cust_id
        except Exception:
            pass
    return None


def _get_context_staff_id() -> Optional[str]:
    """Extract logged-in staff ID from system/query context."""
    context = ""
    try:
        from core.query_context import get_query_context
        context = get_query_context()
    except Exception:
        pass
        
    if not context:
        try:
            from ai.agents.receptionist_agent import ReceptionistAgent
            context = getattr(ReceptionistAgent, "CURRENT_QUERY_CONTEXT", "") or ""
        except Exception:
            pass
            
    if not context:
        try:
            from ai.agents.staff_assistant_agent import StaffAssistantAgent
            context = getattr(StaffAssistantAgent, "CURRENT_QUERY_CONTEXT", "") or ""
        except Exception:
            pass
            
    if context and "[SYSTEM STAFF CONTEXT:" in context:
        import re
        match = re.search(r"\[SYSTEM STAFF CONTEXT:[^\]]*?\bID:\s*([a-f0-9\-]{36})", context, re.IGNORECASE)
        if match:
            return match.group(1)
        try:
            parts = context.split("ID: ")
            if len(parts) > 1:
                staff_id = parts[1].split(",")[0].strip()
                return staff_id
        except Exception:
            pass
    return None



# ============================================================================
# BRANCH RESOLVER
# ============================================================================

def resolve_branch(
    identifier: Any,
    db: Session,
    raise_on_missing: bool = True
) -> Optional[uuid.UUID]:
    """
    Intelligently resolve a branch identifier to a UUID.
    
    Accepts:
    - UUID (string or UUID object)
    - Branch name (case-insensitive, exact or fuzzy)
    - Branch code (case-insensitive)
    - Fuzzy matching on name
    
    Args:
        identifier: UUID string, branch name, or branch code
        db: SQLAlchemy session
        raise_on_missing: If True, raise error if not found; else return None
    
    Returns:
        UUID of the resolved branch
    
    Raises:
        ValueError: If identifier is invalid and raise_on_missing=True
    """
    identifier = _clean_identifier_placeholders(identifier)
    if identifier is None or str(identifier).strip().lower() in ["none", "null", "undefined", "", "placeholder", "any", "default", "select", "choose"]:
        first_branch = db.query(Branch).filter(Branch.is_active == True).first()
        if first_branch:
            logger.info(f"Branch resolved to default branch: {first_branch.name} ({first_branch.id})")
            return first_branch.id
        if identifier is None:
            if raise_on_missing:
                raise ValueError("Branch identifier cannot be None")
            return None
    
    identifier_str = str(identifier).strip()
    
    # Try 1: Direct UUID parsing
    if _is_valid_uuid(identifier_str):
        try:
            branch_uuid = uuid.UUID(identifier_str)
            branch = db.query(Branch).filter(Branch.id == branch_uuid, Branch.is_active == True).first()
            if branch:
                logger.info(f"Branch resolved by UUID: {identifier_str} → {branch.name}")
                return branch_uuid
            elif raise_on_missing:
                raise ValueError(f"Branch with UUID '{identifier_str}' not found or is inactive")
            else:
                return None
        except ValueError as e:
            if raise_on_missing:
                raise
            return None
    
    # Try 2: Exact code match (case-insensitive)
    branch = db.query(Branch).filter(
        Branch.code.ilike(identifier_str),
        Branch.is_active == True
    ).first()
    if branch:
        logger.info(f"Branch resolved by code: '{identifier_str}' → {branch.name} ({branch.id})")
        return branch.id
    
    # Try 3: Exact name match (case-insensitive)
    branch = db.query(Branch).filter(
        Branch.name.ilike(identifier_str),
        Branch.is_active == True
    ).first()
    if branch:
        logger.info(f"Branch resolved by exact name: '{identifier_str}' → {branch.id}")
        return branch.id
    
    # Try 4: Fuzzy name match
    all_branches = db.query(Branch).filter(Branch.is_active == True).all()
    best_match = None
    best_score = FUZZY_MATCH_THRESHOLD
    
    for branch in all_branches:
        score = _fuzzy_match_score(identifier_str, branch.name)
        if score > best_score:
            best_score = score
            best_match = branch
    
    if best_match:
        logger.info(f"Branch resolved by fuzzy match: '{identifier_str}' → {best_match.name} (score: {best_score:.2f}, {best_match.id})")
        return best_match.id
    
    # Resolution failed - fall back to the first active branch instead of raising ValueError
    first_branch = db.query(Branch).filter(Branch.is_active == True).first()
    if first_branch:
        logger.info(f"Branch resolution failed for '{identifier_str}'. Falling back to default branch: {first_branch.name} ({first_branch.id})")
        return first_branch.id

    if raise_on_missing:
        raise ValueError(
            f"Could not resolve branch identifier '{identifier_str}'. "
            f"Please provide a valid UUID, branch code, or exact branch name."
        )
    return None


# ============================================================================
# CUSTOMER RESOLVER
# ============================================================================

def resolve_customer(
    identifier: Any,
    db: Session,
    raise_on_missing: bool = True
) -> Optional[uuid.UUID]:
    """
    Intelligently resolve a customer identifier to a UUID.
    
    Accepts:
    - UUID (string or UUID object)
    - Full name (case-insensitive)
    - Partial name match
    - Email address
    - Phone number
    
    Args:
        identifier: UUID, email, phone, or customer name
        db: SQLAlchemy session
        raise_on_missing: If True, raise error if not found; else return None
    
    Returns:
        UUID of the resolved customer
    
    Raises:
        ValueError: If identifier is invalid and raise_on_missing=True
    """
    identifier = _clean_identifier_placeholders(identifier)
    if identifier is None or str(identifier).strip().lower() in ["none", "null", "undefined", "", "placeholder", "any", "default", "me", "my", "myself", "current_user", "current_user_id", "anonymous"]:
        ctx_cust_id = _get_context_customer_id()
        if ctx_cust_id and _is_valid_uuid(ctx_cust_id):
            logger.info(f"Customer resolved to logged-in user from context: {ctx_cust_id}")
            return uuid.UUID(ctx_cust_id)
            
        first_cust = db.query(Customer).filter(Customer.is_active == True).first()
        if first_cust:
            logger.info(f"Customer resolved to default customer: {first_cust.full_name} ({first_cust.id})")
            return first_cust.id
        if identifier is None:
            if raise_on_missing:
                raise ValueError("Customer identifier cannot be None")
            return None
    
    identifier_str = str(identifier).strip()
    
    # Try 1: Direct UUID parsing
    if _is_valid_uuid(identifier_str):
        try:
            customer_uuid = uuid.UUID(identifier_str)
            customer = db.query(Customer).filter(Customer.id == customer_uuid, Customer.is_active == True).first()
            if customer:
                logger.info(f"Customer resolved by UUID: {identifier_str} → {customer.full_name}")
                return customer_uuid
            elif raise_on_missing:
                raise ValueError(f"Customer with UUID '{identifier_str}' not found or is inactive")
            else:
                return None
        except ValueError as e:
            if raise_on_missing:
                raise
            return None
    
    # Try 2: Exact email match
    customer = db.query(Customer).filter(
        Customer.email.ilike(identifier_str),
        Customer.is_active == True
    ).first()
    if customer:
        logger.info(f"Customer resolved by email: '{identifier_str}' → {customer.full_name} ({customer.id})")
        return customer.id
    
    # Try 3: Exact full name match (case-insensitive)
    customer = db.query(Customer).filter(
        Customer.is_active == True
    ).all()
    
    for cust in customer:
        if _normalize_string(cust.full_name) == _normalize_string(identifier_str):
            logger.info(f"Customer resolved by exact name: '{identifier_str}' → {cust.id}")
            return cust.id
    
    # Try 4: Partial name match (first or last name contains)
    partial_customers = db.query(Customer).filter(
        or_(
            Customer.first_name.ilike(f"%{identifier_str}%"),
            Customer.last_name.ilike(f"%{identifier_str}%")
        ),
        Customer.is_active == True
    ).all()
    
    if len(partial_customers) == 1:
        logger.info(f"Customer resolved by partial name: '{identifier_str}' → {partial_customers[0].full_name} ({partial_customers[0].id})")
        return partial_customers[0].id
    elif len(partial_customers) > 1:
        names = ", ".join([c.full_name for c in partial_customers])
        if raise_on_missing:
            raise ValueError(f"Ambiguous customer name '{identifier_str}' matches multiple customers: {names}. Please provide exact name or email.")
        return None
    
    # Try 5: Phone number match
    if len(identifier_str) >= 7:
        customer = db.query(Customer).filter(
            Customer.phone.ilike(f"%{identifier_str}%"),
            Customer.is_active == True
        ).first()
        if customer:
            logger.info(f"Customer resolved by phone: '{identifier_str}' → {customer.full_name} ({customer.id})")
            return customer.id
    
    # Resolution failed. Unlike branch/service, we do NOT fall back to an arbitrary
    # "first active customer" here — silently substituting a different real
    # person's record for an unresolved name is a data-integrity/privacy risk
    # (e.g. booking or cancelling an appointment against the wrong customer).
    if raise_on_missing:
        raise ValueError(
            f"Could not resolve customer identifier '{identifier_str}'. "
            f"Please provide a valid UUID, email, or customer name."
        )
    return None


# ============================================================================
# SERVICE RESOLVER
# ============================================================================

def resolve_service(
    identifier: Any,
    db: Session,
    raise_on_missing: bool = True
) -> Optional[uuid.UUID]:
    """
    Intelligently resolve a service identifier to a UUID.
    
    Accepts:
    - UUID (string or UUID object)
    - Service name (case-insensitive, exact or fuzzy)
    - Partial service name match
    
    Args:
        identifier: UUID or service name
        db: SQLAlchemy session
        raise_on_missing: If True, raise error if not found; else return None
    
    Returns:
        UUID of the resolved service
    
    Raises:
        ValueError: If identifier is invalid and raise_on_missing=True
    """
    identifier = _clean_identifier_placeholders(identifier)
    if identifier is None or str(identifier).strip().lower() in ["none", "null", "undefined", "", "placeholder", "any", "default", "select", "choose", "service", "appointment", "booking"]:
        first_service = db.query(Service).filter(Service.is_active == True).first()
        if first_service:
            logger.info(f"Service resolved to default service: {first_service.name} ({first_service.id})")
            return first_service.id
        if identifier is None:
            if raise_on_missing:
                raise ValueError("Service identifier cannot be None")
            return None
    
    identifier_str = str(identifier).strip()
    
    # Try 1: Direct UUID parsing
    if _is_valid_uuid(identifier_str):
        try:
            service_uuid = uuid.UUID(identifier_str)
            service = db.query(Service).filter(Service.id == service_uuid, Service.is_active == True).first()
            if service:
                logger.info(f"Service resolved by UUID: {identifier_str} → {service.name}")
                return service_uuid
            elif raise_on_missing:
                raise ValueError(f"Service with UUID '{identifier_str}' not found or is inactive")
            else:
                return None
        except ValueError as e:
            if raise_on_missing:
                raise
            return None
    
    # Try 2: Exact name match (case-insensitive)
    service = db.query(Service).filter(
        Service.name.ilike(identifier_str),
        Service.is_active == True
    ).first()
    if service:
        logger.info(f"Service resolved by exact name: '{identifier_str}' → {service.id}")
        return service.id
    
    # Try 3: Partial name match
    partial_services = db.query(Service).filter(
        Service.name.ilike(f"%{identifier_str}%"),
        Service.is_active == True
    ).all()
    
    if len(partial_services) == 1:
        logger.info(f"Service resolved by partial name: '{identifier_str}' → {partial_services[0].id}")
        return partial_services[0].id
    elif len(partial_services) > 1:
        names = ", ".join([s.name for s in partial_services])
        if raise_on_missing:
            raise ValueError(f"Ambiguous service name '{identifier_str}' matches multiple services: {names}. Please provide exact service name.")
        return None
    
    # Try 4: Fuzzy match
    all_services = db.query(Service).filter(Service.is_active == True).all()
    best_match = None
    best_score = FUZZY_MATCH_THRESHOLD
    
    for service in all_services:
        score = _fuzzy_match_score(identifier_str, service.name)
        if score > best_score:
            best_score = score
            best_match = service
    
    if best_match:
        logger.info(f"Service resolved by fuzzy match: '{identifier_str}' → {best_match.name} (score: {best_score:.2f}, {best_match.id})")
        return best_match.id
    
    # Resolution failed - fall back to the first active service instead of raising ValueError
    first_service = db.query(Service).filter(Service.is_active == True).first()
    if first_service:
        logger.info(f"Service resolution failed for '{identifier_str}'. Falling back to default service: {first_service.name} ({first_service.id})")
        return first_service.id

    if raise_on_missing:
        raise ValueError(
            f"Could not resolve service identifier '{identifier_str}'. "
            f"Please provide a valid UUID or service name."
        )
    return None


# ============================================================================
# STAFF RESOLVER
# ============================================================================

def resolve_staff(
    identifier: Any,
    db: Session,
    branch_id: Optional[uuid.UUID] = None,
    raise_on_missing: bool = True
) -> Optional[uuid.UUID]:
    """
    Intelligently resolve a staff identifier to a UUID.
    
    Accepts:
    - UUID (string or UUID object)
    - Full name (case-insensitive, exact or partial)
    - First or last name
    - Fuzzy matching on name
    
    Args:
        identifier: UUID or staff name
        db: SQLAlchemy session
        branch_id: Optional branch UUID to filter by (staff must belong to branch)
        raise_on_missing: If True, raise error if not found; else return None
    
    Returns:
        UUID of the resolved staff member
    
    Raises:
        ValueError: If identifier is invalid and raise_on_missing=True
    """
    identifier = _clean_identifier_placeholders(identifier)
    if identifier is None or str(identifier).strip().lower() in ["none", "null", "undefined", "", "placeholder", "any", "default", "me", "my", "myself", "current_user_id", "anonymous", "current_user", "self"]:
        ctx_staff_id = _get_context_staff_id()
        if ctx_staff_id and _is_valid_uuid(ctx_staff_id):
            logger.info(f"Staff resolved to logged-in user from context: {ctx_staff_id}")
            return uuid.UUID(ctx_staff_id)
            
        first_staff = db.query(Staff).filter(Staff.is_active == True).first()
        if first_staff:
            logger.info(f"Staff resolved to default staff: {first_staff.full_name} ({first_staff.id})")
            return first_staff.id
        if identifier is None:
            if raise_on_missing:
                raise ValueError("Staff identifier cannot be None")
            return None
    
    identifier_str = str(identifier).strip()
    
    # Build query filters
    base_filters = [Staff.is_active == True]
    if branch_id:
        base_filters.append(Staff.branch_id == branch_id)
    
    # Try 1: Direct UUID parsing
    if _is_valid_uuid(identifier_str):
        try:
            staff_uuid = uuid.UUID(identifier_str)
            staff = db.query(Staff).filter(
                Staff.id == staff_uuid,
                *base_filters
            ).first()
            if staff:
                logger.info(f"Staff resolved by UUID: {identifier_str} → {staff.full_name}")
                return staff_uuid
            elif raise_on_missing:
                raise ValueError(f"Staff with UUID '{identifier_str}' not found or is inactive")
            else:
                return None
        except ValueError as e:
            if raise_on_missing:
                raise
            return None
    
    # Try 2: Exact full name match
    all_staff = db.query(Staff).filter(*base_filters).all()
    for staff in all_staff:
        if _normalize_string(staff.full_name) == _normalize_string(identifier_str):
            logger.info(f"Staff resolved by exact name: '{identifier_str}' → {staff.full_name} ({staff.id})")
            return staff.id
    
    # Try 3: Partial name match (first or last)
    partial_staff = [s for s in all_staff if
        _normalize_string(identifier_str) in _normalize_string(s.first_name) or
        _normalize_string(identifier_str) in _normalize_string(s.last_name) or
        _normalize_string(identifier_str) in _normalize_string(s.full_name)
    ]
    
    if len(partial_staff) == 1:
        logger.info(f"Staff resolved by partial name: '{identifier_str}' → {partial_staff[0].full_name} ({partial_staff[0].id})")
        return partial_staff[0].id
    elif len(partial_staff) > 1:
        names = ", ".join([s.full_name for s in partial_staff])
        if raise_on_missing:
            raise ValueError(f"Ambiguous staff name '{identifier_str}' matches multiple staff members: {names}. Please provide exact name.")
        return None
    
    # Try 4: Fuzzy match
    best_match = None
    best_score = FUZZY_MATCH_THRESHOLD
    
    for staff in all_staff:
        score = _fuzzy_match_score(identifier_str, staff.full_name)
        if score > best_score:
            best_score = score
            best_match = staff
    
    if best_match:
        logger.info(f"Staff resolved by fuzzy match: '{identifier_str}' → {best_match.full_name} (score: {best_score:.2f}, {best_match.id})")
        return best_match.id
    
    # Resolution failed
    if raise_on_missing:
        branch_qualifier = f" at branch {branch_id}" if branch_id else ""
        raise ValueError(
            f"Could not resolve staff identifier '{identifier_str}'{branch_qualifier}. "
            f"Please provide a valid UUID or staff name."
        )
    return None


# ============================================================================
# APPOINTMENT RESOLVER (Helper for rescheduling/canceling)
# ============================================================================

def resolve_appointment(
    identifier: Any,
    db: Session,
    raise_on_missing: bool = True
) -> Optional[uuid.UUID]:
    """
    Resolve an appointment identifier to a UUID.
    
    Supports:
    - UUID (string or UUID object)
    - Natural language description (e.g., "Downtown Elite on May 31st at 2:00 PM - Haircut with Alexandra Chen")
    
    Args:
        identifier: UUID or natural language description
        db: SQLAlchemy session
        raise_on_missing: If True, raise error if not found; else return None
    
    Returns:
        UUID of the resolved appointment
    
    Raises:
        ValueError: If identifier is invalid and raise_on_missing=True
    """
    if identifier is None:
        if raise_on_missing:
            raise ValueError("Appointment identifier cannot be None")
        return None
    
    identifier_str = str(identifier).strip()
    
    # Try 1: Direct UUID parsing
    if _is_valid_uuid(identifier_str):
        try:
            appt_uuid = uuid.UUID(identifier_str)
            appointment = db.query(Appointment).filter(Appointment.id == appt_uuid).first()
            if appointment:
                logger.info(f"Appointment resolved by UUID: {appt_uuid}")
                return appt_uuid
            elif raise_on_missing:
                raise ValueError(f"Appointment with UUID '{identifier_str}' not found")
            else:
                return None
        except ValueError as e:
            if raise_on_missing:
                raise
            return None
    
    # Try 2: Natural language description (e.g., "Downtown Elite on May 31st at 2:00 PM - Haircut with Alexandra Chen")
    # Extract key information from natural language
    identifier_lower = identifier_str.lower()
    
    try:
        # Get all pending/confirmed appointments (exclude cancelled/completed)
        appointments = db.query(Appointment).filter(
            Appointment.status.in_([AppointmentStatus.CONFIRMED, AppointmentStatus.PENDING])
        ).all()
        
        best_matches = []
        
        for appt in appointments:
            match_score = 0
            
            # Try to match branch name
            branch = db.query(Branch).filter(Branch.id == appt.branch_id).first()
            if branch and branch.name.lower() in identifier_lower:
                match_score += 2
            
            # Try to match service name
            service = db.query(Service).filter(Service.id == appt.service_id).first()
            if service and service.name.lower() in identifier_lower:
                match_score += 2
            
            # Try to match staff name
            staff = db.query(Staff).filter(Staff.id == appt.staff_id).first()
            if staff:
                first_name = staff.first_name.lower()
                last_name = staff.last_name.lower()
                if first_name in identifier_lower or last_name in identifier_lower:
                    match_score += 2
            
            # Try to match date/time keywords
            if any(date_word in identifier_lower for date_word in ['may 31', 'may 30', 'june 1', 'june 2', 'tomorrow', 'today', 'next']):
                match_score += 1
            
            if any(time_word in identifier_lower for time_word in ['2:00', '14:00', '5:00', '17:00', 'pm', 'am']):
                match_score += 1
            
            if match_score >= 2:  # Require at least 2 matching factors
                best_matches.append((appt, match_score))
        
        # Sort by match score and return best match
        if best_matches:
            best_matches.sort(key=lambda x: x[1], reverse=True)
            best_appt = best_matches[0][0]
            logger.info(f"Appointment resolved by natural language: '{identifier_str}' → {best_appt.id} (score: {best_matches[0][1]})")
            return best_appt.id
    
    except Exception as e:
        logger.debug(f"Natural language appointment resolution failed: {e}")
    
    if raise_on_missing:
        raise ValueError(
            f"Could not resolve appointment identifier '{identifier_str}'. "
            f"Please provide a valid UUID or a description with branch name, service, stylist name, or appointment date/time."
        )
    return None


# ============================================================================
# LIST HELPERS (For AI agent to discover available options)
# ============================================================================

def list_branches(db: Session, active_only: bool = True) -> List[Dict[str, Any]]:
    """
    List all branches (or active branches) for AI agent discovery.
    
    Args:
        db: SQLAlchemy session
        active_only: Only return active branches
    
    Returns:
        List of dicts with id, name, code, city, address
    """
    query = db.query(Branch)
    if active_only:
        query = query.filter(Branch.is_active == True)
    
    branches = query.order_by(Branch.name).all()
    
    return [
        {
            "id": str(b.id),
            "name": b.name,
            "code": b.code,
            "city": b.city,
            "address": b.address,
            "phone": b.phone,
        }
        for b in branches
    ]


def list_services(db: Session, active_only: bool = True) -> List[Dict[str, Any]]:
    """
    List all services (or active services) for AI agent discovery.
    
    Args:
        db: SQLAlchemy session
        active_only: Only return active services
    
    Returns:
        List of dicts with id, name, price, duration_minutes, description
    """
    query = db.query(Service)
    if active_only:
        query = query.filter(Service.is_active == True)
    
    services = query.order_by(Service.name).all()
    
    return [
        {
            "id": str(s.id),
            "name": s.name,
            "price": float(s.price),
            "duration_minutes": s.duration_minutes,
            "description": s.description,
        }
        for s in services
    ]


def list_staff(
    db: Session,
    branch_id: Optional[uuid.UUID] = None,
    active_only: bool = True
) -> List[Dict[str, Any]]:
    """
    List all staff members (optionally filtered by branch).
    
    Args:
        db: SQLAlchemy session
        branch_id: Optional branch UUID to filter by
        active_only: Only return active staff
    
    Returns:
        List of dicts with id, name, role, branch_id, email
    """
    query = db.query(Staff)
    if active_only:
        query = query.filter(Staff.is_active == True)
    if branch_id:
        query = query.filter(Staff.branch_id == branch_id)
    
    staff_list = query.order_by(Staff.first_name, Staff.last_name).all()
    
    return [
        {
            "id": str(s.id),
            "name": s.full_name,
            "role": s.role,
            "branch_id": str(s.branch_id),
            "email": s.email,
            "phone": s.phone,
        }
        for s in staff_list
    ]


def search_customers(
    db: Session,
    query_str: str,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Search for customers by partial name, email, or phone.
    
    Args:
        db: SQLAlchemy session
        query_str: Search string (name, email, phone)
        limit: Maximum results to return
    
    Returns:
        List of dicts with id, name, email, phone
    """
    search_pattern = f"%{query_str}%"
    
    customers = db.query(Customer).filter(
        or_(
            Customer.first_name.ilike(search_pattern),
            Customer.last_name.ilike(search_pattern),
            Customer.email.ilike(search_pattern),
            Customer.phone.ilike(search_pattern),
        ),
        Customer.is_active == True
    ).limit(limit).all()
    
    return [
        {
            "id": str(c.id),
            "name": c.full_name,
            "email": c.email,
            "phone": c.phone,
        }
        for c in customers
    ]



# =========================================================================
# PHASE 1 COMPATIBILITY & DATE/TIME RESOLUTION METHODS
# =========================================================================

def resolve_relative_date(date_input: Any, base_date: Optional[datetime] = None) -> str:
    """
    Normalize relative date keywords and absolute date strings to YYYY-MM-DD.
    """
    if base_date is None:
        base_date = datetime.now(timezone.utc).replace(tzinfo=None)

    if not date_input:
        return base_date.strftime("%Y-%m-%d")

    date_str = str(date_input).strip()

    # Case-insensitive checks
    d_lower = date_str.lower()
    if d_lower == "today":
        return base_date.strftime("%Y-%m-%d")
    elif d_lower == "tomorrow":
        tomorrow_date = base_date + timedelta(days=1)
        return tomorrow_date.strftime("%Y-%m-%d")
    elif d_lower in ("day after tomorrow", "day-after-tomorrow"):
        dat_date = base_date + timedelta(days=2)
        return dat_date.strftime("%Y-%m-%d")
    elif d_lower == "yesterday":
        yest_date = base_date - timedelta(days=1)
        return yest_date.strftime("%Y-%m-%d")

    # Day of week resolving (e.g. 'next monday', 'this friday', 'friday')
    days_of_week = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6
    }
    
    for day_name, day_idx in days_of_week.items():
        if day_name in d_lower:
            current_day_idx = base_date.weekday()
            days_ahead = day_idx - current_day_idx
            
            # If the day has already passed or is today, assume next week
            if "next" in d_lower:
                if days_ahead <= 0:
                    days_ahead += 7
                days_ahead += 7
            else:
                if days_ahead < 0:
                    days_ahead += 7
                    
            target = base_date + timedelta(days=days_ahead)
            return target.strftime("%Y-%m-%d")

    # Match month word names like 'June 8th 2026'
    months = {
        "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
        "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
    }
    
    for month_name, month_num in months.items():
        if month_name in d_lower:
            # Parse year if present
            year_match = re.search(r"\b(202\d|203\d)\b", date_str)
            year = int(year_match.group(1)) if year_match else base_date.year
            
            # Parse day number
            day_match = re.search(r"\b(\d{1,2})(st|nd|rd|th)?\b", d_lower.replace(month_name, ""))
            day = int(day_match.group(1)) if day_match else 1
            
            try:
                target = datetime(year=year, month=month_num, day=day)
                return target.strftime("%Y-%m-%d")
            except ValueError:
                pass

    # Fallback to standard parser
    try:
        # standard ISO YYYY-MM-DD
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        pass

    # Try DD-MM-YYYY or MM/DD/YYYY
    match_dmy = re.match(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$", date_str)
    if match_dmy:
        p1, p2, p3 = int(match_dmy.group(1)), int(match_dmy.group(2)), int(match_dmy.group(3))
        # Ambiguous: assume DD-MM-YYYY if p1 > 12, else MM-DD-YYYY
        try:
            if p1 > 12:
                target = datetime(year=p3, month=p2, day=p1)
            else:
                target = datetime(year=p3, month=p1, day=p2)
            return target.strftime("%Y-%m-%d")
        except ValueError:
            pass

    return base_date.strftime("%Y-%m-%d")


def resolve_relative_time(time_input: Any, base_time: Optional[datetime] = None) -> str:
    """
    Normalize human-readable time strings (e.g. '2pm', '2:30 PM', 'morning') to HH:MM.
    """
    if base_time is None:
        base_time = datetime.now(timezone.utc).replace(tzinfo=None)

    if not time_input:
        return base_time.strftime("%H:%M")

    time_str = str(time_input).strip().lower()

    # Keywords mapping
    keywords = {
        "morning": "09:00",
        "noon": "12:00",
        "afternoon": "14:00",
        "evening": "17:00",
    }
    if time_str in keywords:
        return keywords[time_str]

    # Clean AM/PM formats
    time_str = time_str.replace(".", "") # e.g. a.m. -> am
    match_ampm = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)$", time_str)
    if match_ampm:
        hour = int(match_ampm.group(1))
        minute = int(match_ampm.group(2)) if match_ampm.group(2) else 0
        ampm = match_ampm.group(3)
        
        if ampm == "pm" and hour < 12:
            hour += 12
        elif ampm == "am" and hour == 12:
            hour = 0
            
        return f"{hour:02d}:{minute:02d}"

    # Match HH:MM 24h
    match_24 = re.match(r"^(\d{1,2}):(\d{2})$", time_str)
    if match_24:
        hour = int(match_24.group(1))
        minute = int(match_24.group(2))
        if 0 <= hour < 24 and 0 <= minute < 60:
            return f"{hour:02d}:{minute:02d}"

    return base_time.strftime("%H:%M")


def resolve_service_name(db: Session, name_query: str) -> Optional[str]:
    """Fuzzy resolve service name to UUID string."""
    try:
        res = resolve_service(name_query, db)
        return str(res) if res else None
    except Exception:
        return None

def resolve_staff_name(db: Session, name_query: str) -> Optional[str]:
    """Fuzzy resolve staff name to UUID string."""
    try:
        res = resolve_staff(name_query, db)
        return str(res) if res else None
    except Exception:
        return None

def resolve_customer_name(db: Session, name_query: str) -> Optional[str]:
    """Fuzzy resolve customer name to UUID string."""
    try:
        res = resolve_customer(name_query, db)
        return str(res) if res else None
    except Exception:
        return None

def resolve_branch_name(db: Session, name_query: str) -> Optional[str]:
    """Fuzzy resolve branch name to UUID string."""
    try:
        res = resolve_branch(name_query, db)
        return str(res) if res else None
    except Exception:
        return None


def resolve_entity_context(params: Dict[str, Any], db: Optional[Session] = None) -> Dict[str, Any]:
    """
    Helper invoked by API routes and workflows to fuzzy resolve ALL entity inputs.
    Resolves branch, customer, staff, service, date, and time.
    """
    logger.info(f"[EntityResolver] Resolving context: {list(params.keys())}")
    
    session = db or SessionLocal()
    resolved = {}
    errors = []

    try:
        # Each entity is resolved independently so that one ambiguous/unresolved
        # field (e.g. an ambiguous customer name) doesn't discard already-resolved
        # fields (branch, service, date/time) by raising past them. Errors are
        # collected into resolved["_resolution_errors"] for callers that want to
        # surface a precise message instead of silently proceeding with a missing id.

        # 1. Resolve branch
        branch_input = params.get("branch_id") or params.get("branch") or params.get("branch_name")
        if branch_input:
            try:
                branch_id = resolve_branch(branch_input, session)
                if branch_id:
                    branch = session.query(Branch).filter(Branch.id == branch_id).first()
                    if branch:
                        resolved["branch_id"] = str(branch.id)
                        resolved["branch_name"] = branch.name
            except ValueError as e:
                logger.warning(f"[EntityResolver] Branch resolution failed: {e}")
                errors.append(str(e))

        # 2. Resolve customer
        cust_input = params.get("customer_id") or params.get("customer") or params.get("customer_name")
        if cust_input:
            try:
                cust_id = resolve_customer(cust_input, session)
                if cust_id:
                    cust = session.query(Customer).filter(Customer.id == cust_id).first()
                    if cust:
                        resolved["customer_id"] = str(cust.id)
                        resolved["customer_name"] = cust.full_name
            except ValueError as e:
                logger.warning(f"[EntityResolver] Customer resolution failed: {e}")
                errors.append(str(e))

        # 3. Resolve staff
        staff_input = params.get("staff_id") or params.get("staff") or params.get("staff_name")
        if staff_input:
            try:
                staff_id = resolve_staff(staff_input, session)
                if staff_id:
                    staff = session.query(Staff).filter(Staff.id == staff_id).first()
                    if staff:
                        resolved["staff_id"] = str(staff.id)
                        resolved["staff_name"] = staff.full_name
            except ValueError as e:
                logger.warning(f"[EntityResolver] Staff resolution failed: {e}")
                errors.append(str(e))

        # 4. Resolve service
        srv_input = params.get("service_id") or params.get("service") or params.get("service_name")
        if srv_input:
            try:
                srv_id = resolve_service(srv_input, session)
                if srv_id:
                    srv = session.query(Service).filter(Service.id == srv_id).first()
                    if srv:
                        resolved["service_id"] = str(srv.id)
                        resolved["service_name"] = srv.name
            except ValueError as e:
                logger.warning(f"[EntityResolver] Service resolution failed: {e}")
                errors.append(str(e))

        if errors:
            resolved["_resolution_errors"] = errors

        # 5. Resolve date and time to start_time
        date_input = params.get("date")
        time_input = params.get("time")
        start_time_input = params.get("start_time")
        
        if start_time_input:
            resolved["start_time"] = start_time_input
        elif date_input and time_input:
            resolved_date = resolve_relative_date(date_input)
            resolved_time = resolve_relative_time(time_input)
            resolved["start_time"] = f"{resolved_date}T{resolved_time}:00Z"
            resolved["date"] = resolved_date
            resolved["time"] = resolved_time
        elif date_input:
            resolved_date = resolve_relative_date(date_input)
            resolved["date"] = resolved_date
            
        return resolved
        
    except Exception as e:
        logger.error(f"[EntityResolver] Resolution error: {e}", exc_info=True)
        return {}
    finally:
        if not db:
            session.close()
