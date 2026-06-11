import os
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from dotenv import load_dotenv
load_dotenv(backend_path / ".env")

from db.database import SessionLocal
from db.models import User, Appointment, Customer, Service, Staff, Branch

def main():
    db = SessionLocal()
    try:
        from datetime import date
        appts = db.query(Appointment).all()
        print(f"Total appointments in DB: {len(appts)}")
        june_9_appts = []
        for a in appts:
            if a.start_time.date() == date(2026, 6, 9):
                june_9_appts.append(a)
        
        print(f"\nAppointments on June 9th, 2026: {len(june_9_appts)}")
        for a in june_9_appts:
            cust = db.query(Customer).filter(Customer.id == a.customer_id).first()
            srv = db.query(Service).filter(Service.id == a.service_id).first()
            staff = db.query(Staff).filter(Staff.id == a.staff_id).first() if a.staff_id else None
            branch = db.query(Branch).filter(Branch.id == a.branch_id).first()
            user = db.query(User).filter(User.customer_id == a.customer_id).first()
            print(f"- ID: {a.id}")
            print(f"  Customer Name: {cust.first_name + ' ' + cust.last_name if cust else 'None'} (Email: {user.email if user else 'None'})")
            print(f"  Service: {srv.name if srv else 'None'} (${float(srv.price) if srv else 0.0})")
            print(f"  Branch: {branch.name if branch else 'None'}")
            print(f"  Stylist: {staff.first_name + ' ' + staff.last_name if staff else 'None'}")
            print(f"  Start: {a.start_time}")
            print(f"  End: {a.end_time}")
            print(f"  Status: {a.status}")
            print(f"  Notes: {a.notes}")
            print("-" * 40)
            
    finally:
        db.close()

if __name__ == "__main__":
    main()
