"""
Reputation & Review Management Tools for SalonAI Workforce Platform.

Provides database-backed functions for:
- Fetching and aggregating customer reviews with star-distribution breakdowns
- Sentiment classification and trend analysis
- Professional review response generation with tone control
- Critical / negative review detection and escalation workflows

All tools follow the same SessionLocal pattern used by bi_tools and lead_tools,
ensuring compatibility with the existing test fixtures and dependency injection.
"""

import logging
import json
import uuid as _uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple

from sqlalchemy import func, case, desc
from sqlalchemy.orm import Session

from db.database import SessionLocal
from db.models import Review, ReviewStatus, Customer, Branch, Appointment, Staff, Service

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Sentiment Helpers
# ---------------------------------------------------------------------------
# Lightweight keyword-based sentiment classifier.  A production deployment
# would swap this for an NLP model (e.g., VADER, TextBlob, or an LLM call),
# but the keyword approach keeps the tool offline-testable and free of
# external API dependencies.

_POSITIVE_KEYWORDS: List[str] = [
    "great", "excellent", "amazing", "wonderful", "fantastic", "love",
    "perfect", "best", "beautiful", "friendly", "clean", "professional",
    "outstanding", "happy", "highly recommend", "top notch", "superb",
    "impressed", "delighted", "awesome", "satisfied",
]
_NEGATIVE_KEYWORDS: List[str] = [
    "bad", "terrible", "horrible", "worst", "rude", "dirty", "slow",
    "disappointing", "never again", "awful", "poor", "unprofessional",
    "overcharged", "nightmare", "waste", "regret", "unacceptable",
    "incompetent", "damaged", "ruined",
]


def _classify_sentiment(text: Optional[str], rating: int) -> str:
    """
    Classify a review's sentiment as positive, neutral, or negative.

    Uses a two-signal approach:
        1. Star rating threshold (≤2 negative, ≥4 positive).
        2. Keyword hits in the comment text to override borderline ratings.
    """
    if text:
        text_lower = text.lower()
        pos_hits = sum(1 for kw in _POSITIVE_KEYWORDS if kw in text_lower)
        neg_hits = sum(1 for kw in _NEGATIVE_KEYWORDS if kw in text_lower)

        # Strong keyword signal overrides borderline ratings (3-star)
        if neg_hits > pos_hits and neg_hits >= 2:
            return "negative"
        if pos_hits > neg_hits and pos_hits >= 2:
            return "positive"

    # Fall back to rating-based classification
    if rating <= 2:
        return "negative"
    if rating >= 4:
        return "positive"
    return "neutral"


def _extract_themes(text: Optional[str]) -> List[str]:
    """
    Extract recurring feedback themes from a review comment.
    Returns a list of matched theme labels.
    """
    if not text:
        return []

    text_lower = text.lower()
    themes: List[str] = []
    theme_keywords = {
        "staff friendliness": ["friendly", "nice staff", "welcoming", "warm", "kind"],
        "cleanliness": ["clean", "hygienic", "spotless", "tidy", "sanitize"],
        "wait times": ["wait", "waited", "late", "delay", "slow"],
        "pricing": ["price", "expensive", "overcharged", "cost", "value", "affordable"],
        "service quality": ["great results", "amazing job", "loved it", "perfect", "excellent work"],
        "atmosphere": ["ambiance", "atmosphere", "relaxing", "vibe", "music", "decor"],
        "booking experience": ["booking", "appointment", "schedule", "easy to book"],
        "parking": ["parking", "park"],
        "communication": ["communication", "rude", "unprofessional", "ignored", "responsive"],
    }

    for theme, keywords in theme_keywords.items():
        if any(kw in text_lower for kw in keywords):
            themes.append(theme)

    return themes


# ---------------------------------------------------------------------------
# Database-Backed Tools
# ---------------------------------------------------------------------------

def fetch_reviews(
    branch_id: Optional[str] = None,
    status: Optional[str] = None,
    min_rating: Optional[int] = None,
    max_rating: Optional[int] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    """
    Fetch customer reviews from the database with optional filtering.

    Args:
        branch_id: Optional UUID string to filter reviews by branch.
        status: Optional review status filter ('PENDING', 'APPROVED', 'REJECTED').
        min_rating: Optional minimum star rating (1-5).
        max_rating: Optional maximum star rating (1-5).
        limit: Maximum number of reviews to return (default 50).

    Returns:
        Dictionary with review list, pagination info, and success flag.
    """
    logger.info(
        f"[ReputationTools] fetch_reviews(branch={branch_id}, status={status}, "
        f"min={min_rating}, max={max_rating}, limit={limit})"
    )

    db: Session = SessionLocal()
    try:
        query = (
            db.query(
                Review.id,
                Review.rating,
                Review.comment,
                Review.status,
                Review.created_at,
                Customer.first_name,
                Customer.last_name,
                Branch.name.label("branch_name"),
            )
            .join(Customer, Review.customer_id == Customer.id)
            .join(Branch, Review.branch_id == Branch.id)
        )

        if branch_id:
            query = query.filter(Review.branch_id == branch_id)
        if status:
            try:
                review_status = ReviewStatus(status.upper())
                query = query.filter(Review.status == review_status)
            except ValueError:
                return {"success": False, "error": f"Invalid status: {status}"}
        if min_rating is not None:
            query = query.filter(Review.rating >= min_rating)
        if max_rating is not None:
            query = query.filter(Review.rating <= max_rating)

        query = query.order_by(desc(Review.created_at)).limit(limit)
        rows = query.all()

        reviews = []
        for row in rows:
            comment = row.comment or ""
            reviews.append({
                "id": str(row.id),
                "rating": row.rating,
                "comment": comment,
                "status": row.status.value if hasattr(row.status, "value") else str(row.status),
                "customer_name": f"{row.first_name} {row.last_name}",
                "branch_name": row.branch_name,
                "sentiment": _classify_sentiment(comment, row.rating),
                "themes": _extract_themes(comment),
                "created_at": row.created_at.isoformat() if row.created_at else None,
            })

        return {
            "success": True,
            "total_returned": len(reviews),
            "reviews": reviews,
        }

    except Exception as e:
        logger.error(f"[ReputationTools] fetch_reviews error: {e}", exc_info=True)
        return {"success": False, "error": f"Failed to fetch reviews: {str(e)}"}
    finally:
        db.close()


def get_review_analytics(
    branch_id: Optional[str] = None,
    days: int = 30,
) -> Dict[str, Any]:
    """
    Generate aggregated review analytics including star distribution,
    sentiment breakdown, average rating trends, and top themes.

    Args:
        branch_id: Optional UUID string to scope analytics to a single branch.
        days: Look-back window in days (default 30).

    Returns:
        Dictionary with metrics, charts, and theme analysis.
    """
    logger.info(f"[ReputationTools] get_review_analytics(branch={branch_id}, days={days})")

    db: Session = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        base_query = db.query(Review).filter(Review.created_at >= cutoff)

        if branch_id:
            base_query = base_query.filter(Review.branch_id == branch_id)

        all_reviews = base_query.all()
        total = len(all_reviews)

        if total == 0:
            return {
                "success": True,
                "period_days": days,
                "metrics": {
                    "total_reviews": 0,
                    "average_rating": 0.0,
                    "star_distribution": {str(i): 0 for i in range(1, 6)},
                    "sentiment_breakdown": {"positive": 0, "neutral": 0, "negative": 0},
                },
                "themes": [],
                "charts": {"rating_over_time": []},
            }

        # Star distribution
        star_dist = {str(i): 0 for i in range(1, 6)}
        sentiment_counts = {"positive": 0, "neutral": 0, "negative": 0}
        total_rating = 0
        theme_counter: Dict[str, int] = {}

        for rev in all_reviews:
            star_dist[str(rev.rating)] = star_dist.get(str(rev.rating), 0) + 1
            total_rating += rev.rating

            sentiment = _classify_sentiment(rev.comment, rev.rating)
            sentiment_counts[sentiment] += 1

            for theme in _extract_themes(rev.comment):
                theme_counter[theme] = theme_counter.get(theme, 0) + 1

        avg_rating = round(total_rating / total, 2) if total else 0.0

        # Sentiment percentages
        sentiment_pct = {
            k: round((v / total) * 100, 1) for k, v in sentiment_counts.items()
        }

        # Top themes sorted by frequency
        top_themes = sorted(theme_counter.items(), key=lambda x: x[1], reverse=True)[:10]

        # Daily average rating chart data
        daily_query = (
            db.query(
                func.date(Review.created_at).label("day"),
                func.avg(Review.rating).label("avg_rating"),
                func.count(Review.id).label("count"),
            )
            .filter(Review.created_at >= cutoff)
        )
        if branch_id:
            daily_query = daily_query.filter(Review.branch_id == branch_id)

        daily_rows = daily_query.group_by(func.date(Review.created_at)).order_by("day").all()

        rating_over_time = [
            {
                "date": str(row.day),
                "average_rating": round(float(row.avg_rating), 2),
                "review_count": row.count,
            }
            for row in daily_rows
        ]

        return {
            "success": True,
            "period_days": days,
            "metrics": {
                "total_reviews": total,
                "average_rating": avg_rating,
                "star_distribution": star_dist,
                "sentiment_breakdown": sentiment_counts,
                "sentiment_percentages": sentiment_pct,
            },
            "themes": [{"theme": t, "mentions": c} for t, c in top_themes],
            "charts": {"rating_over_time": rating_over_time},
        }

    except Exception as e:
        logger.error(f"[ReputationTools] get_review_analytics error: {e}", exc_info=True)
        return {"success": False, "error": f"Failed to generate review analytics: {str(e)}"}
    finally:
        db.close()


def detect_critical_reviews(
    rating_threshold: int = 2,
    branch_id: Optional[str] = None,
    days: int = 7,
) -> Dict[str, Any]:
    """
    Detect critical (negative) reviews that require immediate attention.
    Returns reviews at or below the rating threshold within the look-back window.

    Args:
        rating_threshold: Maximum star rating to flag as critical (default 2).
        branch_id: Optional UUID string to scope detection to a branch.
        days: Look-back window in days (default 7).

    Returns:
        Dictionary with flagged critical reviews and escalation metadata.
    """
    logger.info(
        f"[ReputationTools] detect_critical_reviews(threshold={rating_threshold}, "
        f"branch={branch_id}, days={days})"
    )

    db: Session = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        query = (
            db.query(
                Review.id,
                Review.rating,
                Review.comment,
                Review.status,
                Review.created_at,
                Customer.first_name,
                Customer.last_name,
                Customer.email.label("customer_email"),
                Customer.phone.label("customer_phone"),
                Branch.name.label("branch_name"),
            )
            .join(Customer, Review.customer_id == Customer.id)
            .join(Branch, Review.branch_id == Branch.id)
            .filter(Review.rating <= rating_threshold)
            .filter(Review.created_at >= cutoff)
        )

        if branch_id:
            query = query.filter(Review.branch_id == branch_id)

        query = query.order_by(Review.rating.asc(), desc(Review.created_at))
        rows = query.all()

        critical_reviews = []
        for row in rows:
            comment = row.comment or ""
            severity = "critical" if row.rating == 1 else "high"
            critical_reviews.append({
                "id": str(row.id),
                "rating": row.rating,
                "comment": comment,
                "status": row.status.value if hasattr(row.status, "value") else str(row.status),
                "customer_name": f"{row.first_name} {row.last_name}",
                "customer_email": row.customer_email,
                "customer_phone": row.customer_phone,
                "branch_name": row.branch_name,
                "severity": severity,
                "sentiment": _classify_sentiment(comment, row.rating),
                "themes": _extract_themes(comment),
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "requires_escalation": row.rating == 1,
            })

        return {
            "success": True,
            "period_days": days,
            "rating_threshold": rating_threshold,
            "total_critical": len(critical_reviews),
            "escalation_required": sum(1 for r in critical_reviews if r["requires_escalation"]),
            "critical_reviews": critical_reviews,
        }

    except Exception as e:
        logger.error(f"[ReputationTools] detect_critical_reviews error: {e}", exc_info=True)
        return {"success": False, "error": f"Failed to detect critical reviews: {str(e)}"}
    finally:
        db.close()


def generate_review_response(
    review_id: str,
    tone: str = "professional",
) -> Dict[str, Any]:
    """
    Generate a brand-safe, professional response to a specific customer review.
    Tone adapts based on the review's sentiment and the selected tone profile.

    Args:
        review_id: UUID string of the review to respond to.
        tone: Response tone profile — 'professional', 'empathetic', 'warm', or 'formal'.

    Returns:
        Dictionary with the generated draft response and tone metadata.
    """
    logger.info(f"[ReputationTools] generate_review_response(review={review_id}, tone={tone})")

    valid_tones = {"professional", "empathetic", "warm", "formal"}
    if tone not in valid_tones:
        return {"success": False, "error": f"Invalid tone '{tone}'. Choose from: {', '.join(valid_tones)}"}

    db: Session = SessionLocal()
    try:
        # Convert string UUID to proper UUID object for SQLAlchemy Uuid column
        try:
            review_uuid = _uuid.UUID(review_id)
        except (ValueError, AttributeError):
            return {"success": False, "error": f"Review with ID '{review_id}' not found."}

        review = (
            db.query(
                Review.id,
                Review.rating,
                Review.comment,
                Review.status,
                Customer.first_name,
                Customer.last_name,
                Branch.name.label("branch_name"),
            )
            .join(Customer, Review.customer_id == Customer.id)
            .join(Branch, Review.branch_id == Branch.id)
            .filter(Review.id == review_uuid)
            .first()
        )

        if not review:
            return {"success": False, "error": f"Review with ID '{review_id}' not found."}

        customer_name = f"{review.first_name} {review.last_name}"
        comment = review.comment or ""
        rating = review.rating
        sentiment = _classify_sentiment(comment, rating)
        themes = _extract_themes(comment)

        # Build response based on tone + sentiment
        greeting = f"Dear {review.first_name}"
        branch_name = review.branch_name

        if sentiment == "negative":
            if tone == "empathetic":
                body = (
                    f"We are truly sorry to hear about your experience at {branch_name}. "
                    f"Your feedback is incredibly important to us, and we take your concerns very seriously. "
                    f"We would love the opportunity to make things right — please reach out to us directly "
                    f"so we can address your concerns personally."
                )
            elif tone == "formal":
                body = (
                    f"Thank you for bringing this matter to our attention regarding your visit to {branch_name}. "
                    f"We sincerely apologize for any inconvenience you experienced. "
                    f"Our management team will review this feedback immediately. "
                    f"We would appreciate the chance to discuss this further at your convenience."
                )
            else:  # professional or warm
                body = (
                    f"Thank you for your feedback about your experience at {branch_name}. "
                    f"We sincerely apologize that we did not meet your expectations. "
                    f"We are committed to improving and would love to discuss how we can make it right. "
                    f"Please don't hesitate to contact us directly."
                )
        elif sentiment == "neutral":
            body = (
                f"Thank you for sharing your experience at {branch_name}! "
                f"We appreciate your honest feedback and are always looking for ways to improve. "
                f"We hope to see you again soon and provide an even better experience."
            )
        else:  # positive
            if tone == "warm":
                body = (
                    f"We're absolutely thrilled to hear you had a wonderful experience at {branch_name}! 🌟 "
                    f"Your kind words mean the world to our team. "
                    f"We can't wait to welcome you back for another amazing visit!"
                )
            else:
                body = (
                    f"Thank you so much for your wonderful review of {branch_name}! "
                    f"We're delighted to hear you enjoyed your visit. "
                    f"Your support means everything to our team, and we look forward to welcoming you back!"
                )

        closing = "Warm regards,\nThe SalonAI Team"
        draft_response = f"{greeting},\n\n{body}\n\n{closing}"

        return {
            "success": True,
            "review_id": str(review.id),
            "customer_name": customer_name,
            "rating": rating,
            "sentiment": sentiment,
            "themes": themes,
            "tone_used": tone,
            "draft_response": draft_response,
            "status": "draft",
        }

    except Exception as e:
        logger.error(f"[ReputationTools] generate_review_response error: {e}", exc_info=True)
        return {"success": False, "error": f"Failed to generate review response: {str(e)}"}
    finally:
        db.close()


def get_reputation_scorecard(
    branch_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate a comprehensive reputation scorecard with NPS-style metrics,
    response-rate tracking, and branch-level comparisons.

    Args:
        branch_id: Optional UUID string to scope scorecard to a single branch.

    Returns:
        Dictionary with overall score, NPS estimate, and per-branch breakdowns.
    """
    logger.info(f"[ReputationTools] get_reputation_scorecard(branch={branch_id})")

    db: Session = SessionLocal()
    try:
        base_query = db.query(Review)
        if branch_id:
            base_query = base_query.filter(Review.branch_id == branch_id)

        all_reviews = base_query.all()
        total = len(all_reviews)

        if total == 0:
            return {
                "success": True,
                "total_reviews": 0,
                "overall_rating": 0.0,
                "nps_estimate": 0,
                "branches": [],
            }

        # Overall metrics
        total_rating = sum(r.rating for r in all_reviews)
        overall_avg = round(total_rating / total, 2)

        # NPS estimation: promoters (4-5) - detractors (1-2) as % of total
        promoters = sum(1 for r in all_reviews if r.rating >= 4)
        detractors = sum(1 for r in all_reviews if r.rating <= 2)
        nps = round(((promoters - detractors) / total) * 100, 1)

        # Per-branch breakdown
        branch_query = (
            db.query(
                Branch.id,
                Branch.name,
                func.count(Review.id).label("review_count"),
                func.avg(Review.rating).label("avg_rating"),
            )
            .join(Review, Branch.id == Review.branch_id)
        )
        if branch_id:
            branch_query = branch_query.filter(Branch.id == branch_id)

        branch_rows = branch_query.group_by(Branch.id, Branch.name).all()

        branches = []
        for row in branch_rows:
            branches.append({
                "branch_id": str(row.id),
                "branch_name": row.name,
                "review_count": row.review_count,
                "average_rating": round(float(row.avg_rating), 2),
            })

        # Review status distribution
        status_dist = {}
        for r in all_reviews:
            s = r.status.value if hasattr(r.status, "value") else str(r.status)
            status_dist[s] = status_dist.get(s, 0) + 1

        return {
            "success": True,
            "total_reviews": total,
            "overall_rating": overall_avg,
            "nps_estimate": nps,
            "status_distribution": status_dist,
            "branches": branches,
        }

    except Exception as e:
        logger.error(f"[ReputationTools] get_reputation_scorecard error: {e}", exc_info=True)
        return {"success": False, "error": f"Failed to generate reputation scorecard: {str(e)}"}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------
__all__ = [
    "fetch_reviews",
    "get_review_analytics",
    "detect_critical_reviews",
    "generate_review_response",
    "get_reputation_scorecard",
]
