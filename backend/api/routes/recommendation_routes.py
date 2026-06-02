"""
FastAPI router for Automated Upsell and Recommendation endpoints.
Defines customer upsell queries, rules-based offers, and admin analytics.
"""

import logging
from typing import Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

# Project imports
from db import get_db
from api.deps import get_current_user
from services.recommendation_service import RecommendationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


# Pydantic Schemas
class RecommendationActionRequest(BaseModel):
    customer_id: str = Field(..., description="UUID string of the customer")
    service_id: str = Field(..., description="UUID string of the recommended service")
    appointment_id: Optional[str] = Field(None, description="Optional UUID string of the active appointment context")


@router.get(
    "/{customer_id}",
    status_code=status.HTTP_200_OK,
    summary="Get personalized service recommendations for a customer"
)
async def get_recommendations(
    customer_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Retrieves personalized service upsells based on active bookings,
    purchase history, and predefined automated rules.
    """
    logger.info(f"GET /recommendations/{customer_id} called by user {current_user.email}")
    try:
        # Validate UUID format
        UUID(customer_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid customer ID format. Must be a valid UUID."
        )
        
    try:
        recommendations = RecommendationService.get_customer_recommendations(db=db, customer_id=customer_id)
        return {
            "success": True,
            "customer_id": customer_id,
            "recommendations": recommendations
        }
    except Exception as e:
        logger.error(f"Failed to generate recommendations: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error generating recommendations: {str(e)}"
        )


@router.post(
    "/accept",
    status_code=status.HTTP_200_OK,
    summary="Accept an upsell recommendation"
)
async def accept_recommendation(
    payload: RecommendationActionRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Accepts a service recommendation, updates database analytics, and creates
    the linked add-on appointment automatically.
    """
    logger.info(f"POST /recommendations/accept called by user {current_user.email}")
    try:
        result = RecommendationService.accept_recommendation(
            db=db,
            customer_id=payload.customer_id,
            service_id=payload.service_id,
            appointment_id=payload.appointment_id
        )
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "Failed to accept recommendation")
            )
        return result
    except Exception as e:
        logger.error(f"Error accepting recommendation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post(
    "/reject",
    status_code=status.HTTP_200_OK,
    summary="Reject/dismiss an upsell recommendation"
)
async def reject_recommendation(
    payload: RecommendationActionRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Rejects or dismisses a service recommendation.
    """
    logger.info(f"POST /recommendations/reject called by user {current_user.email}")
    try:
        result = RecommendationService.reject_recommendation(
            db=db,
            customer_id=payload.customer_id,
            service_id=payload.service_id,
            appointment_id=payload.appointment_id
        )
        return result
    except Exception as e:
        logger.error(f"Error rejecting recommendation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/analytics/stats",
    status_code=status.HTTP_200_OK,
    summary="Get Automated Upsell performance analytics"
)
async def get_upsell_analytics(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Returns high-level upsell performance analytics including recommendations generated,
    recommendations accepted, total upsell revenue, and top add-on services.
    Authorized for Admin/Staff only.
    """
    logger.info(f"GET /recommendations/analytics/stats called by user {current_user.email}")
    if current_user.role.value not in ["ADMIN", "STAFF", "MANAGER", "OWNER"]:
         raise HTTPException(
             status_code=status.HTTP_403_FORBIDDEN,
             detail="Only salon staff and administrators can view upsell analytics."
         )
         
    try:
        analytics = RecommendationService.get_upsell_analytics(db=db)
        return {
            "success": True,
            "analytics": analytics
        }
    except Exception as e:
        logger.error(f"Error fetching upsell analytics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
