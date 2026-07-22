import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
import uuid
from datetime import date, time

from infrastructure.db import User, UserRole, Customer, Lead, LeadStatus, SessionLocal, Branch, Service, Appointment
from application.services.appointment_service import create_appointment

def test_lead_draft_flow(client: TestClient):
    # Clear any existing appointments and leads for the test customer to ensure test isolation
    db_init = SessionLocal()
    try:
        user_init = db_init.query(User).filter(User.email == "customer@example.com").first()
        if user_init:
            db_init.query(Appointment).filter(Appointment.customer_id == user_init.customer_id).delete()
            db_init.query(Lead).filter(Lead.customer_id == user_init.customer_id).delete()
            db_init.commit()
    finally:
        db_init.close()

    # 1. Login as customer
    login_resp = client.post("/api/v1/auth/login", json={
        "email": "customer@example.com",
        "password": "password123"
    })
    assert login_resp.status_code == status.HTTP_200_OK
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Retrieve branch and service to use in draft payload
    db = SessionLocal()
    try:
        branch = db.query(Branch).first()
        service = db.query(Service).first()
        assert branch is not None
        assert service is not None
        branch_id = str(branch.id)
        service_id = str(service.id)
    finally:
        db.close()

    # 2. Save draft lead
    draft_payload = {
        "branch_id": branch_id,
        "service_id": service_id,
        "date": "2026-06-10",
        "time": "14:30",
        "notes": "Testing manual booking draft lead creation."
    }
    
    response = client.post("/api/v1/leads/draft", json=draft_payload, headers=headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["success"] is True
    lead_id = response.json()["lead_id"]

    # 3. Get active lead
    active_resp = client.get("/api/v1/leads/active", headers=headers)
    assert active_resp.status_code == status.HTTP_200_OK
    active_lead = active_resp.json()
    assert active_lead is not None
    assert active_lead["id"] == lead_id
    assert active_lead["service_name"] == service.name
    assert active_lead["branch_id"] == branch_id
    assert active_lead["preferred_date"] == "2026-06-10"

    # 4. Save draft again to update
    updated_payload = {
        "branch_id": branch_id,
        "service_id": service_id,
        "date": "2026-06-12",
        "time": "15:00",
        "notes": "Updated notes."
    }
    update_resp = client.post("/api/v1/leads/draft", json=updated_payload, headers=headers)
    assert update_resp.status_code == status.HTTP_200_OK
    
    # Verify active lead updated
    active_resp2 = client.get("/api/v1/leads/active", headers=headers)
    assert active_resp2.status_code == status.HTTP_200_OK
    assert active_resp2.json()["preferred_date"] == "2026-06-12"
    assert active_resp2.json()["notes"] == "Updated notes."

    # 5. Book appointment and verify lead conversion
    # Create appointment using create_appointment logic
    from datetime import datetime, timedelta
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "customer@example.com").first()
        customer_id = str(user.customer_id)
        
        future_time = (datetime.now() + timedelta(days=3)).replace(hour=15, minute=0, second=0, microsecond=0)
        start_time_str = future_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        # Call booking tool
        appt_res = create_appointment(
            customer_id=customer_id,
            branch_id=branch_id,
            service_id=service_id,
            start_time=start_time_str,
            db=db
        )
        print("\nDEBUG APPT RESULT:", appt_res)
        assert appt_res["success"] is True
        
        # Verify the lead is now CONVERTED
        lead = db.query(Lead).filter(Lead.id == uuid.UUID(lead_id)).first()
        assert lead.status == LeadStatus.CONVERTED
        assert lead.converted is True
    finally:
        db.close()

