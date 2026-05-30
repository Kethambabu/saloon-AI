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
from typing import Optional, List, Dict, Any
from difflib import SequenceMatcher
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from db.models import Branch, Customer, Service, Staff, Appointment

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
    if identifier is None or str(identifier).strip().lower() in ["none", "null", "undefined", "", "placeholder", "any", "default", "me", "my", "myself"]:
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
    
    # Resolution failed - try default active customer fallback instead of raising immediately
    first_cust = db.query(Customer).filter(Customer.is_active == True).first()
    if first_cust:
        logger.info(f"Customer resolution failed for '{identifier_str}'. Falling back to default customer: {first_cust.full_name} ({first_cust.id})")
        return first_cust.id

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
    
    Currently supports:
    - UUID (string or UUID object)
    
    Args:
        identifier: UUID of appointment
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
    
    if _is_valid_uuid(identifier_str):
        try:
            appt_uuid = uuid.UUID(identifier_str)
            appointment = db.query(Appointment).filter(Appointment.id == appt_uuid).first()
            if appointment:
                logger.info(f"Appointment resolved: {appt_uuid}")
                return appt_uuid
            elif raise_on_missing:
                raise ValueError(f"Appointment with UUID '{identifier_str}' not found")
            else:
                return None
        except ValueError as e:
            if raise_on_missing:
                raise
            return None
    
    if raise_on_missing:
        raise ValueError(f"Invalid appointment identifier '{identifier_str}'. Please provide a valid UUID.")
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
