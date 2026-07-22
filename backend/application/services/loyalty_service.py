"""
Loyalty Points Service - Calculates and manages customer loyalty points.
Points vary based on appointment completion, cancellations, ratings, and app usage.
"""

import logging
from typing import Optional
from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from infrastructure.db.models import (
    Customer,
    Appointment,
    AppointmentStatus,
    Review,
    LoyaltyTransaction,
    LoyaltyTransactionType,
)

logger = logging.getLogger(__name__)

# Loyalty point configuration
LOYALTY_CONFIG = {
    "appointment_completed": 100,  # Points per completed appointment
    "appointment_cancelled": -50,  # Points deducted for cancellation
    "review_submitted": 25,  # Bonus points for submitting review
    "high_rating_bonus": {
        5: 50,  # 5-star rating bonus
        4: 25,  # 4-star rating bonus
        3: 10,  # 3-star rating bonus
    },
    "app_usage_bonus": {
        7: 10,  # 10 points for 7+ app visits per month
        15: 20,  # 20 points for 15+ app visits per month
        30: 50,  # 50 points for 30+ app visits per month
    },
}

_loyalty_service_instance: Optional["LoyaltyService"] = None

class LoyaltyService:
    """
    Application service managing customer loyalty ledger transactions and event-driven updates.
    """

    def add_loyalty_points(
        self,
        db: Session,
        customer_id: UUID,
        points: int,
        transaction_type: LoyaltyTransactionType,
        description: str = "",
        appointment_id: Optional[UUID] = None,
        review_id: Optional[UUID] = None,
    ) -> LoyaltyTransaction:
        """Add or deduct loyalty points for a customer."""
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        if not customer:
            raise ValueError(f"Customer {customer_id} not found")

        if customer.loyalty_points is None:
            customer.loyalty_points = 0
        
        previous_balance = customer.loyalty_points
        new_balance = max(0, previous_balance + points)

        transaction = LoyaltyTransaction(
            customer_id=customer_id,
            transaction_type=transaction_type,
            points_change=points,
            previous_balance=previous_balance,
            new_balance=new_balance,
            description=description,
            appointment_id=appointment_id,
            review_id=review_id,
        )

        customer.loyalty_points = new_balance
        db.add(transaction)
        db.flush()
        
        logger.info(
            f"Added {points} loyalty points to customer {customer_id}. "
            f"Balance: {previous_balance} -> {new_balance}"
        )
        return transaction

    def on_appointment_completed(self, db: Session, appointment_id: UUID, customer_id: UUID) -> None:
        """Deduct standard completion reward points."""
        self.add_loyalty_points(
            db,
            customer_id=customer_id,
            points=LOYALTY_CONFIG["appointment_completed"],
            transaction_type=LoyaltyTransactionType.APPOINTMENT_COMPLETED,
            description="Appointment completed bonus points",
            appointment_id=appointment_id,
        )

    def on_appointment_cancelled(self, db: Session, appointment_id: UUID, customer_id: UUID) -> None:
        """Deduct points for appointment cancellation."""
        self.add_loyalty_points(
            db,
            customer_id=customer_id,
            points=LOYALTY_CONFIG["appointment_cancelled"],
            transaction_type=LoyaltyTransactionType.APPOINTMENT_CANCELLED,
            description="Appointment cancellation penalty",
            appointment_id=appointment_id,
        )

    def on_review_submitted(self, db: Session, review_id: UUID, customer_id: UUID) -> None:
        """Award points when review is submitted, plus rating bonuses."""
        review = db.query(Review).filter(Review.id == review_id).first()
        if not review:
            return

        points = LOYALTY_CONFIG["review_submitted"]
        description = "Review submitted feedback bonus"

        rating = review.rating
        bonus = LOYALTY_CONFIG["high_rating_bonus"].get(rating, 0)
        if bonus > 0:
            points += bonus
            description += f" including {rating}-star rating bonus"

        self.add_loyalty_points(
            db,
            customer_id=customer_id,
            points=points,
            transaction_type=LoyaltyTransactionType.REVIEW_SUBMITTED,
            description=description,
            review_id=review_id,
        )

    # Trigger helpers matching legacy loyalty_triggers.py API
    def trigger_loyalty_update_on_completion(self, db: Session, appointment_id: UUID, customer_id: UUID) -> bool:
        try:
            self.on_appointment_completed(db, appointment_id, customer_id)
            return True
        except Exception as e:
            logger.error(f"Error updating loyalty on completion: {e}")
            return False

    def trigger_loyalty_update_on_cancellation(self, db: Session, appointment_id: UUID, customer_id: UUID) -> bool:
        try:
            self.on_appointment_cancelled(db, appointment_id, customer_id)
            return True
        except Exception as e:
            logger.error(f"Error updating loyalty on cancellation: {e}")
            return False

    def trigger_loyalty_update_on_review(self, db: Session, review_id: UUID, customer_id: UUID) -> bool:
        try:
            self.on_review_submitted(db, review_id, customer_id)
            return True
        except Exception as e:
            logger.error(f"Error updating loyalty on review: {e}")
            return False


def get_loyalty_service() -> LoyaltyService:
    global _loyalty_service_instance
    if _loyalty_service_instance is None:
        _loyalty_service_instance = LoyaltyService()
    return _loyalty_service_instance


# Backward-compatibility wrappers for standalone functions
def get_customer_loyalty_summary(db: Session, customer_id: UUID) -> dict:
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise ValueError(f"Customer {customer_id} not found")

    recent_transactions = (
        db.query(LoyaltyTransaction)
        .filter(LoyaltyTransaction.customer_id == customer_id)
        .order_by(LoyaltyTransaction.created_at.desc())
        .limit(10)
        .all()
    )

    completed_appointments = (
        db.query(Appointment)
        .filter(
            Appointment.customer_id == customer_id,
            Appointment.status == AppointmentStatus.COMPLETED,
        )
        .count()
    )

    reviews = (
        db.query(Review)
        .filter(Review.customer_id == customer_id)
        .all()
    )
    review_count = len(reviews)
    avg_rating = (
        sum(r.rating for r in reviews) / review_count if review_count > 0 else 0
    )

    return {
        "customer_id": str(customer_id),
        "current_balance": customer.loyalty_points,
        "completed_appointments": completed_appointments,
        "reviews_submitted": review_count,
        "average_rating": round(avg_rating, 2),
        "recent_transactions": [
            {
                "id": str(t.id),
                "type": t.transaction_type.value,
                "points_change": t.points_change,
                "new_balance": t.new_balance,
                "description": t.description,
                "created_at": t.created_at.isoformat(),
            }
            for t in recent_transactions
        ],
    }


def reset_customer_loyalty_points(db: Session, customer_id: UUID, reason: str = "Manual reset") -> LoyaltyTransaction:
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise ValueError(f"Customer {customer_id} not found")
    points_to_deduct = -(customer.loyalty_points or 0)
    return get_loyalty_service().add_loyalty_points(
        db,
        customer_id=customer_id,
        points=points_to_deduct,
        transaction_type=LoyaltyTransactionType.DEDUCTED,
        description=reason
    )


def on_appointment_completed(*args, **kwargs):
    return get_loyalty_service().on_appointment_completed(*args, **kwargs)


def on_appointment_cancelled(*args, **kwargs):
    return get_loyalty_service().on_appointment_cancelled(*args, **kwargs)


def on_review_submitted(*args, **kwargs):
    return get_loyalty_service().on_review_submitted(*args, **kwargs)


def trigger_loyalty_update_on_completion(*args, **kwargs):
    return get_loyalty_service().trigger_loyalty_update_on_completion(*args, **kwargs)


def trigger_loyalty_update_on_cancellation(*args, **kwargs):
    return get_loyalty_service().trigger_loyalty_update_on_cancellation(*args, **kwargs)


def trigger_loyalty_update_on_review(*args, **kwargs):
    return get_loyalty_service().trigger_loyalty_update_on_review(*args, **kwargs)



