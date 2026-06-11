import os
import sys
import datetime
import requests
import json
import uuid

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from db.database import SessionLocal
from db.models import (
    Customer, Staff, Branch, Service, Appointment, ChatLog, 
    BusinessMetricsHistory, AppointmentStatus, UserRole
)

BASE_URL = "http://localhost:8000/api/v1"

def create_mock_activity_for_today():
    """Ensure we have at least one active appointment and chat log for today so the daily pipeline processes them."""
    db = SessionLocal()
    try:
        today = datetime.date.today()
        day_start = datetime.datetime.combine(today, datetime.time.min)
        day_end = datetime.datetime.combine(today, datetime.time.max)

        # Check if we already have appointments for today
        appt_count = db.query(Appointment).filter(Appointment.start_time >= day_start, Appointment.start_time <= day_end).count()
        chat_count = db.query(ChatLog).filter(ChatLog.created_at >= day_start, ChatLog.created_at <= day_end).count()

        if appt_count > 0 and chat_count > 0:
            print(f"Already have {appt_count} appointments and {chat_count} chat logs for today.")
            return

        print("Seeding today's activity for memory pipeline testing...")
        # Get customer, staff, service, branch
        cust = db.query(Customer).filter(Customer.email == "customer@example.com").first()
        stf = db.query(Staff).filter(Staff.email == "marcus@salonai.com").first()
        if not stf:
            stf = db.query(Staff).first()
        if not cust:
            cust = db.query(Customer).first()
            
        branch = db.query(Branch).first()
        service = db.query(Service).first()

        if not (cust and stf and branch and service):
            print("ERROR: Cannot find database entities to create mock activities. Run setup/seed first.")
            return

        # Create appointment for today
        if appt_count == 0:
            appt = Appointment(
                id=uuid.uuid4(),
                customer_id=cust.id,
                branch_id=branch.id,
                staff_id=stf.id,
                service_id=service.id,
                start_time=day_start + datetime.timedelta(hours=14), # 2 PM today
                end_time=day_start + datetime.timedelta(hours=14, minutes=45),
                status=AppointmentStatus.COMPLETED,
                notes="Customer requested natural styling for hair layers."
            )
            db.add(appt)
            print(f"Created mock appointment for {cust.full_name} with {stf.first_name} {stf.last_name}")

        # Create chat log for today
        if chat_count == 0:
            chat = ChatLog(
                id=uuid.uuid4(),
                session_id=f"test-session-{uuid.uuid4().hex[:6]}",
                user_id=cust.id,
                customer_id=cust.id,
                agent_type="RECEPTIONIST",
                sender="user",
                message="I would love to book another styling session next week for short layer haircut.",
                created_at=day_start + datetime.timedelta(hours=10) # 10 AM today
            )
            db.add(chat)
            print(f"Created mock chat log for customer {cust.full_name}")

        # Create BI snapshot for today if none exists
        bi_snap = db.query(BusinessMetricsHistory).filter(BusinessMetricsHistory.metric_date == today).first()
        if not bi_snap:
            bi_snap = BusinessMetricsHistory(
                id=uuid.uuid4(),
                metric_date=today,
                revenue=float(service.price),
                appointments=1,
                lead_conversion=1.0,
                average_rating=5.0,
                upsell_revenue=0.0,
                top_service=service.name,
                top_staff=f"{stf.first_name} {stf.last_name}",
                created_at=day_start + datetime.timedelta(hours=23)
            )
            db.add(bi_snap)
            print(f"Created mock BusinessMetricsHistory for today: {today}")

        db.commit()
        print("Mock activity seeded successfully.")
    except Exception as e:
        db.rollback()
        print(f"Error seeding mock activity: {e}")
    finally:
        db.close()

def run_pipeline_via_api():
    # 1. Login as Admin to get token
    login_payload = {
        "email": "owner@salonai.com",
        "password": "password123"
    }
    print("Logging in to obtain admin JWT...")
    r = requests.post(f"{BASE_URL}/auth/login", json=login_payload)
    if r.status_code != 200:
        print(f"Login failed: {r.status_code} - {r.text}")
        return
        
    token = r.json().get("access_token")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    print("Logged in successfully.")

    # 2. Trigger daily pipeline via API
    print("Triggering daily memory pipeline via POST /api/v1/memory/trigger/daily ...")
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    r = requests.post(f"{BASE_URL}/memory/trigger/daily?date_str={today_str}", headers=headers)
    
    print(f"Response Status Code: {r.status_code}")
    try:
        response_json = r.json()
        print("Response JSON:")
        print(json.dumps(response_json, indent=2))
        
        if r.status_code == 200 and response_json.get("success"):
            print("\nDaily memory pipeline run succeeded via API!")
            
            # 3. Trigger weekly consolidation
            print("\nTriggering weekly memory pipeline via POST /api/v1/memory/trigger/weekly ...")
            r_weekly = requests.post(f"{BASE_URL}/memory/trigger/weekly?end_date_str={today_str}", headers=headers)
            print(f"Weekly Status Code: {r_weekly.status_code}")
            print("Weekly Response:", json.dumps(r_weekly.json(), indent=2))

            # 4. Trigger monthly consolidation
            print("\nTriggering monthly memory pipeline via POST /api/v1/memory/trigger/monthly ...")
            r_monthly = requests.post(f"{BASE_URL}/memory/trigger/monthly?end_date_str={today_str}", headers=headers)
            print(f"Monthly Status Code: {r_monthly.status_code}")
            print("Monthly Response:", json.dumps(r_monthly.json(), indent=2))

            # 5. Trigger yearly consolidation
            current_year = datetime.date.today().year
            print(f"\nTriggering yearly memory pipeline via POST /api/v1/memory/trigger/yearly for year {current_year}...")
            r_yearly = requests.post(f"{BASE_URL}/memory/trigger/yearly?year={current_year}", headers=headers)
            print(f"Yearly Status Code: {r_yearly.status_code}")
            print("Yearly Response:", json.dumps(r_yearly.json(), indent=2))

            # 6. Trigger interactions RAG index ingestion
            print("\nTriggering interactions RAG ingestion via POST /api/v1/memory/trigger/interactions ...")
            r_interactions = requests.post(f"{BASE_URL}/memory/trigger/interactions", headers=headers)
            print(f"Interactions Status Code: {r_interactions.status_code}")
            print("Interactions Response:", json.dumps(r_interactions.json(), indent=2))
            assert r_interactions.status_code == 200 and r_interactions.json().get("success"), "Interactions RAG ingestion failed!"

            # Verify FAISS files on disk
            check_faiss_indices()
        else:
            print("\nAPI returned failure or error status.")
    except Exception as e:
        print(f"Failed to parse JSON: {e}")
        print(f"Raw response: {r.text}")

def check_faiss_indices():
    """Verify that index.faiss and index.pkl files exist under data/faiss_indices/ for daily/ receptionist, customer, staff, etc."""
    indices_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "faiss_indices")
    print(f"\nVerifying FAISS indices in directory: {indices_dir}")
    
    agents = ["receptionist", "customer", "staff", "lead", "upsell", "reputation", "business_intelligence"]
    levels = ["daily", "weekly", "monthly", "yearly"]
    
    all_ok = True
    for agent in agents:
        print(f"\n[{agent.capitalize()} Memory Paths]")
        for level in levels:
            index_path = os.path.join(indices_dir, agent, level, "index.faiss")
            meta_path = os.path.join(indices_dir, agent, level, "index.pkl")
            
            exists = os.path.exists(index_path) and os.path.exists(meta_path)
            status = "FOUND" if exists else "NOT FOUND (Expected if no data in time range)"
            print(f"  - {level:7s}: {status}")
            
            # Daily and weekly are mandatory to exist since we have seeded data
            if level in ["daily", "weekly"] and not exists:
                all_ok = False
                
    # Also verify interactions index exists
    interactions_index = os.path.join(indices_dir, "customer_interactions", "index.faiss")
    interactions_meta = os.path.join(indices_dir, "customer_interactions", "index.pkl")
    interactions_exists = os.path.exists(interactions_index) and os.path.exists(interactions_meta)
    print(f"\n[Interactions RAG Index]")
    print(f"  - Status: {'FOUND' if interactions_exists else 'NOT FOUND'}")
    if not interactions_exists:
        all_ok = False

    if all_ok:
        print("\nVerification Success: All essential FAISS index collections are generated on disk!")
    else:
        print("\nVerification Warning: Some essential indices were not found or not created.")

if __name__ == "__main__":
    create_mock_activity_for_today()
    run_pipeline_via_api()
