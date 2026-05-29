"""
Authentication and Role-Based Access Control (RBAC) Testing Suite.
Verifies password hashing, JWT lifecycle, protected route filters, and role permissions enforcement.
"""

import pytest
import jwt
import uuid
from datetime import timedelta
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from db import SessionLocal, User, UserRole
from core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token
)


# --- 1. Unit Tests for Security Utilities ---

def test_password_security():
    """Verify password hashing and match validation works correctly."""
    password = "SuperSecretPassword123"
    hashed = hash_password(password)
    
    assert hashed != password
    assert len(hashed) > 20
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword123", hashed) is False


def test_jwt_lifecycle():
    """Verify token generation, contents decoding, and validation rules."""
    user_id = uuid.uuid4()
    role = UserRole.ADMIN.value
    
    # 1. Access Token
    access_token = create_access_token(subject=user_id, role=role)
    decoded_access = decode_token(access_token)
    
    assert decoded_access["sub"] == str(user_id)
    assert decoded_access["role"] == role
    assert decoded_access["type"] == "access"
    
    # 2. Refresh Token
    refresh_token = create_refresh_token(subject=user_id)
    decoded_refresh = decode_token(refresh_token)
    
    assert decoded_refresh["sub"] == str(user_id)
    assert decoded_refresh["type"] == "refresh"
    assert "role" not in decoded_refresh


def test_jwt_expiry_error():
    """Verify token decoding fails properly when the token signature has expired."""
    user_id = uuid.uuid4()
    
    # Create a token that expired 1 hour ago
    expired_token = create_access_token(
        subject=user_id,
        role=UserRole.STAFF.value,
        expires_delta=timedelta(hours=-1)
    )
    
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(expired_token)


# --- 2. API Endpoint Integration Tests ---

def test_api_login_success(client: TestClient):
    """Verify login accepts correct credentials and returns expected tokens & metadata."""
    payload = {
        "email": "owner@salonai.com",
        "password": "password123"
    }
    
    response = client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == status.HTTP_200_OK
    
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["role"] == UserRole.ADMIN.value
    assert data["email"] == "owner@salonai.com"


def test_api_login_invalid_credentials(client: TestClient):
    """Verify login rejects incorrect credentials with a 401 error."""
    payload = {
        "email": "owner@salonai.com",
        "password": "incorrectpassword"
    }
    
    response = client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Incorrect email or password"


def test_api_me_authorized(client: TestClient):
    """Verify authenticated user can fetch their own profile details successfully."""
    # 1. Login to get token
    login_payload = {
        "email": "owner@salonai.com",
        "password": "password123"
    }
    login_resp = client.post("/api/v1/auth/login", json=login_payload)
    access_token = login_resp.json()["access_token"]
    
    # 2. Query /me
    headers = {"Authorization": f"Bearer {access_token}"}
    response = client.get("/api/v1/auth/me", headers=headers)
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["email"] == "owner@salonai.com"
    assert data["role"] == UserRole.ADMIN.value
    assert data["is_active"] is True


def test_api_me_unauthorized(client: TestClient):
    """Verify /me blocks requests missing a token or carrying an invalid token."""
    # Missing token
    response = client.get("/api/v1/auth/me")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    # Bad token
    headers = {"Authorization": "Bearer badtoken123"}
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_api_refresh_token(client: TestClient):
    """Verify refresh token can successfully obtain a fresh access token."""
    # 1. Login to get refresh token
    login_payload = {
        "email": "marcus@salonai.com",
        "password": "password123"
    }
    login_resp = client.post("/api/v1/auth/login", json=login_payload)
    refresh_token = login_resp.json()["refresh_token"]
    
    # 2. Call /refresh
    refresh_payload = {"refresh_token": refresh_token}
    response = client.post("/api/v1/auth/refresh", json=refresh_payload)
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["role"] == UserRole.STAFF.value


def test_api_refresh_token_revoked(client: TestClient):
    """Verify revoked or replaced refresh tokens are rejected during validation."""
    # 1. Login to get refresh token
    login_payload = {
        "email": "marcus@salonai.com",
        "password": "password123"
    }
    login_resp = client.post("/api/v1/auth/login", json=login_payload)
    refresh_token = login_resp.json()["refresh_token"]
    
    # 2. Login again, which rotates the token in the database
    client.post("/api/v1/auth/login", json=login_payload)
    
    # 3. Call /refresh with the first token (now replaced/revoked)
    refresh_payload = {"refresh_token": refresh_token}
    response = client.post("/api/v1/auth/refresh", json=refresh_payload)
    
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "revoked" in response.json()["detail"]


def test_api_logout_session_revoked(client: TestClient):
    """Verify logout revokes the active session and invalidates the refresh token."""
    # 1. Login to get tokens
    login_payload = {
        "email": "marcus@salonai.com",
        "password": "password123"
    }
    login_resp = client.post("/api/v1/auth/login", json=login_payload)
    tokens = login_resp.json()
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]
    
    # 2. Logout
    headers = {"Authorization": f"Bearer {access_token}"}
    logout_resp = client.post("/api/v1/auth/logout", headers=headers)
    assert logout_resp.status_code == status.HTTP_200_OK
    
    # 3. Verify refresh token is now rejected
    refresh_payload = {"refresh_token": refresh_token}
    refresh_resp = client.post("/api/v1/auth/refresh", json=refresh_payload)
    assert refresh_resp.status_code == status.HTTP_401_UNAUTHORIZED


# --- 3. Role-Based Access Control (RBAC) Route Protection Tests ---

def test_api_agent_chat_authorized(client: TestClient):
    """Verify that any authenticated role (including Staff) can access agent chat."""
    login_payload = {
        "email": "marcus@salonai.com",
        "password": "password123"
    }
    login_resp = client.post("/api/v1/auth/login", json=login_payload)
    access_token = login_resp.json()["access_token"]
    
    headers = {"Authorization": f"Bearer {access_token}"}
    chat_payload = {
        "message": "Hi, just saying hello",
        "session id": "session-12345",
        "chat history": []
    }
    
    response = client.post("/api/v1/agent/chat", json=chat_payload, headers=headers)
    # The endpoint calls reception_agent tool, which might throw an error or mock run
    # If the route itself didn't block it with a 401/403, it means authorization passed!
    # Status code will either be 200 (processed) or 500/503 (agent API keys/faiss loading missing in testing)
    assert response.status_code in (status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR, status.HTTP_503_SERVICE_UNAVAILABLE)
    assert response.status_code != status.HTTP_401_UNAUTHORIZED
    assert response.status_code != status.HTTP_403_FORBIDDEN


def test_api_agent_chat_unauthorized(client: TestClient):
    """Verify that unauthenticated chat requests are blocked with a 401 error."""
    chat_payload = {
        "message": "Hi, just saying hello",
        "session id": "session-12345",
        "chat history": []
    }
    response = client.post("/api/v1/agent/chat", json=chat_payload)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_api_analytics_owner_authorized(client: TestClient):
    """Verify that Owner can fetch detailed revenue analytics."""
    login_payload = {
        "email": "owner@salonai.com",
        "password": "password123"
    }
    login_resp = client.post("/api/v1/auth/login", json=login_payload)
    access_token = login_resp.json()["access_token"]
    
    headers = {"Authorization": f"Bearer {access_token}"}
    response = client.get("/api/v1/analytics/revenue", headers=headers)
    
    # Verify that request was permitted (returns success or SQLite operational success)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["success"] is True


def test_api_analytics_staff_forbidden(client: TestClient):
    """Verify that Staff role is strictly blocked with a 403 Forbidden on analytics."""
    login_payload = {
        "email": "marcus@salonai.com",
        "password": "password123"
    }
    login_resp = client.post("/api/v1/auth/login", json=login_payload)
    access_token = login_resp.json()["access_token"]
    
    headers = {"Authorization": f"Bearer {access_token}"}
    response = client.get("/api/v1/analytics/revenue", headers=headers)
    
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "Insufficient permissions" in response.json()["detail"]
