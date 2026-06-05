"""
Recommendation & Upsell Service for SalonAI Workforce Platform.
Implements rule-based, history-aware recommendation scoring,
acceptance/rejection workflows, and performance analytics.
"""

import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from db.models import (
    Service,
    Appointment,
    Customer,
    ServiceRecommendation,
    CustomerRecommendation,
    AppointmentStatus,
)

logger = logging.getLogger(__name__)


class RecommendationService:
    """
    Core engine handling Automated Upsell logic.
    Provides rule matching, history-based RAG learning fallbacks,
    acceptance updates, and comprehensive analytics.
    """

    @staticmethod
    def get_customer_recommendations(db: Session, customer_id: str) -> List[Dict[str, Any]]:
        """
        Generates personalized upsell recommendations for a customer.
        Rules:
        1. Checks current active (PENDING/CONFIRMED) appointments.
        2. Queries service_recommendations to find defined rules for those services.
        3. Analyzes completed booking history to learn customer preferences.
        4. Fallbacks to default rule associations (Hair Cut -> Hair Spa, Facial -> Head Massage, Pedicure -> Foot Spa).
        """
        cust_uuid = uuid.UUID(customer_id) if isinstance(customer_id, str) else customer_id
        
        # 1. Fetch active appointments
        active_appts = db.query(Appointment).filter(
            Appointment.customer_id == cust_uuid,
            Appointment.status.in_([AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED])
        ).order_by(Appointment.start_time.asc()).all()

        recommendations = []
        already_recommended = set()

        if active_appts:
            for appt in active_appts:
                service_id = appt.service_id
                
                # Check for explicit service-to-service rules
                rules = db.query(ServiceRecommendation).filter(
                    ServiceRecommendation.service_id == service_id
                ).order_by(ServiceRecommendation.confidence_score.desc()).all()

                for rule in rules:
                    rec_service = db.query(Service).filter(Service.id == rule.recommended_service_id).first()
                    if rec_service and rec_service.id not in already_recommended:
                        recommendations.append({
                            "id": str(uuid.uuid4()),  # Temporary ID if not stored in DB yet
                            "service_id": str(rec_service.id),
                            "name": rec_service.name,
                            "description": rec_service.description or "",
                            "price": float(rec_service.price),
                            "duration_minutes": rec_service.duration_minutes,
                            "confidence_score": rule.confidence_score,
                            "reason": f"Pairs perfectly with your booked {appt.service.name}",
                            "appointment_id": str(appt.id)
                        })
                        already_recommended.add(rec_service.id)

        # 2. Analyze customer completed booking history (RAG fallback logic)
        completed_appts = db.query(Appointment).filter(
            Appointment.customer_id == cust_uuid,
            Appointment.status == AppointmentStatus.COMPLETED
        ).all()

        if completed_appts:
            # Count historical services
            history_counts = {}
            for appt in completed_appts:
                history_counts[appt.service_id] = history_counts.get(appt.service_id, 0) + 1
            
            # Find favorite service that is NOT currently booked
            sorted_favs = sorted(history_counts.items(), key=lambda x: x[1], reverse=True)
            for fav_service_id, count in sorted_favs:
                if fav_service_id not in already_recommended:
                    fav_service = db.query(Service).filter(Service.id == fav_service_id).first()
                    if fav_service:
                        recommendations.append({
                            "id": str(uuid.uuid4()),
                            "service_id": str(fav_service.id),
                            "name": fav_service.name,
                            "description": fav_service.description or "",
                            "price": float(fav_service.price),
                            "duration_minutes": fav_service.duration_minutes,
                            "confidence_score": 0.8,
                            "reason": f"Based on your purchase history (you booked this {count} times previously)",
                            "appointment_id": str(active_appts[0].id) if active_appts else None
                        })
                        already_recommended.add(fav_service.id)

        # 3. Fallback static rules if no recommendations generated
        if not recommendations:
            fallback_map = {
                "haircut": "Hair Spa",
                "precision haircut": "Hair Spa",
                "facial": "Head Massage",
                "massage": "Head Massage",
                "pedicure": "Foot Spa"
            }
            for appt in active_appts:
                name_lower = appt.service.name.lower()
                matched_target = None
                for keyword, target in fallback_map.items():
                    if keyword in name_lower:
                        matched_target = target
                        break
                
                if matched_target:
                    rec_service = db.query(Service).filter(
                        Service.name.ilike(f"%{matched_target}%")
                    ).first()
                    if rec_service and rec_service.id not in already_recommended:
                        recommendations.append({
                            "id": str(uuid.uuid4()),
                            "service_id": str(rec_service.id),
                            "name": rec_service.name,
                            "description": rec_service.description or "",
                            "price": float(rec_service.price),
                            "duration_minutes": rec_service.duration_minutes,
                            "confidence_score": 0.75,
                            "reason": f"Popular add-on for {appt.service.name}",
                            "appointment_id": str(appt.id)
                        })
                        already_recommended.add(rec_service.id)

        # 4. Global default high-value service fallback
        if not recommendations:
            default_services = ["Hair Spa", "Head Massage", "Foot Spa"]
            for s_name in default_services:
                rec_service = db.query(Service).filter(Service.name.ilike(f"%{s_name}%")).first()
                if rec_service and rec_service.id not in already_recommended:
                    recommendations.append({
                        "id": str(uuid.uuid4()),
                        "service_id": str(rec_service.id),
                        "name": rec_service.name,
                        "description": rec_service.description or "",
                        "price": float(rec_service.price),
                        "duration_minutes": rec_service.duration_minutes,
                        "confidence_score": 0.7,
                        "reason": "Top trending treatment for you today",
                        "appointment_id": str(active_appts[0].id) if active_appts else None
                    })
                    already_recommended.add(rec_service.id)

        # Store recommendations in database as PENDING customer_recommendations so we can track analytics
        for rec in recommendations:
            appt_id = uuid.UUID(rec["appointment_id"]) if rec["appointment_id"] else None
            # Check if already generated in this session
            existing = db.query(CustomerRecommendation).filter(
                CustomerRecommendation.customer_id == cust_uuid,
                CustomerRecommendation.recommended_service_id == uuid.UUID(rec["service_id"]),
                CustomerRecommendation.appointment_id == appt_id
            ).first()
            
            if not existing:
                db_rec = CustomerRecommendation(
                    id=uuid.UUID(rec["id"]),
                    customer_id=cust_uuid,
                    appointment_id=appt_id,
                    recommended_service_id=uuid.UUID(rec["service_id"]),
                    accepted=False
                )
                db.add(db_rec)
        db.commit()

        return recommendations

    @staticmethod
    def accept_recommendation(db: Session, customer_id: str, service_id: str, appointment_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Accepts a generated recommendation.
        Updates the accepted flag to True and updates the active booking.
        Creates a linked appointment for the recommended service.
        """
        cust_uuid = uuid.UUID(customer_id)
        service_uuid = uuid.UUID(service_id)
        appt_uuid = uuid.UUID(appointment_id) if appointment_id else None

        # 1. Update customer_recommendations table
        rec = db.query(CustomerRecommendation).filter(
            CustomerRecommendation.customer_id == cust_uuid,
            CustomerRecommendation.recommended_service_id == service_uuid
        )
        if appt_uuid:
            rec = rec.filter(CustomerRecommendation.appointment_id == appt_uuid)
        
        rec_item = rec.first()
        if rec_item:
            rec_item.accepted = True
        else:
            # Create a completed recommendation record if it wasn't pre-generated
            rec_item = CustomerRecommendation(
                id=uuid.uuid4(),
                customer_id=cust_uuid,
                appointment_id=appt_uuid,
                recommended_service_id=service_uuid,
                accepted=True
            )
            db.add(rec_item)

        # 2. Add as an add-on to the active appointment
        rec_service = db.query(Service).filter(Service.id == service_uuid).first()
        if not rec_service:
            db.rollback()
            return {"success": False, "error": "Recommended service not found"}

        # Create a linked appointment
        if appt_uuid:
            original_appt = db.query(Appointment).filter(Appointment.id == appt_uuid).first()
            if original_appt:
                # Add add-on note to original appointment
                original_appt.notes = (
                    f"{original_appt.notes or ''}\n"
                    f"[Automated Upsell Accepted: Added {rec_service.name} (${rec_service.price})]"
                ).strip()
                
                # Check if linked add-on appointment already exists
                existing_addon = db.query(Appointment).filter(
                    Appointment.customer_id == cust_uuid,
                    Appointment.service_id == service_uuid,
                    Appointment.start_time == original_appt.start_time
                ).first()
                
                if not existing_addon:
                    # Create linked appointment
                    from datetime import timedelta
                    new_appt = Appointment(
                        id=uuid.uuid4(),
                        customer_id=cust_uuid,
                        branch_id=original_appt.branch_id,
                        staff_id=original_appt.staff_id,
                        service_id=service_uuid,
                        start_time=original_appt.start_time,
                        end_time=original_appt.start_time + timedelta(minutes=int(rec_service.duration_minutes)),
                        status=AppointmentStatus.CONFIRMED,
                        notes=f"Linked Add-on from Appointment {original_appt.id}"
                    )
                    db.add(new_appt)

        db.commit()
        return {
            "success": True,
            "message": f"Successfully accepted {rec_service.name} and updated your booking!"
        }

    @staticmethod
    def reject_recommendation(db: Session, customer_id: str, service_id: str, appointment_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Rejects a recommendation by keeping/marking accepted=False.
        """
        cust_uuid = uuid.UUID(customer_id)
        service_uuid = uuid.UUID(service_id)
        appt_uuid = uuid.UUID(appointment_id) if appointment_id else None

        rec = db.query(CustomerRecommendation).filter(
            CustomerRecommendation.customer_id == cust_uuid,
            CustomerRecommendation.recommended_service_id == service_uuid
        )
        if appt_uuid:
            rec = rec.filter(CustomerRecommendation.appointment_id == appt_uuid)
        
        rec_item = rec.first()
        if rec_item:
            rec_item.accepted = False
        else:
            rec_item = CustomerRecommendation(
                id=uuid.uuid4(),
                customer_id=cust_uuid,
                appointment_id=appt_uuid,
                recommended_service_id=service_uuid,
                accepted=False
            )
            db.add(rec_item)
        
        db.commit()
        return {"success": True, "message": "Recommendation dismissed"}

    @staticmethod
    def get_upsell_analytics(db: Session) -> Dict[str, Any]:
        """
        Returns Automated Upsell performance analytics.
        Calculations:
        - Generated: Count of all customer_recommendations
        - Accepted: Count of customer_recommendations where accepted = True
        - Revenue: Sum of prices of all accepted recommendations
        - Acceptance Rate: (Accepted / Generated) * 100
        """
        generated_count = db.query(CustomerRecommendation).count()
        accepted_count = db.query(CustomerRecommendation).filter(CustomerRecommendation.accepted == True).count()

        # Calculate revenue generated
        revenue = 0.0
        accepted_recs = db.query(CustomerRecommendation).filter(CustomerRecommendation.accepted == True).all()
        for rec in accepted_recs:
            if rec.recommended_service:
                revenue += float(rec.recommended_service.price)

        acceptance_rate = 0.0
        if generated_count > 0:
            acceptance_rate = round((accepted_count / generated_count) * 100.0, 2)

        # Fetch top add-ons
        top_addons_query = db.query(
            CustomerRecommendation.recommended_service_id,
            func.count(CustomerRecommendation.id).label("count")
        ).filter(
            CustomerRecommendation.accepted == True
        ).group_by(
            CustomerRecommendation.recommended_service_id
        ).order_by(
            func.count(CustomerRecommendation.id).desc()
        ).limit(3).all()

        top_addons = []
        for service_id, count in top_addons_query:
            service = db.query(Service).filter(Service.id == service_id).first()
            if service:
                top_addons.append({
                    "name": service.name,
                    "count": count,
                    "revenue": float(service.price) * count
                })

        return {
            "generated": generated_count,
            "accepted": accepted_count,
            "revenue": revenue,
            "acceptance_rate": acceptance_rate,
            "top_addons": top_addons
        }
