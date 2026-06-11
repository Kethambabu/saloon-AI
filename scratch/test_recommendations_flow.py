import os
import sys
import uuid
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from dotenv import load_dotenv
load_dotenv(backend_path / ".env")

from db.database import SessionLocal
from db.models import Customer, Appointment, AppointmentStatus, Service, Branch, Staff, User, CustomerRecommendation
from tools.booking_tools import create_appointment, auto_cancel_past_customer_appointments
from services.recommendation_service import RecommendationService

def main():
    db = SessionLocal()
    try:
        # 1. Setup test customer
        email = "test_flow@example.com"
        user = db.query(User).filter(User.email == email).first()
        if user:
            # Clean up old data
            db.query(Appointment).filter(Appointment.customer_id == user.customer_id).delete()
            db.query(CustomerRecommendation).filter(CustomerRecommendation.customer_id == user.customer_id).delete()
            db.query(User).filter(User.id == user.id).delete()
            db.query(Customer).filter(Customer.id == user.customer_id).delete()
            db.commit()
            
        customer = Customer(first_name="Test", last_name="Flow", email=email)
        db.add(customer)
        db.commit()
        
        user = User(email=email, hashed_password="password", role="CUSTOMER", customer_id=customer.id)
        db.add(user)
        db.commit()
        
        branch = db.query(Branch).first()
        service = db.query(Service).filter(Service.name.ilike("%haircut%")).first()
        if not service:
            service = db.query(Service).first()
            
        rec_service1 = db.query(Service).filter(Service.name.ilike("%spa%")).first()
        if not rec_service1:
            rec_service1 = db.query(Service).all()[1]
            
        rec_service2 = db.query(Service).filter(Service.name.ilike("%massage%")).first()
        if not rec_service2:
            rec_service2 = db.query(Service).all()[2]
            
        staff = db.query(Staff).first()
        
        print(f"Customer created: {customer.full_name} ({customer.id})")
        print(f"Branch: {branch.name}")
        print(f"Service: {service.name}")
        print(f"Recommended Service 1: {rec_service1.name}")
        print(f"Recommended Service 2: {rec_service2.name}")
        
        # 2. Test auto-cancellation of past appointments
        past_time = datetime.now(timezone.utc) - timedelta(days=2)
        past_appt = Appointment(
            customer_id=customer.id,
            branch_id=branch.id,
            staff_id=staff.id,
            service_id=service.id,
            start_time=past_time,
            end_time=past_time + timedelta(hours=1),
            status=AppointmentStatus.CONFIRMED,
            notes="Past test appointment"
        )
        db.add(past_appt)
        db.commit()
        
        print("\n--- TEST 1: Auto-cancellation of past appointments ---")
        print(f"Before cancel, status: {past_appt.status}")
        auto_cancel_past_customer_appointments(customer.id, db)
        
        # Refresh
        db.refresh(past_appt)
        print(f"After cancel, status: {past_appt.status}")
        assert past_appt.status == AppointmentStatus.CANCELLED, "Failed to auto-cancel past appointment!"
        print("[PASS] Test 1 Passed: Past appointment auto-cancelled successfully!")
        
        # 3. Test consecutive scheduling of recommended add-ons
        # Create a future appointment
        tomorrow = datetime.now(timezone.utc) + timedelta(days=1)
        # Combine date and time, starting at 12:00 UTC
        start_time = datetime.combine(tomorrow.date(), datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=12)
        
        appt_res = create_appointment(
            customer_id=customer.id,
            branch_id=branch.id,
            service_id=service.id,
            start_time=start_time.isoformat(),
            staff_id=staff.id,
            db=db
        )
        assert appt_res["success"] is True
        appt_id = appt_res["appointment_id"]
        appt = db.query(Appointment).filter(Appointment.id == uuid.UUID(appt_id)).first()
        print(f"\n--- TEST 2: Consecutive Scheduling of Add-ons ---")
        print(f"Parent Appointment {appt.id} starts at {appt.start_time}, ends at {appt.end_time}")
        
        # Accept first recommendation (rec_service1)
        accept_res1 = RecommendationService.accept_recommendation(
            db=db,
            customer_id=str(customer.id),
            service_id=str(rec_service1.id),
            appointment_id=appt_id
        )
        assert accept_res1["success"] is True
        
        # Find first add-on
        addon1 = db.query(Appointment).filter(
            Appointment.customer_id == customer.id,
            Appointment.service_id == rec_service1.id,
            Appointment.notes.like(f"Linked Add-on from Appointment {appt_id}%")
        ).first()
        
        print(f"Add-on 1 (Spa) starts at {addon1.start_time}, ends at {addon1.end_time}")
        assert addon1.start_time == appt.end_time, "Add-on 1 did not start consecutively!"
        
        # Accept second recommendation (rec_service2)
        accept_res2 = RecommendationService.accept_recommendation(
            db=db,
            customer_id=str(customer.id),
            service_id=str(rec_service2.id),
            appointment_id=appt_id
        )
        assert accept_res2["success"] is True
        
        # Find second add-on
        addon2 = db.query(Appointment).filter(
            Appointment.customer_id == customer.id,
            Appointment.service_id == rec_service2.id,
            Appointment.notes.like(f"Linked Add-on from Appointment {appt_id}%")
        ).first()
        
        print(f"Add-on 2 (Massage) starts at {addon2.start_time}, ends at {addon2.end_time}")
        assert addon2.start_time == addon1.end_time, "Add-on 2 did not start consecutively after Add-on 1!"
        print("[PASS] Test 2 Passed: Recommended add-ons scheduled consecutively without overlapping!")
        
        # 4. Test recommendation conversion on create_appointment
        # Create a new recommendation that is NOT accepted yet
        db_rec = CustomerRecommendation(
            id=uuid.uuid4(),
            customer_id=customer.id,
            recommended_service_id=rec_service2.id,
            accepted=False
        )
        db.add(db_rec)
        db.commit()
        
        print("\n--- TEST 3: Recommendation Auto-Conversion on Booking ---")
        print(f"Before booking, recommendation accepted: {db_rec.accepted}")
        
        # Book the service rec_service2
        new_start = start_time + timedelta(hours=6)
        booking_res = create_appointment(
            customer_id=customer.id,
            branch_id=branch.id,
            service_id=rec_service2.id,
            start_time=new_start.isoformat(),
            db=db
        )
        assert booking_res["success"] is True
        
        # Refresh recommendation
        db.refresh(db_rec)
        print(f"After booking, recommendation accepted: {db_rec.accepted}, appointment_id: {db_rec.appointment_id}")
        assert db_rec.accepted is True, "Recommendation was not automatically accepted!"
        assert str(db_rec.appointment_id) == booking_res["appointment_id"], "Recommendation was not linked to correct appointment ID!"
        print("[PASS] Test 3 Passed: Recommendation automatically accepted and linked upon booking via wizard!")
        
    finally:
        db.close()

if __name__ == "__main__":
    main()
