"""
Analytics Service for SalonAI Workforce Platform.
Aggregates performance data across branches, staff, customers, appointments, leads, reviews, and upsells.

EXPANDED: Now covers 30+ BI query patterns from basic to advanced including:
- Appointment trends, peak hours, no-show/cancellation analysis
- Branch comparison & multi-location analytics
- Customer acquisition, churn, cohort, LTV deep analysis
- Staff utilization, efficiency scores, upsell conversion
- Revenue per period with comparative analytics
- Service popularity, booking velocity, demand forecasting
- Lead source performance, funnel leakage, reactivation potential
- Operational efficiency, capacity analysis, booking lead time
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta, timezone, date
from decimal import Decimal
from collections import defaultdict
from sqlalchemy import func, text, desc, case, and_, or_, extract
from sqlalchemy.orm import Session

from infrastructure.db.models import (
    Appointment, Customer, Service, Staff, Branch, Review, Lead,
    CustomerRecommendation, AppointmentStatus, LeadStatus, ReviewStatus
)

logger = logging.getLogger(__name__)



from ai.tools.mcp_tool import mcp_execute, mcp_write
from infrastructure.events.event_bus import (
    get_event_bus,
    AppointmentBookedEvent,
)

class AnalyticsService:
    """
    Analytics Service Engine compiling aggregates for role-based dashboards and BI reports.
    Supports 30+ unique business intelligence queries from basic to advanced levels.
    """

    # =========================================================================
    # CORE DASHBOARD (Basic Level)
    # =========================================================================

    @staticmethod
    def get_dashboard_summary(db: Session, period: str = "today") -> Dict[str, Any]:
        """Calculates core business performance indicators for a given time period."""
        logger.info(f"[AnalyticsService] Generating dashboard summary for period: {period}...")

        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Define start date and end date based on the period
        period_lower = str(period).strip().lower()
        if period_lower == "weekly":
            start_date = today_start - timedelta(days=7)
            end_date = today_start + timedelta(days=1)
        elif period_lower == "monthly":
            start_date = today_start - timedelta(days=30)
            end_date = today_start + timedelta(days=1)
        elif period_lower == "yearly":
            start_date = today_start - timedelta(days=365)
            end_date = today_start + timedelta(days=1)
        elif period_lower == "yesterday":
            start_date = today_start - timedelta(days=1)
            end_date = today_start
        else: # today
            start_date = today_start
            end_date = today_start + timedelta(days=1)

        # 1. Appointments
        appt_query = db.query(Appointment).filter(
            Appointment.start_time >= start_date,
            Appointment.start_time < end_date
        )
            
        total_appts = appt_query.filter(
            Appointment.status != AppointmentStatus.CANCELLED,
            Appointment.status != AppointmentStatus.NO_SHOW
        ).count()
        
        completed_appts = appt_query.filter(Appointment.status == AppointmentStatus.COMPLETED).all()

        # 2. Revenue
        revenue = Decimal("0.00")
        for appt in completed_appts:
            if appt.service:
                revenue += Decimal(str(appt.service.price))

        # 3. New Customers
        cust_query = db.query(Customer).filter(
            Customer.created_at >= start_date,
            Customer.created_at < end_date
        )
        new_cust = cust_query.count()

        # 4. Lead Conversion
        total_leads = db.query(Lead).count()
        converted_leads = db.query(Lead).filter(Lead.status == LeadStatus.CONVERTED).count()
        lead_conv_rate = round((converted_leads / total_leads * 100.0), 1) if total_leads > 0 else 0.0

        # 5. Average Rating
        avg_rating_val = db.query(func.avg(Review.rating)).filter(Review.status == ReviewStatus.APPROVED).scalar()
        average_rating = round(float(avg_rating_val), 1) if avg_rating_val is not None else 0.0

        # 6. Upsells
        upsell_rev = Decimal("0.00")
        upsell_query = db.query(CustomerRecommendation).filter(
            CustomerRecommendation.accepted == True,
            CustomerRecommendation.created_at >= start_date,
            CustomerRecommendation.created_at < end_date
        )
        accepted_recs = upsell_query.all()
        
        for rec in accepted_recs:
            if rec.recommended_service:
                upsell_rev += Decimal(str(rec.recommended_service.price))

        # Period-over-period comparison calculation
        wow_pct = 0.0
        comp_start_date = None
        comp_end_date = start_date
        
        if period_lower == "weekly":
            comp_start_date = start_date - timedelta(days=7)
        elif period_lower == "monthly":
            comp_start_date = start_date - timedelta(days=30)
        elif period_lower == "yearly":
            comp_start_date = start_date - timedelta(days=365)
        elif period_lower == "yesterday":
            comp_start_date = start_date - timedelta(days=1)
            comp_end_date = start_date
        else: # today
            comp_start_date = start_date - timedelta(days=7) # Wow same-day
            comp_end_date = comp_start_date + timedelta(days=1)
            
        if comp_start_date:
            comp_appts = db.query(Appointment).filter(
                Appointment.start_time >= comp_start_date,
                Appointment.start_time < comp_end_date,
                Appointment.status == AppointmentStatus.COMPLETED
            ).all()
            comp_revenue = sum(float(a.service.price) for a in comp_appts if a.service)
            if comp_revenue > 0:
                wow_pct = round(((float(revenue) - comp_revenue) / comp_revenue) * 100, 1)

        return {
            "revenue_today": float(revenue),
            "appointments_today": total_appts,
            "new_customers": new_cust,
            "lead_conversion_rate": lead_conv_rate,
            "average_rating": average_rating,
            "upsell_revenue": float(upsell_rev),
            "wow_revenue_change_pct": wow_pct,
            "completed_today": len(completed_appts),
        }

    # =========================================================================
    # REVENUE ANALYTICS (Basic - Intermediate)
    # =========================================================================

    @staticmethod
    def get_revenue_summary(db: Session) -> Dict[str, Any]:
        """Compiles detailed revenue metrics by service, branch, and staff over time."""
        logger.info("[AnalyticsService] Generating revenue intelligence summaries...")



        now = datetime.now(timezone.utc)
        one_day_ago = now - timedelta(days=1)
        seven_days_ago = now - timedelta(days=7)
        thirty_days_ago = now - timedelta(days=30)
        ninety_days_ago = now - timedelta(days=90)

        # Calendar yesterday start/end in UTC
        from datetime import time as dt_time
        today_start_utc = datetime.combine(now.date(), dt_time.min).replace(tzinfo=timezone.utc)
        yesterday_start_utc = today_start_utc - timedelta(days=1)
        yesterday_end_utc = today_start_utc

        def get_completed_rev(start_date=None, end_date=None):
            q = db.query(func.sum(Service.price)).join(
                Appointment, Service.id == Appointment.service_id
            ).filter(Appointment.status == AppointmentStatus.COMPLETED)
            if start_date:
                q = q.filter(Appointment.start_time >= start_date)
            if end_date:
                q = q.filter(Appointment.start_time < end_date)
            val = q.scalar()
            return float(val) if val is not None else 0.0

        today_rev = get_completed_rev(one_day_ago)
        yesterday_rev = get_completed_rev(yesterday_start_utc, yesterday_end_utc)
        wk_rev = get_completed_rev(seven_days_ago)
        mo_rev = get_completed_rev(thirty_days_ago)
        yr_rev = get_completed_rev()
        q90_rev = get_completed_rev(ninety_days_ago)

        # Previous period comparisons for MoM
        prev_mo_start = thirty_days_ago - timedelta(days=30)
        prev_mo_rev = get_completed_rev(prev_mo_start) - mo_rev
        mom_pct = 0.0
        if prev_mo_rev > 0:
            mom_pct = round(((mo_rev - prev_mo_rev) / prev_mo_rev) * 100, 1)

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

        service_query = (
            db.query(Service.name, func.sum(Service.price).label("sum"), func.count(Appointment.id).label("cnt"))
            .join(Appointment, Service.id == Appointment.service_id)
            .filter(Appointment.status == AppointmentStatus.COMPLETED)
            .group_by(Service.id)
            .all()
        )
        by_service = {row.name: float(row.sum or 0) for row in service_query}
        service_booking_counts = {row.name: int(row.cnt or 0) for row in service_query}

        branch_query = (
            db.query(Branch.name, func.sum(Service.price).label("sum"))
            .join(Appointment, Branch.id == Appointment.branch_id)
            .join(Service, Appointment.service_id == Service.id)
            .filter(Appointment.status == AppointmentStatus.COMPLETED)
            .group_by(Branch.id)
            .all()
        )
        by_branch = {row.name: float(row.sum or 0) for row in branch_query}

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
                "yesterday_revenue": yesterday_rev,
                "weekly_revenue": wk_rev,
                "monthly_revenue": mo_rev,
                "quarterly_revenue": q90_rev,
                "yearly_revenue": yr_rev,
                "mom_change_pct": mom_pct,
            },
            "charts": {
                "labels": labels,
                "revenue_over_time": data,
                "by_service": by_service,
                "by_branch": by_branch,
                "by_staff": by_staff,
                "service_booking_counts": service_booking_counts,
            }
        }

    @staticmethod
    def get_revenue_by_period(db: Session, period: str = "monthly") -> Dict[str, Any]:
        """
        Detailed revenue breakdown by period (daily/weekly/monthly/quarterly/yearly).
        Provides period-over-period comparisons for trend analysis.
        """
        logger.info(f"[AnalyticsService] Revenue breakdown by period: {period}")

        now = datetime.now(timezone.utc)

        if period == "daily":
            periods = [(now - timedelta(days=i), now - timedelta(days=i-1)) for i in range(30, 0, -1)]
            period_labels = [(now - timedelta(days=i)).strftime("%b %d") for i in range(30, 0, -1)]
        elif period == "weekly":
            periods = [(now - timedelta(weeks=i), now - timedelta(weeks=i-1)) for i in range(12, 0, -1)]
            period_labels = [f"Week -{i}" for i in range(12, 0, -1)]
        elif period == "quarterly":
            periods = [(now - timedelta(days=90*i), now - timedelta(days=90*(i-1))) for i in range(4, 0, -1)]
            period_labels = [f"Q-{i}" for i in range(4, 0, -1)]
        else:  # monthly
            periods = [(now - timedelta(days=30*i), now - timedelta(days=30*(i-1))) for i in range(12, 0, -1)]
            period_labels = [(now - timedelta(days=30*i)).strftime("%b %Y") for i in range(12, 0, -1)]

        revenue_data = []
        for start, end in periods:
            rev = db.query(func.sum(Service.price)).join(
                Appointment, Service.id == Appointment.service_id
            ).filter(
                Appointment.status == AppointmentStatus.COMPLETED,
                Appointment.start_time >= start,
                Appointment.start_time < end
            ).scalar()
            revenue_data.append(float(rev) if rev else 0.0)

        total_period_rev = sum(revenue_data)
        avg_period_rev = total_period_rev / len(revenue_data) if revenue_data else 0.0
        growth = 0.0
        if len(revenue_data) >= 2 and revenue_data[-2] > 0:
            growth = round(((revenue_data[-1] - revenue_data[-2]) / revenue_data[-2]) * 100, 1)

        return {
            "period": period,
            "labels": period_labels,
            "revenue_data": revenue_data,
            "total": total_period_rev,
            "average_per_period": round(avg_period_rev, 2),
            "latest_period_growth_pct": growth,
            "highest_period": max(revenue_data) if revenue_data else 0.0,
            "lowest_period": min(revenue_data) if revenue_data else 0.0,
        }

    # =========================================================================
    # CUSTOMER ANALYTICS (Basic - Advanced)
    # =========================================================================

    @staticmethod
    def get_customer_summary(db: Session) -> Dict[str, Any]:
        """Aggregates cohort customer details and LTV stats."""
        logger.info("[AnalyticsService] Compiling customer intelligence...")
        total_customers = db.query(Customer).count()

        bookings_by_cust = (
            db.query(Appointment.customer_id, func.count(Appointment.id).label("cnt"))
            .filter(Appointment.status == AppointmentStatus.COMPLETED)
            .group_by(Appointment.customer_id)
            .all()
        )
        returning_customers = sum(1 for row in bookings_by_cust if row.cnt >= 2)
        vip_customers = sum(1 for row in bookings_by_cust if row.cnt >= 5)

        clv_scalar = db.query(func.avg(Service.price)).join(
            Appointment, Service.id == Appointment.service_id
        ).filter(Appointment.status == AppointmentStatus.COMPLETED).scalar()
        avg_clv = round(float(clv_scalar), 2) if clv_scalar is not None else 0.0

        limit_date = datetime.now(timezone.utc) - timedelta(days=90)
        recent_bookings = db.query(Appointment.customer_id).filter(
            Appointment.start_time >= limit_date
        ).distinct().all()
        recent_active_ids = {row[0] for row in recent_bookings}

        active_count = db.query(Customer.id).filter(Customer.id.in_(list(recent_active_ids))).count() if recent_active_ids else 0
        inactive_count = max(0, total_customers - active_count)

        # 30-day new customers
        thirty_ago = datetime.now(timezone.utc) - timedelta(days=30)
        new_last_30 = db.query(Customer).filter(Customer.created_at >= thirty_ago).count()

        # High LTV customers (top spenders)
        top_spenders = (
            db.query(Customer.first_name, Customer.last_name, func.sum(Service.price).label("total_spent"))
            .join(Appointment, Customer.id == Appointment.customer_id)
            .join(Service, Appointment.service_id == Service.id)
            .filter(Appointment.status == AppointmentStatus.COMPLETED)
            .group_by(Customer.id)
            .order_by(func.sum(Service.price).desc())
            .limit(5)
            .all()
        )
        top_ltv = [{"name": f"{r.first_name} {r.last_name}", "ltv": float(r.total_spent or 0)} for r in top_spenders]

        return {
            "total_customers": total_customers,
            "returning_customers": returning_customers,
            "inactive_customers": inactive_count,
            "vip_customers": vip_customers,
            "customer_lifetime_value": avg_clv,
            "new_customers_last_30_days": new_last_30,
            "retention_rate_pct": round((returning_customers / total_customers * 100), 1) if total_customers > 0 else 0.0,
            "top_ltv_customers": top_ltv,
        }

    @staticmethod
    def get_customer_acquisition_analysis(db: Session) -> Dict[str, Any]:
        """
        Analyzes customer acquisition trends, growth velocity, and new-vs-returning split.
        Covers: How many new customers joined? What is the growth rate?
        """
        logger.info("[AnalyticsService] Compiling customer acquisition analysis...")

        now = datetime.now(timezone.utc)
        periods = {
            "last_7_days": now - timedelta(days=7),
            "last_30_days": now - timedelta(days=30),
            "last_90_days": now - timedelta(days=90),
        }

        acquisition = {}
        for label, start in periods.items():
            count = db.query(Customer).filter(Customer.created_at >= start).count()
            acquisition[label] = count

        # Monthly growth rate
        last_month = now - timedelta(days=30)
        prev_month = now - timedelta(days=60)
        this_month_new = db.query(Customer).filter(Customer.created_at >= last_month).count()
        prev_month_new = db.query(Customer).filter(
            Customer.created_at >= prev_month, Customer.created_at < last_month
        ).count()
        mom_growth = 0.0
        if prev_month_new > 0:
            mom_growth = round(((this_month_new - prev_month_new) / prev_month_new) * 100, 1)

        # Daily acquisition trend (last 14 days)
        daily_trend = []
        for i in range(14, 0, -1):
            day_start = now - timedelta(days=i)
            day_end = now - timedelta(days=i-1)
            count = db.query(Customer).filter(
                Customer.created_at >= day_start, Customer.created_at < day_end
            ).count()
            daily_trend.append({"date": day_start.strftime("%b %d"), "new_customers": count})

        total = db.query(Customer).count()
        return {
            "acquisition_by_period": acquisition,
            "mom_growth_pct": mom_growth,
            "daily_trend_14_days": daily_trend,
            "total_customers": total,
            "avg_daily_acquisition": round(acquisition.get("last_30_days", 0) / 30, 1),
        }

    @staticmethod
    def get_churn_analysis(db: Session, inactive_days: int = 90) -> Dict[str, Any]:
        """
        Analyzes customer churn: who stopped coming, when, and what is the churn rate.
        """
        logger.info(f"[AnalyticsService] Churn analysis (inactive > {inactive_days} days)...")

        cutoff = datetime.now(timezone.utc) - timedelta(days=inactive_days)
        total_customers = db.query(Customer).count()

        # Customers who had at least 1 booking
        ever_booked = db.query(Appointment.customer_id).filter(
            Appointment.status == AppointmentStatus.COMPLETED
        ).distinct().count()

        # Customers who had booking before cutoff but not after
        had_booking_before = db.query(Appointment.customer_id).filter(
            Appointment.start_time < cutoff,
            Appointment.status == AppointmentStatus.COMPLETED
        ).distinct()
        had_booking_after = db.query(Appointment.customer_id).filter(
            Appointment.start_time >= cutoff,
            Appointment.status == AppointmentStatus.COMPLETED
        ).distinct()

        before_ids = {r[0] for r in had_booking_before.all()}
        after_ids = {r[0] for r in had_booking_after.all()}
        churned_ids = before_ids - after_ids
        churn_count = len(churned_ids)
        churn_rate = round((churn_count / ever_booked * 100), 1) if ever_booked > 0 else 0.0

        # At-risk customers (had 2+ bookings, not seen in 45 days)
        at_risk_cutoff = datetime.now(timezone.utc) - timedelta(days=45)
        at_risk = 0
        for cid in before_ids:
            if cid not in after_ids:
                count = db.query(Appointment).filter(
                    Appointment.customer_id == cid,
                    Appointment.status == AppointmentStatus.COMPLETED,
                    Appointment.start_time >= cutoff
                ).count()
                if count == 0:
                    at_risk += 1

        return {
            "inactive_threshold_days": inactive_days,
            "total_customers": total_customers,
            "ever_booked": ever_booked,
            "churned_count": churn_count,
            "churn_rate_pct": churn_rate,
            "at_risk_count": at_risk,
            "retained_count": len(after_ids),
            "retention_pct": round((len(after_ids) / ever_booked * 100), 1) if ever_booked > 0 else 0.0,
            "reactivation_opportunity": churn_count,
        }

    @staticmethod
    def get_cohort_analysis(db: Session) -> Dict[str, Any]:
        """
        Cohort retention analysis: tracks how many customers from each month
        came back in subsequent months.
        """
        logger.info("[AnalyticsService] Cohort retention analysis...")

        now = datetime.now(timezone.utc)
        cohorts = {}

        for months_ago in range(6, 0, -1):
            cohort_start = now - timedelta(days=30 * months_ago)
            cohort_end = now - timedelta(days=30 * (months_ago - 1))

            # New customers this month (first booking)
            cohort_customers = db.query(Appointment.customer_id).filter(
                Appointment.start_time >= cohort_start,
                Appointment.start_time < cohort_end,
                Appointment.status == AppointmentStatus.COMPLETED
            ).distinct().all()
            cohort_ids = {r[0] for r in cohort_customers}

            if not cohort_ids:
                continue

            cohort_key = cohort_start.strftime("%b %Y")
            cohort_size = len(cohort_ids)

            returned_next = db.query(Appointment.customer_id).filter(
                Appointment.customer_id.in_(list(cohort_ids)),
                Appointment.start_time >= cohort_end,
                Appointment.status == AppointmentStatus.COMPLETED
            ).distinct().count()

            retention_rate = round((returned_next / cohort_size * 100), 1) if cohort_size > 0 else 0.0
            cohorts[cohort_key] = {
                "cohort_size": cohort_size,
                "returned": returned_next,
                "retention_rate_pct": retention_rate,
            }

        return {
            "cohort_analysis": cohorts,
            "analysis_description": "Shows what % of customers from each month came back in the following period",
        }

    # =========================================================================
    # STAFF ANALYTICS (Basic - Advanced)
    # =========================================================================

    @staticmethod
    def get_staff_summary(db: Session) -> Dict[str, Any]:
        """Aggregates staff metrics benchmark indicators."""
        logger.info("[AnalyticsService] Compiling staff intelligence...")
        staff_members = db.query(Staff).filter(Staff.is_active == True).all()
        roster_data = []

        # Aggregate completed appointments and revenue per staff member
        appt_stats = db.query(
            Appointment.staff_id,
            func.count(Appointment.id).label("completed_count"),
            func.sum(Service.price).label("revenue")
        ).join(Service, Appointment.service_id == Service.id)\
         .filter(Appointment.status == AppointmentStatus.COMPLETED)\
         .group_by(Appointment.staff_id).all()
        appt_stats_map = {row.staff_id: (row.completed_count, float(row.revenue or 0.0)) for row in appt_stats}

        # Aggregate reviews/ratings per staff member
        ratings_stats = db.query(
            Appointment.staff_id,
            func.avg(Review.rating).label("avg_rating")
        ).join(Review, Review.appointment_id == Appointment.id)\
         .filter(Review.status == ReviewStatus.APPROVED)\
         .group_by(Appointment.staff_id).all()
        ratings_map = {row.staff_id: float(row.avg_rating or 0.0) for row in ratings_stats}

        # Aggregate upsells per staff member
        upsells_stats = db.query(
            Appointment.staff_id,
            func.sum(Service.price).label("upsell_revenue")
        ).join(CustomerRecommendation, CustomerRecommendation.appointment_id == Appointment.id)\
         .join(Service, CustomerRecommendation.recommended_service_id == Service.id)\
         .filter(CustomerRecommendation.accepted == True)\
         .group_by(Appointment.staff_id).all()
        upsells_map = {row.staff_id: float(row.upsell_revenue or 0.0) for row in upsells_stats}

        # Aggregate total assigned, no-shows, cancellations per staff member
        assigned_stats = db.query(
            Appointment.staff_id,
            func.count(Appointment.id).label("total_count"),
            func.sum(case((Appointment.status == AppointmentStatus.NO_SHOW, 1), else_=0)).label("no_shows"),
            func.sum(case((Appointment.status == AppointmentStatus.CANCELLED, 1), else_=0)).label("cancellations")
        ).group_by(Appointment.staff_id).all()
        assigned_map = {row.staff_id: (row.total_count, int(row.no_shows or 0), int(row.cancellations or 0)) for row in assigned_stats}

        for st in staff_members:
            completed_count, revenue = appt_stats_map.get(st.id, (0, 0.0))
            rating = ratings_map.get(st.id, 0.0)
            upsells = upsells_map.get(st.id, 0.0)
            total_assigned, no_shows, cancellations = assigned_map.get(st.id, (0, 0, 0))

            roster_data.append({
                "id": str(st.id),
                "email": st.email,
                "name": f"{st.first_name} {st.last_name}",
                "role": st.role,
                "appointments": completed_count,
                "revenue": revenue,
                "rating": round(rating, 2),
                "upsells": upsells,
                "no_shows": no_shows,
                "cancellations": cancellations,
                "total_assigned": total_assigned,
                "utilization_pct": round((completed_count / total_assigned * 100), 1) if total_assigned > 0 else 0.0,
            })

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
    def get_staff_utilization(db: Session, period_days: int = 30) -> Dict[str, Any]:
        """
        Staff utilization analysis: hours booked vs available, efficiency scores.
        Covers: Which stylist is most/least utilized? Capacity optimization?
        """
        logger.info(f"[AnalyticsService] Staff utilization for last {period_days} days...")

        cutoff = datetime.now(timezone.utc) - timedelta(days=period_days)
        staff_members = db.query(Staff).filter(Staff.is_active == True).all()

        utilization_data = []
        for st in staff_members:
            completed = db.query(Appointment).filter(
                Appointment.staff_id == st.id,
                Appointment.start_time >= cutoff,
                Appointment.status == AppointmentStatus.COMPLETED
            ).all()

            cancelled = db.query(Appointment).filter(
                Appointment.staff_id == st.id,
                Appointment.start_time >= cutoff,
                Appointment.status == AppointmentStatus.CANCELLED
            ).count()

            no_show = db.query(Appointment).filter(
                Appointment.staff_id == st.id,
                Appointment.start_time >= cutoff,
                Appointment.status == AppointmentStatus.NO_SHOW
            ).count()

            total_booked = db.query(Appointment).filter(
                Appointment.staff_id == st.id,
                Appointment.start_time >= cutoff,
            ).count()

            # Estimate working hours (8 hrs/day, 5 days/week for the period)
            working_days = max(int(period_days * 5 / 7), 1)
            available_slots = working_days * 8  # rough hourly slots
            booked_hours = sum(
                (a.end_time - a.start_time).total_seconds() / 3600
                for a in completed
                if a.end_time and a.start_time
            )
            if booked_hours == 0:
                # Fallback: estimate by service duration
                booked_hours = sum(
                    (a.service.duration_minutes / 60) for a in completed if a.service
                )

            utilization_pct = round((booked_hours / available_slots * 100), 1) if available_slots > 0 else 0.0
            revenue = sum(float(a.service.price) for a in completed if a.service)

            utilization_data.append({
                "name": f"{st.first_name} {st.last_name}",
                "role": st.role,
                "completed_appointments": len(completed),
                "cancelled_count": cancelled,
                "no_show_count": no_show,
                "total_assigned": total_booked,
                "estimated_booked_hours": round(booked_hours, 1),
                "utilization_pct": min(utilization_pct, 100.0),
                "revenue_generated": revenue,
                "revenue_per_hour": round(revenue / booked_hours, 2) if booked_hours > 0 else 0.0,
            })

        utilization_data.sort(key=lambda x: x["utilization_pct"], reverse=True)
        return {
            "period_days": period_days,
            "staff_utilization": utilization_data,
            "most_utilized": utilization_data[0]["name"] if utilization_data else "None",
            "least_utilized": utilization_data[-1]["name"] if len(utilization_data) > 1 else "None",
            "avg_utilization_pct": round(
                sum(s["utilization_pct"] for s in utilization_data) / len(utilization_data), 1
            ) if utilization_data else 0.0,
        }

    # =========================================================================
    # APPOINTMENT ANALYTICS (Intermediate - Advanced)
    # =========================================================================

    @staticmethod
    def get_appointment_trends(db: Session, period_days: int = 30) -> Dict[str, Any]:
        """
        Appointment volume trends over time with day-of-week and hour analysis.
        Covers: When are we busiest? What's our booking velocity?
        """
        logger.info(f"[AnalyticsService] Appointment trends for last {period_days} days...")

        cutoff = datetime.now(timezone.utc) - timedelta(days=period_days)
        now = datetime.now(timezone.utc)

        # Daily appointment counts
        daily_counts = []
        for i in range(period_days, 0, -1):
            day_start = now - timedelta(days=i)
            day_end = now - timedelta(days=i-1)
            count = db.query(Appointment).filter(
                Appointment.start_time >= day_start,
                Appointment.start_time < day_end,
                Appointment.status != AppointmentStatus.CANCELLED
            ).count()
            daily_counts.append({
                "date": day_start.strftime("%b %d"),
                "count": count
            })

        # Status breakdown
        status_breakdown = {}
        for status in AppointmentStatus:
            count = db.query(Appointment).filter(
                Appointment.start_time >= cutoff,
                Appointment.status == status
            ).count()
            status_breakdown[status.value] = count

        total = sum(status_breakdown.values())
        completion_rate = round((status_breakdown.get("COMPLETED", 0) / total * 100), 1) if total > 0 else 0.0
        no_show_rate = round((status_breakdown.get("NO_SHOW", 0) / total * 100), 1) if total > 0 else 0.0
        cancellation_rate = round((status_breakdown.get("CANCELLED", 0) / total * 100), 1) if total > 0 else 0.0

        return {
            "period_days": period_days,
            "daily_trend": daily_counts,
            "status_breakdown": status_breakdown,
            "total_appointments": total,
            "completion_rate_pct": completion_rate,
            "no_show_rate_pct": no_show_rate,
            "cancellation_rate_pct": cancellation_rate,
            "avg_daily_appointments": round(total / period_days, 1),
        }

    @staticmethod
    def get_peak_hours_analysis(db: Session) -> Dict[str, Any]:
        """
        Peak hour and peak day analysis for appointments.
        Covers: When is the salon busiest? Optimal staffing times?
        """
        logger.info("[AnalyticsService] Peak hours analysis...")

        all_appts = db.query(Appointment).filter(
            Appointment.status != AppointmentStatus.CANCELLED
        ).all()

        hourly_counts = defaultdict(int)
        daily_counts = defaultdict(int)
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        for appt in all_appts:
            if appt.start_time:
                try:
                    dt = appt.start_time
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    hourly_counts[dt.hour] += 1
                    daily_counts[dt.weekday()] += 1
                except Exception:
                    pass

        hourly_data = [{"hour": f"{h:02d}:00", "count": hourly_counts.get(h, 0)} for h in range(7, 22)]
        daily_data = [{"day": day_names[d], "count": daily_counts.get(d, 0)} for d in range(7)]

        peak_hour = max(hourly_counts, key=hourly_counts.get, default=10)
        peak_day = max(daily_counts, key=daily_counts.get, default=5)

        return {
            "hourly_distribution": hourly_data,
            "daily_distribution": daily_data,
            "peak_hour": f"{peak_hour:02d}:00",
            "peak_day": day_names[peak_day] if daily_counts else "Saturday",
            "busiest_hour_count": hourly_counts.get(peak_hour, 0),
            "busiest_day_count": daily_counts.get(peak_day, 0),
            "recommendation": f"Peak traffic at {peak_hour:02d}:00 on {day_names[peak_day]}. Ensure maximum staff coverage."
        }

    @staticmethod
    def get_no_show_analysis(db: Session) -> Dict[str, Any]:
        """
        No-show and cancellation analysis with trend data.
        Covers: What is our no-show rate? Which services/staff have most no-shows?
        """
        logger.info("[AnalyticsService] No-show and cancellation analysis...")

        total = db.query(Appointment).count()
        no_shows = db.query(Appointment).filter(Appointment.status == AppointmentStatus.NO_SHOW).count()
        cancellations = db.query(Appointment).filter(Appointment.status == AppointmentStatus.CANCELLED).count()

        ns_rate = round((no_shows / total * 100), 2) if total > 0 else 0.0
        cancel_rate = round((cancellations / total * 100), 2) if total > 0 else 0.0

        # No-shows by service
        ns_by_service = (
            db.query(Service.name, func.count(Appointment.id).label("cnt"))
            .join(Appointment, Service.id == Appointment.service_id)
            .filter(Appointment.status == AppointmentStatus.NO_SHOW)
            .group_by(Service.id)
            .order_by(func.count(Appointment.id).desc())
            .limit(5)
            .all()
        )

        # No-shows by staff
        ns_by_staff = (
            db.query(Staff.first_name, Staff.last_name, func.count(Appointment.id).label("cnt"))
            .join(Appointment, Staff.id == Appointment.staff_id)
            .filter(Appointment.status == AppointmentStatus.NO_SHOW)
            .group_by(Staff.id)
            .order_by(func.count(Appointment.id).desc())
            .limit(5)
            .all()
        )

        # Revenue lost from no-shows
        ns_appts = db.query(Appointment).filter(Appointment.status == AppointmentStatus.NO_SHOW).all()
        revenue_lost = sum(float(a.service.price) for a in ns_appts if a.service)

        cancel_appts = db.query(Appointment).filter(Appointment.status == AppointmentStatus.CANCELLED).all()
        revenue_lost_cancel = sum(float(a.service.price) for a in cancel_appts if a.service)

        return {
            "total_appointments": total,
            "no_shows": no_shows,
            "cancellations": cancellations,
            "no_show_rate_pct": ns_rate,
            "cancellation_rate_pct": cancel_rate,
            "revenue_lost_to_no_shows": revenue_lost,
            "revenue_lost_to_cancellations": revenue_lost_cancel,
            "total_revenue_lost": revenue_lost + revenue_lost_cancel,
            "top_no_show_services": [{"service": r.name, "count": r.cnt} for r in ns_by_service],
            "top_no_show_staff": [{"staff": f"{r.first_name} {r.last_name}", "count": r.cnt} for r in ns_by_staff],
            "recommendation": (
                "High no-show rate detected. Consider SMS/WhatsApp reminders 24h before appointments "
                "and introduce a deposit policy." if ns_rate > 10 else "No-show rate within acceptable range."
            )
        }

    # =========================================================================
    # LEAD & CRM ANALYTICS (Intermediate - Advanced)
    # =========================================================================

    @staticmethod
    def get_lead_summary(db: Session) -> Dict[str, Any]:
        """Aggregates CRM leads pipeline conversions."""
        logger.info("[AnalyticsService] Compiling lead conversion details...")
        total_leads = db.query(Lead).count()
        new_leads = db.query(Lead).filter(Lead.status == LeadStatus.NEW).count()
        contacted = db.query(Lead).filter(Lead.status == LeadStatus.CONTACTED).count()
        interested = db.query(Lead).filter(Lead.status == LeadStatus.INTERESTED).count()
        converted = db.query(Lead).filter(Lead.status == LeadStatus.CONVERTED).count()
        lost = db.query(Lead).filter(Lead.status == LeadStatus.LOST).count()

        # 30-day window
        thirty_ago = datetime.now(timezone.utc) - timedelta(days=30)
        new_last_30 = db.query(Lead).filter(Lead.created_at >= thirty_ago).count()
        converted_last_30 = db.query(Lead).filter(
            Lead.status == LeadStatus.CONVERTED, Lead.created_at >= thirty_ago
        ).count()
        conv_rate_30 = round((converted_last_30 / new_last_30 * 100), 1) if new_last_30 > 0 else 0.0

        return {
            "new_leads": new_leads,
            "contacted_leads": contacted,
            "interested_leads": interested,
            "converted_leads": converted,
            "lost_leads": lost,
            "pending_leads": contacted,
            "total_leads": total_leads,
            "conversion_rate": round((converted / total_leads * 100.0), 1) if total_leads > 0 else 0.0,
            "new_last_30_days": new_last_30,
            "conv_rate_last_30_days": conv_rate_30,
            "funnel_leakage_pct": round((lost / total_leads * 100), 1) if total_leads > 0 else 0.0,
        }

    @staticmethod
    def get_lead_pipeline_analysis(db: Session) -> Dict[str, Any]:
        """
        Deep lead pipeline analysis: funnel visualization, service preferences, 
        average time to convert, and win/loss patterns.
        """
        logger.info("[AnalyticsService] Deep lead pipeline analysis...")

        total = db.query(Lead).count()
        stages = {
            "NEW": db.query(Lead).filter(Lead.status == LeadStatus.NEW).count(),
            "CONTACTED": db.query(Lead).filter(Lead.status == LeadStatus.CONTACTED).count(),
            "INTERESTED": db.query(Lead).filter(Lead.status == LeadStatus.INTERESTED).count(),
            "CONVERTED": db.query(Lead).filter(Lead.status == LeadStatus.CONVERTED).count(),
            "LOST": db.query(Lead).filter(Lead.status == LeadStatus.LOST).count(),
        }

        # Funnel conversion rates per stage
        funnel_rates = {}
        prev = total
        for stage, count in stages.items():
            funnel_rates[stage] = round((count / prev * 100), 1) if prev > 0 else 0.0
            prev = count if count > 0 else prev

        # Top requested services by leads
        service_demand = (
            db.query(Lead.service_name, func.count(Lead.id).label("cnt"))
            .filter(Lead.service_name.isnot(None))
            .group_by(Lead.service_name)
            .order_by(func.count(Lead.id).desc())
            .limit(10)
            .all()
        )

        # Win rate
        win_rate = round((stages["CONVERTED"] / total * 100), 1) if total > 0 else 0.0
        loss_rate = round((stages["LOST"] / total * 100), 1) if total > 0 else 0.0

        return {
            "funnel_stages": stages,
            "funnel_rates": funnel_rates,
            "win_rate_pct": win_rate,
            "loss_rate_pct": loss_rate,
            "top_demanded_services": [{"service": r.service_name, "demand_count": r.cnt} for r in service_demand],
            "active_pipeline": stages["NEW"] + stages["CONTACTED"] + stages["INTERESTED"],
            "pipeline_health": "Healthy" if win_rate > 20 else "At Risk - Low conversion",
        }

    # =========================================================================
    # SERVICE ANALYTICS (Intermediate)
    # =========================================================================

    @staticmethod
    def get_service_popularity(db: Session) -> Dict[str, Any]:
        """
        Service popularity analysis: most/least booked services, revenue per service,
        booking frequency, and customer preference mapping.
        """
        logger.info("[AnalyticsService] Service popularity analytics...")

        service_data = (
            db.query(
                Service.name,
                Service.price,
                Service.duration_minutes,
                func.count(Appointment.id).label("bookings"),
                func.sum(Service.price).label("total_revenue"),
                func.avg(Review.rating).label("avg_rating")
            )
            .outerjoin(Appointment, Service.id == Appointment.service_id)
            .outerjoin(Review, and_(Review.appointment_id == Appointment.id, Review.status == ReviewStatus.APPROVED))
            .filter(or_(Appointment.status == AppointmentStatus.COMPLETED, Appointment.id.is_(None)))
            .group_by(Service.id)
            .order_by(func.count(Appointment.id).desc())
            .all()
        )

        services = []
        for row in service_data:
            services.append({
                "service": row.name,
                "price": float(row.price),
                "duration_mins": row.duration_minutes,
                "total_bookings": int(row.bookings or 0),
                "total_revenue": float(row.total_revenue or 0),
                "avg_rating": round(float(row.avg_rating), 1) if row.avg_rating else 0.0,
                "revenue_per_booking": round(float(row.price), 2),
            })

        most_popular = services[0]["service"] if services else "None"
        least_popular = services[-1]["service"] if len(services) > 1 else "None"
        top_revenue_service = max(services, key=lambda x: x["total_revenue"])["service"] if services else "None"

        return {
            "services": services,
            "most_popular_service": most_popular,
            "least_popular_service": least_popular,
            "highest_revenue_service": top_revenue_service,
            "total_services": len(services),
        }

    # =========================================================================
    # REVIEW & REPUTATION ANALYTICS
    # =========================================================================

    @staticmethod
    def get_review_summary(db: Session) -> Dict[str, Any]:
        """Aggregates customer reviews and feedback sentiment."""
        logger.info("[AnalyticsService] Compiling reputation shield summary...")
        total_reviews = db.query(Review).count()
        pos_count = db.query(Review).filter(Review.sentiment == "POSITIVE").count()
        neu_count = db.query(Review).filter(Review.sentiment == "NEUTRAL").count()
        neg_count = db.query(Review).filter(Review.sentiment == "NEGATIVE").count()
        crit_count = db.query(Review).filter(Review.sentiment == "CRITICAL").count()

        avg_rating_val = db.query(func.avg(Review.rating)).scalar()
        average_rating = round(float(avg_rating_val), 2) if avg_rating_val is not None else 0.0

        primary_complaint = "None"
        if neg_count > 0 or crit_count > 0:
            bad_reviews = db.query(Review).filter(
                Review.sentiment.in_(["NEGATIVE", "CRITICAL"])
            ).all()

            counts = {"Waiting Time": 0, "Pricing": 0, "Staff Behavior": 0, "Cleanliness": 0}
            for r in bad_reviews:
                text_val = ((r.comment or "") + " " + (r.review_text or "")).lower()
                if any(x in text_val for x in ["wait", "time", "delay", "slow"]):
                    counts["Waiting Time"] += 1
                if any(x in text_val for x in ["price", "expensive", "cost", "charge", "money"]):
                    counts["Pricing"] += 1
                if any(x in text_val for x in ["rude", "staff", "behavior", "attitude", "stylist"]):
                    counts["Staff Behavior"] += 1
                if any(x in text_val for x in ["dirty", "clean", "hygiene", "mess"]):
                    counts["Cleanliness"] += 1

            best_cat = max(counts, key=counts.get)
            primary_complaint = best_cat if counts[best_cat] > 0 else "General Service"

        # Rating distribution
        rating_dist = {}
        for rating in range(1, 6):
            cnt = db.query(Review).filter(Review.rating == rating).count()
            rating_dist[f"{rating}_star"] = cnt

        return {
            "total_reviews": total_reviews,
            "average_rating": average_rating,
            "positive_reviews": pos_count,
            "neutral_reviews": neu_count,
            "negative_reviews": neg_count,
            "critical_complaints": crit_count,
            "primary_complaint": primary_complaint,
            "rating_distribution": rating_dist,
            "positive_rate_pct": round((pos_count / total_reviews * 100), 1) if total_reviews > 0 else 0.0,
            "nps_score": round(((pos_count - neg_count - crit_count) / total_reviews * 100), 1) if total_reviews > 0 else 0.0,
        }

    @staticmethod
    def get_review_trends(db: Session, period_days: int = 30) -> Dict[str, Any]:
        """
        Review sentiment trends over time. Tracks if reputation is improving or declining.
        """
        logger.info(f"[AnalyticsService] Review trends for last {period_days} days...")

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=period_days)
        prev_cutoff = cutoff - timedelta(days=period_days)

        # Current period
        curr_reviews = db.query(Review).filter(Review.created_at >= cutoff).all()
        curr_avg = sum(r.rating for r in curr_reviews) / len(curr_reviews) if curr_reviews else 0.0

        # Previous period
        prev_reviews = db.query(Review).filter(
            Review.created_at >= prev_cutoff, Review.created_at < cutoff
        ).all()
        prev_avg = sum(r.rating for r in prev_reviews) / len(prev_reviews) if prev_reviews else 0.0

        trend_pct = 0.0
        if prev_avg > 0:
            trend_pct = round(((curr_avg - prev_avg) / prev_avg) * 100, 1)

        # Weekly breakdown
        weekly = []
        for i in range(4, 0, -1):
            wk_start = now - timedelta(weeks=i)
            wk_end = now - timedelta(weeks=i-1)
            wk_reviews = db.query(Review).filter(
                Review.created_at >= wk_start, Review.created_at < wk_end
            ).all()
            wk_avg = sum(r.rating for r in wk_reviews) / len(wk_reviews) if wk_reviews else 0.0
            weekly.append({
                "week": wk_start.strftime("W/E %b %d"),
                "count": len(wk_reviews),
                "avg_rating": round(wk_avg, 2),
            })

        return {
            "period_days": period_days,
            "current_period_reviews": len(curr_reviews),
            "current_avg_rating": round(curr_avg, 2),
            "previous_avg_rating": round(prev_avg, 2),
            "rating_trend_pct": trend_pct,
            "weekly_breakdown": weekly,
            "trend_direction": "Improving" if trend_pct > 0 else ("Stable" if trend_pct == 0 else "Declining"),
        }

    # =========================================================================
    # UPSELL ANALYTICS
    # =========================================================================

    @staticmethod
    def get_upsell_summary(db: Session) -> Dict[str, Any]:
        """Aggregates automated upsells revenue yield."""
        logger.info("[AnalyticsService] Compiling upsell yield aggregates...")
        total_recs = db.query(CustomerRecommendation).count()
        accepted_recs = db.query(CustomerRecommendation).filter(CustomerRecommendation.accepted == True).count()

        upsell_revenue = Decimal("0.00")
        recs_list = db.query(CustomerRecommendation).filter(CustomerRecommendation.accepted == True).all()
        for r in recs_list:
            if r.recommended_service:
                upsell_revenue += Decimal(str(r.recommended_service.price))

        acceptance_rate = round((accepted_recs / total_recs * 100.0), 1) if total_recs > 0 else 0.0

        most_accepted_q = db.query(Service.name, func.count(CustomerRecommendation.id).label("cnt")).join(
            CustomerRecommendation, Service.id == CustomerRecommendation.recommended_service_id
        ).filter(CustomerRecommendation.accepted == True).group_by(Service.id).order_by(desc("cnt")).first()

        most_accepted_service = most_accepted_q.name if most_accepted_q else "None"

        # Top upsell performers by staff
        upsell_by_staff = (
            db.query(Staff.first_name, Staff.last_name, func.count(CustomerRecommendation.id).label("cnt"))
            .join(Appointment, Appointment.staff_id == Staff.id)
            .join(CustomerRecommendation, CustomerRecommendation.appointment_id == Appointment.id)
            .filter(CustomerRecommendation.accepted == True)
            .group_by(Staff.id)
            .order_by(func.count(CustomerRecommendation.id).desc())
            .limit(5)
            .all()
        )

        return {
            "upsell_revenue": float(upsell_revenue),
            "acceptance_rate": acceptance_rate,
            "accepted_count": accepted_recs,
            "total_offers": total_recs,
            "most_accepted": most_accepted_service,
            "top_upselling_staff": [{"name": f"{r.first_name} {r.last_name}", "upsells": r.cnt} for r in upsell_by_staff],
        }

    @staticmethod
    def get_upsell_conversion_analysis(db: Session) -> Dict[str, Any]:
        """
        Deep upsell conversion analysis by service, staff, and time.
        Covers: Which upsells convert best? Revenue impact analysis?
        """
        logger.info("[AnalyticsService] Upsell conversion deep analysis...")

        # By recommended service
        by_service = (
            db.query(
                Service.name,
                func.count(CustomerRecommendation.id).label("total_offers"),
                func.sum(case((CustomerRecommendation.accepted == True, 1), else_=0)).label("accepted"),
                func.sum(case((CustomerRecommendation.accepted == True, Service.price), else_=0)).label("revenue")
            )
            .join(CustomerRecommendation, Service.id == CustomerRecommendation.recommended_service_id)
            .group_by(Service.id)
            .all()
        )

        service_conv = []
        for row in by_service:
            total = int(row.total_offers or 0)
            accepted = int(row.accepted or 0)
            rate = round((accepted / total * 100), 1) if total > 0 else 0.0
            service_conv.append({
                "service": row.name,
                "total_offers": total,
                "accepted": accepted,
                "conversion_rate_pct": rate,
                "revenue_generated": float(row.revenue or 0),
            })

        service_conv.sort(key=lambda x: x["conversion_rate_pct"], reverse=True)

        total_offers = db.query(CustomerRecommendation).count()
        total_accepted = db.query(CustomerRecommendation).filter(CustomerRecommendation.accepted == True).count()
        overall_rate = round((total_accepted / total_offers * 100), 1) if total_offers > 0 else 0.0

        return {
            "overall_acceptance_rate_pct": overall_rate,
            "by_service_conversion": service_conv,
            "best_converting_service": service_conv[0]["service"] if service_conv else "None",
            "worst_converting_service": service_conv[-1]["service"] if len(service_conv) > 1 else "None",
            "total_upsell_offers": total_offers,
            "total_accepted": total_accepted,
        }

    # =========================================================================
    # BRANCH / MULTI-LOCATION ANALYTICS (Advanced)
    # =========================================================================

    @staticmethod
    def get_branch_comparison(db: Session) -> Dict[str, Any]:
        """
        Multi-branch performance comparison.
        Covers: Which branch performs best? Revenue per branch? Customer satisfaction by location?
        """
        logger.info("[AnalyticsService] Branch comparison analytics...")

        branches = db.query(Branch).filter(Branch.is_active == True).all()
        branch_data = []

        for branch in branches:
            # Revenue
            rev = db.query(func.sum(Service.price)).join(
                Appointment, Service.id == Appointment.service_id
            ).filter(
                Appointment.branch_id == branch.id,
                Appointment.status == AppointmentStatus.COMPLETED
            ).scalar()

            # Appointment counts
            completed = db.query(Appointment).filter(
                Appointment.branch_id == branch.id,
                Appointment.status == AppointmentStatus.COMPLETED
            ).count()
            cancelled = db.query(Appointment).filter(
                Appointment.branch_id == branch.id,
                Appointment.status == AppointmentStatus.CANCELLED
            ).count()
            no_shows = db.query(Appointment).filter(
                Appointment.branch_id == branch.id,
                Appointment.status == AppointmentStatus.NO_SHOW
            ).count()

            # Average rating
            avg_rating = db.query(func.avg(Review.rating)).join(
                Appointment, Review.appointment_id == Appointment.id
            ).filter(
                Appointment.branch_id == branch.id,
                Review.status == ReviewStatus.APPROVED
            ).scalar()

            # Staff count
            staff_count = db.query(Staff).filter(
                Staff.branch_id == branch.id, Staff.is_active == True
            ).count()

            # Unique customers
            unique_customers = db.query(Appointment.customer_id).filter(
                Appointment.branch_id == branch.id
            ).distinct().count()

            branch_data.append({
                "branch_id": str(branch.id),
                "branch_name": branch.name,
                "city": branch.city,
                "revenue": float(rev) if rev else 0.0,
                "completed_appointments": completed,
                "cancelled_count": cancelled,
                "no_show_count": no_shows,
                "average_rating": round(float(avg_rating), 2) if avg_rating else 0.0,
                "staff_count": staff_count,
                "unique_customers": unique_customers,
                "revenue_per_staff": round(float(rev) / staff_count, 2) if rev and staff_count > 0 else 0.0,
            })

        branch_data.sort(key=lambda x: x["revenue"], reverse=True)
        top_branch = branch_data[0]["branch_name"] if branch_data else "None"
        lowest_branch = branch_data[-1]["branch_name"] if len(branch_data) > 1 else "None"

        return {
            "branches": branch_data,
            "top_performing_branch": top_branch,
            "lowest_performing_branch": lowest_branch,
            "total_branches": len(branch_data),
        }

    # =========================================================================
    # OPERATIONAL EFFICIENCY ANALYTICS (Advanced)
    # =========================================================================

    @staticmethod
    def get_booking_lead_time_analysis(db: Session) -> Dict[str, Any]:
        """
        Booking lead time analysis: how far in advance do customers book?
        Covers: Advance booking patterns, same-day bookings, rush hour patterns.
        """
        logger.info("[AnalyticsService] Booking lead time analysis...")

        appts = db.query(Appointment).filter(
            Appointment.status == AppointmentStatus.COMPLETED,
            Appointment.created_at.isnot(None)
        ).all()

        if not appts:
            return {"message": "No completed appointments with creation timestamp found."}

        lead_times = []
        same_day = 0
        next_day = 0
        week_ahead = 0
        more_than_week = 0

        for appt in appts:
            try:
                if appt.start_time and appt.created_at:
                    start = appt.start_time
                    created = appt.created_at
                    if start.tzinfo is None:
                        start = start.replace(tzinfo=timezone.utc)
                    if created.tzinfo is None:
                        created = created.replace(tzinfo=timezone.utc)
                    lead_hours = (start - created).total_seconds() / 3600
                    if lead_hours >= 0:
                        lead_times.append(lead_hours)
                        if lead_hours < 24:
                            same_day += 1
                        elif lead_hours < 48:
                            next_day += 1
                        elif lead_hours < 168:
                            week_ahead += 1
                        else:
                            more_than_week += 1
            except Exception:
                pass

        avg_lead_hours = sum(lead_times) / len(lead_times) if lead_times else 0.0
        total = len(lead_times)

        return {
            "average_lead_time_hours": round(avg_lead_hours, 1),
            "average_lead_time_days": round(avg_lead_hours / 24, 1),
            "same_day_bookings": same_day,
            "next_day_bookings": next_day,
            "week_ahead_bookings": week_ahead,
            "more_than_week_ahead": more_than_week,
            "total_analyzed": total,
            "pct_same_day": round((same_day / total * 100), 1) if total > 0 else 0.0,
            "recommendation": (
                "High same-day bookings. Consider incentivizing advance scheduling." if total > 0 and same_day / total > 0.3
                else "Healthy advance booking patterns."
            )
        }

    @staticmethod
    def get_capacity_analysis(db: Session) -> Dict[str, Any]:
        """
        Salon capacity analysis: compare total available slots vs booked slots.
        Covers: Capacity utilization, free slots, over-booking risk?
        """
        logger.info("[AnalyticsService] Capacity utilization analysis...")

        now = datetime.now(timezone.utc)
        thirty_ago = now - timedelta(days=30)

        total_appts = db.query(Appointment).filter(
            Appointment.start_time >= thirty_ago
        ).count()
        completed = db.query(Appointment).filter(
            Appointment.start_time >= thirty_ago,
            Appointment.status == AppointmentStatus.COMPLETED
        ).count()
        pending = db.query(Appointment).filter(
            Appointment.start_time >= thirty_ago,
            Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED])
        ).count()
        cancelled = db.query(Appointment).filter(
            Appointment.start_time >= thirty_ago,
            Appointment.status == AppointmentStatus.CANCELLED
        ).count()
        no_show = db.query(Appointment).filter(
            Appointment.start_time >= thirty_ago,
            Appointment.status == AppointmentStatus.NO_SHOW
        ).count()

        staff_count = db.query(Staff).filter(Staff.is_active == True).count()
        # Estimate: 8 hrs/day, 5 days/week, 30 days = ~120 slots per staff
        total_capacity_slots = staff_count * 120
        utilization_pct = round((completed / total_capacity_slots * 100), 1) if total_capacity_slots > 0 else 0.0

        return {
            "period": "Last 30 days",
            "total_appointments_scheduled": total_appts,
            "completed_appointments": completed,
            "pending_appointments": pending,
            "cancelled_count": cancelled,
            "no_show_count": no_show,
            "active_staff_count": staff_count,
            "estimated_total_capacity_slots": total_capacity_slots,
            "capacity_utilization_pct": min(utilization_pct, 100.0),
            "wasted_capacity_pct": round(((cancelled + no_show) / total_appts * 100), 1) if total_appts > 0 else 0.0,
            "recommendation": (
                "Low capacity utilization. Marketing campaigns recommended." if utilization_pct < 50
                else ("Near peak capacity. Consider adding staff." if utilization_pct > 85
                      else "Capacity utilization is optimal.")
            )
        }

    # =========================================================================
    # ADVANCED REVENUE & FINANCIAL ANALYTICS
    # =========================================================================

    @staticmethod
    def get_revenue_per_staff_analysis(db: Session, period_days: int = 30) -> Dict[str, Any]:
        """
        Revenue per staff member analysis: which staff generates most revenue?
        Covers: Revenue efficiency, earnings per appointment, revenue per hour.
        """
        logger.info(f"[AnalyticsService] Revenue per staff for last {period_days} days...")

        cutoff = datetime.now(timezone.utc) - timedelta(days=period_days)
        staff_members = db.query(Staff).filter(Staff.is_active == True).all()

        staff_revenue = []
        for st in staff_members:
            appts = db.query(Appointment).filter(
                Appointment.staff_id == st.id,
                Appointment.start_time >= cutoff,
                Appointment.status == AppointmentStatus.COMPLETED
            ).all()

            revenue = sum(float(a.service.price) for a in appts if a.service)
            avg_ticket = revenue / len(appts) if appts else 0.0

            # Estimate hours
            booked_hours = sum(
                (a.service.duration_minutes / 60) for a in appts if a.service
            )
            revenue_per_hour = round(revenue / booked_hours, 2) if booked_hours > 0 else 0.0

            staff_revenue.append({
                "name": f"{st.first_name} {st.last_name}",
                "role": st.role,
                "total_revenue": revenue,
                "appointment_count": len(appts),
                "average_ticket_value": round(avg_ticket, 2),
                "estimated_hours": round(booked_hours, 1),
                "revenue_per_hour": revenue_per_hour,
            })

        staff_revenue.sort(key=lambda x: x["total_revenue"], reverse=True)
        total_revenue = sum(s["total_revenue"] for s in staff_revenue)

        return {
            "period_days": period_days,
            "staff_revenue_analysis": staff_revenue,
            "total_staff_revenue": total_revenue,
            "top_earner": staff_revenue[0]["name"] if staff_revenue else "None",
            "avg_revenue_per_staff": round(total_revenue / len(staff_revenue), 2) if staff_revenue else 0.0,
        }

    @staticmethod
    def get_average_ticket_analysis(db: Session) -> Dict[str, Any]:
        """
        Average ticket (AOV) analysis: what is the average transaction value?
        Trend analysis of ticket value over time.
        """
        logger.info("[AnalyticsService] Average ticket analysis...")

        overall_avg = db.query(func.avg(Service.price)).join(
            Appointment, Service.id == Appointment.service_id
        ).filter(Appointment.status == AppointmentStatus.COMPLETED).scalar()

        overall_aov = round(float(overall_avg), 2) if overall_avg else 0.0

        # By period
        now = datetime.now(timezone.utc)
        periods = {
            "last_7_days": now - timedelta(days=7),
            "last_30_days": now - timedelta(days=30),
            "last_90_days": now - timedelta(days=90),
        }
        aov_by_period = {}
        for label, start in periods.items():
            val = db.query(func.avg(Service.price)).join(
                Appointment, Service.id == Appointment.service_id
            ).filter(
                Appointment.status == AppointmentStatus.COMPLETED,
                Appointment.start_time >= start
            ).scalar()
            aov_by_period[label] = round(float(val), 2) if val else 0.0

        # By service category
        by_service = (
            db.query(Service.name, func.avg(Service.price).label("avg_price"), func.count(Appointment.id).label("cnt"))
            .join(Appointment, Service.id == Appointment.service_id)
            .filter(Appointment.status == AppointmentStatus.COMPLETED)
            .group_by(Service.id)
            .order_by(func.avg(Service.price).desc())
            .all()
        )

        return {
            "overall_aov": overall_aov,
            "aov_by_period": aov_by_period,
            "by_service": [{"service": r.name, "avg_price": round(float(r.avg_price), 2), "bookings": int(r.cnt)} for r in by_service],
            "highest_ticket_service": by_service[0].name if by_service else "None",
        }

    # =========================================================================
    # COHORT REMINDERS
    # =========================================================================

    @staticmethod
    def send_returning_cohort_reminders(db: Session) -> int:
        """
        Sends exactly one daily booking and loyalty reminder to all customers
        in the Returning Cohort (customers with >= 2 completed appointments).
        """
        from infrastructure.db.models import User, Notification

        logger.info("[AnalyticsService] Executing send_returning_cohort_reminders...")

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

        today_start = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        today_start_utc = today_start.astimezone(timezone.utc).replace(tzinfo=None)
        today_end_utc = today_end.astimezone(timezone.utc).replace(tzinfo=None)

        sent_count = 0

        for cust_id in returning_cust_ids:
            customer = db.query(Customer).filter(Customer.id == cust_id).first()
            if not customer:
                continue

            user = db.query(User).filter(User.customer_id == cust_id).first()
            if not user:
                continue

            existing_notif = db.query(Notification).filter(
                Notification.user_id == user.id,
                Notification.title == "Returning Cohort Daily Reminder",
                Notification.created_at >= today_start_utc,
                Notification.created_at < today_end_utc
            ).first()

            if existing_notif:
                continue

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

    # =========================================================================
    # COMPREHENSIVE BUSINESS OVERVIEW (Advanced)
    # =========================================================================

    @staticmethod
    def get_executive_scorecard(db: Session) -> Dict[str, Any]:
        """
        Complete executive scorecard combining all KPIs into one view.
        Covers: C-suite view — all critical metrics at a glance.
        """
        logger.info("[AnalyticsService] Compiling executive scorecard...")

        now = datetime.now(timezone.utc)
        thirty_ago = now - timedelta(days=30)
        prev_thirty = thirty_ago - timedelta(days=30)

        # Revenue
        curr_rev = db.query(func.sum(Service.price)).join(
            Appointment, Service.id == Appointment.service_id
        ).filter(
            Appointment.status == AppointmentStatus.COMPLETED,
            Appointment.start_time >= thirty_ago
        ).scalar()
        prev_rev = db.query(func.sum(Service.price)).join(
            Appointment, Service.id == Appointment.service_id
        ).filter(
            Appointment.status == AppointmentStatus.COMPLETED,
            Appointment.start_time >= prev_thirty,
            Appointment.start_time < thirty_ago
        ).scalar()
        curr_rev = float(curr_rev) if curr_rev else 0.0
        prev_rev = float(prev_rev) if prev_rev else 0.0
        rev_growth = round(((curr_rev - prev_rev) / prev_rev * 100), 1) if prev_rev > 0 else 0.0

        # Customers
        total_cust = db.query(Customer).count()
        new_cust_30 = db.query(Customer).filter(Customer.created_at >= thirty_ago).count()

        # Appointments
        completed_30 = db.query(Appointment).filter(
            Appointment.status == AppointmentStatus.COMPLETED,
            Appointment.start_time >= thirty_ago
        ).count()
        no_shows_30 = db.query(Appointment).filter(
            Appointment.status == AppointmentStatus.NO_SHOW,
            Appointment.start_time >= thirty_ago
        ).count()

        # Rating
        avg_rating = db.query(func.avg(Review.rating)).filter(Review.status == ReviewStatus.APPROVED).scalar()
        avg_rating = round(float(avg_rating), 2) if avg_rating else 0.0

        # Leads
        total_leads = db.query(Lead).count()
        converted = db.query(Lead).filter(Lead.status == LeadStatus.CONVERTED).count()
        conv_rate = round((converted / total_leads * 100), 1) if total_leads > 0 else 0.0

        # Upsell
        total_recs = db.query(CustomerRecommendation).count()
        accepted_recs = db.query(CustomerRecommendation).filter(CustomerRecommendation.accepted == True).count()
        upsell_rate = round((accepted_recs / total_recs * 100), 1) if total_recs > 0 else 0.0

        return {
            "executive_scorecard": {
                "revenue_last_30_days": curr_rev,
                "revenue_growth_mom_pct": rev_growth,
                "total_customers": total_cust,
                "new_customers_last_30_days": new_cust_30,
                "completed_appointments_30_days": completed_30,
                "no_show_count_30_days": no_shows_30,
                "average_rating": avg_rating,
                "lead_conversion_rate_pct": conv_rate,
                "total_leads": total_leads,
                "upsell_acceptance_rate_pct": upsell_rate,
                "health_score": _calculate_health_score(
                    rev_growth, avg_rating, conv_rate, upsell_rate
                ),
            },
            "period": "Last 30 days",
            "generated_at": now.isoformat(),
        }

    # =========================================================================
    # DOMAIN REPRESENTATION & AGENT DELEGATION METHODS
    # =========================================================================

    def __init__(self) -> None:
        self._event_bus = get_event_bus()
        logger.info("AnalyticsService (Application Layer) initialised.")

    def get_dashboard(self, tenant_id: str = "default") -> Dict[str, Any]:
        logger.info("AnalyticsService.get_dashboard | tenant_id=%s", tenant_id)
        from ai.agents.bi_agent import get_dashboard_summary as bi_get_dashboard_summary
        try:
            data = bi_get_dashboard_summary()
            return {"success": True, "data": data}
        except Exception as exc:
            logger.exception("AnalyticsService.get_dashboard | error | tenant_id=%s | %s", tenant_id, exc)
            return {"success": False, "error": str(exc)}

    def get_revenue(self, tenant_id: str = "default") -> Dict[str, Any]:
        logger.info("AnalyticsService.get_revenue | tenant_id=%s", tenant_id)
        from ai.agents.bi_agent import get_revenue_summary as bi_get_revenue_summary
        try:
            data = bi_get_revenue_summary()
            return {"success": True, "data": data}
        except Exception as exc:
            logger.exception("AnalyticsService.get_revenue | error | tenant_id=%s | %s", tenant_id, exc)
            return {"success": False, "error": str(exc)}

    def get_customer_metrics(self, tenant_id: str = "default") -> Dict[str, Any]:
        logger.info("AnalyticsService.get_customer_metrics | tenant_id=%s", tenant_id)
        from ai.agents.bi_agent import get_customer_summary as bi_get_customer_summary
        try:
            data = bi_get_customer_summary()
            return {"success": True, "data": data}
        except Exception as exc:
            logger.exception("AnalyticsService.get_customer_metrics | error | tenant_id=%s | %s", tenant_id, exc)
            return {"success": False, "error": str(exc)}

    def get_staff_performance_summary(self, tenant_id: str = "default") -> Dict[str, Any]:
        logger.info("AnalyticsService.get_staff_performance_summary | tenant_id=%s", tenant_id)
        from ai.agents.bi_agent import get_staff_summary as bi_get_staff_summary
        try:
            data = bi_get_staff_summary()
            return {"success": True, "data": data}
        except Exception as exc:
            logger.exception("AnalyticsService.get_staff_performance_summary | error | tenant_id=%s | %s", tenant_id, exc)
            return {"success": False, "error": str(exc)}

    def get_lead_analytics(self, tenant_id: str = "default") -> Dict[str, Any]:
        logger.info("AnalyticsService.get_lead_analytics | tenant_id=%s", tenant_id)
        from ai.agents.bi_agent import get_lead_summary as bi_get_lead_summary
        try:
            data = bi_get_lead_summary()
            return {"success": True, "data": data}
        except Exception as exc:
            logger.exception("AnalyticsService.get_lead_analytics | error | tenant_id=%s | %s", tenant_id, exc)
            return {"success": False, "error": str(exc)}

    def get_review_analytics_summary(self, tenant_id: str = "default") -> Dict[str, Any]:
        logger.info("AnalyticsService.get_review_analytics_summary | tenant_id=%s", tenant_id)
        from ai.agents.bi_agent import get_review_summary as bi_get_review_summary
        try:
            data = bi_get_review_summary()
            return {"success": True, "data": data}
        except Exception as exc:
            logger.exception("AnalyticsService.get_review_analytics_summary | error | tenant_id=%s | %s", tenant_id, exc)
            return {"success": False, "error": str(exc)}

    def get_upsell_analytics(self, tenant_id: str = "default") -> Dict[str, Any]:
        logger.info("AnalyticsService.get_upsell_analytics | tenant_id=%s", tenant_id)
        from ai.agents.bi_agent import get_upsell_summary as bi_get_upsell_summary
        try:
            data = bi_get_upsell_summary()
            return {"success": True, "data": data}
        except Exception as exc:
            logger.exception("AnalyticsService.get_upsell_analytics | error | tenant_id=%s | %s", tenant_id, exc)
            return {"success": False, "error": str(exc)}

    def get_forecast(self, tenant_id: str = "default") -> Dict[str, Any]:
        logger.info("AnalyticsService.get_forecast | tenant_id=%s", tenant_id)
        from ai.agents.bi_agent import forecast_revenue as bi_forecast_revenue
        try:
            data = bi_forecast_revenue()
            return {"success": True, "data": data}
        except Exception as exc:
            logger.exception("AnalyticsService.get_forecast | error | tenant_id=%s | %s", tenant_id, exc)
            return {"success": False, "error": str(exc)}

    def get_insights(self, tenant_id: str = "default") -> Dict[str, Any]:
        logger.info("AnalyticsService.get_insights | tenant_id=%s", tenant_id)
        from ai.agents.bi_agent import generate_ai_insights as bi_generate_ai_insights
        try:
            data = bi_generate_ai_insights()
            return {"success": True, "data": data}
        except Exception as exc:
            logger.exception("AnalyticsService.get_insights | error | tenant_id=%s | %s", tenant_id, exc)
            return {"success": False, "error": str(exc)}

    def handle_appointment_booked_event(self, event: AppointmentBookedEvent) -> None:
        logger.info("AnalyticsService.handle_appointment_booked_event | event_id=%s", getattr(event, "event_id", "?"))
        try:
            payload: Dict[str, Any] = event.payload or {}
            tenant_id = payload.get("tenant_id", "default")
            appointment_id = payload.get("appointment_id")

            import json
            mcp_write(
                resource="analytics_records",
                operation="insert",
                data={
                    "metric_name": "appointment_booked",
                    "metric_value": 1.0,
                    "dimensions": json.dumps({
                        "appointment_id": str(appointment_id) if appointment_id else None,
                        "tenant_id": tenant_id
                    })
                },
            )
            logger.info("AnalyticsService.handle_appointment_booked_event | metric incremented | appointment_id=%s tenant_id=%s", appointment_id, tenant_id)
        except Exception as exc:
            logger.exception("AnalyticsService.handle_appointment_booked_event | error | %s", exc)


# Singleton factory
_analytics_service_instance = None

def get_analytics_service() -> AnalyticsService:
    global _analytics_service_instance
    if _analytics_service_instance is None:
        _analytics_service_instance = AnalyticsService()
    return _analytics_service_instance

def register_event_subscribers() -> None:
    svc = get_analytics_service()
    bus = get_event_bus()
    bus.subscribe(AppointmentBookedEvent, svc.handle_appointment_booked_event)
    logger.info("AnalyticsService | registered subscriber for AppointmentBookedEvent")


def _calculate_health_score(rev_growth: float, avg_rating: float, conv_rate: float, upsell_rate: float) -> str:
    """Calculate a simple business health score."""
    score = 0
    if rev_growth > 0:
        score += 25
    if avg_rating >= 4.0:
        score += 25
    if conv_rate >= 20:
        score += 25
    if upsell_rate >= 30:
        score += 25

    if score >= 75:
        return "Excellent"
    elif score >= 50:
        return "Good"
    elif score >= 25:
        return "Fair"
    else:
        return "Needs Attention"


def process_returning_cohort_reminders():
    """
    Automated background job to dispatch daily reminders to Returning Cohort customers.
    """
    from infrastructure.db.database import SessionLocal
    logger.info("⏱️ [Scheduler] Starting automated returning cohort daily reminders...")
    db = SessionLocal()
    try:
        AnalyticsService.send_returning_cohort_reminders(db)
    except Exception as e:
        logger.error(f"[Scheduler] Error running automated returning cohort reminders: {e}", exc_info=True)
    finally:
        db.close()
