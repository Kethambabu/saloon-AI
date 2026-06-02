"""
Decoupled AutoGen tools for the Upsell & Recommendation Agent.
Wraps the SQLAlchemy database sessions safely.
"""

import logging
from typing import Optional

from db.database import SessionLocal
from services.recommendation_service import RecommendationService

logger = logging.getLogger(__name__)


def get_customer_recommendations_tool(customer_id: str) -> str:
    """
    Fetch personalized service recommendations for a customer.
    Checks active appointments, completed purchase history, and static rules.

    Args:
        customer_id: UUID string of the customer.
    """
    logger.info(f"[RecommendationTool] Fetching recommendations for customer: {customer_id}")
    db = SessionLocal()
    try:
        recs = RecommendationService.get_customer_recommendations(db=db, customer_id=customer_id)
        return str(recs)
    except Exception as e:
        logger.error(f"Error in get_customer_recommendations_tool: {e}")
        return f"Error fetching recommendations: {str(e)}"
    finally:
        db.close()


def accept_recommendation_tool(
    customer_id: str,
    service_id: str,
    appointment_id: Optional[str] = None
) -> str:
    """
    Accept an upsell recommendation, adding it as a confirmed booking add-on.

    Args:
        customer_id: UUID string of the customer.
        service_id: UUID string of the recommended service.
        appointment_id: Optional UUID string of the associated active appointment.
    """
    logger.info(f"[RecommendationTool] Accepting recommendation: customer={customer_id}, service={service_id}, appt={appointment_id}")
    db = SessionLocal()
    try:
        result = RecommendationService.accept_recommendation(
            db=db,
            customer_id=customer_id,
            service_id=service_id,
            appointment_id=appointment_id
        )
        return str(result)
    except Exception as e:
        logger.error(f"Error in accept_recommendation_tool: {e}")
        return f"Error accepting recommendation: {str(e)}"
    finally:
        db.close()


def reject_recommendation_tool(
    customer_id: str,
    service_id: str,
    appointment_id: Optional[str] = None
) -> str:
    """
    Dismiss or reject an upsell recommendation.

    Args:
        customer_id: UUID string of the customer.
        service_id: UUID string of the recommended service.
        appointment_id: Optional UUID string of the associated active appointment.
    """
    logger.info(f"[RecommendationTool] Rejecting recommendation: customer={customer_id}, service={service_id}, appt={appointment_id}")
    db = SessionLocal()
    try:
        result = RecommendationService.reject_recommendation(
            db=db,
            customer_id=customer_id,
            service_id=service_id,
            appointment_id=appointment_id
        )
        return str(result)
    except Exception as e:
        logger.error(f"Error in reject_recommendation_tool: {e}")
        return f"Error rejecting recommendation: {str(e)}"
    finally:
        db.close()


def get_upsell_analytics_tool() -> str:
    """
    Generate comprehensive upsell analytics including total generated,
    accepted counts, conversion rate, total revenue, and top add-ons.
    """
    logger.info("[RecommendationTool] Querying upsell analytics scorecard...")
    db = SessionLocal()
    try:
        analytics = RecommendationService.get_upsell_analytics(db=db)
        return str(analytics)
    except Exception as e:
        logger.error(f"Error in get_upsell_analytics_tool: {e}")
        return f"Error retrieving analytics: {str(e)}"
    finally:
        db.close()
