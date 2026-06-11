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
        user = db.query(User).filter(User.email == "balu@gmail.com").first()
        if not user:
            print("User balu@gmail.com not found!")
            return
        
        print(f"User found: ID={user.id}, email={user.email}, role={user.role}, customer_id={user.customer_id}")
        
        if user.customer_id:
            customer = db.query(Customer).filter(Customer.id == user.customer_id).first()
            if customer:
                print(f"Customer details: name={customer.first_name} {customer.last_name}, phone={customer.phone}")
            else:
                print("Customer record not found for customer_id!")
            
            appts = db.query(Appointment).filter(Appointment.customer_id == user.customer_id).all()
            print(f"\nTotal appointments for customer in DB: {len(appts)}")
            for a in appts:
                srv = db.query(Service).filter(Service.id == a.service_id).first()
                staff = db.query(Staff).filter(Staff.id == a.staff_id).first() if a.staff_id else None
                branch = db.query(Branch).filter(Branch.id == a.branch_id).first()
                print(f"- ID: {a.id}")
                print(f"  Service: {srv.name if srv else 'None'} (${float(srv.price) if srv else 0.0})")
                print(f"  Branch: {branch.name if branch else 'None'}")
                print(f"  Stylist: {staff.first_name + ' ' + staff.last_name if staff else 'None'}")
                print(f"  Start: {a.start_time}")
                print(f"  End: {a.end_time}")
                print(f"  Status: {a.status}")
                print(f"  Notes: {a.notes}")
                print("-" * 40)
        else:
            print("User does not have a customer_id!")
            
    finally:
        db.close()

if __name__ == "__main__":
    main()
