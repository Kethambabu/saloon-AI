"""
Review Workflows — Orchestrating review responses, critical reviews, and escalations.
Interacts directly with ReviewService.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ReviewWorkflow:
    """
    Consolidated review capability workflow calling ReviewService.
    """

    @staticmethod
    def get_reviews(
        customer_id: Optional[str] = None,
        staff_id: Optional[str] = None,
        sentiment: Optional[str] = None,
        rating: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Retrieve customer reviews matching filter criteria."""
        logger.info(
            "[ReviewWorkflow] get_reviews: customer=%s staff=%s sentiment=%s rating=%s",
            customer_id, staff_id, sentiment, rating
        )
        from infrastructure.db.database import SessionLocal
        from application.services.review_service import ReviewService
        db = SessionLocal()
        try:
            data = ReviewService.get_reviews(
                db=db,
                customer_id=customer_id,
                staff_id=staff_id,
                sentiment=sentiment,
                rating=rating,
            )
            return {"success": True, "data": data}
        except Exception as exc:
            logger.error("[ReviewWorkflow] get_reviews failed: %s", exc)
            return {"success": False, "error": str(exc)}
        finally:
            db.close()

    @staticmethod
    def get_analytics() -> Dict[str, Any]:
        """Generate comprehensive reputation analytics."""
        logger.info("[ReviewWorkflow] get_analytics")
        from infrastructure.db.database import SessionLocal
        from application.services.review_service import ReviewService
        db = SessionLocal()
        try:
            data = ReviewService.get_review_analytics(db)
            return {"success": True, "data": data}
        except Exception as exc:
            logger.error("[ReviewWorkflow] get_analytics failed: %s", exc)
            return {"success": False, "error": str(exc)}
        finally:
            db.close()

    @staticmethod
    def get_critical_reviews() -> Dict[str, Any]:
        """Retrieve all critical-sentiment reviews requiring urgent attention."""
        logger.info("[ReviewWorkflow] get_critical_reviews")
        from infrastructure.db.database import SessionLocal
        from application.services.review_service import ReviewService
        db = SessionLocal()
        try:
            data = ReviewService.get_reviews(db=db, sentiment="CRITICAL")
            return {"success": True, "data": data}
        except Exception as exc:
            logger.error("[ReviewWorkflow] get_critical_reviews failed: %s", exc)
            return {"success": False, "error": str(exc)}
        finally:
            db.close()

    @staticmethod
    def draft_response(
        review_id: str,
        custom_response: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Draft or register a salon response to a specific customer review."""
        logger.info("[ReviewWorkflow] draft_response: review=%s", review_id)
        from infrastructure.db.database import SessionLocal
        from application.services.review_service import ReviewService
        db = SessionLocal()
        try:
            data = ReviewService.generate_response(
                db=db,
                review_id=review_id,
                custom_response=custom_response,
            )
            return data
        except Exception as exc:
            logger.error("[ReviewWorkflow] draft_response failed: %s", exc)
            return {"success": False, "error": str(exc)}
        finally:
            db.close()

    @staticmethod
    def get_scorecard() -> Dict[str, Any]:
        """Generate the overall reputation metrics scorecard."""
        logger.info("[ReviewWorkflow] get_scorecard")
        from infrastructure.db.database import SessionLocal
        from application.services.review_service import ReviewService
        db = SessionLocal()
        try:
            data = ReviewService.get_review_analytics(db)
            return {
                "success": True,
                "data": {
                    "POSITIVE": data.get("positive_reviews", 0),
                    "NEUTRAL": data.get("neutral_reviews", 0),
                    "NEGATIVE": data.get("negative_reviews", 0),
                    "CRITICAL": data.get("critical_reviews", 0),
                }
            }
        except Exception as exc:
            logger.error("[ReviewWorkflow] get_scorecard failed: %s", exc)
            return {"success": False, "error": str(exc)}
        finally:
            db.close()

    @staticmethod
    def escalate_review(review_id: str) -> Dict[str, Any]:
        """Escalate a critical customer review to management."""
        logger.info("[ReviewWorkflow] escalate_review: review=%s", review_id)
        from infrastructure.db.database import SessionLocal
        from application.services.review_service import ReviewService
        db = SessionLocal()
        try:
            data = ReviewService.escalate_review(db=db, review_id=review_id)
            return data
        except Exception as exc:
            logger.error("[ReviewWorkflow] escalate_review failed: %s", exc)
            return {"success": False, "error": str(exc)}
        finally:
            db.close()


def respond_to_review_workflow(
    review_id: str,
    custom_response: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Workflow to draft and register a response to a review."""
    return ReviewWorkflow.draft_response(review_id=review_id, custom_response=custom_response)


def escalate_review_workflow(
    review_id: str,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Workflow to escalate a critical negative review."""
    return ReviewWorkflow.escalate_review(review_id=review_id)
