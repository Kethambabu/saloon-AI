"""
Integration and Security Tests for Staff Dashboard and Staff API Routes.
Verifies login, profile retrieval, dashboard metrics calculations, appointment retrieval, and RBAC guards.
"""

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from infrastructure.db import User, UserRole, Staff, Appointment, AppointmentStatus, SessionLocal

def test_staff_login_success(client: TestClient):
    """Verify that a staff member can log in successfully with correct credentials."""
    payload = {
        "email": "marcus@salonai.com",
        "password": "password123"
    }
    response = client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == status.HTTP_200_OK
    
    data = response.json()
    assert "access_token" in data
    assert data["role"] == UserRole.STAFF.value
    assert data["email"] == "marcus@salonai.com"


def test_staff_profile_and_dashboard(client: TestClient):
    """Verify staff profile and dashboard API details query successfully."""
    # 1. Login as staff
    login_resp = client.post("/api/v1/auth/login", json={
        "email": "marcus@salonai.com",
        "password": "password123"
    })
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Query staff details from db to make assertion dynamic
    db = SessionLocal()
    try:
        staff = db.query(Staff).filter(Staff.email == "marcus@salonai.com").first()
        assert staff is not None, "Seeded staff member not found in DB"
        expected_first = staff.first_name
        expected_last = staff.last_name
        expected_branch_id = str(staff.branch_id)
        expected_role = staff.role
    finally:
        db.close()

    # 2. Get staff profile
    profile_resp = client.get("/api/v1/staff/profile", headers=headers)
    assert profile_resp.status_code == status.HTTP_200_OK
    
    profile_data = profile_resp.json()
    assert profile_data["email"] == "marcus@salonai.com"
    assert profile_data["first_name"] == expected_first
    assert profile_data["last_name"] == expected_last
    assert profile_data["role"] == expected_role
    assert profile_data["branch_id"] == expected_branch_id

    # 3. Get staff dashboard details
    dash_resp = client.get("/api/v1/staff/dashboard", headers=headers)
    assert dash_resp.status_code == status.HTTP_200_OK
    
    dash_data = dash_resp.json()
    assert dash_data["staff_id"] == profile_data["id"]
    assert dash_data["name"] == f"{expected_first} {expected_last}"
    assert "today_appointments" in dash_data
    assert "upcoming_appointments" in dash_data
    assert "performance_metrics" in dash_data


def test_staff_appointments_endpoints(client: TestClient):
    """Verify staff appointments and performance metrics endpoints."""
    # Login
    login_resp = client.post("/api/v1/auth/login", json={
        "email": "marcus@salonai.com",
        "password": "password123"
    })
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Get today's appointments
    today_resp = client.get("/api/v1/staff/appointments/today", headers=headers)
    assert today_resp.status_code == status.HTTP_200_OK
    assert isinstance(today_resp.json(), list)

    # 2. Get upcoming appointments
    upcoming_resp = client.get("/api/v1/staff/appointments/upcoming", headers=headers)
    assert upcoming_resp.status_code == status.HTTP_200_OK
    assert isinstance(upcoming_resp.json(), list)

    # 3. Get performance metrics
    perf_resp = client.get("/api/v1/staff/performance", headers=headers)
    assert perf_resp.status_code == status.HTTP_200_OK
    perf_data = perf_resp.json()
    assert "total_appointments" in perf_data
    assert "average_rating" in perf_data


def test_staff_endpoints_role_guards(client: TestClient):
    """Verify role-based access control (RBAC) is enforced on staff endpoints."""
    # 1. Login as Customer
    login_cust = client.post("/api/v1/auth/login", json={
        "email": "customer@example.com",
        "password": "password123"
    })
    cust_token = login_cust.json()["access_token"]
    cust_headers = {"Authorization": f"Bearer {cust_token}"}

    # 2. Request staff dashboard as Customer - should be forbidden
    dash_resp = client.get("/api/v1/staff/dashboard", headers=cust_headers)
    assert dash_resp.status_code == status.HTTP_403_FORBIDDEN
    assert "only accessible to staff members" in dash_resp.json()["detail"]

    # 3. Request staff dashboard without authentication - should be unauthorized
    dash_unauth = client.get("/api/v1/staff/dashboard")
    assert dash_unauth.status_code == status.HTTP_401_UNAUTHORIZED

