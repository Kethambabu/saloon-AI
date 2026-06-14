"""
Decoupled AutoGen tools for the Reputation Management Agent.
Wraps the SQLAlchemy database sessions safely.
"""

import logging
from typing import Optional

from db.database import SessionLocal
from services.review_service import ReviewService

logger = logging.getLogger(__name__)


def generate_response_tool(review_id: str, custom_response: Optional[str] = None) -> str:
    """
    Generate or register an official salon response to a specific customer review.

    Args:
        review_id: UUID string of the target review.
        custom_response: Optional custom text response. If omitted, generates response automatically.
    """
    logger.info(f"[ReviewTool] Responding to review: {review_id}")
    db = SessionLocal()
    try:
        result = ReviewService.generate_response(
            db=db,
            review_id=review_id,
            custom_response=custom_response
        )
        return str(result)
    except Exception as e:
        logger.error(f"Error in generate_response_tool: {e}")
        return f"Error responding to review: {str(e)}"
    finally:
        db.close()


def escalate_review_tool(review_id: str) -> str:
    """
    Escalate a review to the salon manager for review. Required for all critical reviews.

    Args:
        review_id: UUID string of the target review to escalate.
    """
    logger.info(f"[ReviewTool] Escalating review: {review_id}")
    db = SessionLocal()
    try:
        result = ReviewService.escalate_review(db=db, review_id=review_id)
        return str(result)
    except Exception as e:
        logger.error(f"Error in escalate_review_tool: {e}")
        return f"Error escalating review: {str(e)}"
    finally:
        db.close()
