"""
Review & Reputation Management Service for SalonAI Workforce Platform.
Consolidates sentiment analysis, auto-responses, manager escalations, and review analytics.
"""

import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from sqlalchemy import case, desc

from infrastructure.db.database import SessionLocal, db_transaction
from infrastructure.db.models import (
    Review,
    ReviewStatus,
    Appointment,
    AppointmentStatus,
    Customer,
    Staff,
    Branch,
    LoyaltyTransactionType,
)
from infrastructure.events.event_bus import get_event_bus

logger = logging.getLogger(__name__)

_review_service_instance: Optional["ReviewService"] = None

class ReviewService:
    """
    Core application service managing customer reviews, sentiment, and reputation metrics.
    """

    def __init__(self) -> None:
        self._event_bus = get_event_bus()
        logger.info("ReviewService initialized.")

    @staticmethod
    def submit_review(
        db: Session,
        customer_id: str,
        rating: int,
        comment: str,
        branch_id: Optional[str] = None,
        staff_id: Optional[str] = None,
        appointment_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Submit a customer review and award loyalty points."""
        try:
            # Resolve branch if not given (use first active)
            br_uuid = uuid.UUID(branch_id) if branch_id else db.query(Branch).filter(Branch.is_active == True).first().id
            cust_uuid = uuid.UUID(str(customer_id))
            review = Review(
                id=uuid.uuid4(),
                customer_id=cust_uuid,
                branch_id=br_uuid,
                staff_id=uuid.UUID(str(staff_id)) if staff_id else None,
                appointment_id=uuid.UUID(str(appointment_id)) if appointment_id else None,
                rating=rating,
                comment=comment,
                review_text=comment,
                status=ReviewStatus.PENDING,
                sentiment=ReviewService.analyze_sentiment_rules(comment, rating),
                escalation_required=False,
                responded=False,
            )
            db.add(review)
            db.flush()

            # Generate AI auto reply
            try:
                ReviewService.auto_reply_to_review(db, review.id)
            except Exception as reply_exc:
                logger.error(f"[ReviewService] Auto reply generation failed: {reply_exc}")

            # Award loyalty points for review
            from application.services.loyalty_service import get_loyalty_service
            get_loyalty_service().on_review_submitted(db, review.id, cust_uuid)

            db.commit()
            return {
                "success": True,
                "review_id": str(review.id),
                "rating": rating,
                "sentiment": review.sentiment,
                "ai_response": review.ai_response,
                "escalation_required": review.escalation_required,
                "data": {
                    "review_id": str(review.id),
                    "sentiment": review.sentiment,
                    "ai_response": review.ai_response,
                    "escalation_required": review.escalation_required,
                }
            }
        except Exception as e:
            logger.error(f"[ReviewService] submit_review error: {e}", exc_info=True)
            db.rollback()
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_reviews(
        db: Session,
        customer_id: Optional[str] = None,
        staff_id: Optional[str] = None,
        sentiment: Optional[str] = None,
        escalation_required: Optional[bool] = None,
        rating: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieves reviews matching specified filter criteria."""
        query = db.query(Review)

        if customer_id:
            query = query.filter(Review.customer_id == uuid.UUID(customer_id))
        if staff_id:
            query = query.filter(Review.staff_id == uuid.UUID(staff_id))
        if sentiment:
            query = query.filter(Review.sentiment.ilike(sentiment))
        if escalation_required is not None:
            query = query.filter(Review.escalation_required == escalation_required)
        if rating:
            query = query.filter(Review.rating == rating)

        reviews = query.order_by(Review.id.desc()).all()
        result = []
        for r in reviews:
            result.append({
                "id": str(r.id),
                "customer_id": str(r.customer_id),
                "customer_name": r.customer.full_name if r.customer else "Valued Client",
                "staff_id": str(r.staff_id) if r.staff_id else None,
                "staff_name": r.staff.full_name if r.staff else None,
                "branch_id": str(r.branch_id),
                "branch_name": r.branch.name if r.branch else "Salon Branch",
                "appointment_id": str(r.appointment_id) if r.appointment_id else None,
                "rating": r.rating,
                "comment": r.comment or "",
                "review_text": r.review_text or r.comment or "",
                "sentiment": r.sentiment or "NEUTRAL",
                "ai_response": r.ai_response or "",
                "escalation_required": r.escalation_required,
                "responded": r.responded,
                "status": r.status.value if hasattr(r.status, "value") else str(r.status),
                "created_at": r.created_at.isoformat() if r.created_at else datetime.now(timezone.utc).isoformat(),
            })
        return result

    @staticmethod
    def analyze_sentiment_rules(text: str, rating: int) -> str:
        """Deduce sentiment dynamically based on keyword heuristic rules."""
        txt_lower = text.lower()
        
        # Rule 1: Detect CRITICAL red flags
        critical_keywords = [
            "fraud", "scam", "police", "court", "lawyer", "legal", 
            "harass", "harassment", "abuse", "abusive", "steal", 
            "rob", "robbed", "sue", "stole", "overcharge", "overcharged", "injured", "injury"
        ]
        if any(kw in txt_lower for kw in critical_keywords):
            return "CRITICAL"
            
        # Rule 2: Check standard negatives
        negative_keywords = [
            "bad", "rude", "worst", "terrible", "disappointed", "disappointing",
            "dirty", "slow", "delay", "waited", "waiting", "poor", "angry", 
            "awful", "horrible", "unprofessional", "regret", "waste", "never again", "hate"
        ]
        if any(kw in txt_lower for kw in negative_keywords) or rating <= 2:
            return "NEGATIVE"
            
        # Rule 3: Check positives
        positive_keywords = [
            "good", "nice", "great", "excellent", "love", "loved", "friendly", 
            "professional", "clean", "happy", "perfect", "awesome", "best", "satisfied"
        ]
        if any(kw in txt_lower for kw in positive_keywords) or rating >= 4:
            return "POSITIVE"
            
        return "NEUTRAL"

    @staticmethod
    def auto_reply_to_review(db: Session, review_id: uuid.UUID) -> Optional[str]:
        """Drafts and logs an AI response based on sentiment guidelines."""
        review = db.query(Review).filter(Review.id == review_id).first()
        if not review:
            return None

        sentiment = ReviewService.analyze_sentiment_rules(review.comment or "", review.rating)
        review.sentiment = sentiment

        # Rule 17: Professional Tone Response guidelines
        if sentiment == "POSITIVE":
            reply = f"Thank you so much for the review, {review.customer.first_name if review.customer else 'client'}! We are thrilled that you loved your experience and hope to see you again soon."
        elif sentiment == "NEGATIVE":
            reply = f"Hello {review.customer.first_name if review.customer else 'client'}, we are extremely sorry for the disappointing experience. We have flagged this to management and would love to make this right."
        elif sentiment == "CRITICAL":
            reply = "Thank you for bringing this to our attention. We take this extremely seriously and have escalated it to management for immediate investigation."
            review.escalation_required = True
        else:
            reply = f"Thank you for sharing your feedback with us, {review.customer.first_name if review.customer else 'client'}. We appreciate it and will use it to improve."

        review.ai_response = reply
        review.responded = True
        db.flush()
        return reply

    @staticmethod
    def escalate_negative_review(db: Session, review_id: uuid.UUID) -> bool:
        """Escalate critical review to management by setting escalation flag."""
        review = db.query(Review).filter(Review.id == review_id).first()
        if not review:
            return False
            
        review.escalation_required = True
        db.flush()
        
        # Trigger notification log
        notification = Notification(
            id=uuid.uuid4(),
            message=f"CRITICAL ESCALATION: Low-rating review {review_id} from {review.customer.full_name if review.customer else 'Client'} requires attention.",
            channel="EMAIL",
            sent=False
        )
        db.add(notification)
        db.flush()
        return True

    @staticmethod
    def get_reputation_scorecard(db: Session) -> Dict[str, Any]:
        """Compute aggregates of star reviews and response stats."""
        total = db.query(Review).count()
        if total == 0:
            return {
                "total_reviews": 0,
                "average_rating": 5.0,
                "sentiment_distribution": {"POSITIVE": 0, "NEUTRAL": 0, "NEGATIVE": 0, "CRITICAL": 0},
                "response_rate": 100.0,
                "pending_escalations": 0,
            }

        avg = db.query(func.avg(Review.rating)).scalar() or 5.0
        escalated = db.query(Review).filter(Review.escalation_required == True).count()
        responded = db.query(Review).filter(Review.responded == True).count()
        response_rate = round((responded / total * 100.0), 1)

        sentiments = db.query(Review.sentiment, func.count(Review.id)).group_by(Review.sentiment).all()
        sent_dict = {"POSITIVE": 0, "NEUTRAL": 0, "NEGATIVE": 0, "CRITICAL": 0}
        for s, count in sentiments:
            if s:
                sent_dict[s.upper()] = count

        return {
            "total_reviews": total,
            "average_rating": round(float(avg), 2),
            "sentiment_distribution": sent_dict,
            "response_rate": response_rate,
            "pending_escalations": escalated,
        }

    # =========================================================================
    # TRANSACTION / WORKFLOW ENTRYPOINTS
    # =========================================================================



    def generate_response(self, review_id: str, custom_response: Optional[str] = None) -> Dict[str, Any]:
        """Update or generate AI/manual reply to a review."""
        session = SessionLocal()
        try:
            r_id = uuid.UUID(review_id)
            review = session.query(Review).filter(Review.id == r_id).first()
            if not review:
                return {"success": False, "error": f"Review {review_id} not found."}
                
            if custom_response:
                review.ai_response = custom_response
                review.responded = True
            else:
                self.auto_reply_to_review(session, r_id)
                
            session.commit()
            return {
                "success": True,
                "data": {
                    "review_id": str(r_id),
                    "response": review.ai_response,
                }
            }
        except Exception as e:
            session.rollback()
            return {"success": False, "error": str(e)}
        finally:
            session.close()

    def escalate_review(self, review_id: str) -> Dict[str, Any]:
        """Flag review for manual intervention."""
        session = SessionLocal()
        try:
            r_id = uuid.UUID(review_id)
            success = self.escalate_negative_review(session, r_id)
            if not success:
                return {"success": False, "error": f"Review {review_id} not found."}
            session.commit()
            return {
                "success": True,
                "data": {
                    "review_id": str(review_id),
                    "message": "Review escalated to management.",
                }
            }
        except Exception as e:
            session.rollback()
            return {"success": False, "error": str(e)}
        finally:
            session.close()


def get_review_service() -> ReviewService:
    global _review_service_instance
    if _review_service_instance is None:
        _review_service_instance = ReviewService()
    return _review_service_instance


# Backward-compatibility wrappers and helpers for reviews/reputation
_POSITIVE_KEYWORDS = [
    "great", "excellent", "amazing", "wonderful", "fantastic", "love",
    "perfect", "best", "beautiful", "friendly", "clean", "professional",
    "outstanding", "happy", "highly recommend", "top notch", "superb",
    "impressed", "delighted", "awesome", "satisfied",
]
_NEGATIVE_KEYWORDS = [
    "bad", "terrible", "horrible", "worst", "rude", "dirty", "slow",
    "disappointing", "never again", "awful", "poor", "unprofessional",
    "overcharged", "nightmare", "waste", "regret", "unacceptable",
    "incompetent", "damaged", "ruined",
]

def _classify_sentiment(text: Optional[str], rating: int) -> str:
    if text:
        text_lower = text.lower()
        pos_hits = sum(1 for kw in _POSITIVE_KEYWORDS if kw in text_lower)
        neg_hits = sum(1 for kw in _NEGATIVE_KEYWORDS if kw in text_lower)
        if neg_hits > pos_hits and neg_hits >= 2:
            return "negative"
        if pos_hits > neg_hits and pos_hits >= 2:
            return "positive"
    if rating <= 2:
        return "negative"
    if rating >= 4:
        return "positive"
    return "neutral"

def _extract_themes(text: Optional[str]) -> List[str]:
    if not text:
        return []
    text_lower = text.lower()
    themes = []
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

def fetch_reviews(
    branch_id: Optional[str] = None,
    status: Optional[str] = None,
    min_rating: Optional[int] = None,
    max_rating: Optional[int] = None,
    limit: int = 50,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    logger.info(f"[ReviewService] fetch_reviews(branch={branch_id}, status={status})")
    session = db or SessionLocal()
    try:
        query = (
            session.query(
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
            query = query.filter(Review.branch_id == uuid.UUID(branch_id))
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
        return {"success": True, "total_returned": len(reviews), "reviews": reviews}
    except Exception as e:
        logger.error(f"[ReviewService] fetch_reviews error: {e}", exc_info=True)
        return {"success": False, "error": f"Failed to fetch reviews: {str(e)}"}
    finally:
        if not db:
            session.close()

def get_review_analytics(
    branch_id: Optional[str] = None,
    days: int = 30,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    logger.info(f"[ReviewService] get_review_analytics(branch={branch_id}, days={days})")
    session = db or SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        base_query = session.query(Review).filter(Review.created_at >= cutoff)
        if branch_id:
            base_query = base_query.filter(Review.branch_id == uuid.UUID(branch_id))
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
        star_dist = {str(i): 0 for i in range(1, 6)}
        sentiment_counts = {"positive": 0, "neutral": 0, "negative": 0}
        total_rating = 0
        theme_counter = {}
        for rev in all_reviews:
            star_dist[str(rev.rating)] = star_dist.get(str(rev.rating), 0) + 1
            total_rating += rev.rating
            sentiment = _classify_sentiment(rev.comment, rev.rating)
            sentiment_counts[sentiment] = sentiment_counts.get(sentiment, 0) + 1
            for theme in _extract_themes(rev.comment):
                theme_counter[theme] = theme_counter.get(theme, 0) + 1
        avg_rating = round(total_rating / total, 2)
        sentiment_pct = {k: round((v / total) * 100, 1) for k, v in sentiment_counts.items()}
        top_themes = sorted(theme_counter.items(), key=lambda x: x[1], reverse=True)[:10]
        daily_query = (
            session.query(
                func.date(Review.created_at).label("day"),
                func.avg(Review.rating).label("avg_rating"),
                func.count(Review.id).label("count"),
            )
            .filter(Review.created_at >= cutoff)
        )
        if branch_id:
            daily_query = daily_query.filter(Review.branch_id == uuid.UUID(branch_id))
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
        logger.error(f"[ReviewService] get_review_analytics error: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
    finally:
        if not db:
            session.close()

def detect_critical_reviews(
    rating_threshold: int = 2,
    branch_id: Optional[str] = None,
    days: int = 7,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    logger.info(f"[ReviewService] detect_critical_reviews(threshold={rating_threshold})")
    session = db or SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        query = (
            session.query(
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
            query = query.filter(Review.branch_id == uuid.UUID(branch_id))
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
        logger.error(f"[ReviewService] detect_critical_reviews error: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
    finally:
        if not db:
            session.close()

def generate_review_response(
    review_id: str,
    tone: str = "professional",
    db: Optional[Session] = None
) -> Dict[str, Any]:
    logger.info(f"[ReviewService] generate_review_response(review={review_id}, tone={tone})")
    valid_tones = {"professional", "empathetic", "warm", "formal"}
    if tone not in valid_tones:
        return {"success": False, "error": f"Invalid tone '{tone}'. Choose from: {', '.join(valid_tones)}"}
    session = db or SessionLocal()
    try:
        review_uuid = uuid.UUID(review_id)
        review = (
            session.query(
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
        greeting = f"Dear {review.first_name}"
        branch_name = review.branch_name
        if sentiment == "negative":
            if tone == "empathetic":
                body = f"We are truly sorry to hear about your experience at {branch_name}. Your feedback is incredibly important to us, and we take your concerns very seriously. We would love the opportunity to make things right — please reach out to us directly so we can address your concerns personally."
            elif tone == "formal":
                body = f"Thank you for bringing this matter to our attention regarding your visit to {branch_name}. We sincerely apologize for any inconvenience you experienced. Our management team will review this feedback immediately. We would appreciate the chance to discuss this further at your convenience."
            else:
                body = f"Thank you for your feedback about your experience at {branch_name}. We sincerely apologize that we did not meet your expectations. We are committed to improving and would love to discuss how we can make it right. Please don't hesitate to contact us directly."
        elif sentiment == "neutral":
            body = f"Thank you for sharing your experience at {branch_name}! We appreciate your honest feedback and are always looking for ways to improve. We hope to see you again soon and provide an even better experience."
        else:
            if tone == "warm":
                body = f"We're absolutely thrilled to hear you had a wonderful experience at {branch_name}! 🌟 Your kind words mean the world to our team. We can't wait to welcome you back for another amazing visit!"
            else:
                body = f"Thank you so much for your wonderful review of {branch_name}! We're delighted to hear you enjoyed your visit. Your support means everything to our team, and we look forward to welcoming you back!"
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
        logger.error(f"[ReviewService] generate_review_response error: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
    finally:
        if not db:
            session.close()

def get_reputation_scorecard(
    branch_id: Optional[str] = None,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    logger.info(f"[ReviewService] get_reputation_scorecard(branch={branch_id})")
    session = db or SessionLocal()
    try:
        base_query = session.query(Review)
        if branch_id:
            base_query = base_query.filter(Review.branch_id == uuid.UUID(branch_id))
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
        total_rating = sum(r.rating for r in all_reviews)
        overall_avg = round(total_rating / total, 2)
        promoters = sum(1 for r in all_reviews if r.rating >= 4)
        detractors = sum(1 for r in all_reviews if r.rating <= 2)
        nps = round(((promoters - detractors) / total) * 100, 1)
        branch_query = (
            session.query(
                Branch.id,
                Branch.name,
                func.count(Review.id).label("review_count"),
                func.avg(Review.rating).label("avg_rating"),
            )
            .join(Review, Branch.id == Review.branch_id)
        )
        if branch_id:
            branch_query = branch_query.filter(Branch.id == uuid.UUID(branch_id))
        branch_rows = branch_query.group_by(Branch.id, Branch.name).all()
        branches = []
        for row in branch_rows:
            branches.append({
                "branch_id": str(row.id),
                "branch_name": row.name,
                "review_count": row.review_count,
                "average_rating": round(float(row.avg_rating), 2),
            })
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
        logger.error(f"[ReviewService] get_reputation_scorecard error: {e}", exc_info=True)
        return {"success": False, "error": str(e)}
    finally:
        if not db:
            session.close()

