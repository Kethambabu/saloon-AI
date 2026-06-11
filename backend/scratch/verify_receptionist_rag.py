import os
import sys
import uuid
import datetime

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from main import create_app
from db.database import engine
from db.models import Base, User, UserRole
from core.config import get_settings

def run_verification():
    print("=" * 70)
    print("== Receptionist RAG & Local FAISS End-to-End Verification ==")
    print("=" * 70)

    # 1. Initialize DB schemas on the configured database
    print("\n[Step 1] Ensuring database schemas exist...")
    Base.metadata.create_all(bind=engine)
    print("Schemas verified.")

    # 2. Boot up FastAPI app with TestClient
    print("\n[Step 2] Initializing TestClient...")
    app = create_app()
    client = TestClient(app)
    print("TestClient ready.")

    # 3. Authenticate as Admin/Owner to get access token
    print("\n[Step 3] Logging in as Admin...")
    login_payload = {
        "email": "owner@salonai.com",
        "password": "password"
    }
    # Fallback to try password123 if password fails
    try:
        resp = client.post("/api/v1/auth/login", json=login_payload)
        if resp.status_code != 200:
            print("Trying fallback password 'password123'...")
            login_payload["password"] = "password123"
            resp = client.post("/api/v1/auth/login", json=login_payload)
        
        assert resp.status_code == 200, f"Login failed: {resp.text}"
        access_token = resp.json()["access_token"]
        print(f"Successfully logged in. Token: {access_token[:20]}...")
    except Exception as e:
        print(f"Authentication failed: {e}")
        return

    headers = {"Authorization": f"Bearer {access_token}"}

    # 4. Upload Cancellation Policy via admin API
    print("\n[Step 4] Uploading Cancellation Policy document...")
    cancel_text = (
        "Cancellation Policy Guidelines:\n"
        "1. Appointments must be cancelled at least 12 hours in advance.\n"
        "2. Cancellations made within 12 hours will incur a 30% penalty fee.\n"
        "3. No-shows will be charged the full service price."
    )
    upload_data = {
        "title": "Cancellation Policy V2",
        "document_type": "cancellation_policy"
    }
    upload_files = {
        "file": ("cancellation_policy.txt", cancel_text.encode("utf-8"), "text/plain")
    }
    resp = client.post("/api/v1/admin/knowledge/upload", data=upload_data, files=upload_files, headers=headers)
    assert resp.status_code == 201, f"Upload failed: {resp.text}"
    print("Cancellation policy uploaded and FAISS index rebuilt.")

    # 5. Create a Special Offer via admin API
    print("\n[Step 5] Creating a new Special Offer...")
    today = datetime.date.today()
    offer_payload = {
        "title": "Super Styling Special",
        "description": "Get a haircut and a facial for 25% off",
        "discount_pct": 25.0,
        "start_date": today.isoformat(),
        "end_date": (today + datetime.timedelta(days=10)).isoformat()
    }
    resp = client.post("/api/v1/admin/offers", json=offer_payload, headers=headers)
    assert resp.status_code == 201, f"Offer creation failed: {resp.text}"
    print("Special offer created and FAISS index rebuilt.")

    # 6. Test Clara agent's response to cancellation query
    print("\n[Step 6] Chatting with Clara regarding cancellation...")
    chat_payload = {
        "message": "Can I cancel my appointment? What is the policy?",
        "session_id": "verify-session-101",
        "chat_history": []
    }
    # Chatting as customer - requires customer profile. Log in as Alice (customer@example.com)
    print("Logging in as Customer Alice...")
    cust_login_payload = {
        "email": "customer@example.com",
        "password": "password"
    }
    resp = client.post("/api/v1/auth/login", json=cust_login_payload)
    if resp.status_code != 200:
        cust_login_payload["password"] = "password123"
        resp = client.post("/api/v1/auth/login", json=cust_login_payload)
    assert resp.status_code == 200, f"Customer login failed: {resp.text}"
    cust_token = resp.json()["access_token"]
    cust_headers = {"Authorization": f"Bearer {cust_token}"}

    resp = client.post("/api/v1/agent/chat", json=chat_payload, headers=cust_headers)
    if resp.status_code == 200:
        print(f"Agent responded successfully!")
        print("-" * 50)
        print(f"Agent Name: {resp.json().get('agent_name')}")
        print(f"Clara's Reply:\n{resp.json().get('response')}")
        print("-" * 50)
    else:
        print(f"Chat request failed with status {resp.status_code}: {resp.text}")

    # 7. Test Clara agent's response to special offers query
    print("\n[Step 7] Chatting with Clara regarding special offers...")
    chat_payload_offers = {
        "message": "Do you have any special offers or discounts?",
        "session_id": "verify-session-101",
        "chat_history": []
    }
    resp = client.post("/api/v1/agent/chat", json=chat_payload_offers, headers=cust_headers)
    if resp.status_code == 200:
        print(f"Agent responded successfully!")
        print("-" * 50)
        print(f"Agent Name: {resp.json().get('agent_name')}")
        print(f"Clara's Reply:\n{resp.json().get('response')}")
        print("-" * 50)
    else:
        print(f"Chat request failed with status {resp.status_code}: {resp.text}")

if __name__ == "__main__":
    run_verification()
