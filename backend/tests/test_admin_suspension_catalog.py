"""
Unit tests for Admin User deactivation/suspension features and catalog service management.
"""

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from db import SessionLocal, User, UserRole, Service
from core.security import hash_password


def test_get_users_admin_only(client: TestClient):
    """Verify that only admins can retrieve the user roster."""
    # 1. Staff login
    staff_login = client.post("/api/v1/auth/login", json={
        "email": "marcus@salonai.com",
        "password": "password123"
    })
    staff_token = staff_login.json()["access_token"]
    
    # Staff request roster -> Should be forbidden
    response = client.get("/api/v1/auth/users", headers={"Authorization": f"Bearer {staff_token}"})
    assert response.status_code == status.HTTP_403_FORBIDDEN
    
    # 2. Admin login
    admin_login = client.post("/api/v1/auth/login", json={
        "email": "owner@salonai.com",
        "password": "password123"
    })
    admin_token = admin_login.json()["access_token"]
    
    # Admin request roster -> Should be OK
    response = client.get("/api/v1/auth/users", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == status.HTTP_200_OK
    users_list = response.json()
    assert len(users_list) > 0
    assert any(u["email"] == "owner@salonai.com" for u in users_list)


def test_toggle_user_active_and_login_block(client: TestClient):
    """Verify deactivation endpoints and enforcement of the suspension login blocks."""
    db = SessionLocal()
    
    # Create a dummy user
    email = "suspend_test@example.com"
    pwd = "password123"
    hashed = hash_password(pwd)
    
    # Cleanup if already exists
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        db.delete(existing)
        db.commit()
        
    dummy_user = User(
        email=email,
        hashed_password=hashed,
        role=UserRole.STAFF,
        is_active=True
    )
    db.add(dummy_user)
    db.commit()
    db.refresh(dummy_user)
    user_id = str(dummy_user.id)
    
    # Admin login to get auth token
    admin_login = client.post("/api/v1/auth/login", json={
        "email": "owner@salonai.com",
        "password": "password123"
    })
    admin_token = admin_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    try:
        # 1. Toggle user active status to suspended
        resp = client.post(f"/api/v1/auth/users/{user_id}/toggle", headers=headers)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["success"] is True
        assert resp.json()["is_active"] is False
        
        # Verify in DB
        db.refresh(dummy_user)
        assert dummy_user.is_active is False
        
        # 2. Try to log in as the suspended user -> Should return 403
        login_resp = client.post("/api/v1/auth/login", json={
            "email": email,
            "password": pwd
        })
        assert login_resp.status_code == status.HTTP_403_FORBIDDEN
        assert "suspended" in login_resp.json()["detail"].lower()
        
        # 3. Toggle back to active
        resp2 = client.post(f"/api/v1/auth/users/{user_id}/toggle", headers=headers)
        assert resp2.status_code == status.HTTP_200_OK
        assert resp2.json()["is_active"] is True
        
        # 4. Try to log in again -> Should succeed
        login_resp2 = client.post("/api/v1/auth/login", json={
            "email": email,
            "password": pwd
        })
        assert login_resp2.status_code == status.HTTP_200_OK
        assert "access_token" in login_resp2.json()
        
    finally:
        # Clean up
        db.delete(dummy_user)
        db.commit()
        db.close()


def test_catalog_management(client: TestClient):
    """Verify admin is able to create services and update prices."""
    db = SessionLocal()
    
    # Admin login
    admin_login = client.post("/api/v1/auth/login", json={
        "email": "owner@salonai.com",
        "password": "password123"
    })
    admin_token = admin_login.json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}
    
    # 1. Create a service
    service_payload = {
        "name": "Super Deluxe Premium Styling",
        "description": "Premium luxury haircut and blowdry with styling experts",
        "price": 250.0,
        "duration_minutes": 90
    }
    
    # Clean up first if it exists
    existing = db.query(Service).filter(Service.name == service_payload["name"]).first()
    if existing:
        db.delete(existing)
        db.commit()
        
    resp_create = client.post("/api/v1/services", json=service_payload, headers=headers)
    assert resp_create.status_code == status.HTTP_201_CREATED
    created_data = resp_create.json()
    assert created_data["name"] == service_payload["name"]
    assert created_data["price"] == service_payload["price"]
    assert created_data["duration_minutes"] == service_payload["duration_minutes"]
    service_id = created_data["id"]
    
    try:
        # 2. Update service price
        update_payload = {"price": 280.0}
        resp_update = client.put(f"/api/v1/services/{service_id}", json=update_payload, headers=headers)
        assert resp_update.status_code == status.HTTP_200_OK
        assert resp_update.json()["price"] == 280.0
        
        # 3. Verify public catalog includes the new service
        resp_catalog = client.get("/api/v1/services")
        assert resp_catalog.status_code == status.HTTP_200_OK
        catalog = resp_catalog.json()
        assert any(item["id"] == service_id and item["price"] == 280.0 for item in catalog)
        
    finally:
        # Clean up
        db_service = db.query(Service).filter(Service.id == service_id).first()
        if db_service:
            db.delete(db_service)
            db.commit()
        db.close()
