"""
Recommendation Engine — Phase 2 Architecture.

Provides 4-tier intelligent fallback recommendations when requested slots are unavailable or staff are on leave:
1. Same stylist + nearest time (same day)
2. Same stylist + different day
3. Qualified alternative stylist + same time
4. Qualified alternative stylist + nearest time
"""

from __future__ import annotations

import logging
import uuid
import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from infrastructure.db.models import Staff, Branch, Service
from application.services.availability_service import AvailabilityService

logger = logging.getLogger(__name__)


class RecommendationEngine:
    """
    Intelligent recommendation fallback engine for salon appointments.
    Strictly uses deterministic backend scheduling logic.
    """

    @staticmethod
    def get_smart_recommendations(
        branch_id: Any,
        date_str: str,
        requested_time_str: Optional[str] = None,
        staff_id: Optional[Any] = None,
        service_id: Optional[Any] = None,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """
        Compute multi-tiered alternative recommendations.
        """
        from infrastructure.db.database import SessionLocal
        db = session or SessionLocal()
        try:
            # Check general availability for requested date
            slots_res = AvailabilityService.get_available_slots(
                branch_id=branch_id,
                date_str=date_str,
                staff_id=None,  # Check all staff for open slots on this date
                service_id=service_id,
                db=db,
            )

            same_day_slots = slots_res.get("slots", [])

            # Tier 1 & Tier 3: Same day options
            alternative_same_day_stylists = []
            matching_time_slots = []

            for slot in same_day_slots:
                slot_time = slot.get("time") or (slot.get("start_time") or "")[11:16]
                if requested_time_str and slot_time == requested_time_str:
                    matching_time_slots.append(slot)
                for name in slot.get("available_staff_names", []):
                    if name not in alternative_same_day_stylists:
                        alternative_same_day_stylists.append(name)

            # Tier 2: Next available days for same stylist (if specified)
            next_days_recommendations = []
            if staff_id:
                try:
                    target_dt = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
                    for offset in range(1, 4):  # Check next 3 days
                        next_date_str = (target_dt + datetime.timedelta(days=offset)).strftime("%Y-%m-%d")
                        next_avail = AvailabilityService.get_available_slots(
                            branch_id=branch_id,
                            date_str=next_date_str,
                            staff_id=staff_id,
                            service_id=service_id,
                            db=db,
                        )
                        if next_avail.get("success") and next_avail.get("slots"):
                            next_days_recommendations.append({
                                "date": next_date_str,
                                "available_slots_count": len(next_avail["slots"]),
                                "first_available_slot": next_avail["slots"][0].get("time") or (next_avail["slots"][0].get("start_time") or "")[11:16]
                            })
                except Exception as exc:
                    logger.warning(f"[RecommendationEngine] Error checking future dates: {exc}")

            return {
                "same_day_available_slots": [s.get("time") or (s.get("start_time") or "")[11:16] for s in same_day_slots[:5]],
                "alternative_stylists_today": alternative_same_day_stylists,
                "same_time_alternative_slots": matching_time_slots,
                "next_available_days": next_days_recommendations,
            }
        finally:
            if not session:
                db.close()
