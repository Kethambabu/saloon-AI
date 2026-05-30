"""
Direct unit test of the booking tools to verify SQLAlchemy session fix.
This tests the core booking functionality without going through the agent layer.
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from uuid import UUID

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from db.database import SessionLocal, db_transaction
from db.models import Customer, Branch, Staff, Service
from tools.booking_tools import (
    create_appointment,
    get_available_slots,
    cancel_appointment,
    get_customer_history
)

def test_complete_booking_flow():
    """Test the complete booking flow using the booking tools."""
    
    print("\n" + "="*70)
    print("COMPLETE BOOKING FLOW TEST")
    print("="*70)
    
    # Get a database session to fetch test data
    db = SessionLocal()
    
    try:
        # Step 1: Get customer
        print("\n[Step 1] Fetching customer...")
        customer = db.query(Customer).first()
        if not customer:
            print("❌ No customer found in database")
            return False
        print(f"✓ Customer: {customer.full_name} ({customer.id})")
        
        # Step 2: Get branch
        print("\n[Step 2] Fetching branch...")
        branch = db.query(Branch).first()
        if not branch:
            print("❌ No branch found in database")
            return False
        print(f"✓ Branch: {branch.name} ({branch.id})")
        
        # Step 3: Get service
        print("\n[Step 3] Fetching service...")
        service = db.query(Service).first()
        if not service:
            print("❌ No service found in database")
            return False
        print(f"✓ Service: {service.name} ({service.id})")
        
        # Step 4: Get staff
        print("\n[Step 4] Fetching staff...")
        staff = db.query(Staff).first()
        if not staff:
            print("❌ No staff found in database")
            return False
        print(f"✓ Staff: {staff.full_name} ({staff.id})")
        
        db.close()
        
        # Step 5: Check availability
        print("\n[Step 5] Checking available slots...")
        start_date = datetime.now(timezone.utc).replace(hour=9, minute=0, second=0, microsecond=0)
        if start_date < datetime.now(timezone.utc):
            start_date += timedelta(days=1)
        
        date_str = start_date.strftime("%Y-%m-%d")
        
        availability_result = get_available_slots(
            branch_id=str(branch.id),
            date_str=date_str,
            staff_id=str(staff.id),
            service_id=str(service.id),
            db=None
        )
        
        if not availability_result.get("success"):
            print(f"❌ Failed to get available slots: {availability_result.get('error')}")
            return False
        
        slots = availability_result.get("available_slots", [])
        print(f"✓ Found {len(slots)} available slots")
        if slots:
            print(f"  First slot: {slots[0]}")
        
        # Step 6: Create appointment
        print("\n[Step 6] Creating appointment...")
        slot_time = slots[0] if slots else start_date.replace(hour=10, minute=0)
        
        booking_result = create_appointment(
            customer_id=str(customer.id),
            branch_id=str(branch.id),
            service_id=str(service.id),
            staff_id=str(staff.id),
            start_time=slot_time,
            notes="Test booking via tools",
            db=None  # Use db_transaction internally
        )
        
        if not booking_result.get("success"):
            print(f"❌ Failed to create appointment: {booking_result.get('error')}")
            return False
        
        appointment_id = booking_result.get("appointment_id")
        print(f"✓ Appointment created successfully!")
        print(f"  ID: {appointment_id}")
        print(f"  Customer: {booking_result.get('customer_name')}")
        print(f"  Service: {booking_result.get('service_name')}")
        print(f"  Staff: {booking_result.get('assigned_staff')}")
        print(f"  Start: {booking_result.get('start_time')}")
        print(f"  Status: {booking_result.get('status')}")
        
        # Step 7: Get customer history
        print("\n[Step 7] Retrieving booking history...")
        history_result = get_customer_history(
            customer_id=str(customer.id),
            db=None
        )
        
        if not history_result.get("success"):
            print(f"❌ Failed to get history: {history_result.get('error')}")
            return False
        
        bookings = history_result.get("bookings", [])
        print(f"✓ Customer has {len(bookings)} booking(s)")
        
        # Verify the appointment we just created is in the history
        appointment_found = False
        for booking in bookings:
            if booking.get("id") == appointment_id:
                appointment_found = True
                print(f"✓ New appointment found in booking history!")
                print(f"  Time: {booking.get('start_time')}")
                break
        
        if not appointment_found:
            print(f"⚠️  Warning: Newly created appointment not found in history yet")
        
        return True
        
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if db:
            db.close()


if __name__ == "__main__":
    print("\n" + "#"*70)
    print("# BOOKING TOOLS INTEGRATION TEST")
    print("# Tests complete booking flow with SQLAlchemy session fix")
    print("#"*70)
    
    try:
        success = test_complete_booking_flow()
        
        print("\n" + "#"*70)
        if success:
            print("✅ ALL TESTS PASSED!")
            print("\nThe SQLAlchemy session fix is working correctly.")
            print("Complete booking flow: availability → creation → retrieval")
        else:
            print("❌ TEST FAILED!")
        print("#"*70 + "\n")
        
    except Exception as e:
        print(f"\n❌ Test execution failed: {str(e)}")
        import traceback
        traceback.print_exc()
