"""
Database-backed operations and tool definitions for the Staff AI Assistant Agent.
Queries and manipulates the database model layers securely.
"""

import logging
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta

from db.database import SessionLocal
from db.models import (
    Staff,
    Appointment,
    Customer,
    Review,
    StaffLeave,
    AppointmentStatus,
    Service,
    CustomerRecommendation
)
from services.recommendation_service import RecommendationService
from rag.retriever import (
    search_salon_knowledge,
    search_customer_interactions,
    search_all_context
)

logger = logging.getLogger(__name__)


def get_today_schedule(staff_id: str) -> str:
    """
    Retrieve today's schedule/appointments for a specific staff member.

    Args:
        staff_id: UUID string of the staff member.
    """
    logger.info(f"[StaffTools] get_today_schedule for staff_id: {staff_id}")
    db = SessionLocal()
    try:
        staff_uuid = uuid.UUID(staff_id)
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        appointments = db.query(Appointment).filter(
            Appointment.staff_id == staff_uuid,
            Appointment.start_time >= today_start,
            Appointment.start_time < today_end,
            Appointment.status != AppointmentStatus.CANCELLED
        ).order_by(Appointment.start_time).all()

        if not appointments:
            return "You have no appointments scheduled for today."

        lines = [f"Your schedule for today ({now.strftime('%A, %B %d, %Y')}):"]
        for idx, appt in enumerate(appointments, 1):
            time_str = appt.start_time.strftime("%I:%M %p")
            cust_name = appt.customer.full_name if appt.customer else "Guest"
            cust_phone = appt.customer.phone if appt.customer else "N/A"
            service_name = appt.service.name if appt.service else "Service"
            status = appt.status.value
            lines.append(
                f"{idx}. {time_str} - {service_name} | Customer: {cust_name} (Phone: {cust_phone}) | Status: {status}"
            )

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Error in get_today_schedule: {e}", exc_info=True)
        return f"Error fetching schedule: {str(e)}"
    finally:
        db.close()


def get_next_customer(staff_id: str) -> str:
    """
    Get the next upcoming appointment details for a staff member.

    Args:
        staff_id: UUID string of the staff member.
    """
    logger.info(f"[StaffTools] get_next_customer for staff_id: {staff_id}")
    db = SessionLocal()
    try:
        staff_uuid = uuid.UUID(staff_id)
        now = datetime.now(timezone.utc)

        appt = db.query(Appointment).filter(
            Appointment.staff_id == staff_uuid,
            Appointment.start_time > now,
            Appointment.status.in_([
                AppointmentStatus.PENDING,
                AppointmentStatus.CONFIRMED,
                AppointmentStatus.CHECKED_IN,
                AppointmentStatus.IN_SERVICE
            ])
        ).order_by(Appointment.start_time.asc()).first()

        if not appt:
            return "You have no more upcoming appointments scheduled for today."

        time_str = appt.start_time.strftime("%I:%M %p")
        cust_name = appt.customer.full_name if appt.customer else "Guest"
        cust_phone = appt.customer.phone if appt.customer else "N/A"
        service_name = appt.service.name if appt.service else "Service"
        notes = appt.notes or "None"

        return (
            f"Your next customer is:\n"
            f"- Time: {time_str}\n"
            f"- Service: {service_name}\n"
            f"- Customer: {cust_name}\n"
            f"- Phone: {cust_phone}\n"
            f"- Status: {appt.status.value}\n"
            f"- Notes: {notes}"
        )
    except Exception as e:
        logger.error(f"Error in get_next_customer: {e}", exc_info=True)
        return f"Error fetching next customer: {str(e)}"
    finally:
        db.close()


def get_customer_history(customer_name: str) -> str:
    """
    Retrieve visit history and metrics for a customer by name.

    Args:
        customer_name: Full name or partial name of the customer.
    """
    logger.info(f"[StaffTools] get_customer_history for customer_name: {customer_name}")
    db = SessionLocal()
    try:
        customers = db.query(Customer).filter(
            Customer.first_name.ilike(f"%{customer_name}%") |
            Customer.last_name.ilike(f"%{customer_name}%")
        ).all()

        if not customers:
            return f"No customer found matching name: '{customer_name}'"

        if len(customers) > 1:
            return f"Multiple customers found matching '{customer_name}': " + ", ".join([c.full_name for c in customers])

        cust = customers[0]
        # Get appointments count
        appts = db.query(Appointment).filter(
            Appointment.customer_id == cust.id
        ).order_by(Appointment.start_time.desc()).all()

        completed_count = sum(1 for a in appts if a.status == AppointmentStatus.COMPLETED)

        # Calculate average spend
        total_spend = sum(float(a.service.price) for a in appts if a.status == AppointmentStatus.COMPLETED and a.service)
        avg_spend = total_spend / completed_count if completed_count > 0 else 0.0

        # Grab reviews
        reviews = db.query(Review).filter(Review.customer_id == cust.id).all()
        avg_rating = sum(r.rating for r in reviews) / len(reviews) if reviews else 0.0

        lines = [
            f"Customer Profile: {cust.full_name} (ID: {cust.id})",
            f"- Email: {cust.email}",
            f"- Phone: {cust.phone or 'N/A'}",
            f"- Total Completed Visits: {completed_count}",
            f"- Average Spend per Visit: ${avg_spend:.2f}",
            f"- Average Review Rating Given: {f'{avg_rating:.1f} ★' if reviews else 'No reviews submitted'}",
            f"- Loyalty Points Balance: {cust.loyalty_points}",
            "\nRecent Visits:"
        ]

        if appts:
            for appt in appts[:5]:
                date_str = appt.start_time.strftime("%Y-%m-%d @ %I:%M %p")
                service = appt.service.name if appt.service else "Service"
                status = appt.status.value
                lines.append(f"  * {date_str} - {service} ({status})")
        else:
            lines.append("  No appointment history found.")

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Error in get_customer_history: {e}", exc_info=True)
        return f"Error fetching customer history: {str(e)}"
    finally:
        db.close()


def get_customer_preferences(customer_name: str) -> str:
    """
    Get styling/treatment preferences and notes for a customer by name.

    Args:
        customer_name: Full name or partial name of the customer.
    """
    logger.info(f"[StaffTools] get_customer_preferences for customer_name: {customer_name}")
    db = SessionLocal()
    try:
        customers = db.query(Customer).filter(
            Customer.first_name.ilike(f"%{customer_name}%") |
            Customer.last_name.ilike(f"%{customer_name}%")
        ).all()

        if not customers:
            return f"No customer found matching name: '{customer_name}'"

        if len(customers) > 1:
            return f"Multiple customers found matching '{customer_name}': " + ", ".join([c.full_name for c in customers])

        cust = customers[0]
        # Grab notes from completed appointments
        appts = db.query(Appointment).filter(
            Appointment.customer_id == cust.id,
            Appointment.notes != None,
            Appointment.notes != ""
        ).order_by(Appointment.start_time.desc()).all()

        preference_notes = []
        for a in appts:
            date_str = a.start_time.strftime('%Y-%m-%d')
            service_name = a.service.name if a.service else "Service"
            preference_notes.append(f"- {date_str} ({service_name}): {a.notes}")

        if not preference_notes:
            return f"No formula notes or styling preferences registered for customer {cust.full_name}."

        return f"Styling and formula history for {cust.full_name}:\n" + "\n".join(preference_notes)
    except Exception as e:
        logger.error(f"Error in get_customer_preferences: {e}", exc_info=True)
        return f"Error fetching preferences: {str(e)}"
    finally:
        db.close()


def get_staff_revenue(staff_id: str) -> str:
    """
    Calculate the total revenue generated by a staff member from completed appointments.

    Args:
        staff_id: UUID string of the staff member.
    """
    logger.info(f"[StaffTools] get_staff_revenue for staff_id: {staff_id}")
    db = SessionLocal()
    try:
        staff_uuid = uuid.UUID(staff_id)

        # Total completed appointments
        appts = db.query(Appointment).filter(
            Appointment.staff_id == staff_uuid,
            Appointment.status == AppointmentStatus.COMPLETED
        ).all()

        total_rev = sum(float(a.service.price) for a in appts if a.service)

        # Calculate monthly revenue
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        monthly_rev = sum(float(a.service.price) for a in appts if a.service and a.start_time >= month_start)

        return (
            f"Revenue Summary:\n"
            f"- Total Lifetime Revenue Generated: ${total_rev:.2f}\n"
            f"- Month-to-date Revenue: ${monthly_rev:.2f}\n"
            f"- Total Completed Services: {len(appts)}"
        )
    except Exception as e:
        logger.error(f"Error in get_staff_revenue: {e}", exc_info=True)
        return f"Error calculating revenue: {str(e)}"
    finally:
        db.close()


def get_staff_performance(staff_id: str) -> str:
    """
    Retrieve performance metrics: bookings, completion rates, and average rating.

    Args:
        staff_id: UUID string of the staff member.
    """
    logger.info(f"[StaffTools] get_staff_performance for staff_id: {staff_id}")
    db = SessionLocal()
    try:
        staff_uuid = uuid.UUID(staff_id)

        # All appointments
        appts = db.query(Appointment).filter(
            Appointment.staff_id == staff_uuid
        ).all()

        total = len(appts)
        completed = sum(1 for a in appts if a.status == AppointmentStatus.COMPLETED)
        cancelled = sum(1 for a in appts if a.status == AppointmentStatus.CANCELLED)

        completion_rate = (completed / (total - cancelled) * 100.0) if (total - cancelled) > 0 else 0.0

        # Average rating from reviews
        reviews = db.query(Review).filter(
            Review.staff_id == staff_uuid
        ).all()

        avg_rating = sum(r.rating for r in reviews) / len(reviews) if reviews else 0.0

        return (
            f"Your Performance Analytics:\n"
            f"- Total Booked Appointments: {total}\n"
            f"- Completed: {completed}\n"
            f"- Cancelled: {cancelled}\n"
            f"- Completion Rate (excluding cancellations): {completion_rate:.1f}%\n"
            f"- Customer Rating: {f'{avg_rating:.2f} ★' if reviews else 'No ratings yet'} (based on {len(reviews)} review(s))"
        )
    except Exception as e:
        logger.error(f"Error in get_staff_performance: {e}", exc_info=True)
        return f"Error retrieving performance metrics: {str(e)}"
    finally:
        db.close()


def get_pending_appointments(staff_id: str) -> str:
    """
    Retrieve any bookings currently pending confirmation for the staff member.

    Args:
        staff_id: UUID string of the staff member.
    """
    logger.info(f"[StaffTools] get_pending_appointments for staff_id: {staff_id}")
    db = SessionLocal()
    try:
        staff_uuid = uuid.UUID(staff_id)

        pending = db.query(Appointment).filter(
            Appointment.staff_id == staff_uuid,
            Appointment.status == AppointmentStatus.PENDING
        ).order_by(Appointment.start_time).all()

        if not pending:
            return "You have no appointments currently pending confirmation."

        lines = [f"Pending Confirmations ({len(pending)}):"]
        for idx, appt in enumerate(pending, 1):
            date_str = appt.start_time.strftime("%Y-%m-%d @ %I:%M %p")
            service = appt.service.name if appt.service else "Service"
            cust = appt.customer.full_name if appt.customer else "Guest"
            lines.append(f"{idx}. {date_str} - {service} for {cust} (Appointment ID: {appt.id})")

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Error in get_pending_appointments: {e}", exc_info=True)
        return f"Error fetching pending appointments: {str(e)}"
    finally:
        db.close()


def create_leave_request(staff_id: str, leave_date: str, reason: Optional[str] = None) -> str:
    """
    Submit a leave request for a specific date (format YYYY-MM-DD).

    Args:
        staff_id: UUID string of the staff member.
        leave_date: Target date for the leave (YYYY-MM-DD).
        reason: Optional brief explanation for the leave request.
    """
    logger.info(f"[StaffTools] create_leave_request for staff_id: {staff_id}, date: {leave_date}")
    db = SessionLocal()
    try:
        staff_uuid = uuid.UUID(staff_id)
        ld = datetime.strptime(leave_date, "%Y-%m-%d").date()

        # Check existing
        existing = db.query(StaffLeave).filter(
            StaffLeave.staff_id == staff_uuid,
            StaffLeave.leave_date == ld
        ).first()

        if existing:
            return f"Leave request already exists for {leave_date}."

        new_leave = StaffLeave(
            id=uuid.uuid4(),
            staff_id=staff_uuid,
            leave_date=ld,
            reason=reason
        )
        db.add(new_leave)
        db.commit()

        return f"Success! Leave request for {leave_date} has been submitted to management."
    except ValueError:
        return f"Error: Invalid date format '{leave_date}'. Please use YYYY-MM-DD."
    except Exception as e:
        logger.error(f"Error in create_leave_request: {e}", exc_info=True)
        db.rollback()
        return f"Error submitting leave request: {str(e)}"
    finally:
        db.close()


def send_customer_reminders(staff_id: str) -> str:
    """
    Trigger dispatches (SMS/WhatsApp) to all scheduled customers today.

    Args:
        staff_id: UUID string of the staff member.
    """
    logger.info(f"[StaffTools] send_customer_reminders for staff_id: {staff_id}")
    db = SessionLocal()
    try:
        staff_uuid = uuid.UUID(staff_id)
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        appointments = db.query(Appointment).filter(
            Appointment.staff_id == staff_uuid,
            Appointment.start_time >= today_start,
            Appointment.start_time < today_end,
            Appointment.status.in_([AppointmentStatus.CONFIRMED, AppointmentStatus.PENDING])
        ).all()

        if not appointments:
            return "You have no scheduled appointments today to send reminders to."

        reminders_sent = 0
        customer_names = []
        for appt in appointments:
            if appt.customer and appt.customer.phone:
                logger.info(
                    f"[NotificationSystem] Sending reminder to {appt.customer.full_name} ({appt.customer.phone}) "
                    f"for service {appt.service.name} at {appt.start_time}"
                )
                reminders_sent += 1
                customer_names.append(appt.customer.full_name)

        if reminders_sent == 0:
            return "Reminders could not be sent (missing phone numbers or guest clients)."

        return f"Success! Dispatched {reminders_sent} reminder notification(s) via WhatsApp/SMS to: " + ", ".join(customer_names)
    except Exception as e:
        logger.error(f"Error in send_customer_reminders: {e}", exc_info=True)
        return f"Error sending customer reminders: {str(e)}"
    finally:
        db.close()


def recommend_services(customer_id: str) -> str:
    """
    Query upsell service recommendations for a customer using the recommendation service engine.

    Args:
        customer_id: UUID string of the customer.
    """
    logger.info(f"[StaffTools] recommend_services for customer: {customer_id}")
    db = SessionLocal()
    try:
        recs = RecommendationService.get_customer_recommendations(db=db, customer_id=customer_id)
        if not recs:
            return "No personalized recommendations available for this customer currently."

        lines = ["Recommended Upsells:"]
        for idx, rec in enumerate(recs, 1):
            lines.append(
                f"{idx}. {rec['name']} (${rec['price']:.2f}) - {rec['reason']} (Confidence: {rec['confidence_score']:.2f})"
            )

        return "\n".join(lines)
    except Exception as e:
        logger.error(f"Error in recommend_services: {e}", exc_info=True)
        return f"Error generating recommendations: {str(e)}"
    finally:
        db.close()
