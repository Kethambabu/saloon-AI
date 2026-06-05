"""
Business Metrics RAG Service for SalonAI Workforce Platform.
Caches and retrieves historical daily performance snapshots for multi-dimensional business context mapping.
"""

import logging
import uuid
from typing import Dict, Any, List
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.orm import Session
from db.models import BusinessMetricsHistory

logger = logging.getLogger(__name__)

class RAGService:
    """
    RAG service compiling daily operational records into an structured narrative 
    providing high-fidelity contextual trends to the BI Agent.
    """

    @staticmethod
    def capture_daily_snapshot(
        db: Session,
        revenue: float,
        appointments: int,
        lead_conversion: float,
        average_rating: float,
        upsell_revenue: float,
        top_service: str,
        top_staff: str
    ) -> Dict[str, Any]:
        """
        Creates and commits a new daily BusinessMetricsHistory record.
        """
        logger.info("[RAGService] Capturing daily business intelligence snapshot...")
        today_date = datetime.now().date()
        
        # Check if snapshot already exists for today
        existing = db.query(BusinessMetricsHistory).filter(BusinessMetricsHistory.metric_date == today_date).first()
        if existing:
            existing.revenue = Decimal(str(revenue))
            existing.appointments = appointments
            existing.lead_conversion = lead_conversion
            existing.average_rating = average_rating
            existing.upsell_revenue = Decimal(str(upsell_revenue))
            existing.top_service = top_service
            existing.top_staff = top_staff
            db.commit()
            return {"success": True, "message": "Updated existing snapshot for today."}

        snapshot_id = uuid.uuid4()
        db_snap = BusinessMetricsHistory(
            id=snapshot_id,
            metric_date=today_date,
            revenue=Decimal(str(revenue)),
            appointments=appointments,
            lead_conversion=lead_conversion,
            average_rating=average_rating,
            upsell_revenue=Decimal(str(upsell_revenue)),
            top_service=top_service,
            top_staff=top_staff,
            created_at=datetime.now(timezone.utc)
        )
        
        db.add(db_snap)
        db.commit()
        
        return {
            "success": True,
            "snapshot_id": str(snapshot_id),
            "message": "Saved daily snapshot successfully!"
        }

    @staticmethod
    def retrieve_business_context(db: Session, days: int = 90) -> str:
        """
        Fetches historical business intelligence records and structures a comparative text context
        for the Business Metrics RAG reasoning pipeline.
        """
        logger.info(f"[RAGService] Retrieving business context logs for the last {days} days...")
        history = db.query(BusinessMetricsHistory).order_by(BusinessMetricsHistory.metric_date.desc()).limit(days).all()
        
        if not history:
            return (
                "Historical Context RAG Ledger is empty. No historical daily snapshots recorded yet. "
                "All performance values are initially zero."
            )
            
        context_lines = [
            f"Here is the historical Business Metrics RAG history for the last {len(history)} days to compare trends:"
        ]
        
        for snap in history:
            context_lines.append(
                f"- Date: {snap.metric_date} | Revenue: ₹{float(snap.revenue):,.2f} | "
                f"Appointments completed: {snap.appointments} | "
                f"Lead Conversion rate: {snap.lead_conversion * 100.0:.1f}% | "
                f"Stylist rating: {snap.average_rating:.1f}★ | "
                f"Upsell revenue: ₹{float(snap.upsell_revenue):,.2f} | "
                f"Most popular service: {snap.top_service or 'Precision Haircut'} | "
                f"Top Stylist: {snap.top_staff or 'Priya Sharma'}"
            )
            
        return "\n".join(context_lines)
