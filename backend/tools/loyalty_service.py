"""
Loyalty Points Service - Calculates and manages customer loyalty points.
Points vary based on appointment completion, cancellations, ratings, and app usage.
"""

import logging
from typing import Optional
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from db.models import (
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


def add_loyalty_points(
    db: Session,
    customer_id: UUID,
    points: int,
    transaction_type: LoyaltyTransactionType,
    description: str = "",
    appointment_id: Optional[UUID] = None,
    review_id: Optional[UUID] = None,
) -> LoyaltyTransaction:
    """
    Add or deduct loyalty points for a customer.

    Args:
        db: Database session
        customer_id: Customer UUID
        points: Number of points to add (negative for deductions)
        transaction_type: Type of transaction
        description: Optional description
        appointment_id: Optional related appointment
        review_id: Optional related review

    Returns:
        Created LoyaltyTransaction record
    """
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise ValueError(f"Customer {customer_id} not found")

    previous_balance = customer.loyalty_points
    new_balance = max(0, previous_balance + points)  # Don't allow negative points

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
        f"Balance: {previous_balance} → {new_balance}"
    )

    return transaction


def on_appointment_completed(
    db: Session,
    appointment_id: UUID,
    customer_id: UUID,
) -> LoyaltyTransaction:
    """Award points when appointment is completed."""
    points = LOYALTY_CONFIG["appointment_completed"]
    return add_loyalty_points(
        db=db,
        customer_id=customer_id,
        points=points,
        transaction_type=LoyaltyTransactionType.APPOINTMENT_COMPLETED,
        description=f"Earned {points} points for completing appointment",
        appointment_id=appointment_id,
    )


def on_appointment_cancelled(
    db: Session,
    appointment_id: UUID,
    customer_id: UUID,
) -> LoyaltyTransaction:
    """Deduct points when appointment is cancelled."""
    points = LOYALTY_CONFIG["appointment_cancelled"]
    return add_loyalty_points(
        db=db,
        customer_id=customer_id,
        points=points,
        transaction_type=LoyaltyTransactionType.APPOINTMENT_CANCELLED,
        description=f"Deducted {abs(points)} points for cancelling appointment",
        appointment_id=appointment_id,
    )


def on_review_submitted(
    db: Session,
    review_id: UUID,
    customer_id: UUID,
) -> Optional[LoyaltyTransaction]:
    """Award points for submitting a review and bonus for high ratings."""
    review = db.query(Review).filter(Review.id == review_id).first()
    if not review:
        logger.warning(f"Review {review_id} not found")
        return None

    # Award base points for submitting review
    points = LOYALTY_CONFIG["review_submitted"]
    transaction = add_loyalty_points(
        db=db,
        customer_id=customer_id,
        points=points,
        transaction_type=LoyaltyTransactionType.REVIEW_SUBMITTED,
        description=f"Earned {points} points for submitting review",
        review_id=review_id,
    )

    # Award bonus for high rating
    if review.rating >= 3:
        rating_bonus = LOYALTY_CONFIG["high_rating_bonus"].get(review.rating, 0)
        add_loyalty_points(
            db=db,
            customer_id=customer_id,
            points=rating_bonus,
            transaction_type=LoyaltyTransactionType.RATING_BONUS,
            description=f"Earned {rating_bonus} point bonus for {review.rating}-star rating",
            review_id=review_id,
        )

    return transaction


def calculate_app_usage_bonus(
    db: Session,
    customer_id: UUID,
    days: int = 30,
) -> Optional[LoyaltyTransaction]:
    """
    Calculate and award app usage bonus based on chat log activity.
    Checks number of app visits (chat sessions) in last N days.
    """
    from db.models import ChatLog

    # Count unique chat sessions for customer in last N days
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    session_count = (
        db.query(ChatLog.session_id)
        .distinct()
        .filter(
            ChatLog.customer_id == customer_id,
            ChatLog.created_at >= cutoff_date,
        )
        .count()
    )

    if session_count == 0:
        return None

    # Award bonus based on visit count
    bonus_points = 0
    description = ""

    for threshold in sorted(
        LOYALTY_CONFIG["app_usage_bonus"].keys(), reverse=True
    ):
        if session_count >= threshold:
            bonus_points = LOYALTY_CONFIG["app_usage_bonus"][threshold]
            description = (
                f"Earned {bonus_points} points for {session_count} app visits"
            )
            break

    if bonus_points > 0:
        return add_loyalty_points(
            db=db,
            customer_id=customer_id,
            points=bonus_points,
            transaction_type=LoyaltyTransactionType.APP_USAGE_BONUS,
            description=description,
        )

    return None


def get_customer_loyalty_summary(
    db: Session,
    customer_id: UUID,
) -> dict:
    """Get loyalty points summary for a customer."""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise ValueError(f"Customer {customer_id} not found")

    # Get recent transactions
    recent_transactions = (
        db.query(LoyaltyTransaction)
        .filter(LoyaltyTransaction.customer_id == customer_id)
        .order_by(LoyaltyTransaction.created_at.desc())
        .limit(10)
        .all()
    )

    # Get appointment completion count
    completed_appointments = (
        db.query(Appointment)
        .filter(
            Appointment.customer_id == customer_id,
            Appointment.status == AppointmentStatus.COMPLETED,
        )
        .count()
    )

    # Get review count
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


def reset_customer_loyalty_points(
    db: Session,
    customer_id: UUID,
    reason: str = "Manual reset",
) -> LoyaltyTransaction:
    """Reset customer loyalty points to 0 (admin function)."""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise ValueError(f"Customer {customer_id} not found")

    previous_balance = customer.loyalty_points
    customer.loyalty_points = 0

    transaction = LoyaltyTransaction(
        customer_id=customer_id,
        transaction_type=LoyaltyTransactionType.MANUAL_ADJUSTMENT,
        points_change=-previous_balance,
        previous_balance=previous_balance,
        new_balance=0,
        description=reason,
    )

    db.add(transaction)
    db.flush()

    logger.info(f"Reset loyalty points for customer {customer_id} from {previous_balance} to 0")

    return transaction
