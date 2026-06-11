import os
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from dotenv import load_dotenv
load_dotenv(backend_path / ".env")

from db.database import SessionLocal
from tools.booking_tools import create_appointment

def main():
    db = SessionLocal()
    try:
        customer_id = "balu@gmail.com"
        branch_id = "Main Salon"
        service_id = "Precision Haircut"
        staff_id = "Marcus Johnson"
        start_time = "2026-06-09T10:00:00Z"
        
        print("Inserting June 9th appointment...")
        res = create_appointment(
            customer_id=customer_id,
            branch_id=branch_id,
            service_id=service_id,
            start_time=start_time,
            staff_id=staff_id,
            notes="Self-guided booking",
            db=db
        )
        print("Result:", res)
        if res.get("success"):
            db.commit()
            print("Successfully committed to DB!")
    except Exception as e:
        db.rollback()
        print("Error, rolled back:", e)
    finally:
        db.close()

if __name__ == "__main__":
    main()
