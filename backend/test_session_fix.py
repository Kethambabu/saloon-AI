"""
Test script to verify the SQLAlchemy session fix for appointment creation.
Tests both with injected session and with db_transaction context manager.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from db.database import SessionLocal, db_transaction
from db.models import (
    Branch, Customer, Staff, Service, Appointment,
    AppointmentStatus
)
from tools.booking_tools import create_appointment


def test_appointment_creation_with_session():
    """Test appointment creation when a session is injected (with db=True scenario)."""
    print("\n" + "="*70)
    print("TEST 1: Appointment Creation WITH Injected Session")
    print("="*70)
    
    db = SessionLocal()
    try:
        # Get real IDs from the database
        customer = db.query(Customer).first()
        branch = db.query(Branch).first()
        service = db.query(Service).first()
        staff = db.query(Staff).first()
        
        if not all([customer, branch, service, staff]):
            print("❌ Missing required entities. Skipping test.")
            return False
            
        print(f"✓ Found customer: {customer.id} ({customer.full_name})")
        print(f"✓ Found branch: {branch.id} ({branch.name})")
        print(f"✓ Found service: {service.id} ({service.name})")
        print(f"✓ Found staff: {staff.id} ({staff.full_name})")
        
        # Create appointment with injected session
        # Business hours are 9:00 AM - 8:00 PM UTC, so use 10:00 AM
        start_time = datetime.now(timezone.utc).replace(hour=10, minute=0, second=0, microsecond=0)
        if start_time < datetime.now(timezone.utc):
            start_time += timedelta(days=1)
        
        result = create_appointment(
            customer_id=customer.id,
            branch_id=branch.id,
            service_id=service.id,
            staff_id=staff.id,
            start_time=start_time,
            notes="Test appointment with session",
            db=db
        )
        
        if result.get("success"):
            print(f"\n✅ SUCCESS: Appointment created!")
            print(f"   Appointment ID: {result['appointment_id']}")
            print(f"   Customer: {result['customer_name']}")
            print(f"   Service: {result['service_name']}")
            print(f"   Staff: {result['assigned_staff']}")
            print(f"   Start: {result['start_time']}")
            return True
        else:
            print(f"\n❌ FAILED: {result.get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"\n❌ EXCEPTION: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


def test_appointment_creation_without_session():
    """Test appointment creation without injected session (with db_transaction scenario)."""
    print("\n" + "="*70)
    print("TEST 2: Appointment Creation WITHOUT Injected Session (db_transaction)")
    print("="*70)
    
    db = SessionLocal()
    try:
        # Get real IDs from the database
        customer = db.query(Customer).first()
        branch = db.query(Branch).first()
        service = db.query(Service).first()
        staff = db.query(Staff).first()
        
        if not all([customer, branch, service, staff]):
            print("❌ Missing required entities. Skipping test.")
            return False
            
        print(f"✓ Found customer: {customer.id} ({customer.full_name})")
        print(f"✓ Found branch: {branch.id} ({branch.name})")
        print(f"✓ Found service: {service.id} ({service.name})")
        print(f"✓ Found staff: {staff.id} ({staff.full_name})")
        
    finally:
        db.close()
    
    # Create appointment WITHOUT injected session (forces db_transaction usage)
    try:
        # Business hours are 9:00 AM - 8:00 PM UTC, so use 2:00 PM
        start_time = datetime.now(timezone.utc).replace(hour=14, minute=0, second=0, microsecond=0)
        if start_time < datetime.now(timezone.utc):
            start_time += timedelta(days=1)
        
        result = create_appointment(
            customer_id=customer.id,
            branch_id=branch.id,
            service_id=service.id,
            staff_id=staff.id,
            start_time=start_time,
            notes="Test appointment without session",
            db=None  # This forces db_transaction usage
        )
        
        if result.get("success"):
            print(f"\n✅ SUCCESS: Appointment created!")
            print(f"   Appointment ID: {result['appointment_id']}")
            print(f"   Customer: {result['customer_name']}")
            print(f"   Service: {result['service_name']}")
            print(f"   Staff: {result['assigned_staff']}")
            print(f"   Start: {result['start_time']}")
            return True
        else:
            print(f"\n❌ FAILED: {result.get('error', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"\n❌ EXCEPTION: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("\n" + "#"*70)
    print("# SQLAlchemy Session Management Fix - Verification Tests")
    print("#"*70)
    
    test1_passed = test_appointment_creation_with_session()
    test2_passed = test_appointment_creation_without_session()
    
    print("\n" + "#"*70)
    print("# TEST SUMMARY")
    print("#"*70)
    print(f"Test 1 (With Injected Session): {'✅ PASSED' if test1_passed else '❌ FAILED'}")
    print(f"Test 2 (Without Session/db_transaction): {'✅ PASSED' if test2_passed else '❌ FAILED'}")
    print()
    
    if test1_passed and test2_passed:
        print("✅ All tests passed! Session management fix is working correctly.")
    else:
        print("❌ Some tests failed. Review the output above for details.")
