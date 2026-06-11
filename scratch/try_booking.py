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
        # Parameters from screenshot:
        # Customer: balu@gmail.com
        # Service: Precision Haircut
        # Branch: Main Salon
        # Stylist: Marcus Johnson
        # Date: 2026-06-09
        # Time: 10:00
        
        customer_id = "balu@gmail.com"
        branch_id = "Main Salon"
        service_id = "Precision Haircut"
        staff_id = "Marcus Johnson"
        start_time = "2026-06-09T10:00:00Z"
        
        print("Attempting to create appointment...")
        res = create_appointment(
            customer_id=customer_id,
            branch_id=branch_id,
            service_id=service_id,
            start_time=start_time,
            staff_id=staff_id,
            notes="Self-guided booking Test",
            db=db
        )
        print("Result:", res)
    finally:
        db.close()

if __name__ == "__main__":
    main()
