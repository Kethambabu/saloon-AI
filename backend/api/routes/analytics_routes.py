"""
Analytics API Routes for SalonAI Workforce Dashboard.
Exposes BI tool aggregations as REST endpoints for the React frontend.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Query, HTTPException

from tools.bi_tools import (
    get_revenue_analytics,
    get_staff_performance_analytics,
    get_retention_analytics,
    get_service_popularity_analytics,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("/revenue", summary="Revenue Analytics")
async def revenue_analytics(
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    branch_id: Optional[str] = Query(None, description="Branch UUID filter"),
):
    """Returns revenue KPIs, service breakdown, and time-series chart data."""
    try:
        result = get_revenue_analytics(start_date, end_date, branch_id)
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Revenue analytics endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/staff", summary="Staff Performance Analytics")
async def staff_analytics(
    branch_id: Optional[str] = Query(None, description="Branch UUID filter"),
):
    """Returns staff performance metrics, revenue per stylist, and rating data."""
    try:
        result = get_staff_performance_analytics(branch_id)
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Staff analytics endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/retention", summary="Customer Retention Analytics")
async def retention_analytics():
    """Returns retention rates, LTV rankings, and customer distribution data."""
    try:
        result = get_retention_analytics()
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Retention analytics endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/services", summary="Service Popularity Analytics")
async def services_analytics():
    """Returns service popularity, booking counts, and revenue share data."""
    try:
        result = get_service_popularity_analytics()
        if not result.get("success"):
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Service analytics endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/overview", summary="Dashboard Overview")
async def dashboard_overview():
    """Aggregated overview combining all analytics for the main dashboard view."""
    try:
        revenue = get_revenue_analytics()
        staff = get_staff_performance_analytics()
        retention = get_retention_analytics()
        services = get_service_popularity_analytics()

        return {
            "success": True,
            "revenue": revenue if revenue.get("success") else None,
            "staff": staff if staff.get("success") else None,
            "retention": retention if retention.get("success") else None,
            "services": services if services.get("success") else None,
        }
    except Exception as e:
        logger.error(f"Dashboard overview endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
