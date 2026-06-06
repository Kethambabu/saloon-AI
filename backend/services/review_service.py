"""
Review & Reputation Management Service for SalonAI Workforce Platform.
Implements sentiment analysis, auto-responses, manager escalations, and review analytics.
"""

import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from db.models import (
    Review,
    ReviewStatus,
    Appointment,
    AppointmentStatus,
    Customer,
    Staff,
    Branch,
)

logger = logging.getLogger(__name__)


class ReviewService:
    """
    Core engine handling customer reviews and brand reputation management.
    """

    @staticmethod
    def get_reviews(
        db: Session,
        customer_id: Optional[str] = None,
        staff_id: Optional[str] = None,
        sentiment: Optional[str] = None,
        escalation_required: Optional[bool] = None,
        rating: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieves reviews matching specified filter criteria.
        """
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
        """
        Deduce sentiment dynamically based on keyword heuristic rules.
        Handles critical complaints, negatives, neutrals, and positives.
        """
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
            "hate", "waste", "useless", "unprofessional"
        ]
        
        # Heuristic combined with rating
        if rating <= 2:
            return "NEGATIVE"
        if rating == 3:
            return "NEUTRAL"
            
        # If text contains heavy negative words despite high rating, mark negative
        if rating >= 4 and any(kw in txt_lower for kw in ["worst", "terrible", "rude"]):
            return "NEGATIVE"
            
        if any(kw in txt_lower for kw in negative_keywords):
            return "NEGATIVE"
            
        # Rule 3: Check positives
        positive_keywords = [
            "good", "great", "excellent", "amazing", "love", "perfect", 
            "happy", "friendly", "satisfied", "satisfying", "wonderful", "best"
        ]
        if any(kw in txt_lower for kw in positive_keywords) or rating >= 4:
            return "POSITIVE"
            
        return "NEUTRAL"

    @staticmethod
    def submit_review(
        db: Session,
        customer_id: str,
        rating: int,
        comment: str,
        appointment_id: Optional[str] = None,
        staff_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Creates and processes a new customer review, analyzes sentiment, 
        and flags escalation or formats auto-responses.
        """
        cust_uuid = uuid.UUID(customer_id)
        appt_uuid = uuid.UUID(appointment_id) if appointment_id else None
        staff_uuid = uuid.UUID(staff_id) if staff_id else None

        # 1. Resolve branch_id and staff_id from appointment if available
        branch_uuid = None
        if appt_uuid:
            appt = db.query(Appointment).filter(Appointment.id == appt_uuid).first()
            if not appt:
                return {"success": False, "error": "Appointment not found."}
            status_val = appt.status.value if hasattr(appt.status, "value") else str(appt.status)
            if status_val != "COMPLETED":
                return {"success": False, "error": "Only completed appointments can be reviewed."}
            branch_uuid = appt.branch_id
            if not staff_uuid:
                staff_uuid = appt.staff_id

        # Fallback branch resolver if no appointment
        if not branch_uuid:
            branch = db.query(Branch).first()
            branch_uuid = branch.id if branch else None

        if not branch_uuid:
            return {"success": False, "error": "No physical branch registered to file review."}

        # 2. Heuristics Sentiment analysis
        sentiment = ReviewService.analyze_sentiment_rules(comment, rating)
        escalation_required = (sentiment == "CRITICAL")

        # 3. Formulate default responses
        ai_response = None
        responded = False
        if sentiment == "POSITIVE":
            ai_response = "Thank you for your kind words. We're delighted you enjoyed your experience and look forward to welcoming you again."
            responded = True
        elif sentiment == "NEUTRAL":
            ai_response = "Thank you for your feedback. We appreciate your visit and are always working to improve."
            responded = True
        elif sentiment == "NEGATIVE":
            ai_response = "We sincerely apologize for the inconvenience. Thank you for bringing this to our attention. We will work to improve our scheduling process."
            responded = True
        else: # CRITICAL
            ai_response = "This review has been flagged and escalated to management for immediate review."
            responded = False

        # 4. Check if review already exists for this appointment
        if appt_uuid:
            existing = db.query(Review).filter(Review.appointment_id == appt_uuid).first()
            if existing:
                return {"success": False, "error": "A review already exists for this appointment."}

        # 5. Create Review DB record
        review_id = uuid.uuid4()
        db_review = Review(
            id=review_id,
            customer_id=cust_uuid,
            branch_id=branch_uuid,
            appointment_id=appt_uuid,
            staff_id=staff_uuid,
            rating=rating,
            comment=comment,
            review_text=comment,
            sentiment=sentiment,
            ai_response=ai_response,
            escalation_required=escalation_required,
            responded=responded,
            status=ReviewStatus.PENDING
        )
        
        db.add(db_review)
        db.commit()

        # Trigger loyalty points update on review submission
        try:
            from tools.loyalty_triggers import trigger_loyalty_update_on_review
            trigger_loyalty_update_on_review(db, review_id, cust_uuid)
        except Exception as loyalty_err:
            logger.error(f"Error triggering loyalty update on review: {loyalty_err}")

        return {
            "success": True,
            "review_id": str(review_id),
            "sentiment": sentiment,
            "ai_response": ai_response,
            "escalation_required": escalation_required,
            "message": "Review submitted and analyzed successfully!"
        }

    @staticmethod
    def generate_response(db: Session, review_id: str, custom_response: Optional[str] = None) -> Dict[str, Any]:
        """
        Manually responds to or drafts/commits an AI response for a review.
        """
        rev_uuid = uuid.UUID(review_id)
        review = db.query(Review).filter(Review.id == rev_uuid).first()
        if not review:
            return {"success": False, "error": "Review not found"}

        if custom_response:
            review.ai_response = custom_response
        else:
            # Re-generate based on rating
            if review.rating >= 4:
                review.ai_response = f"Thank you for rating us {review.rating} stars! We always strive for perfection."
            elif review.rating == 3:
                review.ai_response = "Thank you for the rating. We appreciate your feedback and are looking into how we can improve."
            else:
                review.ai_response = "We sincerely apologize for the experience. The team has been briefed, and we are working to prevent this in the future."
                
        review.responded = True
        db.commit()

        return {
            "success": True,
            "message": "Response registered successfully!",
            "ai_response": review.ai_response
        }

    @staticmethod
    def escalate_review(db: Session, review_id: str) -> Dict[str, Any]:
        """
        Escalates a critical or contested review to managers for review.
        """
        rev_uuid = uuid.UUID(review_id)
        review = db.query(Review).filter(Review.id == rev_uuid).first()
        if not review:
            return {"success": False, "error": "Review not found"}

        review.escalation_required = True
        db.commit()

        return {
            "success": True,
            "message": "Review escalated to branch manager successfully!"
        }

    @staticmethod
    def get_review_analytics(db: Session) -> Dict[str, Any]:
        """
        Aggregates comprehensive reputation management stats for Admin & Staff.
        """
        total_reviews = db.query(Review).count()
        
        # Average rating
        avg_rating_query = db.query(func.avg(Review.rating)).scalar()
        average_rating = round(float(avg_rating_query), 2) if avg_rating_query else 0.0

        # Sentiment breakdown
        pos_count = db.query(Review).filter(Review.sentiment == "POSITIVE").count()
        neu_count = db.query(Review).filter(Review.sentiment == "NEUTRAL").count()
        neg_count = db.query(Review).filter(Review.sentiment == "NEGATIVE").count()
        crit_count = db.query(Review).filter(Review.sentiment == "CRITICAL").count()

        # Ratings distribution
        rating_dist = {}
        for r in range(1, 6):
            rating_dist[f"{r}_star"] = db.query(Review).filter(Review.rating == r).count()

        # Dynamic keyword-scanning for top complaints (Waiting Time, Staff Availability, Pricing)
        all_reviews = db.query(Review).all()
        complaint_counts = {"Waiting Time": 0, "Staff Availability": 0, "Pricing": 0}
        praise_counts = {"Hair Styling": 0, "Customer Service": 0, "Cleanliness": 0}

        for rev in all_reviews:
            comment = (rev.comment or "").lower()
            rating = rev.rating
            
            if rating <= 3: # scan complaints
                if any(k in comment for k in ["wait", "delayed", "delay", "time", "slow"]):
                    complaint_counts["Waiting Time"] += 1
                if any(k in comment for k in ["staff", "stylist", "available", "behavior", "rude"]):
                    complaint_counts["Staff Availability"] += 1
                if any(k in comment for k in ["price", "cost", "charge", "fee", "expensive", "money"]):
                    complaint_counts["Pricing"] += 1
            else: # scan praises
                if any(k in comment for k in ["hair", "cut", "color", "styling", "style"]):
                    praise_counts["Hair Styling"] += 1
                if any(k in comment for k in ["service", "friendly", "kind", "nice", "hospitality"]):
                    praise_counts["Customer Service"] += 1
                if any(k in comment for k in ["clean", "hygienic", "neat", "beautiful", "fresh"]):
                    praise_counts["Cleanliness"] += 1

        # Sort and structure
        top_complaints = [
            {"category": cat, "count": count} for cat, count in sorted(complaint_counts.items(), key=lambda x: x[1], reverse=True)
        ]
        most_praised = [
            {"category": cat, "count": count} for cat, count in sorted(praise_counts.items(), key=lambda x: x[1], reverse=True)
        ]

        return {
            "total_reviews": total_reviews,
            "average_rating": average_rating,
            "sentiment_distribution": {
                "positive": pos_count,
                "neutral": neu_count,
                "negative": neg_count,
                "critical": crit_count
            },
            "ratings_distribution": rating_dist,
            "top_complaints": top_complaints,
            "most_praised": most_praised,
            "escalated_count": db.query(Review).filter(Review.escalation_required == True).count(),
            "responded_count": db.query(Review).filter(Review.responded == True).count(),
        }

    @staticmethod
    def update_review_status(db: Session, review_id: str, status: str) -> Dict[str, Any]:
        """
        Updates the moderation status of a review (APPROVED / REJECTED).
        """
        rev_uuid = uuid.UUID(review_id)
        review = db.query(Review).filter(Review.id == rev_uuid).first()
        if not review:
            return {"success": False, "error": "Review not found"}
            
        try:
            from db.models import ReviewStatus
            review.status = ReviewStatus(status.upper())
            db.commit()
            return {
                "success": True,
                "message": f"Review status updated to {status.upper()} successfully!",
                "status": review.status.value
            }
        except ValueError:
            return {"success": False, "error": f"Invalid review status: {status}"}
