"""
Core API Routes for SalonAI Workforce Platform.
Public endpoints for services, branches, and basic discovery (no authentication required).
"""

import logging
from typing import List, Optional, Any
from fastapi import APIRouter, Query, Path, HTTPException, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db import (
    get_db,
    SessionLocal,
    Branch,
    Service,
    Staff,
    Customer,
    Appointment,
    Review,
    User,
    UserRole,
    AppointmentStatus,
    ReviewStatus,
    Notification,
)
from api.deps import RoleChecker, get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="",
    tags=["Core"]
)


# ============================================================================
# RESPONSE MODELS
# ============================================================================

class BranchResponse(BaseModel):
    """Response model for branch data"""
    id: str = Field(..., description="Branch UUID")
    name: str = Field(..., description="Branch name")
    code: str = Field(..., description="Branch code")
    address: str = Field(..., description="Physical address")
    city: str = Field(..., description="City/Location")
    phone: Optional[str] = Field(None, description="Phone number")
    email: Optional[str] = Field(None, description="Email address")
    is_active: bool = Field(..., description="Is branch active")

    class Config:
        from_attributes = True


class ServiceResponse(BaseModel):
    """Response model for service data"""
    id: str = Field(..., description="Service UUID")
    name: str = Field(..., description="Service name")
    description: Optional[str] = Field(None, description="Service description")
    price: float = Field(..., description="Service price in USD")
    duration_minutes: int = Field(..., description="Service duration in minutes")
    is_active: bool = Field(..., description="Is service active")

    class Config:
        from_attributes = True


class StaffResponse(BaseModel):
    """Response model for staff data"""
    id: str = Field(..., description="Staff UUID")
    first_name: str = Field(..., description="First name")
    last_name: str = Field(..., description="Last name")
    email: str = Field(..., description="Email address")
    phone: Optional[str] = Field(None, description="Phone number")
    role: str = Field(..., description="Job role")
    branch_id: str = Field(..., description="Branch UUID")
    is_active: bool = Field(..., description="Is staff active")

    class Config:
        from_attributes = True

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class CustomerResponse(BaseModel):
    """Response model for customer data"""
    id: str = Field(..., description="Customer UUID")
    first_name: str = Field(..., description="First name")
    last_name: str = Field(..., description="Last name")
    email: str = Field(..., description="Email address")
    phone: Optional[str] = Field(None, description="Phone number")
    is_active: bool = Field(..., description="Is customer active")

    class Config:
        from_attributes = True

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class ServiceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    price: float = Field(..., gt=0.0)
    duration_minutes: int = Field(..., gt=0)
    is_active: Optional[bool] = True


class ServiceUpdatePrice(BaseModel):
    price: float = Field(..., gt=0.0)


# ============================================================================
# PUBLIC ENDPOINTS - No authentication required
# ============================================================================

@router.get(
    "/services",
    response_model=List[ServiceResponse],
    summary="Get All Available Services",
    tags=["Public"]
)
async def get_all_services(
    active_only: bool = Query(True, description="Filter to active services only"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Number of records to return")
):
    """
    Retrieve all available salon services.
    Public endpoint - no authentication required.
    Perfect for frontend booking interface to display service catalog.
    
    Returns:
        List of services with ID, name, price, duration, and active status
    """
    db = SessionLocal()
    try:
        query = db.query(Service)
        
        if active_only:
            query = query.filter(Service.is_active == True)
        
        services = query.offset(skip).limit(limit).all()
        logger.info(f"Retrieved {len(services)} services")
        
        return [
            ServiceResponse(
                id=str(service.id),
                name=service.name,
                description=service.description,
                price=float(service.price),
                duration_minutes=service.duration_minutes,
                is_active=service.is_active
            )
            for service in services
        ]
    except Exception as e:
        logger.error(f"Error retrieving services: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.post(
    "/services",
    response_model=ServiceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new service (Admin Only)",
    dependencies=[Depends(RoleChecker([UserRole.ADMIN, UserRole.OWNER]))]
)
async def create_service(
    payload: ServiceCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new salon service catalog item.
    Restricted to Admin / Owner users.
    """
    try:
        existing = db.query(Service).filter(Service.name.ilike(payload.name)).first()
        if existing:
            raise HTTPException(status_code=400, detail="Service with this name already exists")
            
        new_service = Service(
            name=payload.name,
            description=payload.description,
            price=payload.price,
            duration_minutes=payload.duration_minutes,
            is_active=payload.is_active if payload.is_active is not None else True
        )
        db.add(new_service)
        db.commit()
        db.refresh(new_service)
        return ServiceResponse(
            id=str(new_service.id),
            name=new_service.name,
            description=new_service.description,
            price=float(new_service.price),
            duration_minutes=new_service.duration_minutes,
            is_active=new_service.is_active
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating service: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.put(
    "/services/{service_id}",
    response_model=ServiceResponse,
    summary="Update service price (Admin Only)",
    dependencies=[Depends(RoleChecker([UserRole.ADMIN, UserRole.OWNER]))]
)
async def update_service_price(
    service_id: str,
    payload: ServiceUpdatePrice,
    db: Session = Depends(get_db)
):
    """
    Update an existing service's price.
    Restricted to Admin / Owner users.
    """
    import uuid
    try:
        s_id = uuid.UUID(service_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid service ID format")
        
    service = db.query(Service).filter(Service.id == s_id).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
        
    try:
        service.price = payload.price
        db.commit()
        db.refresh(service)
        return ServiceResponse(
            id=str(service.id),
            name=service.name,
            description=service.description,
            price=float(service.price),
            duration_minutes=service.duration_minutes,
            is_active=service.is_active
        )
    except Exception as e:
        logger.error(f"Error updating service: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/branches",
    response_model=List[BranchResponse],
    summary="Get All Available Branches",
    tags=["Public"]
)
async def get_all_branches(
    active_only: bool = Query(True, description="Filter to active branches only"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Number of records to return")
):
    """
    Retrieve all available salon branches/locations.
    Public endpoint - no authentication required.
    Perfect for frontend booking interface to display available locations.
    
    Returns:
        List of branches with ID, name, code, address, city, phone, and active status
    """
    db = SessionLocal()
    try:
        query = db.query(Branch)
        
        if active_only:
            query = query.filter(Branch.is_active == True)
        
        branches = query.offset(skip).limit(limit).all()
        logger.info(f"Retrieved {len(branches)} branches")
        
        return [
            BranchResponse(
                id=str(branch.id),
                name=branch.name,
                code=branch.code,
                address=branch.address,
                city=branch.city,
                phone=branch.phone,
                email=branch.email,
                is_active=branch.is_active
            )
            for branch in branches
        ]
    except Exception as e:
        logger.error(f"Error retrieving branches: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.get(
    "/branches/{branch_id}/staff",
    response_model=List[StaffResponse],
    summary="Get Staff Members by Branch",
    tags=["Public"]
)
async def get_branch_staff(
    branch_id: str = Path(..., description="Branch UUID"),
    active_only: bool = Query(True, description="Filter to active staff only"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Number of records to return")
):
    """
    Retrieve staff members for a specific branch.
    Public endpoint - no authentication required.
    Used to show available stylists when customer selects a branch.
    
    Args:
        branch_id: UUID of the branch
        
    Returns:
        List of staff members with ID, name, email, phone, role, and active status
    """
    db = SessionLocal()
    try:
        from uuid import UUID
        
        try:
            branch_uuid = UUID(branch_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid branch_id format")
        
        query = db.query(Staff).filter(Staff.branch_id == branch_uuid)
        
        if active_only:
            query = query.filter(Staff.is_active == True)
        
        staff_list = query.offset(skip).limit(limit).all()
        logger.info(f"Retrieved {len(staff_list)} staff members for branch {branch_id}")
        
        return [
            StaffResponse(
                id=str(staff.id),
                first_name=staff.first_name,
                last_name=staff.last_name,
                email=staff.email,
                phone=staff.phone,
                role=staff.role,
                branch_id=str(staff.branch_id),
                is_active=staff.is_active
            )
            for staff in staff_list
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving staff: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


# ============================================================================
# PROTECTED ENDPOINTS - Staff/Admin only
# ============================================================================

@router.get(
    "/customers",
    response_model=List[CustomerResponse],
    summary="Search Customers",
    tags=["Protected"],
    dependencies=[Depends(RoleChecker([UserRole.STAFF, UserRole.ADMIN]))]
)
async def search_customers(
    query: str = Query("", description="Search by name, email, or phone"),
    active_only: bool = Query(True, description="Filter to active customers only"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=500, description="Number of records to return"),
    current_user = Depends(lambda: None)  # Placeholder for auth
):
    """
    Search for customers by name, email, or phone.
    Protected endpoint - requires Staff or Admin role.
    Used internally to find customers for booking.
    
    Returns:
        List of matching customers
    """
    db = SessionLocal()
    try:
        query_obj = db.query(Customer)
        
        if query.strip():
            search_term = f"%{query.strip()}%"
            query_obj = query_obj.filter(
                (Customer.first_name.ilike(search_term)) |
                (Customer.last_name.ilike(search_term)) |
                (Customer.email.ilike(search_term)) |
                (Customer.phone.ilike(search_term))
            )
        
        if active_only:
            query_obj = query_obj.filter(Customer.is_active == True)
        
        customers = query_obj.offset(skip).limit(limit).all()
        logger.info(f"Found {len(customers)} customers matching: {query}")
        
        return [
            CustomerResponse(
                id=str(customer.id),
                first_name=customer.first_name,
                last_name=customer.last_name,
                email=customer.email,
                phone=customer.phone,
                is_active=customer.is_active
            )
            for customer in customers
        ]
    except Exception as e:
        logger.error(f"Error searching customers: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.get(
    "/health",
    summary="API Health Check",
    tags=["Health"]
)
async def core_health():
    """
    Health check endpoint for core API.
    Verifies that database and basic services are operational.
    """
    db = SessionLocal()
    try:
        # Test database connection
        branch_count = db.query(Branch).count()
        service_count = db.query(Service).count()
        
        return {
            "status": "healthy",
            "database": "connected",
            "branches": branch_count,
            "services": service_count,
            "timestamp": __import__('datetime').datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e)
        }
    finally:
        db.close()


# ============================================================================
# CUSTOMER APPOINTMENTS & REVIEWS ENDPOINTS
# ============================================================================

class AppointmentCreateRequest(BaseModel):
    branch_id: str
    service_id: str
    start_time: str
    staff_id: Optional[str] = None
    notes: Optional[str] = None

class RescheduleRequest(BaseModel):
    new_start_time: str

class ReviewCreateRequest(BaseModel):
    appointment_id: str
    rating: int
    comment: Optional[str] = None

class StatusUpdateRequest(BaseModel):
    status: AppointmentStatus

class WaitlistCreateRequest(BaseModel):
    branch_id: str
    service_id: str
    date_str: str
    time_str: str
    staff_id: Optional[str] = None


@router.get(
    "/appointments/my",
    summary="Get My Appointments",
    tags=["Appointments"]
)
async def get_my_appointments(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve all appointments for the currently authenticated user.
    """
    logger.info(f"Retrieving appointments for user {current_user.email} (customer_id={current_user.customer_id})")
    
    if current_user.role == UserRole.CUSTOMER or current_user.role.value == "CUSTOMER":
        if not current_user.customer_id:
            return []
        
        # Trigger lazy reminders (Rule 11)
        try:
            from tools.booking_tools import send_appointment_reminders
            send_appointment_reminders(str(current_user.customer_id), db)
        except Exception as e:
            logger.warning(f"Lazy reminders trigger failed: {e}")

        query = db.query(Appointment).filter(Appointment.customer_id == current_user.customer_id)
    elif current_user.role == UserRole.STAFF or current_user.role.value == "STAFF":
        if not current_user.staff_id:
            return []
        query = db.query(Appointment).filter(Appointment.staff_id == current_user.staff_id)
    else:
        query = db.query(Appointment)
        
    appointments = query.order_by(Appointment.start_time.desc()).all()
    
    result = []
    for appt in appointments:
        result.append({
            "id": str(appt.id),
            "start_time": appt.start_time.isoformat() if appt.start_time.tzinfo else f"{appt.start_time.isoformat()}Z",
            "end_time": appt.end_time.isoformat() if appt.end_time.tzinfo else f"{appt.end_time.isoformat()}Z",
            "status": appt.status.value if hasattr(appt.status, "value") else str(appt.status),
            "notes": appt.notes,
            "service": {
                "name": appt.service.name,
                "price": float(appt.service.price),
                "duration_minutes": appt.service.duration_minutes
            },
            "staff": {
                "first_name": appt.staff.first_name,
                "last_name": appt.staff.last_name
            } if appt.staff else None,
            "branch": {
                "name": appt.branch.name,
                "city": appt.branch.city
            },
            "customer": {
                "id": str(appt.customer.id),
                "first_name": appt.customer.first_name,
                "last_name": appt.customer.last_name,
                "email": appt.customer.email,
                "phone": appt.customer.phone
            } if appt.customer else None
        })
    return result


@router.post(
    "/appointments",
    status_code=status.HTTP_201_CREATED,
    summary="Book a New Appointment",
    tags=["Appointments"]
)
async def book_appointment(
    payload: AppointmentCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Book a new validated appointment.
    """
    if not current_user.customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only customer accounts can book appointments."
        )
        
    from tools.booking_tools import create_appointment
    result = create_appointment(
        customer_id=str(current_user.customer_id),
        branch_id=payload.branch_id,
        service_id=payload.service_id,
        start_time=payload.start_time,
        staff_id=payload.staff_id,
        notes=payload.notes,
        db=db
    )
    
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Booking failed.")
        )
    db.commit()
    return result


@router.delete(
    "/appointments/{appointment_id}",
    summary="Cancel an Appointment",
    tags=["Appointments"]
)
async def cancel_booking(
    appointment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Cancel an existing appointment.
    """
    from uuid import UUID
    try:
        appt_uuid = UUID(appointment_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid appointment_id format.")
        
    appt = db.query(Appointment).filter(Appointment.id == appt_uuid).first()
    if not appt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found.")
        
    if (current_user.role == UserRole.CUSTOMER or current_user.role.value == "CUSTOMER") and appt.customer_id != current_user.customer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to cancel this appointment."
        )
        
    from tools.booking_tools import cancel_appointment
    result = cancel_appointment(appointment_id=appointment_id, customer_id=str(current_user.customer_id) if current_user.customer_id else None, db=db)
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Cancellation failed.")
        )
    db.commit()
    return result


@router.post(
    "/appointments/{appointment_id}/reschedule",
    summary="Reschedule an Appointment",
    tags=["Appointments"]
)
async def reschedule_booking(
    appointment_id: str,
    payload: RescheduleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Reschedule an existing appointment.
    """
    from uuid import UUID
    try:
        appt_uuid = UUID(appointment_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid appointment_id format.")
        
    appt = db.query(Appointment).filter(Appointment.id == appt_uuid).first()
    if not appt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found.")
        
    if (current_user.role == UserRole.CUSTOMER or current_user.role.value == "CUSTOMER") and appt.customer_id != current_user.customer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to reschedule this appointment."
        )
        
    from tools.booking_tools import reschedule_appointment
    result = reschedule_appointment(
        appointment_id=appointment_id,
        new_start_time=payload.new_start_time,
        customer_id=str(current_user.customer_id) if current_user.customer_id else None,
        db=db
    )
    
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Rescheduling failed.")
        )
    db.commit()
    return result


# Reviews routing is now handled by api/routes/review_routes.py (Reputation Agent module)


@router.post(
    "/appointments/{appointment_id}/status",
    summary="Update Appointment Status with Strict Workflow",
    tags=["Appointments"]
)
async def update_appointment_status(
    appointment_id: str,
    payload: StatusUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update appointment status following the strict workflow rules:
    Pending -> Confirmed -> Checked In -> In Service -> Completed
    or
    Confirmed -> Cancelled
    """
    from uuid import UUID
    try:
        appt_uuid = UUID(appointment_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid appointment_id format.")
        
    appt = db.query(Appointment).filter(Appointment.id == appt_uuid).first()
    if not appt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found.")
        
    current = appt.status
    target = payload.status
    
    if current == target:
        return {"success": True, "appointment_id": str(appt.id), "status": appt.status.value}

    # Strict workflow check
    allowed = False
    if current == AppointmentStatus.PENDING:
        if target in [AppointmentStatus.CONFIRMED, AppointmentStatus.CANCELLED]:
            allowed = True
    elif current == AppointmentStatus.CONFIRMED:
        if target in [AppointmentStatus.CHECKED_IN, AppointmentStatus.CANCELLED]:
            allowed = True
    elif current == AppointmentStatus.CHECKED_IN:
        if target == AppointmentStatus.IN_SERVICE:
            allowed = True
    elif current == AppointmentStatus.IN_SERVICE:
        if target == AppointmentStatus.COMPLETED:
            allowed = True
            
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status transition from {current} to {target}. Strict workflow is Pending -> Confirmed -> Checked In -> In Service -> Completed, or Confirmed -> Cancelled."
        )
        
    if target == AppointmentStatus.CANCELLED:
        from tools.booking_tools import cancel_appointment
        result = cancel_appointment(appointment_id=appointment_id, customer_id=str(current_user.customer_id) if current_user.customer_id else None, db=db)
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Cancellation failed.")
            )
        db.commit()
        return result
        
    appt.status = target
    db.commit()

    # Dispatch notification to user dynamically
    try:
        user = db.query(User).filter(User.customer_id == appt.customer_id).first()
        if user:
            import uuid
            title = "Appointment Status Updated"
            msg = f"Your appointment for {appt.service.name} status is now {target.value}."
            
            if target == AppointmentStatus.CONFIRMED:
                title = "Appointment Confirmed"
                msg = f"Your styling session for {appt.service.name} has been confirmed for {appt.start_time.strftime('%Y-%m-%d %H:%M')}."
            elif target == AppointmentStatus.CHECKED_IN:
                title = "Checked In"
                msg = f"Welcome! You have checked in for your {appt.service.name} session."
            elif target == AppointmentStatus.IN_SERVICE:
                title = "Service Started"
                msg = f"Your {appt.service.name} service is now in progress."
            elif target == AppointmentStatus.COMPLETED:
                title = "Service Completed"
                msg = f"Your service {appt.service.name} is completed. Thank you for visiting! Please leave a review."
                # Auto-award loyalty points
                try:
                    from tools.loyalty_service import on_appointment_completed
                    on_appointment_completed(db=db, appointment_id=appt.id, customer_id=appt.customer_id)
                except Exception as loyalty_err:
                    logger.error(f"Failed to auto-award loyalty points: {loyalty_err}")
                    
            notif = Notification(
                id=uuid.uuid4(),
                user_id=user.id,
                title=title,
                message=msg,
                is_read=False
            )
            db.add(notif)
            db.commit()
    except Exception as notif_err:
        logger.error(f"Error creating status transition notification: {notif_err}")

    return {"success": True, "appointment_id": str(appt.id), "status": appt.status.value}


@router.post(
    "/waitlist",
    summary="Join Waitlist",
    tags=["Waitlist"]
)
async def join_waitlist(
    payload: WaitlistCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Join waitlist for a slot that is currently booked out (Rule 16).
    """
    if not current_user.customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only customer accounts can join the waitlist."
        )
        
    from tools.booking_tools import add_to_waitlist
    result = add_to_waitlist(
        customer_id=str(current_user.customer_id),
        branch_id=payload.branch_id,
        service_id=payload.service_id,
        date_str=payload.date_str,
        time_str=payload.time_str,
        staff_id=payload.staff_id,
        db=db
    )
    
    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.get("error", "Failed to join waitlist.")
        )
        
    return result

