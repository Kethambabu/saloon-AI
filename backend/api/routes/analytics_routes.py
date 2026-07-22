"""
Analytics API Routes for SalonAI Workforce Dashboard.
Exposes BI summaries, forecasts, AI insights, and Business Metrics RAG summaries.
[Hot Reload: Database seeded]
"""

import logging
from typing import Optional
from fastapi import APIRouter, Query, HTTPException, Depends
from sqlalchemy.orm import Session

# Project imports
from infrastructure.db import get_db, UserRole
from api.deps import RoleChecker
from application.services.analytics_service import AnalyticsService
from application.services.insights_service import InsightsService
from application.services.forecast_service import ForecastService
from application.services.rag_service import RAGService

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/analytics",
    tags=["Analytics"],
    dependencies=[Depends(RoleChecker([UserRole.ADMIN, UserRole.STAFF]))]
)


# These two endpoints back the frontend's dashboard auto-poll (every
# POLL_INTERVAL_MS = 30s, see frontend/src/hooks/useAnalytics.ts). Without
# caching, every connected admin/staff tab recomputes these expensive,
# business-wide aggregates from scratch every 30s, competing for DB/CPU with
# concurrent BI-agent chat traffic. Reuse the same "analytics" ResultCache the
# BI agent's tool-dispatch path already uses (infrastructure/cache/token_optimizer.py)
# so both paths can share one computed result, with a TTL matched to the poll cadence.
_REST_ANALYTICS_CACHE_TTL_SECONDS = 30


@router.get("/dashboard-summary", summary="Get Today's Business Performance Indicators")
async def get_dashboard_summary(
    period: str = Query("today", description="Time period filter: today, weekly, monthly, yearly"),
    db: Session = Depends(get_db)
):
    """Returns today's or period's revenue, active appointments, conversions, ratings, and upsell aggregates."""
    try:
        from infrastructure.cache.token_optimizer import get_cache
        cache = get_cache("analytics")
        cache_key = ("rest_dashboard_summary", period)
        summary = cache.get(*cache_key)
        if summary is None:
            summary = AnalyticsService.get_dashboard_summary(db, period=period)
            cache.set(summary, *cache_key, ttl=_REST_ANALYTICS_CACHE_TTL_SECONDS)
        return {"success": True, "summary": summary}
    except Exception as e:
        logger.error(f"Dashboard summary endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/revenue-summary", summary="Revenue Intelligence Breakdown")
async def get_revenue_summary(db: Session = Depends(get_db)):
    """Returns detailed revenue aggregates by service, branch, staff, and daily line charts."""
    try:
        from infrastructure.cache.token_optimizer import get_cache
        cache = get_cache("analytics")
        cache_key = ("rest_revenue_summary",)
        revenue = cache.get(*cache_key)
        if revenue is None:
            revenue = AnalyticsService.get_revenue_summary(db)
            cache.set(revenue, *cache_key, ttl=_REST_ANALYTICS_CACHE_TTL_SECONDS)
        return {"success": True, "revenue": revenue}
    except Exception as e:
        logger.error(f"Revenue summary endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/revenue",
    summary="Revenue Intelligence Breakdown (Admin Only)",
    dependencies=[Depends(RoleChecker([UserRole.ADMIN]))]
)
async def get_revenue(
    db: Session = Depends(get_db),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    branch_id: Optional[str] = Query(None),
):
    """Returns detailed revenue aggregates. Restricted to Admin/Owner."""
    try:
        from infrastructure.cache.token_optimizer import get_cache
        cache = get_cache("analytics")
        cache_key = ("rest_revenue", start_date, end_date, branch_id)
        result = cache.get(*cache_key)
        if result is None:
            revenue = AnalyticsService.get_revenue_summary(db)
            cards = revenue.get("cards", {})
            charts = revenue.get("charts", {})
            result = {
                "success": True,
                "metrics": {
                    "total_revenue": cards.get("yearly_revenue", 0.0),
                    "total_bookings": 0,
                    "average_ticket": 0.0,
                },
                "revenue_by_service": charts.get("by_service", {}),
                "revenue_by_branch": charts.get("by_branch", {}),
                "charts": {
                    "revenue_over_time": {
                        "labels": charts.get("labels", []),
                        "datasets": [{"label": "Revenue ($)", "data": charts.get("revenue_over_time", [])}],
                    }
                },
            }
            cache.set(result, *cache_key, ttl=_REST_ANALYTICS_CACHE_TTL_SECONDS)
        return result
    except Exception as e:
        logger.error(f"Revenue endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/customer-summary", summary="Customer Intelligence Metrics")
async def get_customer_summary(db: Session = Depends(get_db)):
    """Returns customer cohort metrics, vip active counts, and CLV aggregates."""
    try:
        from infrastructure.cache.token_optimizer import get_cache
        cache = get_cache("analytics")
        cache_key = ("rest_customer_summary",)
        customers = cache.get(*cache_key)
        if customers is None:
            customers = AnalyticsService.get_customer_summary(db)
            cache.set(customers, *cache_key, ttl=_REST_ANALYTICS_CACHE_TTL_SECONDS)
        return {"success": True, "customers": customers}
    except Exception as e:
        logger.error(f"Customer summary endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/retention", summary="Customer Retention Analytics")
async def get_retention(db: Session = Depends(get_db)):
    """
    Returns customer retention metrics, cohort analysis, and LTV data.
    Frontend-facing alias for customer-summary with retention-focused formatting.
    """
    try:
        from infrastructure.cache.token_optimizer import get_cache
        cache = get_cache("analytics")
        cache_key = ("rest_retention",)
        result = cache.get(*cache_key)
        if result is None:
            customers = AnalyticsService.get_customer_summary(db)
            total = customers.get("total_customers", 0)
            returning = customers.get("returning_customers", 0)
            one_time = max(0, total - returning)
            loyal_3plus = customers.get("vip_customers", 0)
            retention_rate = round((returning / total * 100.0), 1) if total > 0 else 0.0

            result = {
                "success": True,
                "retention_metrics": {
                    "total_registered_customers": total,
                    "total_transacting_customers": returning + one_time,
                    "one_time_visitors": one_time,
                    "repeat_visitors": returning,
                    "loyal_visitors_3plus": loyal_3plus,
                    "retention_rate_pct": retention_rate,
                },
                "top_customers_by_ltv": [],
                "charts": {
                    "retention_distribution": {
                        "labels": ["One-Time Visitors", "Repeat Customers (2+)"],
                        "datasets": [{"label": "Customer Count", "data": [one_time, returning]}],
                    }
                },
            }
            cache.set(result, *cache_key, ttl=_REST_ANALYTICS_CACHE_TTL_SECONDS)
        return result
    except Exception as e:
        logger.error(f"Retention endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/staff-summary", summary="Staff Intelligence Metrics")
async def get_staff_summary(db: Session = Depends(get_db)):
    """Returns benchmark rankings, completed styling volumes, and utilization scores."""
    try:
        from infrastructure.cache.token_optimizer import get_cache
        cache = get_cache("analytics")
        cache_key = ("rest_staff_summary",)
        staff_data = cache.get(*cache_key)
        if staff_data is None:
            staff_data = AnalyticsService.get_staff_summary(db)
            cache.set(staff_data, *cache_key, ttl=_REST_ANALYTICS_CACHE_TTL_SECONDS)
        return {"success": True, "staff": staff_data}
    except Exception as e:
        logger.error(f"Staff summary endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/staff", summary="Staff Analytics (Frontend-Facing)")
async def get_staff_analytics(
    db: Session = Depends(get_db),
    branch_id: Optional[str] = Query(None),
):
    """Staff analytics formatted for the frontend dashboard."""
    try:
        from infrastructure.cache.token_optimizer import get_cache
        cache = get_cache("analytics")
        cache_key = ("rest_staff_analytics", branch_id)
        result = cache.get(*cache_key)
        if result is None:
            staff_data = AnalyticsService.get_staff_summary(db)
            roster = staff_data.get("roster", [])
            staff_metrics = [
                {
                    "staff_id": s.get("id", ""),
                    "name": s.get("name", ""),
                    "role": s.get("role", ""),
                    "completed_bookings": s.get("appointments", 0),
                    "revenue_generated": s.get("revenue", 0.0),
                    "utilization_rate_pct": 0.0,
                    "average_rating": s.get("rating", 0.0),
                }
                for s in roster
            ]
            result = {
                "success": True,
                "staff_metrics": staff_metrics,
                "charts": {
                    "staff_revenue": {
                        "labels": [s["name"] for s in staff_metrics],
                        "datasets": [{"label": "Revenue Generated ($)", "data": [s["revenue_generated"] for s in staff_metrics]}],
                    },
                    "staff_ratings": {
                        "labels": [s["name"] for s in staff_metrics],
                        "datasets": [{"label": "Average Rating", "data": [s["average_rating"] for s in staff_metrics]}],
                    },
                },
            }
            cache.set(result, *cache_key, ttl=_REST_ANALYTICS_CACHE_TTL_SECONDS)
        return result
    except Exception as e:
        logger.error(f"Staff analytics endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/services", summary="Service-Level Analytics")
async def get_service_analytics(db: Session = Depends(get_db)):
    """Returns per-service bookings, revenue, and trend data."""
    try:
        from infrastructure.cache.token_optimizer import get_cache
        cache = get_cache("analytics")
        cache_key = ("rest_service_analytics",)
        result = cache.get(*cache_key)
        if result is None:
            from infrastructure.db import Appointment, Service, AppointmentStatus
            from sqlalchemy import func

            service_query = (
                db.query(Service.name, func.count(Appointment.id).label("bookings"), func.sum(Service.price).label("revenue"))
                .join(Appointment, Service.id == Appointment.service_id)
                .filter(Appointment.status == AppointmentStatus.COMPLETED)
                .group_by(Service.id)
                .all()
            )

            services = [
                {
                    "service_name": row.name,
                    "total_bookings": row.bookings,
                    "total_revenue": float(row.revenue or 0),
                }
                for row in service_query
            ]

            result = {
                "success": True,
                "services": services,
                "charts": {
                    "service_bookings": {
                        "labels": [s["service_name"] for s in services],
                        "datasets": [{"label": "Bookings Count", "data": [s["total_bookings"] for s in services]}],
                    },
                    "service_revenue_share": {
                        "labels": [s["service_name"] for s in services],
                        "datasets": [{"label": "Revenue Share ($)", "data": [s["total_revenue"] for s in services]}],
                    },
                },
            }
            cache.set(result, *cache_key, ttl=_REST_ANALYTICS_CACHE_TTL_SECONDS)
        return result
    except Exception as e:
        logger.error(f"Service analytics endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/overview", summary="Complete Analytics Overview (All Summaries)")
async def get_overview(db: Session = Depends(get_db)):
    """
    Aggregates ALL analytics summaries into a single payload.
    Frontend-facing endpoint used by the analytics dashboard overview page.
    """
    try:
        from infrastructure.cache.token_optimizer import get_cache
        cache = get_cache("analytics")
        cache_key = ("rest_overview",)
        result = cache.get(*cache_key)
        if result is None:
            revenue_data = AnalyticsService.get_revenue_summary(db)
            staff_data = AnalyticsService.get_staff_summary(db)
            customer_data = AnalyticsService.get_customer_summary(db)

            # Build retention summary
            total = customer_data.get("total_customers", 0)
            returning = customer_data.get("returning_customers", 0)
            one_time = max(0, total - returning)
            loyal_3plus = customer_data.get("vip_customers", 0)
            retention_rate = round((returning / total * 100.0), 1) if total > 0 else 0.0

            # Build staff metrics
            roster = staff_data.get("roster", [])
            staff_metrics = [
                {
                    "staff_id": s.get("id", ""),
                    "name": s.get("name", ""),
                    "role": s.get("role", ""),
                    "completed_bookings": s.get("appointments", 0),
                    "revenue_generated": s.get("revenue", 0.0),
                    "utilization_rate_pct": 0.0,
                    "average_rating": s.get("rating", 0.0),
                }
                for s in roster
            ]

            # Build revenue section
            cards = revenue_data.get("cards", {})
            charts = revenue_data.get("charts", {})

            result = {
                "success": True,
                "revenue": {
                    "success": True,
                    "metrics": {
                        "total_revenue": cards.get("yearly_revenue", 0.0),
                        "total_bookings": 0,
                        "average_ticket": 0.0,
                    },
                    "revenue_by_service": charts.get("by_service", {}),
                    "revenue_by_branch": charts.get("by_branch", {}),
                    "charts": {
                        "revenue_over_time": {
                            "labels": charts.get("labels", []),
                            "datasets": [{"label": "Revenue ($)", "data": charts.get("revenue_over_time", [])}],
                        }
                    },
                },
                "staff": {
                    "success": True,
                    "staff_metrics": staff_metrics,
                    "charts": {
                        "staff_revenue": {
                            "labels": [s["name"] for s in staff_metrics],
                            "datasets": [{"label": "Revenue Generated ($)", "data": [s["revenue_generated"] for s in staff_metrics]}],
                        },
                        "staff_ratings": {
                            "labels": [s["name"] for s in staff_metrics],
                            "datasets": [{"label": "Average Rating", "data": [s["average_rating"] for s in staff_metrics]}],
                        },
                    },
                },
                "retention": {
                    "success": True,
                    "retention_metrics": {
                        "total_registered_customers": total,
                        "total_transacting_customers": returning + one_time,
                        "one_time_visitors": one_time,
                        "repeat_visitors": returning,
                        "loyal_visitors_3plus": loyal_3plus,
                        "retention_rate_pct": retention_rate,
                    },
                    "top_customers_by_ltv": [],
                    "charts": {
                        "retention_distribution": {
                            "labels": ["One-Time Visitors", "Repeat Customers (2+)"],
                            "datasets": [{"label": "Customer Count", "data": [one_time, returning]}],
                        }
                    },
                },
                "services": {"success": True, "services": []},
            }
            cache.set(result, *cache_key, ttl=_REST_ANALYTICS_CACHE_TTL_SECONDS)
        return result
    except Exception as e:
        logger.error(f"Overview endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/lead-summary", summary="Lead Intelligence Metrics")
async def get_lead_summary(db: Session = Depends(get_db)):
    """Returns CRM pipeline conversion and nurturing volumes."""
    try:
        from infrastructure.cache.token_optimizer import get_cache
        cache = get_cache("analytics")
        cache_key = ("rest_lead_summary",)
        leads = cache.get(*cache_key)
        if leads is None:
            leads = AnalyticsService.get_lead_summary(db)
            cache.set(leads, *cache_key, ttl=_REST_ANALYTICS_CACHE_TTL_SECONDS)
        return {"success": True, "leads": leads}
    except Exception as e:
        logger.error(f"Lead summary endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/review-summary", summary="Reputation Intelligence Metrics")
async def get_review_summary(db: Session = Depends(get_db)):
    """Returns overall star reviews, sentiment counts, and main complaints indicators."""
    try:
        from infrastructure.cache.token_optimizer import get_cache
        cache = get_cache("analytics")
        cache_key = ("rest_review_summary",)
        reviews = cache.get(*cache_key)
        if reviews is None:
            reviews = AnalyticsService.get_review_summary(db)
            cache.set(reviews, *cache_key, ttl=_REST_ANALYTICS_CACHE_TTL_SECONDS)
        return {"success": True, "reviews": reviews}
    except Exception as e:
        logger.error(f"Review summary endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/upsell-summary", summary="Upsell Intelligence Metrics")
async def get_upsell_summary(db: Session = Depends(get_db)):
    """Returns incremental bookings earnings, acceptances, and conversion rates."""
    try:
        from infrastructure.cache.token_optimizer import get_cache
        cache = get_cache("analytics")
        cache_key = ("rest_upsell_summary",)
        upsells = cache.get(*cache_key)
        if upsells is None:
            upsells = AnalyticsService.get_upsell_summary(db)
            cache.set(upsells, *cache_key, ttl=_REST_ANALYTICS_CACHE_TTL_SECONDS)
        return {"success": True, "upsells": upsells}
    except Exception as e:
        logger.error(f"Upsell summary endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ai-insights", summary="Executive AI Business Insights")
async def get_ai_insights(db: Session = Depends(get_db)):
    """Returns dynamic natural language corporate suggestions based on live database trends."""
    try:
        from infrastructure.cache.token_optimizer import get_cache
        cache = get_cache("analytics")
        cache_key = ("rest_ai_insights",)
        insights = cache.get(*cache_key)
        if insights is None:
            insights = InsightsService.generate_ai_insights(db)
            cache.set(insights, *cache_key, ttl=_REST_ANALYTICS_CACHE_TTL_SECONDS)
        return {"success": True, "insights": insights}
    except Exception as e:
        logger.error(f"AI insights endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/forecast-metrics", summary="Forecast Intelligence Estimates")
async def get_forecast_metrics(db: Session = Depends(get_db)):
    """Returns expected next month parameters for revenue, appointments, and conversions."""
    try:
        from infrastructure.cache.token_optimizer import get_cache
        cache = get_cache("analytics")
        cache_key = ("rest_forecast_metrics",)
        forecast = cache.get(*cache_key)
        if forecast is None:
            forecast = ForecastService.get_forecast_metrics(db)
            cache.set(forecast, *cache_key, ttl=_REST_ANALYTICS_CACHE_TTL_SECONDS)
        return {"success": True, "forecast": forecast}
    except Exception as e:
        logger.error(f"Forecast metrics endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/retrieve-rag-context", summary="Historical Business Metrics RAG Retrieve")
async def retrieve_rag_context(days: int = Query(90), db: Session = Depends(get_db)):
    """Retrieves business context logs from daily snapshots history for RAG matching."""
    try:
        from infrastructure.cache.token_optimizer import get_cache
        cache = get_cache("analytics")
        cache_key = ("rest_retrieve_rag_context", days)
        context = cache.get(*cache_key)
        if context is None:
            context = RAGService.retrieve_business_context(db, days)
            cache.set(context, *cache_key, ttl=_REST_ANALYTICS_CACHE_TTL_SECONDS)
        return {"success": True, "context": context}
    except Exception as e:
        logger.error(f"Retrieve RAG context endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

