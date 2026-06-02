"""
Analytics API Routes for SalonAI Workforce Dashboard.
Exposes BI summaries, forecasts, AI insights, and Business Metrics RAG summaries.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Query, HTTPException, Depends
from sqlalchemy.orm import Session

# Project imports
from db import get_db, UserRole
from api.deps import RoleChecker
from services.analytics_service import AnalyticsService
from services.insights_service import InsightsService
from services.forecast_service import ForecastService
from services.rag_service import RAGService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/analytics",
    tags=["Analytics"],
    dependencies=[Depends(RoleChecker([UserRole.ADMIN, UserRole.STAFF]))]
)


@router.get("/dashboard-summary", summary="Get Today's Business Performance Indicators")
async def get_dashboard_summary(db: Session = Depends(get_db)):
    """Returns today's revenue, active appointments, conversions, ratings, and upsell aggregates."""
    try:
        summary = AnalyticsService.get_dashboard_summary(db)
        return {"success": True, "summary": summary}
    except Exception as e:
        logger.error(f"Dashboard summary endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/revenue-summary", summary="Revenue Intelligence Breakdown")
async def get_revenue_summary(db: Session = Depends(get_db)):
    """Returns detailed revenue aggregates by service, branch, staff, and daily line charts."""
    try:
        revenue = AnalyticsService.get_revenue_summary(db)
        return {"success": True, "revenue": revenue}
    except Exception as e:
        logger.error(f"Revenue summary endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/customer-summary", summary="Customer Intelligence Metrics")
async def get_customer_summary(db: Session = Depends(get_db)):
    """Returns customer cohort metrics, vip active counts, and CLV aggregates."""
    try:
        customers = AnalyticsService.get_customer_summary(db)
        return {"success": True, "customers": customers}
    except Exception as e:
        logger.error(f"Customer summary endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/staff-summary", summary="Staff Intelligence Metrics")
async def get_staff_summary(db: Session = Depends(get_db)):
    """Returns benchmark rankings, completed styling volumes, and utilization scores."""
    try:
        staff_data = AnalyticsService.get_staff_summary(db)
        return {"success": True, "staff": staff_data}
    except Exception as e:
        logger.error(f"Staff summary endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/lead-summary", summary="Lead Intelligence Metrics")
async def get_lead_summary(db: Session = Depends(get_db)):
    """Returns CRM pipeline conversion and nurturing volumes."""
    try:
        leads = AnalyticsService.get_lead_summary(db)
        return {"success": True, "leads": leads}
    except Exception as e:
        logger.error(f"Lead summary endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/review-summary", summary="Reputation Intelligence Metrics")
async def get_review_summary(db: Session = Depends(get_db)):
    """Returns overall star reviews, sentiment counts, and main complaints indicators."""
    try:
        reviews = AnalyticsService.get_review_summary(db)
        return {"success": True, "reviews": reviews}
    except Exception as e:
        logger.error(f"Review summary endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/upsell-summary", summary="Upsell Intelligence Metrics")
async def get_upsell_summary(db: Session = Depends(get_db)):
    """Returns incremental bookings earnings, acceptances, and conversion rates."""
    try:
        upsells = AnalyticsService.get_upsell_summary(db)
        return {"success": True, "upsells": upsells}
    except Exception as e:
        logger.error(f"Upsell summary endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ai-insights", summary="Executive AI Business Insights")
async def get_ai_insights(db: Session = Depends(get_db)):
    """Returns dynamic natural language corporate suggestions based on live database trends."""
    try:
        insights = InsightsService.generate_ai_insights(db)
        return {"success": True, "insights": insights}
    except Exception as e:
        logger.error(f"AI insights endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/forecast-metrics", summary="Forecast Intelligence Estimates")
async def get_forecast_metrics(db: Session = Depends(get_db)):
    """Returns expected next month parameters for revenue, appointments, and conversions."""
    try:
        forecast = ForecastService.get_forecast_metrics(db)
        return {"success": True, "forecast": forecast}
    except Exception as e:
        logger.error(f"Forecast metrics endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/retrieve-rag-context", summary="Historical Business Metrics RAG Retrieve")
async def retrieve_rag_context(days: int = Query(90), db: Session = Depends(get_db)):
    """Retrieves business context logs from daily snapshots history for RAG matching."""
    try:
        context = RAGService.retrieve_business_context(db, days)
        return {"success": True, "context": context}
    except Exception as e:
        logger.error(f"Retrieve RAG context endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
