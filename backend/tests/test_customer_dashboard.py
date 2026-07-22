"""
Integration and Security Tests for Customer Dashboard and Customer API Routes.
Verifies login, profile retrieval, dashboard metrics calculations, loyalty logs, and RBAC guards.
"""

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from infrastructure.db import User, UserRole, Customer, Appointment, AppointmentStatus, SessionLocal
from datetime import datetime, timezone, timedelta

def test_customer_login_success(client: TestClient):
    """Verify that a customer can log in successfully with correct credentials."""
    payload = {
        "email": "customer@example.com",
        "password": "password123"
    }
    response = client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == status.HTTP_200_OK
    
    data = response.json()
    assert "access_token" in data
    assert data["role"] == UserRole.CUSTOMER.value  # Customer role maps to UserRole.CUSTOMER internally
    assert data["email"] == "customer@example.com"


def test_customer_profile_and_dashboard(client: TestClient):
    """Verify customer profile and dashboard API details query successfully."""
    # 1. Login as customer
    login_resp = client.post("/api/v1/auth/login", json={
        "email": "customer@example.com",
        "password": "password123"
    })
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Query customer details from db to make assertion dynamic
    db = SessionLocal()
    try:
        customer = db.query(Customer).filter(Customer.email == "customer@example.com").first()
        assert customer is not None, "Seeded customer not found in DB"
        expected_first = customer.first_name
        expected_last = customer.last_name
    finally:
        db.close()

    # 2. Get customer profile
    profile_resp = client.get("/api/v1/customer/profile", headers=headers)
    assert profile_resp.status_code == status.HTTP_200_OK
    
    profile_data = profile_resp.json()
    assert profile_data["email"] == "customer@example.com"
    assert profile_data["first_name"] == expected_first
    assert profile_data["last_name"] == expected_last

    # 3. Get customer dashboard details
    dash_resp = client.get("/api/v1/customer/dashboard", headers=headers)
    assert dash_resp.status_code == status.HTTP_200_OK
    
    dash_data = dash_resp.json()
    assert dash_data["customer_id"] == profile_data["id"]
    assert dash_data["name"] == f"{expected_first} {expected_last}"
    assert "loyalty_points" in dash_data
    assert "total_appointments" in dash_data
    assert "recent_appointments" in dash_data
    assert "recent_reviews" in dash_data


def test_customer_loyalty_and_appointments(client: TestClient):
    """Verify customer loyalty points balance and transactions endpoints."""
    # Login
    login_resp = client.post("/api/v1/auth/login", json={
        "email": "customer@example.com",
        "password": "password123"
    })
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Get loyalty points balance
    balance_resp = client.get("/api/v1/customer/loyalty/balance", headers=headers)
    assert balance_resp.status_code == status.HTTP_200_OK
    
    balance_data = balance_resp.json()
    assert "current_balance" in balance_data
    assert "completed_appointments" in balance_data

    # 2. Get loyalty transactions
    transactions_resp = client.get("/api/v1/customer/loyalty/transactions", headers=headers)
    assert transactions_resp.status_code == status.HTTP_200_OK
    assert isinstance(transactions_resp.json(), list)

    # 3. Get customer appointment list
    appointments_resp = client.get("/api/v1/customer/appointments", headers=headers)
    assert appointments_resp.status_code == status.HTTP_200_OK
    assert isinstance(appointments_resp.json(), list)


def test_customer_endpoints_role_guards(client: TestClient):
    """Verify role-based access control (RBAC) is enforced on customer endpoints."""
    # 1. Login as Staff
    login_staff = client.post("/api/v1/auth/login", json={
        "email": "marcus@salonai.com",
        "password": "password123"
    })
    staff_token = login_staff.json()["access_token"]
    staff_headers = {"Authorization": f"Bearer {staff_token}"}

    # 2. Request customer dashboard as Staff - should be forbidden
    dash_resp = client.get("/api/v1/customer/dashboard", headers=staff_headers)
    assert dash_resp.status_code == status.HTTP_403_FORBIDDEN
    assert "only accessible to customers" in dash_resp.json()["detail"]

    # 3. Request customer dashboard without authentication - should be unauthorized
    dash_unauth = client.get("/api/v1/customer/dashboard")
    assert dash_unauth.status_code == status.HTTP_401_UNAUTHORIZED

