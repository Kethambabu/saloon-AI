import sys
import os
import uuid
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from db.database import SessionLocal
from db.models import Customer, Appointment, AppointmentStatus, Service, Branch, Staff

db = SessionLocal()
try:
    alice = db.query(Customer).filter(Customer.first_name == "Alice").first()
    branch = db.query(Branch).first()
    service = db.query(Service).filter(Service.name.ilike("%Haircut%")).first()
    staff = db.query(Staff).filter(Staff.branch_id == branch.id).first()
    
    # Delete any existing confirmed/pending appointments for Alice to avoid conflicts/limits
    db.query(Appointment).filter(
        Appointment.customer_id == alice.id,
        Appointment.status.in_([AppointmentStatus.CONFIRMED, AppointmentStatus.PENDING])
    ).delete()
    db.commit()
    
    # Create a confirmed appointment for Alice for today at 6 PM UTC (so it's in the future relative to now)
    now_utc = datetime.now(timezone.utc)
    start_time = now_utc.replace(hour=18, minute=0, second=0, microsecond=0)
    if start_time < now_utc:
        start_time += timedelta(days=1)
        
    appt = Appointment(
        id=uuid.uuid4(),
        customer_id=alice.id,
        branch_id=branch.id,
        staff_id=staff.id if staff else None,
        service_id=service.id,
        start_time=start_time,
        end_time=start_time + timedelta(minutes=60),
        status=AppointmentStatus.CONFIRMED,
        notes="Test active appointment"
    )
    db.add(appt)
    db.commit()
    print(f"Created confirmed appointment for Alice: ID={appt.id}, Start={appt.start_time}")
finally:
    db.close()
