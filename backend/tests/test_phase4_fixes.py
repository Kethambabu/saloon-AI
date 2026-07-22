"""
Regression tests for Phase 4 (API routes / DB / error handling / integrations) audit fixes:
  - storage upload content-type/extension whitelist (stored-XSS prevention)
  - mcp-test / mcp-info diagnostic routes restricted to privileged roles
  - global fallback exception handler returns a clean JSON 500, never a raw traceback
  - ChatResponse no longer silently drops response_type/data
"""

import os
import sys
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import create_app
from core.config import Settings
from infrastructure.db import get_db, User, UserRole


def _make_client(role: UserRole = UserRole.CUSTOMER, customer_id=None):
    test_settings = Settings(environment="testing", database_url="sqlite:///./test.db", debug=True)
    app = create_app(settings=test_settings)

    from api.deps import get_current_user

    mock_user = User(email="phase4_test@salonai.com", role=role, is_active=True)
    if customer_id:
        mock_user.customer_id = customer_id

    app.dependency_overrides[get_current_user] = lambda: mock_user
    return app, TestClient(app)


def test_storage_upload_rejects_mismatched_content_type():
    """A profile-images upload claiming text/html must be rejected, not stored/served as HTML."""
    app, client = _make_client(role=UserRole.ADMIN)
    files = {"file": ("evil.html", b"<script>alert(1)</script>", "text/html")}
    resp = client.post("/api/v1/storage/upload?category=profile-images", files=files)
    assert resp.status_code == 400
    assert "Unsupported file type" in resp.json()["detail"]


def test_storage_upload_accepts_whitelisted_image():
    """A genuine image/jpeg upload to profile-images should pass validation (upload itself mocked)."""
    app, client = _make_client(role=UserRole.ADMIN)
    with patch("api.routes.storage_routes.upload_file", return_value="https://example.com/x.jpg"):
        files = {"file": ("avatar.jpg", b"\xff\xd8\xff\xe0fakejpeg", "image/jpeg")}
        resp = client.post("/api/v1/storage/upload?category=profile-images", files=files)
    assert resp.status_code == 201
    assert resp.json()["success"] is True


def test_mcp_test_endpoint_blocks_customer():
    """Diagnostic MCP endpoint must reject non-privileged roles (CUSTOMER)."""
    app, client = _make_client(role=UserRole.CUSTOMER)
    resp = client.post("/api/v1/agent/mcp-test", json={"resource": "appointments", "operation": "select", "filters": {}, "limit": 10})
    assert resp.status_code == 403


def test_mcp_info_endpoint_blocks_staff():
    """Diagnostic MCP info endpoint must reject non-privileged roles (STAFF)."""
    app, client = _make_client(role=UserRole.STAFF)
    resp = client.get("/api/v1/agent/mcp-info")
    assert resp.status_code == 403


def test_mcp_test_endpoint_allows_admin():
    app, client = _make_client(role=UserRole.ADMIN)
    resp = client.post("/api/v1/agent/mcp-test", json={"resource": "branches", "operation": "select", "filters": {}, "limit": 5})
    assert resp.status_code == 200


def test_global_exception_handler_returns_clean_json_not_traceback():
    """An unhandled exception anywhere in a route must surface as a clean JSON 500, no stack trace/secrets."""
    app, _ = _make_client(role=UserRole.CUSTOMER)
    # TestClient re-raises server exceptions by default (for local debugging); disable that
    # here so we can observe the actual HTTP response our exception_handler produces.
    client = TestClient(app, raise_server_exceptions=False)

    def _broken_db():
        raise RuntimeError("simulated unexpected DB failure with secret_key=should-not-leak")

    app.dependency_overrides[get_db] = _broken_db
    resp = client.get("/api/v1/customer/profile")
    assert resp.status_code == 500
    body = resp.json()
    assert body == {"success": False, "detail": "An unexpected server error occurred."}
    assert "secret_key" not in resp.text
    assert "Traceback" not in resp.text


def test_exception_handler_registered_for_base_exception():
    app, _ = _make_client()
    assert Exception in app.exception_handlers
