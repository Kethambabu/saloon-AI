"""
FastAPI router for Reputation Management Agent and customer review endpoints.
Defines submit review, respond, escalate, and admin analytics stats.
"""

import logging
from typing import Optional, Dict, Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

# Project imports
from db import get_db
from api.deps import get_current_user
from services.review_service import ReviewService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reviews", tags=["reviews"])


# Pydantic Schemas
class ReviewCreateRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5, description="Star rating between 1 and 5")
    comment: str = Field(..., description="Written review text feedback comment")
    appointment_id: Optional[str] = Field(None, description="Optional UUID string of appointment being reviewed")
    staff_id: Optional[str] = Field(None, description="Optional UUID string of the stylist being reviewed")


class RespondReviewRequest(BaseModel):
    review_id: str = Field(..., description="UUID string of review being responded to")
    custom_response: Optional[str] = Field(None, description="Optional manual message draft to override AI response")


class EscalateReviewRequest(BaseModel):
    review_id: str = Field(..., description="UUID string of review being escalated")


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Submit and analyze a new customer review"
)
async def submit_review(
    payload: ReviewCreateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Submits a new customer review on a completed appointment.
    Analyzes sentiment dynamically, generates auto-response drafts,
    and flags critical complaints for branch managers.
    """
    logger.info(f"POST /reviews called by user {current_user.email}")
    if not current_user.customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only customer accounts can submit reviews."
        )

    try:
        result = ReviewService.submit_review(
            db=db,
            customer_id=str(current_user.customer_id),
            rating=payload.rating,
            comment=payload.comment,
            appointment_id=payload.appointment_id,
            staff_id=payload.staff_id
        )
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to submit review.")
            )
        return result
    except Exception as e:
        logger.error(f"Error submitting review: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal database error: {str(e)}"
        )


@router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="Retrieve customer reviews with optional filtering"
)
async def get_reviews(
    customer_id: Optional[str] = Query(None, description="Filter by customer UUID"),
    staff_id: Optional[str] = Query(None, description="Filter by staff UUID"),
    sentiment: Optional[str] = Query(None, description="Filter by sentiment (POSITIVE, NEUTRAL, NEGATIVE, CRITICAL)"),
    escalation_required: Optional[bool] = Query(None, description="Filter by escalation status"),
    rating: Optional[int] = Query(None, ge=1, le=5, description="Filter by rating star bound"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Retrieves feedback reviews with role-based access.
    - Customers can only query their own reviews (unless they have admin/staff status).
    - Staff members can query their reviews and reviews assigned to them.
    - Admins have full global access to all records.
    """
    logger.info(f"GET /reviews called by user {current_user.email}")
    
    # Enforce role-based access scoping
    user_role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if "UserRole." in user_role:
        user_role = user_role.split("UserRole.")[1]
    scoped_customer_id = customer_id
    scoped_staff_id = staff_id

    if user_role == "CUSTOMER":
        scoped_customer_id = str(current_user.customer_id) if current_user.customer_id else None
        scoped_staff_id = None
    elif user_role == "STAFF":
        # Stylists see all reviews for their assigned chair
        scoped_staff_id = str(current_user.staff_id) if current_user.staff_id else None
        scoped_customer_id = None

    try:
        reviews = ReviewService.get_reviews(
            db=db,
            customer_id=scoped_customer_id,
            staff_id=scoped_staff_id,
            sentiment=sentiment,
            escalation_required=escalation_required,
            rating=rating
        )
        return {
            "success": True,
            "reviews": reviews
        }
    except Exception as e:
        logger.error(f"Error fetching reviews: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving reviews ledger: {str(e)}"
        )


@router.post(
    "/respond",
    status_code=status.HTTP_200_OK,
    summary="Register a manual or AI generated response to a review"
)
async def generate_response(
    payload: RespondReviewRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Submits a response to a review. Authorized for Admin/Staff only.
    """
    logger.info(f"POST /reviews/respond called by user {current_user.email}")
    user_role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if "UserRole." in user_role:
        user_role = user_role.split("UserRole.")[1]
    if user_role not in ["ADMIN", "STAFF", "MANAGER", "OWNER"]:
         raise HTTPException(
             status_code=status.HTTP_403_FORBIDDEN,
             detail="Only salon staff and administrators can respond to reviews."
         )

    try:
        result = ReviewService.generate_response(
            db=db,
            review_id=payload.review_id,
            custom_response=payload.custom_response
        )
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to register response.")
            )
        return result
    except Exception as e:
        logger.error(f"Error responding to review: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post(
    "/escalate",
    status_code=status.HTTP_200_OK,
    summary="Flag and escalate a review to branch managers"
)
async def escalate_review(
    payload: EscalateReviewRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Escalates a review to branch managers. Authorized for Admin/Staff only.
    """
    logger.info(f"POST /reviews/escalate called by user {current_user.email}")
    user_role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if "UserRole." in user_role:
        user_role = user_role.split("UserRole.")[1]
    if user_role not in ["ADMIN", "STAFF", "MANAGER", "OWNER"]:
         raise HTTPException(
             status_code=status.HTTP_403_FORBIDDEN,
             detail="Only salon staff and administrators can escalate reviews."
         )

    try:
        result = ReviewService.escalate_review(db=db, review_id=payload.review_id)
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to escalate review.")
            )
        return result
    except Exception as e:
        logger.error(f"Error escalating review: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/analytics/stats",
    status_code=status.HTTP_200_OK,
    summary="Retrieve customer feedback and reputation analytics"
)
async def get_reputation_analytics(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Returns high-level reputation management stats including rating distribution,
    sentiment breakdown, top complaints, and praises.
    Authorized for Admin/Staff only.
    """
    logger.info(f"GET /reviews/analytics/stats called by user {current_user.email}")
    user_role = current_user.role.value if hasattr(current_user.role, "value") else str(current_user.role)
    if "UserRole." in user_role:
        user_role = user_role.split("UserRole.")[1]
    if user_role not in ["ADMIN", "STAFF", "MANAGER", "OWNER"]:
         raise HTTPException(
             status_code=status.HTTP_403_FORBIDDEN,
             detail="Only salon staff and administrators can view reputation analytics."
         )

    try:
        analytics = ReviewService.get_review_analytics(db=db)
        return {
            "success": True,
            "analytics": analytics
        }
    except Exception as e:
        logger.error(f"Error fetching reputation analytics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
