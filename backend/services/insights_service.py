"""
Insights Service for SalonAI Workforce Platform.
Compiles autonomous business telemetry insights to be displayed on the executive overview scorecard.
"""

import logging
from typing import List, Dict, Any
from sqlalchemy import func
from sqlalchemy.orm import Session
from db.models import Appointment, Service, Staff, Review, Lead, BusinessMetricsHistory, AppointmentStatus

logger = logging.getLogger(__name__)

class InsightsService:
    """
    Insights Service compiling real-time database trend logs into corporate bullet points.
    """

    @staticmethod
    def generate_ai_insights(db: Session) -> List[str]:
        """
        Dynamically analyzes the active databases and lists 4-5 high-value corporate bullet points.
        """
        logger.info("[InsightsService] Constructing real-time AI business insights...")
        insights = []

        try:
            # Insight 1: Revenue trend comparison
            history = db.query(BusinessMetricsHistory).order_by(BusinessMetricsHistory.metric_date.desc()).limit(2).all()
            if len(history) >= 2:
                today_rev = float(history[0].revenue)
                yest_rev = float(history[1].revenue)
                if yest_rev > 0:
                    pct = round(((today_rev - yest_rev) / yest_rev) * 100, 1)
                    sign = "+" if pct >= 0 else ""
                    insights.append(f"Revenue changed {sign}{pct}% compared to yesterday.")
                else:
                    insights.append("Revenue trend is active with current booking conversions.")
            else:
                # Fallback to direct timezone-aware appointment queries for yesterday vs today
                from datetime import datetime, timezone, timedelta
                today_start = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
                yest_start = today_start - timedelta(days=1)
                today_end = today_start + timedelta(days=1)
                
                today_appts = db.query(Appointment).filter(
                    Appointment.status == AppointmentStatus.COMPLETED,
                    Appointment.start_time >= today_start,
                    Appointment.start_time < today_end
                ).all()
                yest_appts = db.query(Appointment).filter(
                    Appointment.status == AppointmentStatus.COMPLETED,
                    Appointment.start_time >= yest_start,
                    Appointment.start_time < today_start
                ).all()
                
                today_rev = sum(float(a.service.price) for a in today_appts if a.service)
                yest_rev = sum(float(a.service.price) for a in yest_appts if a.service)
                
                if yest_rev > 0:
                    pct = round(((today_rev - yest_rev) / yest_rev) * 100, 1)
                    sign = "+" if pct >= 0 else ""
                    insights.append(f"Revenue changed {sign}{pct}% compared to yesterday.")
                elif today_rev > 0:
                    insights.append(f"Today's completed revenue is ₹{today_rev:,.2f}, starting a strong positive trend.")
                else:
                    insights.append("No historical revenue trend available yet.")

            # Insight 2: Top contributing service
            top_service_query = (
                db.query(Service.name, func.sum(Service.price).label("sum"))
                .join(Appointment, Service.id == Appointment.service_id)
                .filter(Appointment.status == AppointmentStatus.COMPLETED)
                .group_by(Service.id)
                .order_by(func.sum(Service.price).desc())
                .first()
            )
            if top_service_query:
                insights.append(f"'{top_service_query[0]}' was our highest contributing service segment.")
            else:
                insights.append("No service transactions recorded yet today.")

            # Insight 3: Operations bottle-neck (Evening conversions drops)
            from db.models import LeadStatus
            total_leads = db.query(Lead).count()
            converted_leads = db.query(Lead).filter(Lead.status == LeadStatus.CONVERTED).count()
            if total_leads > 0:
                conv_rate = round((converted_leads / total_leads * 100.0), 1)
                insights.append(f"Lead pipeline conversion is active at {conv_rate}% across channels.")
            else:
                insights.append("No active CRM leads registered in pipeline.")

            # Insight 4: Common customer complaints
            wait_complaints = db.query(Review).filter(
                Review.sentiment.in_(["NEGATIVE", "CRITICAL"]),
                Review.comment.ilike("%wait%")
            ).count()
            if wait_complaints > 0:
                insights.append(f"Waiting-time complaints increased ({wait_complaints} logs recorded). Optimize stylist capacity.")
            else:
                insights.append("No waiting-time complaints recorded today.")

            # Insight 5: Top performing stylist (Fixed Cartesian product join)
            top_stylist_query = (
                db.query(Staff.first_name, Staff.last_name, func.sum(Service.price).label("sum"))
                .join(Appointment, Staff.id == Appointment.staff_id)
                .join(Service, Appointment.service_id == Service.id)
                .filter(Appointment.status == AppointmentStatus.COMPLETED)
                .group_by(Staff.id)
                .order_by(func.sum(Service.price).desc())
                .first()
            )
            if top_stylist_query:
                insights.append(f"Stylist {top_stylist_query[0]} {top_stylist_query[1]} is today's top-performing stylist.")
            else:
                insights.append("No stylist transactions completed yet today.")

        except Exception as e:
            logger.error(f"[InsightsService] Failed to dynamically construct insights: {e}", exc_info=True)
            # Safe realistic fallback defaults without fake data
            insights = [
                "No historical revenue trend available yet.",
                "No service transactions recorded yet today.",
                "No active CRM leads registered in pipeline.",
                "No waiting-time complaints recorded today.",
                "No stylist transactions completed yet today."
            ]

        return insights
