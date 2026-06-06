"""
Analytics Service for SalonAI Workforce Platform.
Aggregates performance data across branches, staff, customers, appointments, leads, reviews, and upsells.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy import func, text, desc
from sqlalchemy.orm import Session

from db.models import (
    Appointment, Customer, Service, Staff, Branch, Review, Lead,
    CustomerRecommendation, AppointmentStatus, LeadStatus, ReviewStatus
)

logger = logging.getLogger(__name__)

class AnalyticsService:
    """
    Analytics Service Engine compiling aggregates for role-based dashboards and BI reports.
    """

    @staticmethod
    def get_dashboard_summary(db: Session) -> Dict[str, Any]:
        """
        Calculates today's core business performance indicators.
        """
        logger.info("[AnalyticsService] Generating dashboard summary...")
        
        # Today's boundaries
        today_start = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        # Appointments completed or active today
        appt_query = db.query(Appointment).filter(
            Appointment.start_time >= today_start,
            Appointment.start_time < today_end
        )
        total_appts_today = appt_query.filter(
            Appointment.status != AppointmentStatus.CANCELLED,
            Appointment.status != AppointmentStatus.NO_SHOW
        ).count()
        completed_appts_today = appt_query.filter(Appointment.status == AppointmentStatus.COMPLETED).all()
        
        # Today's revenue
        revenue_today = Decimal("0.00")
        for appt in completed_appts_today:
            if appt.service:
                revenue_today += Decimal(str(appt.service.price))
                
        # New transacting customers today
        new_cust_today = db.query(Customer).filter(
            Customer.created_at >= today_start,
            Customer.created_at < today_end
        ).count()
        
        # Lead conversion rate
        total_leads = db.query(Lead).count()
        converted_leads = db.query(Lead).filter(Lead.status == LeadStatus.CONVERTED).count()
        lead_conv_rate = round((converted_leads / total_leads * 100.0), 1) if total_leads > 0 else 0.0
        
        # Average rating
        avg_rating_val = db.query(func.avg(Review.rating)).filter(Review.status == ReviewStatus.APPROVED).scalar()
        average_rating = round(float(avg_rating_val), 1) if avg_rating_val is not None else 0.0
        
        # Upsell revenue today (accepted recommendations)
        upsell_rev_today = Decimal("0.00")
        accepted_recs = db.query(CustomerRecommendation).filter(
            CustomerRecommendation.accepted == True,
            CustomerRecommendation.created_at >= today_start,
            CustomerRecommendation.created_at < today_end
        ).all()
        for rec in accepted_recs:
            if rec.recommended_service:
                upsell_rev_today += Decimal(str(rec.recommended_service.price))
                
        return {
            "revenue_today": float(revenue_today),
            "appointments_today": total_appts_today,
            "new_customers": new_cust_today,
            "lead_conversion_rate": lead_conv_rate,
            "average_rating": average_rating,
            "upsell_revenue": float(upsell_rev_today)
        }

    @staticmethod
    def get_revenue_summary(db: Session) -> Dict[str, Any]:
        """
        Compiles detailed revenue metrics by service, branch, and staff over time.
        """
        logger.info("[AnalyticsService] Generating revenue intelligence summaries...")
        
        # 1. Total aggregations
        total_query = db.query(Appointment).filter(Appointment.status == AppointmentStatus.COMPLETED).all()
        total_rev = Decimal("0.00")
        for appt in total_query:
            if appt.service:
                total_rev += Decimal(str(appt.service.price))
                
        # Get start dates for boundaries
        now = datetime.now(timezone.utc)
        one_day_ago = now - timedelta(days=1)
        seven_days_ago = now - timedelta(days=7)
        thirty_days_ago = now - timedelta(days=30)
        
        def get_completed_rev(start_date=None):
            q = db.query(func.sum(Service.price)).join(Appointment, Service.id == Appointment.service_id).filter(Appointment.status == AppointmentStatus.COMPLETED)
            if start_date:
                q = q.filter(Appointment.start_time >= start_date)
            val = q.scalar()
            return float(val) if val is not None else 0.0

        today_rev = get_completed_rev(one_day_ago)
        wk_rev = get_completed_rev(seven_days_ago)
        mo_rev = get_completed_rev(thirty_days_ago)
        yr_rev = get_completed_rev()
        
        # Dialect-safe date formatter
        if db.bind and db.bind.dialect.name == "sqlite":
            date_expr = func.strftime("%Y-%m-%d", Appointment.start_time)
        else:
            date_expr = func.to_char(Appointment.start_time, "YYYY-MM-DD")
            
        time_query = (
            db.query(date_expr.label("date"), func.sum(Service.price).label("sum"))
            .join(Service, Appointment.service_id == Service.id)
            .filter(Appointment.status == AppointmentStatus.COMPLETED)
            .group_by(text("date"))
            .order_by(text("date"))
            .all()
        )
        
        labels = [row.date for row in time_query]
        data = [float(row.sum or 0.0) for row in time_query]
        
        # Service breakdown
        service_query = (
            db.query(Service.name, func.sum(Service.price).label("sum"))
            .join(Appointment, Service.id == Appointment.service_id)
            .filter(Appointment.status == AppointmentStatus.COMPLETED)
            .group_by(Service.id)
            .all()
        )
        by_service = {row.name: float(row.sum or 0) for row in service_query}

        # Branch breakdown
        branch_query = (
            db.query(Branch.name, func.sum(Service.price).label("sum"))
            .join(Appointment, Branch.id == Appointment.branch_id)
            .join(Service, Appointment.service_id == Service.id)
            .filter(Appointment.status == AppointmentStatus.COMPLETED)
            .group_by(Branch.id)
            .all()
        )
        by_branch = {row.name: float(row.sum or 0) for row in branch_query}

        # Staff breakdown
        staff_query = (
            db.query(Staff.first_name, Staff.last_name, func.sum(Service.price).label("sum"))
            .join(Appointment, Staff.id == Appointment.staff_id)
            .join(Service, Appointment.service_id == Service.id)
            .filter(Appointment.status == AppointmentStatus.COMPLETED)
            .group_by(Staff.id)
            .all()
        )
        by_staff = {f"{row.first_name} {row.last_name}": float(row.sum or 0) for row in staff_query}

        return {
            "cards": {
                "today_revenue": today_rev,
                "weekly_revenue": wk_rev,
                "monthly_revenue": mo_rev,
                "yearly_revenue": yr_rev,
            },
            "charts": {
                "labels": labels,
                "revenue_over_time": data,
                "by_service": by_service,
                "by_branch": by_branch,
                "by_staff": by_staff
            }
        }

    @staticmethod
    def get_customer_summary(db: Session) -> Dict[str, Any]:
        """
        Aggregates cohort customer details and LTV stats.
        """
        logger.info("[AnalyticsService] Compiling customer intelligence...")
        total_customers = db.query(Customer).count()
        
        # Active and returning counts
        bookings_by_cust = (
            db.query(Appointment.customer_id, func.count(Appointment.id).label("cnt"))
            .filter(Appointment.status == AppointmentStatus.COMPLETED)
            .group_by(Appointment.customer_id)
            .all()
        )
        returning_customers = sum(1 for row in bookings_by_cust if row.cnt >= 2)
        vip_customers = sum(1 for row in bookings_by_cust if row.cnt >= 5)
        
        # Simple customer lifetime value average
        clv_scalar = db.query(func.avg(Service.price)).join(
            Appointment, Service.id == Appointment.service_id
        ).filter(Appointment.status == AppointmentStatus.COMPLETED).scalar()
        avg_clv = round(float(clv_scalar), 2) if clv_scalar is not None else 0.0
        
        # AI Insight stats (inactive in last 90 days)
        limit_date = datetime.now(timezone.utc) - timedelta(days=90)
        recent_bookings = db.query(Appointment.customer_id).filter(
            Appointment.start_time >= limit_date
        ).distinct().all()
        recent_active_ids = {row[0] for row in recent_bookings}
        
        inactive_count = 0
        all_customers = db.query(Customer).all()
        for cust in all_customers:
            if cust.id not in recent_active_ids:
                inactive_count += 1
                
        return {
            "total_customers": total_customers,
            "returning_customers": returning_customers,
            "inactive_customers": inactive_count,
            "vip_customers": vip_customers,
            "customer_lifetime_value": avg_clv
        }

    @staticmethod
    def get_staff_summary(db: Session) -> Dict[str, Any]:
        """
        Aggregates staff metrics benchmark indicators.
        """
        logger.info("[AnalyticsService] Compiling staff intelligence...")
        staff_members = db.query(Staff).filter(Staff.is_active == True).all()
        roster_data = []
        
        for st in staff_members:
            appts = db.query(Appointment).filter(
                Appointment.staff_id == st.id,
                Appointment.status == AppointmentStatus.COMPLETED
            ).all()
            
            revenue = sum(float(a.service.price) for a in appts if a.service)
            rating = db.query(func.avg(Review.rating)).join(
                Appointment, Review.appointment_id == Appointment.id
            ).filter(
                Appointment.staff_id == st.id,
                Review.status == ReviewStatus.APPROVED
            ).scalar()
            
            # Upsell revenue matching
            upsells = db.query(func.sum(Service.price)).join(
                CustomerRecommendation, Service.id == CustomerRecommendation.recommended_service_id
            ).join(
                Appointment, CustomerRecommendation.appointment_id == Appointment.id
            ).filter(
                Appointment.staff_id == st.id,
                CustomerRecommendation.accepted == True
            ).scalar()
            
            roster_data.append({
                "id": str(st.id),
                "email": st.email,
                "name": f"{st.first_name} {st.last_name}",
                "role": st.role,
                "appointments": len(appts),
                "revenue": float(revenue),
                "rating": round(float(rating), 2) if rating is not None else 0.0,
                "upsells": float(upsells) if upsells is not None else 0.0
            })
            
        # Benchmark boundaries
        if roster_data:
            roster_data.sort(key=lambda x: x["revenue"], reverse=True)
            top_performer = roster_data[0]["name"]
            top_revenue = roster_data[0]["revenue"]
            top_appointments = roster_data[0]["appointments"]
            top_rating = roster_data[0]["rating"]
            top_upsells = roster_data[0]["upsells"]
            lowest_performer = roster_data[-1]["name"] if len(roster_data) > 1 else "None"
        else:
            top_performer = "None"
            top_revenue = 0.0
            top_appointments = 0
            top_rating = 0.0
            top_upsells = 0.0
            lowest_performer = "None"
            
        return {
            "top_performer": top_performer,
            "top_revenue": top_revenue,
            "top_appointments": top_appointments,
            "top_rating": top_rating,
            "top_upsells": top_upsells,
            "lowest_performer": lowest_performer,
            "roster": roster_data
        }

    @staticmethod
    def get_lead_summary(db: Session) -> Dict[str, Any]:
        """
        Aggregates CRM leads pipeline conversions.
        """
        logger.info("[AnalyticsService] Compiling lead conversion details...")
        total_leads = db.query(Lead).count()
        new_leads = db.query(Lead).filter(Lead.status == LeadStatus.NEW).count()
        contacted = db.query(Lead).filter(Lead.status == LeadStatus.CONTACTED).count()
        converted = db.query(Lead).filter(Lead.status == LeadStatus.CONVERTED).count()
        lost = db.query(Lead).filter(Lead.status == LeadStatus.LOST).count()
        
        return {
            "new_leads": new_leads,
            "converted_leads": converted,
            "lost_leads": lost,
            "pending_leads": contacted,
            "conversion_rate": round((converted / total_leads * 100.0), 1) if total_leads > 0 else 0.0
        }

    @staticmethod
    def get_review_summary(db: Session) -> Dict[str, Any]:
        """
        Aggregates customer reviews and feedback sentiment.
        """
        logger.info("[AnalyticsService] Compiling reputation shield summary...")
        total_reviews = db.query(Review).count()
        pos_count = db.query(Review).filter(Review.sentiment == "POSITIVE").count()
        neu_count = db.query(Review).filter(Review.sentiment == "NEUTRAL").count()
        neg_count = db.query(Review).filter(Review.sentiment == "NEGATIVE").count()
        crit_count = db.query(Review).filter(Review.sentiment == "CRITICAL").count()
        
        # Average rating
        avg_rating_val = db.query(func.avg(Review.rating)).scalar()
        average_rating = round(float(avg_rating_val), 2) if avg_rating_val is not None else 0.0
        
        # Dynamically resolve primary complaint category from NEGATIVE/CRITICAL comments
        primary_complaint = "None"
        if neg_count > 0 or crit_count > 0:
            bad_reviews = db.query(Review).filter(
                Review.sentiment.in_(["NEGATIVE", "CRITICAL"])
            ).all()
            
            counts = {"Waiting Time": 0, "Pricing": 0, "Staff Behavior": 0, "Cleanliness": 0}
            for r in bad_reviews:
                text = ((r.comment or "") + " " + (r.review_text or "")).lower()
                if any(x in text for x in ["wait", "time", "delay", "slow"]):
                    counts["Waiting Time"] += 1
                if any(x in text for x in ["price", "expensive", "cost", "charge", "money"]):
                    counts["Pricing"] += 1
                if any(x in text for x in ["rude", "staff", "behavior", "attitude", "stylist"]):
                    counts["Staff Behavior"] += 1
                if any(x in text for x in ["dirty", "clean", "hygiene", "mess"]):
                    counts["Cleanliness"] += 1
            
            best_cat = max(counts, key=counts.get)
            if counts[best_cat] > 0:
                primary_complaint = best_cat
            else:
                primary_complaint = "General Service"

        return {
            "total_reviews": total_reviews,
            "average_rating": average_rating,
            "positive_reviews": pos_count,
            "neutral_reviews": neu_count,
            "negative_reviews": neg_count,
            "critical_complaints": crit_count,
            "primary_complaint": primary_complaint
        }

    @staticmethod
    def get_upsell_summary(db: Session) -> Dict[str, Any]:
        """
        Aggregates automated upsells revenue yield.
        """
        logger.info("[AnalyticsService] Compiling upsell yield aggregates...")
        total_recs = db.query(CustomerRecommendation).count()
        accepted_recs = db.query(CustomerRecommendation).filter(CustomerRecommendation.accepted == True).count()
        
        upsell_revenue = Decimal("0.00")
        recs_list = db.query(CustomerRecommendation).filter(CustomerRecommendation.accepted == True).all()
        for r in recs_list:
            if r.recommended_service:
                upsell_revenue += Decimal(str(r.recommended_service.price))
                
        acceptance_rate = round((accepted_recs / total_recs * 100.0), 1) if total_recs > 0 else 0.0
        
        # Find most accepted service
        most_accepted_service = "None"
        most_accepted_q = db.query(Service.name, func.count(CustomerRecommendation.id).label("cnt")).join(
            CustomerRecommendation, Service.id == CustomerRecommendation.recommended_service_id
        ).filter(CustomerRecommendation.accepted == True).group_by(Service.id).order_by(desc("cnt")).first()
        if most_accepted_q:
            most_accepted_service = most_accepted_q.name
            
        return {
            "upsell_revenue": float(upsell_revenue),
            "acceptance_rate": acceptance_rate,
            "accepted_count": accepted_recs,
            "total_offers": total_recs,
            "most_accepted": most_accepted_service
        }

    @staticmethod
    def send_returning_cohort_reminders(db: Session) -> int:
        """
        Sends exactly one daily booking and loyalty reminder to all customers
        in the Returning Cohort (customers with >= 2 completed appointments).
        Returns the number of reminders sent.
        """
        from db.models import User, Notification
        
        logger.info("[AnalyticsService] Executing send_returning_cohort_reminders...")
        
        # 1. Identify Returning Cohort customer IDs (>= 2 completed bookings)
        bookings_by_cust = (
            db.query(Appointment.customer_id, func.count(Appointment.id).label("cnt"))
            .filter(Appointment.status == AppointmentStatus.COMPLETED)
            .group_by(Appointment.customer_id)
            .all()
        )
        returning_cust_ids = [row.customer_id for row in bookings_by_cust if row.cnt >= 2]
        
        if not returning_cust_ids:
            logger.info("[AnalyticsService] No returning cohort customers found.")
            return 0
            
        # 2. Get today's local boundaries
        today_start = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        sent_count = 0
        
        # 3. Iterate over returning customers and check their User accounts
        for cust_id in returning_cust_ids:
            customer = db.query(Customer).filter(Customer.id == cust_id).first()
            if not customer:
                continue
                
            user = db.query(User).filter(User.customer_id == cust_id).first()
            if not user:
                # If no linked user account, we cannot send a dashboard notification
                continue
                
            # 4. Check if a reminder has already been sent to this user today
            existing_notif = db.query(Notification).filter(
                Notification.user_id == user.id,
                Notification.title == "Returning Cohort Daily Reminder",
                Notification.created_at >= today_start,
                Notification.created_at < today_end
            ).first()
            
            if existing_notif:
                # Already sent today
                continue
                
            # 5. Create new daily reminder notification
            notif = Notification(
                user_id=user.id,
                title="Returning Cohort Daily Reminder",
                message=f"Hi {customer.first_name}! As one of our valued returning clients, here is your daily reminder to book your next styling appointment or check your loyalty points balance ({customer.loyalty_points} points). We look forward to seeing you soon!",
                is_read=False,
                is_cleared=False
            )
            db.add(notif)
            sent_count += 1
            
        if sent_count > 0:
            db.commit()
            logger.info(f"[AnalyticsService] Sent {sent_count} daily reminders to Returning Cohort customers.")
        else:
            logger.info("[AnalyticsService] No new daily reminders sent today (already sent or no users).")
            
        return sent_count


def process_returning_cohort_reminders():
    """
    Automated background job to dispatch daily reminders to Returning Cohort customers.
    Executed by the background scheduler.
    """
    from db.database import SessionLocal
    logger.info("⏱️ [Scheduler] Starting automated returning cohort daily reminders...")
    db = SessionLocal()
    try:
        AnalyticsService.send_returning_cohort_reminders(db)
    except Exception as e:
        logger.error(f"[Scheduler] Error running automated returning cohort reminders: {e}", exc_info=True)
    finally:
        db.close()
