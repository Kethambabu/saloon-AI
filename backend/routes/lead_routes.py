"""
Lead-specific API Routes for SalonAI Workforce Platform.
Exposes endpoints for Admin lead monitoring, Staff-assigned leads,
lead conversion analytics, follow-up notifications, and conversions.
"""

import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from db import get_db, Lead, LeadStatus, User, UserRole, Staff, Branch
from api.deps import get_current_user
from services.lead_service import send_lead_followup, convert_lead_to_appointment

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Leads"])


# --- Pydantic Schemas ---

class LeadFollowupRequest(BaseModel):
    lead_id: str


class LeadConvertRequest(BaseModel):
    lead_id: str
    staff_id: Optional[str] = None


class LeadResponse(BaseModel):
    id: str
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    service_name: Optional[str] = None
    preferred_date: Optional[str] = None
    preferred_time: Optional[str] = None
    branch_id: Optional[str] = None
    assigned_staff: Optional[str] = None
    source: Optional[str] = None
    status: str
    lead_score: int
    followup_count: int
    last_contacted: Optional[str] = None
    converted: bool
    converted_at: Optional[str] = None
    notes: Optional[str] = None
    created_at: str

    class Config:
        from_attributes = True


class LeadAnalyticsResponse(BaseModel):
    total_leads: int
    new_leads: int
    contacted_leads: int
    interested_leads: int
    converted_leads: int
    lost_leads: int
    conversion_rate: float
    top_recoverable_leads: List[LeadResponse]


# --- Helper Functions ---

def verify_admin_access(current_user: User = Depends(get_current_user)):
    """Verifies that the user has admin or manager access."""
    if current_user.role not in [UserRole.ADMIN, UserRole.MANAGER, UserRole.OWNER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Admin access required."
        )
    return current_user


def verify_staff_access(current_user: User = Depends(get_current_user)):
    """Verifies that the user has staff or admin access."""
    if current_user.role not in [UserRole.STAFF, UserRole.ADMIN, UserRole.MANAGER, UserRole.OWNER]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Staff access required."
        )
    return current_user


# --- Endpoints ---

@router.get(
    "/leads",
    response_model=List[LeadResponse],
    summary="Get All Leads (Admin Only)",
    description="Retrieve all leads across the salon group with filtering options."
)
def get_all_leads(
    status_filter: Optional[str] = None,
    admin_user: User = Depends(verify_admin_access),
    db: Session = Depends(get_db)
):
    logger.info(f"Admin {admin_user.email} fetching all leads...")
    query = db.query(Lead)
    
    if status_filter:
        try:
            status_enum = LeadStatus(status_filter.upper())
            query = query.filter(Lead.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status '{status_filter}'. Use NEW, CONTACTED, INTERESTED, CONVERTED, or LOST."
            )
            
    leads = query.order_by(desc(Lead.created_at)).all()
    
    response_list = []
    for lead in leads:
        response_list.append(LeadResponse(
            id=str(lead.id),
            customer_id=str(lead.customer_id) if lead.customer_id else None,
            customer_name=lead.customer_name,
            customer_email=lead.customer_email,
            customer_phone=lead.customer_phone,
            service_name=lead.service_name,
            preferred_date=lead.preferred_date.isoformat() if lead.preferred_date else None,
            preferred_time=lead.preferred_time.isoformat() if lead.preferred_time else None,
            branch_id=str(lead.branch_id) if lead.branch_id else None,
            assigned_staff=str(lead.assigned_staff) if lead.assigned_staff else None,
            source=lead.source,
            status=lead.status.value,
            lead_score=lead.lead_score,
            followup_count=lead.followup_count,
            last_contacted=lead.last_contacted.isoformat() if lead.last_contacted else None,
            converted=lead.converted,
            converted_at=lead.converted_at.isoformat() if lead.converted_at else None,
            notes=lead.notes,
            created_at=lead.created_at.isoformat() if lead.created_at else None
        ))
    return response_list


@router.get(
    "/staff/leads",
    response_model=List[LeadResponse],
    summary="Get Staff Assigned Leads",
    description="Retrieve leads currently assigned to the authenticated staff member."
)
def get_staff_leads(
    staff_user: User = Depends(verify_staff_access),
    db: Session = Depends(get_db)
):
    logger.info(f"Staff {staff_user.email} fetching assigned leads...")
    
    if staff_user.role in [UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER]:
        # Admins can see all leads
        leads = db.query(Lead).order_by(desc(Lead.created_at)).all()
    else:
        if not staff_user.staff_id:
            raise HTTPException(
                status_code=400,
                detail="User account does not have an associated staff ID."
            )
        leads = db.query(Lead).filter(Lead.assigned_staff == staff_user.staff_id).order_by(desc(Lead.created_at)).all()
        
    response_list = []
    for lead in leads:
        response_list.append(LeadResponse(
            id=str(lead.id),
            customer_id=str(lead.customer_id) if lead.customer_id else None,
            customer_name=lead.customer_name,
            customer_email=lead.customer_email,
            customer_phone=lead.customer_phone,
            service_name=lead.service_name,
            preferred_date=lead.preferred_date.isoformat() if lead.preferred_date else None,
            preferred_time=lead.preferred_time.isoformat() if lead.preferred_time else None,
            branch_id=str(lead.branch_id) if lead.branch_id else None,
            assigned_staff=str(lead.assigned_staff) if lead.assigned_staff else None,
            source=lead.source,
            status=lead.status.value,
            lead_score=lead.lead_score,
            followup_count=lead.followup_count,
            last_contacted=lead.last_contacted.isoformat() if lead.last_contacted else None,
            converted=lead.converted,
            converted_at=lead.converted_at.isoformat() if lead.converted_at else None,
            notes=lead.notes,
            created_at=lead.created_at.isoformat() if lead.created_at else None
        ))
    return response_list


@router.get(
    "/leads/analytics",
    response_model=LeadAnalyticsResponse,
    summary="Get Lead Analytics (Admin Only)",
    description="Calculate lead metrics, conversion rate, and retrieve top priority leads."
)
def get_leads_analytics(
    admin_user: User = Depends(verify_admin_access),
    db: Session = Depends(get_db)
):
    logger.info(f"Admin {admin_user.email} fetching lead analytics...")
    
    total = db.query(Lead).count()
    new_count = db.query(Lead).filter(Lead.status == LeadStatus.NEW).count()
    contacted_count = db.query(Lead).filter(Lead.status == LeadStatus.CONTACTED).count()
    interested_count = db.query(Lead).filter(Lead.status == LeadStatus.INTERESTED).count()
    converted_count = db.query(Lead).filter(Lead.status == LeadStatus.CONVERTED).count()
    lost_count = db.query(Lead).filter(Lead.status == LeadStatus.LOST).count()
    
    # Calculate conversion rate: (Converted Leads / Total Leads) * 100
    conversion_rate = (converted_count / total * 100.0) if total > 0 else 0.0
    
    # Fetch top priority/recoverable leads (NEW or CONTACTED, sorted by lead score descending)
    top_recoverable = db.query(Lead).filter(
        Lead.status.in_([LeadStatus.NEW, LeadStatus.CONTACTED, LeadStatus.INTERESTED])
    ).order_by(desc(Lead.lead_score)).limit(10).all()
    
    top_recoverable_list = []
    for lead in top_recoverable:
        top_recoverable_list.append(LeadResponse(
            id=str(lead.id),
            customer_id=str(lead.customer_id) if lead.customer_id else None,
            customer_name=lead.customer_name,
            customer_email=lead.customer_email,
            customer_phone=lead.customer_phone,
            service_name=lead.service_name,
            preferred_date=lead.preferred_date.isoformat() if lead.preferred_date else None,
            preferred_time=lead.preferred_time.isoformat() if lead.preferred_time else None,
            branch_id=str(lead.branch_id) if lead.branch_id else None,
            assigned_staff=str(lead.assigned_staff) if lead.assigned_staff else None,
            source=lead.source,
            status=lead.status.value,
            lead_score=lead.lead_score,
            followup_count=lead.followup_count,
            last_contacted=lead.last_contacted.isoformat() if lead.last_contacted else None,
            converted=lead.converted,
            converted_at=lead.converted_at.isoformat() if lead.converted_at else None,
            notes=lead.notes,
            created_at=lead.created_at.isoformat() if lead.created_at else None
        ))
        
    return LeadAnalyticsResponse(
        total_leads=total,
        new_leads=new_count,
        contacted_leads=contacted_count,
        interested_leads=interested_count,
        converted_leads=converted_count,
        lost_leads=lost_count,
        conversion_rate=round(conversion_rate, 2),
        top_recoverable_leads=top_recoverable_list
    )


@router.post(
    "/leads/followup",
    summary="Trigger Lead Follow-up Reminder",
    description="Triggers outreach notification to the customer and advances state to CONTACTED."
)
def trigger_followup(
    req: LeadFollowupRequest,
    staff_user: User = Depends(verify_staff_access),
    db: Session = Depends(get_db)
):
    try:
        lead_uuid = uuid.UUID(req.lead_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid lead UUID format.")
        
    res = send_lead_followup(lead_uuid, db)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
        
    return res


@router.post(
    "/leads/convert",
    summary="Convert Lead to Appointment",
    description="Registers a confirmed booking appointment and marks lead state as CONVERTED."
)
def convert_lead(
    req: LeadConvertRequest,
    staff_user: User = Depends(verify_staff_access),
    db: Session = Depends(get_db)
):
    try:
        lead_uuid = uuid.UUID(req.lead_id)
        staff_uuid = uuid.UUID(req.staff_id) if req.staff_id else None
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format for lead or staff.")
        
    res = convert_lead_to_appointment(lead_uuid, db, staff_uuid)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
        
    return res
