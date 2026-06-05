import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from db.database import SessionLocal
from db.models import Appointment, AppointmentStatus, Customer

db = SessionLocal()
try:
    appts = db.query(Appointment).filter(Appointment.status.in_([AppointmentStatus.CONFIRMED, AppointmentStatus.PENDING])).limit(10).all()
    print(f"Confirmed/Pending appointments count: {len(appts)}")
    for a in appts:
        print(f"ID: {a.id}, Customer: {a.customer.full_name}, Start: {a.start_time}, Status: {a.status}")
finally:
    db.close()
