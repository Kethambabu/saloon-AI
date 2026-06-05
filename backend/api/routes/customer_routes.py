"""
Customer-specific API Routes for SalonAI Workforce Platform.
Provides customer dashboard, loyalty points, profile, and isolated data access.
Ensures data isolation so customers only see their own information.
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db, Customer, UserRole, Appointment, Review, LoyaltyTransaction
from api.deps import get_current_user
from tools.loyalty_service import (
    get_customer_loyalty_summary,
    on_appointment_completed,
    on_appointment_cancelled,
    on_review_submitted,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/customer", tags=["Customer"])


# --- Pydantic Schemas ---

class LoyaltyPointsResponse(BaseModel):
    """Loyalty points summary for a customer"""
    current_balance: int
    completed_appointments: int
    reviews_submitted: int
    average_rating: float
    recent_transactions: list


class LoyaltyTransactionResponse(BaseModel):
    """Individual loyalty transaction"""
    id: str
    type: str
    points_change: int
    new_balance: int
    description: Optional[str]
    created_at: str


class AppointmentHistoryResponse(BaseModel):
    """Customer appointment history"""
    id: str
    service_name: str
    branch_name: str
    staff_name: str
    start_time: str
    status: str
    rating: Optional[int] = None


class CustomerDashboardResponse(BaseModel):
    """Complete customer dashboard data"""
    customer_id: str
    name: str
    email: str
    phone: Optional[str]
    is_active: bool
    loyalty_points: int
    total_appointments: int
    completed_appointments: int
    upcoming_appointments: int
    total_spent: Optional[float] = 0.0
    average_rating: float
    recent_appointments: list
    recent_reviews: list


class CustomerProfileResponse(BaseModel):
    """Customer profile information"""
    id: str
    first_name: str
    last_name: str
    email: str
    phone: Optional[str]
    is_active: bool
    loyalty_points: int
    created_at: str
    updated_at: str


# --- Helper Functions ---

def get_current_customer(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Customer:
    """
    Dependency to ensure current user is a customer.
    Returns the associated customer object.
    """
    if current_user.role != UserRole.CUSTOMER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is only accessible to customers"
        )
    
    if not current_user.customer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User does not have an associated customer profile"
        )
    
    customer = db.query(Customer).filter(
        Customer.id == current_user.customer_id
    ).first()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer profile not found"
        )
    
    return customer


# --- Endpoints ---

@router.get(
    "/dashboard",
    response_model=CustomerDashboardResponse,
    summary="Get Customer Dashboard",
    description="Retrieve complete customer dashboard with appointments, loyalty points, and engagement metrics."
)
def get_customer_dashboard(
    customer: Customer = Depends(get_current_customer),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a customer's complete dashboard with:
    - Loyalty points summary
    - Appointment history
    - Reviews and ratings
    - Upcoming appointments
    """
    logger.info(f"Fetching dashboard for customer {customer.id}")
    
    # Get all appointments
    all_appointments = db.query(Appointment).filter(
        Appointment.customer_id == customer.id
    ).order_by(Appointment.created_at.desc()).all()
    
    # Get reviews
    reviews = db.query(Review).filter(
        Review.customer_id == customer.id
    ).all()
    
    avg_rating = sum(r.rating for r in reviews) / len(reviews) if reviews else 0.0
    
    # Count appointment statuses
    from db.models import AppointmentStatus
    from datetime import datetime, timezone
    
    completed_count = sum(1 for a in all_appointments if a.status == AppointmentStatus.COMPLETED)
    upcoming_count = sum(
        1 for a in all_appointments 
        if a.status in [AppointmentStatus.CONFIRMED, AppointmentStatus.PENDING]
        and (
            a.start_time.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc) 
            if a.start_time.tzinfo is None 
            else a.start_time > datetime.now(timezone.utc)
        )
    )
    
    # Format recent appointments
    recent_appointments = []
    for apt in all_appointments[:5]:
        recent_appointments.append({
            "id": str(apt.id),
            "service_name": apt.service.name if apt.service else "N/A",
            "branch_name": apt.branch.name if apt.branch else "N/A",
            "staff_name": apt.staff.full_name if apt.staff else "N/A",
            "start_time": (apt.start_time.isoformat() if apt.start_time.tzinfo else f"{apt.start_time.isoformat()}Z") if apt.start_time else None,
            "status": apt.status.value,
            "rating": next(
                (r.rating for r in reviews if r.appointment_id == apt.id),
                None
            )
        })
    
    # Format recent reviews
    recent_reviews = [
        {
            "id": str(r.id),
            "rating": r.rating,
            "comment": r.comment,
            "created_at": r.created_at.isoformat(),
            "appointment_id": str(r.appointment_id) if r.appointment_id else None
        }
        for r in reviews[:5]
    ]
    
    return CustomerDashboardResponse(
        customer_id=str(customer.id),
        name=customer.full_name,
        email=customer.email,
        phone=customer.phone,
        is_active=customer.is_active,
        loyalty_points=customer.loyalty_points,
        total_appointments=len(all_appointments),
        completed_appointments=completed_count,
        upcoming_appointments=upcoming_count,
        total_spent=0.0,  # Calculate from completed appointments
        average_rating=round(avg_rating, 2),
        recent_appointments=recent_appointments,
        recent_reviews=recent_reviews
    )


@router.get(
    "/loyalty/balance",
    response_model=LoyaltyPointsResponse,
    summary="Get Customer Loyalty Points",
    description="Retrieve customer loyalty points balance and recent transaction history."
)
def get_loyalty_points(
    customer: Customer = Depends(get_current_customer),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get detailed loyalty points summary for the customer."""
    logger.info(f"Fetching loyalty points for customer {customer.id}")
    
    try:
        summary = get_customer_loyalty_summary(db, customer.id)
        return LoyaltyPointsResponse(
            current_balance=summary["current_balance"],
            completed_appointments=summary["completed_appointments"],
            reviews_submitted=summary["reviews_submitted"],
            average_rating=summary["average_rating"],
            recent_transactions=summary["recent_transactions"]
        )
    except Exception as e:
        logger.error(f"Error fetching loyalty points: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve loyalty points"
        )


@router.get(
    "/loyalty/transactions",
    response_model=list[LoyaltyTransactionResponse],
    summary="Get Loyalty Transaction History",
    description="Retrieve complete loyalty transaction history for the customer."
)
def get_loyalty_transactions(
    limit: int = 20,
    customer: Customer = Depends(get_current_customer),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get loyalty transaction history for the customer."""
    logger.info(f"Fetching loyalty transactions for customer {customer.id}")
    
    transactions = (
        db.query(LoyaltyTransaction)
        .filter(LoyaltyTransaction.customer_id == customer.id)
        .order_by(LoyaltyTransaction.created_at.desc())
        .limit(limit)
        .all()
    )
    
    return [
        LoyaltyTransactionResponse(
            id=str(t.id),
            type=t.transaction_type.value,
            points_change=t.points_change,
            new_balance=t.new_balance,
            description=t.description,
            created_at=t.created_at.isoformat()
        )
        for t in transactions
    ]


@router.get(
    "/profile",
    response_model=CustomerProfileResponse,
    summary="Get Customer Profile",
    description="Retrieve customer profile information."
)
def get_customer_profile(
    customer: Customer = Depends(get_current_customer),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get customer profile information."""
    logger.info(f"Fetching profile for customer {customer.id}")
    
    return CustomerProfileResponse(
        id=str(customer.id),
        first_name=customer.first_name,
        last_name=customer.last_name,
        email=customer.email,
        phone=customer.phone,
        is_active=customer.is_active,
        loyalty_points=customer.loyalty_points,
        created_at=customer.created_at.isoformat(),
        updated_at=customer.updated_at.isoformat()
    )


@router.get(
    "/appointments",
    response_model=list[AppointmentHistoryResponse],
    summary="Get Customer Appointment History",
    description="Retrieve all customer appointments with filtering options."
)
def get_customer_appointments(
    limit: int = 50,
    status: Optional[str] = None,
    customer: Customer = Depends(get_current_customer),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get customer appointment history.
    
    Query Parameters:
    - limit: Maximum number of appointments to return (default: 50)
    - status: Filter by appointment status (PENDING, CONFIRMED, COMPLETED, CANCELLED, etc.)
    """
    logger.info(f"Fetching appointments for customer {customer.id}")
    
    query = db.query(Appointment).filter(
        Appointment.customer_id == customer.id
    ).order_by(Appointment.created_at.desc())
    
    if status:
        from db.models import AppointmentStatus
        try:
            status_enum = AppointmentStatus[status.upper()]
            query = query.filter(Appointment.status == status_enum)
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status}"
            )
    
    appointments = query.limit(limit).all()
    
    return [
        AppointmentHistoryResponse(
            id=str(apt.id),
            service_name=apt.service.name if apt.service else "N/A",
            branch_name=apt.branch.name if apt.branch else "N/A",
            staff_name=apt.staff.full_name if apt.staff else "N/A",
            start_time=(apt.start_time.isoformat() if apt.start_time.tzinfo else f"{apt.start_time.isoformat()}Z") if apt.start_time else None,
            status=apt.status.value,
            rating=None
        )
        for apt in appointments
    ]


@router.post(
    "/loyalty/award-completion",
    summary="Award Points for Appointment Completion",
    description="Admin/System endpoint to award loyalty points when appointment is completed. (Internal use)"
)
def award_completion_points(
    appointment_id: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Award points when an appointment is marked as completed.
    This is typically called by the system when appointment status changes to COMPLETED.
    """
    # This endpoint should only be callable by admin or system
    if current_user.role not in [UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can award loyalty points"
        )
    
    try:
        appointment_uuid = UUID(appointment_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid appointment ID format"
        )
    
    appointment = db.query(Appointment).filter(
        Appointment.id == appointment_uuid
    ).first()
    
    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Appointment not found"
        )
    
    try:
        transaction = on_appointment_completed(
            db=db,
            appointment_id=appointment_uuid,
            customer_id=appointment.customer_id
        )
        db.commit()
        
        return {
            "success": True,
            "message": f"Awarded loyalty points for appointment completion",
            "transaction_id": str(transaction.id),
            "points_awarded": transaction.points_change,
            "new_balance": transaction.new_balance
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Error awarding points: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to award loyalty points"
        )
