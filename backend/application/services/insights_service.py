"""
Insights Service for SalonAI Workforce Platform.
Compiles autonomous business telemetry insights to be displayed on the executive overview scorecard.

EXPANDED: Now generates 10+ dynamic insights across revenue, customers, staff, leads, operations.
"""

import logging
from typing import List, Dict, Any
from datetime import datetime, timezone, timedelta
from sqlalchemy import func
from sqlalchemy.orm import Session
from infrastructure.db.models import (
    Appointment, Service, Staff, Review, Lead, Customer,
    CustomerRecommendation, BusinessMetricsHistory, AppointmentStatus,
    LeadStatus, ReviewStatus
)

logger = logging.getLogger(__name__)


class InsightsService:
    """
    Insights Service compiling real-time database trend logs into corporate bullet points.
    Generates 10+ unique insights for any business state.
    """

    @staticmethod
    def generate_ai_insights(db: Session) -> List[str]:
        """
        Dynamically analyzes the active databases and lists 8-10 high-value corporate bullet points.
        Covers: revenue trends, top services, lead pipeline, staff performance, customer retention,
        upsell opportunities, no-show alerts, capacity, review sentiment, and growth recommendations.
        """
        logger.info("[InsightsService] Constructing real-time AI business insights...")
        insights = []

        try:
            now = datetime.now(timezone.utc)
            today_start = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
            yest_start = today_start - timedelta(days=1)
            today_end = today_start + timedelta(days=1)
            thirty_ago = now - timedelta(days=30)
            prev_thirty = thirty_ago - timedelta(days=30)

            # ---------------------------------------------------------------
            # INSIGHT 1: Revenue trend (today vs yesterday OR monthly vs prev month)
            # ---------------------------------------------------------------
            history = db.query(BusinessMetricsHistory).order_by(BusinessMetricsHistory.metric_date.desc()).limit(2).all()
            if len(history) >= 2:
                today_rev = float(history[0].revenue)
                yest_rev = float(history[1].revenue)
                if yest_rev > 0:
                    pct = round(((today_rev - yest_rev) / yest_rev) * 100, 1)
                    sign = "+" if pct >= 0 else ""
                    insights.append(f"📈 Revenue changed {sign}{pct}% compared to yesterday (₹{today_rev:,.0f} vs ₹{yest_rev:,.0f}).")
                else:
                    insights.append(f"💰 Revenue trend is active. Today's revenue: ₹{today_rev:,.0f}.")
            else:
                # Monthly comparison
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
                if prev_rev > 0:
                    pct = round(((curr_rev - prev_rev) / prev_rev) * 100, 1)
                    sign = "+" if pct >= 0 else ""
                    insights.append(f"📈 Monthly revenue is {sign}{pct}% vs previous month (₹{curr_rev:,.0f} this month).")
                elif curr_rev > 0:
                    insights.append(f"💰 Current month revenue stands at ₹{curr_rev:,.0f} — strong positive trend.")
                else:
                    insights.append("📊 Revenue tracking active. Book more appointments to grow revenue.")

            # ---------------------------------------------------------------
            # INSIGHT 2: Top contributing service
            # ---------------------------------------------------------------
            top_service_q = (
                db.query(Service.name, func.sum(Service.price).label("total"), func.count(Appointment.id).label("cnt"))
                .join(Appointment, Service.id == Appointment.service_id)
                .filter(Appointment.status == AppointmentStatus.COMPLETED)
                .group_by(Service.id)
                .order_by(func.sum(Service.price).desc())
                .first()
            )
            if top_service_q:
                insights.append(
                    f"⭐ '{top_service_q.name}' is the highest-revenue service (₹{float(top_service_q.total):,.0f} from {top_service_q.cnt} bookings)."
                )
            else:
                insights.append("📋 No completed service transactions recorded yet.")

            # ---------------------------------------------------------------
            # INSIGHT 3: Lead pipeline health
            # ---------------------------------------------------------------
            total_leads = db.query(Lead).count()
            converted = db.query(Lead).filter(Lead.status == LeadStatus.CONVERTED).count()
            lost = db.query(Lead).filter(Lead.status == LeadStatus.LOST).count()
            new_leads = db.query(Lead).filter(Lead.status == LeadStatus.NEW).count()
            if total_leads > 0:
                conv_rate = round((converted / total_leads * 100.0), 1)
                loss_rate = round((lost / total_leads * 100.0), 1)
                if conv_rate < 15:
                    insights.append(
                        f"⚠️ Lead conversion is low at {conv_rate}% ({converted}/{total_leads}). "
                        f"{new_leads} new leads need immediate follow-up. Loss rate: {loss_rate}%."
                    )
                else:
                    insights.append(
                        f"✅ Lead pipeline conversion: {conv_rate}% ({converted}/{total_leads} leads converted). "
                        f"{new_leads} fresh leads in pipeline."
                    )
            else:
                insights.append("📋 No active CRM leads in pipeline. Launch a lead capture campaign.")

            # ---------------------------------------------------------------
            # INSIGHT 4: Customer retention alert
            # ---------------------------------------------------------------
            limit_date = now - timedelta(days=90)
            recent_active = db.query(Appointment.customer_id).filter(
                Appointment.start_time >= limit_date
            ).distinct().count()
            total_customers = db.query(Customer).count()
            if total_customers > 0:
                inactive_count = total_customers - recent_active
                inactive_pct = round((inactive_count / total_customers * 100), 1)
                if inactive_pct > 40:
                    insights.append(
                        f"🚨 {inactive_pct}% of customers ({inactive_count}/{total_customers}) haven't visited in 90+ days. "
                        "Trigger a reactivation campaign immediately."
                    )
                else:
                    insights.append(
                        f"👥 Customer retention: {round((recent_active / total_customers * 100), 1)}% are active in the last 90 days. "
                        f"Total base: {total_customers} customers."
                    )
            else:
                insights.append("👥 No customers registered yet. Promote booking channels.")

            # ---------------------------------------------------------------
            # INSIGHT 5: Top performing stylist
            # ---------------------------------------------------------------
            top_stylist_q = (
                db.query(Staff.first_name, Staff.last_name, func.sum(Service.price).label("rev"), func.count(Appointment.id).label("cnt"))
                .join(Appointment, Staff.id == Appointment.staff_id)
                .join(Service, Appointment.service_id == Service.id)
                .filter(Appointment.status == AppointmentStatus.COMPLETED)
                .group_by(Staff.id)
                .order_by(func.sum(Service.price).desc())
                .first()
            )
            if top_stylist_q:
                insights.append(
                    f"🏆 {top_stylist_q.first_name} {top_stylist_q.last_name} is the top-performing stylist "
                    f"with ₹{float(top_stylist_q.rev):,.0f} revenue across {top_stylist_q.cnt} appointments."
                )
            else:
                insights.append("👤 No stylist performance data recorded yet.")

            # ---------------------------------------------------------------
            # INSIGHT 6: No-show / cancellation alert
            # ---------------------------------------------------------------
            total_appts = db.query(Appointment).count()
            no_shows = db.query(Appointment).filter(Appointment.status == AppointmentStatus.NO_SHOW).count()
            cancels = db.query(Appointment).filter(Appointment.status == AppointmentStatus.CANCELLED).count()
            if total_appts > 0:
                ns_rate = round((no_shows / total_appts * 100), 1)
                cancel_rate = round((cancels / total_appts * 100), 1)
                revenue_lost_ns = db.query(func.sum(Service.price)).join(
                    Appointment, Service.id == Appointment.service_id
                ).filter(Appointment.status == AppointmentStatus.NO_SHOW).scalar()
                revenue_lost_ns = float(revenue_lost_ns) if revenue_lost_ns else 0.0
                if ns_rate > 10:
                    insights.append(
                        f"⚠️ No-show rate is {ns_rate}% ({no_shows} no-shows). Revenue lost: ₹{revenue_lost_ns:,.0f}. "
                        "Send automated reminders 24h before appointments."
                    )
                else:
                    insights.append(
                        f"✅ No-show rate under control at {ns_rate}% ({no_shows} no-shows). "
                        f"Cancellation rate: {cancel_rate}%."
                    )

            # ---------------------------------------------------------------
            # INSIGHT 7: Upsell opportunity
            # ---------------------------------------------------------------
            total_recs = db.query(CustomerRecommendation).count()
            accepted_recs = db.query(CustomerRecommendation).filter(CustomerRecommendation.accepted == True).count()
            upsell_rev = db.query(func.sum(Service.price)).join(
                CustomerRecommendation, Service.id == CustomerRecommendation.recommended_service_id
            ).filter(CustomerRecommendation.accepted == True).scalar()
            upsell_rev = float(upsell_rev) if upsell_rev else 0.0
            if total_recs > 0:
                acceptance_rate = round((accepted_recs / total_recs * 100), 1)
                if acceptance_rate < 20:
                    insights.append(
                        f"💡 Upsell acceptance rate is low at {acceptance_rate}% ({accepted_recs}/{total_recs}). "
                        "Train staff on personalized recommendation techniques. Potential additional revenue untapped."
                    )
                else:
                    insights.append(
                        f"💰 Upsell engine generated ₹{upsell_rev:,.0f} with {acceptance_rate}% acceptance ({accepted_recs}/{total_recs} offers accepted)."
                    )
            else:
                insights.append("💡 No upsell recommendations recorded yet. Enable the upsell engine.")

            # ---------------------------------------------------------------
            # INSIGHT 8: Reputation / Review alert
            # ---------------------------------------------------------------
            avg_rating = db.query(func.avg(Review.rating)).filter(Review.status == ReviewStatus.APPROVED).scalar()
            critical_reviews = db.query(Review).filter(Review.sentiment == "CRITICAL").count()
            neg_reviews = db.query(Review).filter(Review.sentiment == "NEGATIVE").count()
            total_reviews = db.query(Review).count()
            if avg_rating:
                avg_rating_f = round(float(avg_rating), 2)
                if avg_rating_f < 3.5:
                    insights.append(
                        f"🚨 Average rating is critically low at {avg_rating_f}★. "
                        f"{critical_reviews} critical and {neg_reviews} negative reviews need immediate response."
                    )
                elif avg_rating_f >= 4.5:
                    insights.append(
                        f"⭐ Excellent reputation: average rating {avg_rating_f}★ across {total_reviews} reviews. "
                        "Maintain quality to protect this competitive advantage."
                    )
                else:
                    insights.append(
                        f"⭐ Customer satisfaction at {avg_rating_f}★ ({total_reviews} reviews). "
                        f"{critical_reviews} critical reviews require follow-up."
                    )
            else:
                insights.append("⭐ No approved reviews yet. Encourage customers to leave reviews.")

            # ---------------------------------------------------------------
            # INSIGHT 9: Capacity & Peak hours
            # ---------------------------------------------------------------
            from collections import defaultdict
            all_appts_recent = db.query(Appointment).filter(
                Appointment.start_time >= thirty_ago,
                Appointment.status != AppointmentStatus.CANCELLED
            ).all()
            hourly_counts = defaultdict(int)
            for a in all_appts_recent:
                if a.start_time:
                    try:
                        dt = a.start_time
                        if hasattr(dt, 'hour'):
                            hourly_counts[dt.hour] += 1
                    except Exception:
                        pass
            if hourly_counts:
                peak_hour = max(hourly_counts, key=hourly_counts.get)
                insights.append(
                    f"⏰ Peak booking hour: {peak_hour:02d}:00 ({hourly_counts[peak_hour]} appointments in last 30 days). "
                    "Ensure maximum staff coverage during peak times."
                )
            else:
                insights.append("⏰ Not enough appointment data yet to determine peak hours.")

            # ---------------------------------------------------------------
            # INSIGHT 10: VIP customer opportunity
            # ---------------------------------------------------------------
            vip_count = 0
            bookings_by_cust = (
                db.query(Appointment.customer_id, func.count(Appointment.id).label("cnt"))
                .filter(Appointment.status == AppointmentStatus.COMPLETED)
                .group_by(Appointment.customer_id)
                .all()
            )
            vip_count = sum(1 for row in bookings_by_cust if row.cnt >= 5)
            returning_count = sum(1 for row in bookings_by_cust if row.cnt >= 2)
            if vip_count > 0:
                insights.append(
                    f"👑 {vip_count} VIP customers (5+ visits) driving significant LTV. "
                    f"{returning_count} returning customers (2+ visits). "
                    "Consider a loyalty rewards program to increase retention."
                )
            else:
                insights.append("👑 Build VIP loyalty: no customers have reached 5+ visits yet. Start a loyalty program.")

        except Exception as e:
            logger.error(f"[InsightsService] Failed to dynamically construct insights: {e}", exc_info=True)
            # Do not fabricate specific-sounding business claims here — a failed
            # computation must not be presented as if it were real analysis.
            insights = [
                "⚠️ AI insights could not be generated right now due to a data error. "
                "Please retry, or check the dashboard/revenue reports directly for current figures.",
            ]

        return insights
