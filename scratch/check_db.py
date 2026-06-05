import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from db.database import SessionLocal
from db.models import Customer, Appointment, AppointmentStatus, Service, Staff

db = SessionLocal()
try:
    alice = db.query(Customer).filter(Customer.first_name == "Alice").first()
    if not alice:
        print("Alice not found, listing first 10 customers:")
        for c in db.query(Customer).limit(10).all():
            print(f"ID: {c.id}, Name: {c.full_name}, Email: {c.email}")
    else:
        print(f"Found Customer Alice: ID={alice.id}, Name={alice.full_name}, Email={alice.email}")
        
        # List appointments
        appts = db.query(Appointment).filter(Appointment.customer_id == alice.id).all()
        print(f"Total appointments: {len(appts)}")
        for a in appts:
            print(f"ID: {a.id}, Start: {a.start_time}, End: {a.end_time}, Status: {a.status}, Service: {a.service.name if a.service else 'None'}")
finally:
    db.close()
