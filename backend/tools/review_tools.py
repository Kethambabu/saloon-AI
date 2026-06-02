"""
Decoupled AutoGen tools for the Reputation Management Agent.
Wraps the SQLAlchemy database sessions safely.
"""

import logging
from typing import Optional

from db.database import SessionLocal
from services.review_service import ReviewService

logger = logging.getLogger(__name__)


def get_reviews_tool(
    customer_id: Optional[str] = None,
    staff_id: Optional[str] = None,
    sentiment: Optional[str] = None,
    rating: Optional[int] = None,
) -> str:
    """
    Retrieve customer reviews based on filter parameters like customer_id, staff_id, sentiment, or rating.

    Args:
        customer_id: Optional UUID string of the customer.
        staff_id: Optional UUID string of the stylist/staff.
        sentiment: Optional sentiment string ("POSITIVE", "NEUTRAL", "NEGATIVE", "CRITICAL").
        rating: Optional integer rating from 1 to 5.
    """
    logger.info(f"[ReviewTool] Querying reviews: customer={customer_id}, staff={staff_id}, sentiment={sentiment}")
    db = SessionLocal()
    try:
        reviews = ReviewService.get_reviews(
            db=db,
            customer_id=customer_id,
            staff_id=staff_id,
            sentiment=sentiment,
            rating=rating
        )
        return str(reviews)
    except Exception as e:
        logger.error(f"Error in get_reviews_tool: {e}")
        return f"Error querying reviews: {str(e)}"
    finally:
        db.close()


def analyze_sentiment_tool(text: str, rating: int) -> str:
    """
    Analyze customer review text and rating to evaluate sentiment ("POSITIVE", "NEUTRAL", "NEGATIVE", "CRITICAL").

    Args:
        text: The feedback comment written by the customer.
        rating: The integer rating between 1 and 5 stars.
    """
    logger.info(f"[ReviewTool] Analyzing sentiment for rating={rating}")
    try:
        sentiment = ReviewService.analyze_sentiment_rules(text, rating)
        return sentiment
    except Exception as e:
        logger.error(f"Error in analyze_sentiment_tool: {e}")
        return f"Error analyzing sentiment: {str(e)}"


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


def get_review_analytics_tool() -> str:
    """
    Generate comprehensive reputation management stats including rating distribution, top complaints, and praises.
    """
    logger.info("[ReviewTool] Aggregating reputation analytics scorecard...")
    db = SessionLocal()
    try:
        analytics = ReviewService.get_review_analytics(db=db)
        return str(analytics)
    except Exception as e:
        logger.error(f"Error in get_review_analytics_tool: {e}")
        return f"Error retrieving review analytics: {str(e)}"
    finally:
        db.close()
