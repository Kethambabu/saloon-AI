"""
Staff-specific API Routes for SalonAI Workforce Platform.
Provides staff dashboard, performance metrics, and staff-specific agent access.
Ensures data isolation and role-based access control.
"""

import logging
from typing import Optional
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db, Staff, UserRole, Appointment, User, Customer
from api.deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/staff", tags=["Staff"])


# --- Pydantic Schemas ---

class StaffPerformanceMetrics(BaseModel):
    """Staff performance metrics"""
    staff_id: str
    name: str
    role: str
    total_appointments: int
    completed_appointments: int
    cancelled_appointments: int
    average_rating: float
    total_revenue: float


class StaffDashboardResponse(BaseModel):
    """Complete staff dashboard"""
    staff_id: str
    name: str
    role: str
    branch_id: str
    is_active: bool
    today_appointments: int
    upcoming_appointments: int
    pending_confirmations: int
    total_appointments_month: int
    average_rating: float
    performance_metrics: StaffPerformanceMetrics


class StaffProfileResponse(BaseModel):
    """Staff profile information"""
    id: str
    first_name: str
    last_name: str
    email: str
    phone: Optional[str]
    role: str
    branch_id: str
    is_active: bool
    created_at: str
    updated_at: str


# --- Helper Functions ---

def get_current_staff(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Staff:
    """
    Dependency to ensure current user is a staff member.
    Returns the associated staff object.
    """
    if current_user.role not in [UserRole.STAFF, UserRole.ADMIN, UserRole.MANAGER, UserRole.OWNER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is only accessible to staff members"
        )
    
    if not current_user.staff_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have an associated staff profile"
        )
    
    staff = db.query(Staff).filter(
        Staff.id == current_user.staff_id
    ).first()
    
    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Staff profile not found"
        )
    
    return staff


# --- Endpoints ---

@router.get(
    "/dashboard",
    response_model=StaffDashboardResponse,
    summary="Get Staff Dashboard",
    description="Retrieve staff dashboard with appointments, metrics, and performance data."
)
def get_staff_dashboard(
    staff: Staff = Depends(get_current_staff),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get staff dashboard with:
    - Today's appointments
    - Upcoming appointments
    - Performance metrics
    - Monthly statistics
    """
    logger.info(f"Fetching dashboard for staff {staff.id}")
    
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    
    # Get all appointments for this staff member
    all_appointments = db.query(Appointment).filter(
        Appointment.staff_id == staff.id
    ).all()
    
    # Helper to compare timezone-aware and naive datetimes safely
    def is_between(dt, start, end):
        if dt is None:
            return False
        dt_aware = dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
        return start <= dt_aware < end

    def is_after(dt, reference):
        if dt is None:
            return False
        dt_aware = dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
        return dt_aware > reference

    # Today's appointments
    today_appointments = [
        a for a in all_appointments
        if is_between(a.start_time, today_start, today_end)
    ]
    
    # Upcoming appointments (confirmed/pending in future)
    from db.models import AppointmentStatus
    upcoming_appointments = [
        a for a in all_appointments
        if is_after(a.start_time, now)
        and a.status in [AppointmentStatus.CONFIRMED, AppointmentStatus.PENDING]
    ]
    
    # Pending confirmations (unconfirmed)
    pending_confirmations = [
        a for a in all_appointments
        if a.status == AppointmentStatus.PENDING
    ]
    
    # This month's appointments
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_end = (month_start + timedelta(days=32)).replace(day=1)
    month_appointments = [
        a for a in all_appointments
        if is_between(a.created_at, month_start, month_end)
    ]
    
    # Calculate metrics
    completed_appointments = sum(
        1 for a in all_appointments
        if a.status == AppointmentStatus.COMPLETED
    )
    cancelled_appointments = sum(
        1 for a in all_appointments
        if a.status == AppointmentStatus.CANCELLED
    )
    
    # Get reviews/ratings
    from db.models import Review
    reviews = db.query(Review).filter(
        Review.appointment_id.in_([a.id for a in all_appointments])
    ).all()
    
    avg_rating = sum(r.rating for r in reviews) / len(reviews) if reviews else 0.0
    
    # Performance metrics
    performance = StaffPerformanceMetrics(
        staff_id=str(staff.id),
        name=staff.full_name,
        role=staff.role,
        total_appointments=len(all_appointments),
        completed_appointments=completed_appointments,
        cancelled_appointments=cancelled_appointments,
        average_rating=round(avg_rating, 2),
        total_revenue=0.0  # Can be calculated from appointment prices
    )
    
    return StaffDashboardResponse(
        staff_id=str(staff.id),
        name=staff.full_name,
        role=staff.role,
        branch_id=str(staff.branch_id),
        is_active=staff.is_active,
        today_appointments=len(today_appointments),
        upcoming_appointments=len(upcoming_appointments),
        pending_confirmations=len(pending_confirmations),
        total_appointments_month=len(month_appointments),
        average_rating=round(avg_rating, 2),
        performance_metrics=performance
    )


@router.get(
    "/profile",
    response_model=StaffProfileResponse,
    summary="Get Staff Profile",
    description="Retrieve staff profile information."
)
def get_staff_profile(
    staff: Staff = Depends(get_current_staff),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get staff profile information."""
    logger.info(f"Fetching profile for staff {staff.id}")
    
    return StaffProfileResponse(
        id=str(staff.id),
        first_name=staff.first_name,
        last_name=staff.last_name,
        email=staff.email,
        phone=staff.phone,
        role=staff.role,
        branch_id=str(staff.branch_id),
        is_active=staff.is_active,
        created_at=staff.created_at.isoformat(),
        updated_at=staff.updated_at.isoformat()
    )


@router.get(
    "/appointments/today",
    summary="Get Today's Appointments",
    description="Retrieve all appointments for staff member for today."
)
def get_today_appointments(
    staff: Staff = Depends(get_current_staff),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all appointments scheduled for today."""
    logger.info(f"Fetching today's appointments for staff {staff.id}")
    
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    
    appointments = db.query(Appointment).filter(
        Appointment.staff_id == staff.id,
        Appointment.start_time >= today_start,
        Appointment.start_time < today_end
    ).order_by(Appointment.start_time).all()
    
    return [
        {
            "id": str(apt.id),
            "customer_name": apt.customer.full_name if apt.customer else "N/A",
            "customer_phone": apt.customer.phone if apt.customer else None,
            "service": apt.service.name if apt.service else "N/A",
            "start_time": apt.start_time.isoformat() if apt.start_time.tzinfo else f"{apt.start_time.isoformat()}Z",
            "end_time": apt.end_time.isoformat() if apt.end_time.tzinfo else f"{apt.end_time.isoformat()}Z",
            "status": apt.status.value,
            "notes": apt.notes
        }
        for apt in appointments
    ]


@router.get(
    "/appointments/upcoming",
    summary="Get Upcoming Appointments",
    description="Retrieve upcoming confirmed appointments for staff member."
)
def get_upcoming_appointments(
    limit: int = 20,
    staff: Staff = Depends(get_current_staff),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get upcoming appointments for the staff member."""
    logger.info(f"Fetching upcoming appointments for staff {staff.id}")
    
    from db.models import AppointmentStatus
    
    now = datetime.now(timezone.utc)
    
    appointments = db.query(Appointment).filter(
        Appointment.staff_id == staff.id,
        Appointment.start_time > now,
        Appointment.status.in_([
            AppointmentStatus.CONFIRMED,
            AppointmentStatus.PENDING,
            AppointmentStatus.CHECKED_IN
        ])
    ).order_by(Appointment.start_time).limit(limit).all()
    
    return [
        {
            "id": str(apt.id),
            "customer_name": apt.customer.full_name if apt.customer else "N/A",
            "service": apt.service.name if apt.service else "N/A",
            "start_time": apt.start_time.isoformat() if apt.start_time.tzinfo else f"{apt.start_time.isoformat()}Z",
            "duration_minutes": apt.service.duration_minutes if apt.service else 0,
            "status": apt.status.value
        }
        for apt in appointments
    ]


@router.get(
    "/performance",
    response_model=StaffPerformanceMetrics,
    summary="Get Staff Performance Metrics",
    description="Retrieve staff performance metrics and statistics."
)
def get_performance_metrics(
    staff: Staff = Depends(get_current_staff),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get staff performance metrics."""
    logger.info(f"Fetching performance metrics for staff {staff.id}")
    
    from db.models import AppointmentStatus, Review
    
    # Get all appointments
    all_appointments = db.query(Appointment).filter(
        Appointment.staff_id == staff.id
    ).all()
    
    completed_appointments = sum(
        1 for a in all_appointments
        if a.status == AppointmentStatus.COMPLETED
    )
    
    cancelled_appointments = sum(
        1 for a in all_appointments
        if a.status == AppointmentStatus.CANCELLED
    )
    
    # Get reviews
    reviews = db.query(Review).filter(
        Review.appointment_id.in_([a.id for a in all_appointments])
    ).all()
    
    avg_rating = sum(r.rating for r in reviews) / len(reviews) if reviews else 0.0
    
    return StaffPerformanceMetrics(
        staff_id=str(staff.id),
        name=staff.full_name,
        role=staff.role,
        total_appointments=len(all_appointments),
        completed_appointments=completed_appointments,
        cancelled_appointments=cancelled_appointments,
        average_rating=round(avg_rating, 2),
        total_revenue=0.0
    )


# --- Leaves Management ---
from db import StaffLeave

class LeaveCreateRequest(BaseModel):
    leave_date: str  # YYYY-MM-DD
    reason: Optional[str] = None

class LeaveResponse(BaseModel):
    id: str
    leave_date: str
    reason: Optional[str]

@router.post(
    "/leaves",
    response_model=LeaveResponse,
    summary="Request Leave",
    description="Allows staff to put leave for a specific date."
)
def create_staff_leave(
    payload: LeaveCreateRequest,
    staff: Staff = Depends(get_current_staff),
    db: Session = Depends(get_db)
):
    try:
        ld = datetime.strptime(payload.leave_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format. Expected YYYY-MM-DD."
        )

    # Check if leave already exists
    existing = db.query(StaffLeave).filter(
        StaffLeave.staff_id == staff.id,
        StaffLeave.leave_date == ld
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Leave already requested for this date."
        )

    # Create leave
    new_leave = StaffLeave(
        staff_id=staff.id,
        leave_date=ld,
        reason=payload.reason
    )
    db.add(new_leave)
    db.commit()
    db.refresh(new_leave)

    return LeaveResponse(
        id=str(new_leave.id),
        leave_date=new_leave.leave_date.strftime("%Y-%m-%d"),
        reason=new_leave.reason
    )

@router.get(
    "/leaves",
    response_model=list[LeaveResponse],
    summary="Get Staff Leaves",
    description="Retrieve all leaves registered for the current staff."
)
def get_staff_leaves(
    staff: Staff = Depends(get_current_staff),
    db: Session = Depends(get_db)
):
    leaves = db.query(StaffLeave).filter(
        StaffLeave.staff_id == staff.id
    ).order_by(StaffLeave.leave_date.asc()).all()
    
    return [
        LeaveResponse(
            id=str(l.id),
            leave_date=l.leave_date.strftime("%Y-%m-%d"),
            reason=l.reason
        )
        for l in leaves
    ]

@router.delete(
    "/leaves/{leave_id}",
    summary="Cancel Leave",
    description="Remove/cancel a previously submitted leave."
)
def cancel_staff_leave(
    leave_id: str,
    staff: Staff = Depends(get_current_staff),
    db: Session = Depends(get_db)
):
    from uuid import UUID
    try:
        leave_uuid = UUID(leave_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid leave_id format."
        )
        
    leave = db.query(StaffLeave).filter(
        StaffLeave.id == leave_uuid,
        StaffLeave.staff_id == staff.id
    ).first()
    
    if not leave:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Leave request not found."
        )
        
    db.delete(leave)
    db.commit()
    return {"success": True, "message": "Leave cancelled successfully."}

