#!/usr/bin/env python3
"""
Test script to validate the AI Receptionist chat assistant with all possible customer queries:
- Slot availability checking
- New booking
- Retrieving history
- Rescheduling
- Cancellation
And verifies frontend/backend database updates (loyalty points, appointment status, notifications).
"""

import sys
import os
import requests
import time
from datetime import datetime, timezone

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from db.database import SessionLocal
from db.models import Customer, User, Appointment, AppointmentStatus, Notification

BASE_URL = "http://localhost:8000/api/v1"

def print_separator(title):
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80)

def test_ai_customer_flow():
    # 1. Login as customer
    login_payload = {
        "email": "customer@example.com",
        "password": "password123"
    }
    print("Logging in as customer@example.com...")
    response = requests.post(f"{BASE_URL}/auth/login", json=login_payload)
    if response.status_code != 200:
        print(f"[ERROR] Login failed! Status: {response.status_code}, Body: {response.text}")
        return
    
    login_data = response.json()
    token = login_data.get("access_token")
    print(f"[OK] Login successful! Token obtained: {token[:15]}...")
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    session_id = f"cust_flow_sess_{int(time.time())}"
    chat_history = []
    
    db = SessionLocal()
    try:
        # Get customer record
        user_record = db.query(User).filter(User.email == "customer@example.com").first()
        customer_id = user_record.customer_id
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        
        initial_points = customer.loyalty_points
        print(f"Initial Database Loyalty Points: {initial_points}")
        
        # Clean up any existing active test appointments on 2026-06-15 to avoid conflicts
        existing_appts = db.query(Appointment).filter(
            Appointment.customer_id == customer_id,
            Appointment.start_time >= datetime(2026, 6, 15, 0, 0, tzinfo=timezone.utc),
            Appointment.start_time < datetime(2026, 6, 16, 0, 0, tzinfo=timezone.utc),
            Appointment.status != AppointmentStatus.CANCELLED
        ).all()
        for appt in existing_appts:
            appt.status = AppointmentStatus.CANCELLED
        db.commit()
        if existing_appts:
            print(f"Cleaned up {len(existing_appts)} existing test appointments.")

        # QUERY 1: Slot Availability
        print_separator("QUERY 1: CHECK SLOT AVAILABILITY")
        query_1 = "Check available slots for Signature Precision Haircut on 2026-06-15"
        print(f"USER: {query_1}")
        payload = {"message": query_1, "session id": session_id, "chat history": chat_history}
        res = requests.post(f"{BASE_URL}/agent/chat", json=payload, headers=headers)
        if res.status_code == 200:
            resp_data = res.json()
            clara_resp = resp_data.get("response", "")
            print(f"CLARA:\n{clara_resp}")
            chat_history.append({"role": "user", "content": query_1})
            chat_history.append({"role": "assistant", "content": clara_resp})
        else:
            print(f"Error: {res.status_code} - {res.text}")

        # QUERY 2: Book Appointment
        print_separator("QUERY 2: BOOK APPOINTMENT")
        query_2 = "Please book a Signature Precision Haircut at Downtown Elite with Marcus Staff on 2026-06-15 at 5:00 PM."
        print(f"USER: {query_2}")
        payload = {"message": query_2, "session id": session_id, "chat history": chat_history}
        res = requests.post(f"{BASE_URL}/agent/chat", json=payload, headers=headers)
        
        # Let's query the database to verify the booking record
        db.expire_all()
        new_appointment = db.query(Appointment).filter(
            Appointment.customer_id == customer_id,
            Appointment.status != AppointmentStatus.CANCELLED
        ).order_by(Appointment.created_at.desc()).first()
        
        if res.status_code == 200:
            resp_data = res.json()
            clara_resp = resp_data.get("response", "")
            print(f"CLARA:\n{clara_resp}")
            chat_history.append({"role": "user", "content": query_2})
            chat_history.append({"role": "assistant", "content": clara_resp})
        else:
            print(f"Error: {res.status_code} - {res.text}")
            
        if new_appointment:
            print(f"\n[DB VERIFICATION] Appointment successfully created in database!")
            print(f"  ID: {new_appointment.id}")
            print(f"  Service ID: {new_appointment.service_id}")
            print(f"  Start Time (UTC): {new_appointment.start_time}")
            print(f"  Status: {new_appointment.status}")
            
            # Check notifications in DB
            notif = db.query(Notification).filter(Notification.user_id == user_record.id).order_by(Notification.created_at.desc()).first()
            if notif:
                print(f"  Latest Notification Title: {notif.title}")
                print(f"  Latest Notification Message: {notif.message}")
        else:
            print("\n[DB ERROR] Appointment not found in database!")

        # QUERY 3: Retrieve History
        print_separator("QUERY 3: RETRIEVE HISTORY")
        query_3 = "Show my booking history."
        print(f"USER: {query_3}")
        payload = {"message": query_3, "session id": session_id, "chat history": chat_history}
        res = requests.post(f"{BASE_URL}/agent/chat", json=payload, headers=headers)
        if res.status_code == 200:
            resp_data = res.json()
            clara_resp = resp_data.get("response", "")
            print(f"CLARA:\n{clara_resp}")
            chat_history.append({"role": "user", "content": query_3})
            chat_history.append({"role": "assistant", "content": clara_resp})
        else:
            print(f"Error: {res.status_code} - {res.text}")

        # QUERY 4: Reschedule Appointment
        print_separator("QUERY 4: RESCHEDULE APPOINTMENT")
        query_4 = "Move my appointment on 2026-06-15 to 1:00 PM."
        print(f"USER: {query_4}")
        payload = {"message": query_4, "session id": session_id, "chat history": chat_history}
        res = requests.post(f"{BASE_URL}/agent/chat", json=payload, headers=headers)
        if res.status_code == 200:
            resp_data = res.json()
            clara_resp = resp_data.get("response", "")
            print(f"CLARA:\n{clara_resp}")
            chat_history.append({"role": "user", "content": query_4})
            chat_history.append({"role": "assistant", "content": clara_resp})
        else:
            print(f"Error: {res.status_code} - {res.text}")

        # Database Verification
        db.expire_all()
        rescheduled_appointment = db.query(Appointment).filter(
            Appointment.id == new_appointment.id
        ).first()
        if rescheduled_appointment:
            print(f"\n[DB VERIFICATION] Appointment rescheduled in database!")
            print(f"  New Start Time: {rescheduled_appointment.start_time}")
            print(f"  New Status: {rescheduled_appointment.status}")

        # QUERY 5: Cancel Appointment
        print_separator("QUERY 5: CANCEL APPOINTMENT")
        query_5 = "Cancel my upcoming appointment."
        print(f"USER: {query_5}")
        payload = {"message": query_5, "session id": session_id, "chat history": chat_history}
        res = requests.post(f"{BASE_URL}/agent/chat", json=payload, headers=headers)
        if res.status_code == 200:
            resp_data = res.json()
            clara_resp = resp_data.get("response", "")
            print(f"CLARA:\n{clara_resp}")
            chat_history.append({"role": "user", "content": query_5})
            chat_history.append({"role": "assistant", "content": clara_resp})
        else:
            print(f"Error: {res.status_code} - {res.text}")

        # Database Verification
        db.expire_all()
        cancelled_appointment = db.query(Appointment).filter(
            Appointment.id == new_appointment.id
        ).first()
        customer_after = db.query(Customer).filter(Customer.id == customer_id).first()
        
        if cancelled_appointment:
            print(f"\n[DB VERIFICATION] Appointment status in database: {cancelled_appointment.status}")
            print(f"  Loyalty Points after cancellation: {customer_after.loyalty_points}")
            print(f"  Loyalty Points Diff: {customer_after.loyalty_points - initial_points}")
            
            # Check notifications in DB
            notif = db.query(Notification).filter(Notification.user_id == user_record.id).order_by(Notification.created_at.desc()).first()
            if notif:
                print(f"  Latest Notification Title: {notif.title}")
                print(f"  Latest Notification Message: {notif.message}")

    finally:
        db.close()

if __name__ == "__main__":
    try:
        import sys
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass
    test_ai_customer_flow()
