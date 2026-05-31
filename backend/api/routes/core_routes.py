"""
Core API Routes for SalonAI Workforce Platform.
Public endpoints for services, branches, and basic discovery (no authentication required).
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Query, Path, HTTPException, Depends
from pydantic import BaseModel, Field

from db.database import SessionLocal
from db import Branch, Service, Staff, Customer
from db.models import UserRole
from api.deps import RoleChecker

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/core",
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
