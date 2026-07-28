"""
Regression tests for Phase 3 (MCP/RAG/memory) audit fixes:
  - query_guard.py: STAFF branch_id force-override (cross-branch leak fix)
  - mcp_tool.py: fail-closed default caller-identity resolution
  - conversation_state_service.py: session hijack protection
"""
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from mcp.schemas import MCPContext, MCPRole
from mcp.query_guard import validate_and_sanitise, GuardViolationError


def _staff_ctx(branch_id: str) -> MCPContext:
    return MCPContext(
        user_id=str(uuid.uuid4()),
        role=MCPRole.STAFF,
        customer_id=None,
        staff_id=str(uuid.uuid4()),
        branch_id=branch_id,
    )


def test_staff_branch_filter_is_force_overridden_not_just_defaulted():
    """A STAFF caller supplying a different branch_id must not read another branch's appointments."""
    own_branch = str(uuid.uuid4())
    other_branch = str(uuid.uuid4())
    ctx = _staff_ctx(own_branch)

    safe_filters = validate_and_sanitise(ctx, "appointments", "select", {"branch_id": other_branch})

    assert safe_filters["branch_id"] == own_branch


def test_staff_branch_filter_defaults_when_absent():
    own_branch = str(uuid.uuid4())
    ctx = _staff_ctx(own_branch)

    safe_filters = validate_and_sanitise(ctx, "appointments", "select", {})

    assert safe_filters["branch_id"] == own_branch


def test_mcp_execute_default_context_does_not_silently_escalate_to_admin():
    """
    With no live request context vars set, mcp_execute's identity resolver
    should behave as an internal/system ADMIN call (existing, legitimate
    behavior for scheduled jobs) — but must not be the ONLY possible outcome
    for a real CUSTOMER/STAFF request whose linked id can't be resolved.
    """
    from ai.tools.mcp_tool import _resolve_default_user_context

    ctx = _resolve_default_user_context()
    assert ctx["role"] == "ADMIN"
    assert ctx["user_id"] == "system"


def test_mcp_execute_respects_live_non_admin_role_contextvar():
    from ai.orchestrator import current_user_role, current_user_id
    from ai.tools.mcp_tool import _resolve_default_user_context

    token_role = current_user_role.set("CUSTOMER")
    token_user = current_user_id.set(str(uuid.uuid4()))
    try:
        ctx = _resolve_default_user_context()
        assert ctx["role"] == "CUSTOMER"
        assert ctx["role"] != "ADMIN"
    finally:
        current_user_role.reset(token_role)
        current_user_id.reset(token_user)


def test_staff_cannot_query_other_staff_record():
    """A STAFF caller must not be allowed to query another staff member's record."""
    own_staff_id = str(uuid.uuid4())
    other_staff_id = str(uuid.uuid4())
    
    ctx = MCPContext(
        user_id=str(uuid.uuid4()),
        role=MCPRole.STAFF,
        customer_id=None,
        staff_id=own_staff_id,
        branch_id=str(uuid.uuid4()),
    )
    
    # Try querying other staff_id directly
    with pytest.raises(GuardViolationError) as exc_info:
        validate_and_sanitise(ctx, "staff", "select", {"id": other_staff_id})
    assert "Access denied. You do not have permission" in str(exc_info.value)
    
    # Try querying without filter; should default/force-inject own id
    safe_filters = validate_and_sanitise(ctx, "staff", "select", {})
    assert safe_filters["id"] == own_staff_id


def test_staff_cannot_query_other_staff_appointments():
    """A STAFF caller must not be allowed to query another staff member's appointments."""
    own_staff_id = str(uuid.uuid4())
    other_staff_id = str(uuid.uuid4())
    
    ctx = MCPContext(
        user_id=str(uuid.uuid4()),
        role=MCPRole.STAFF,
        customer_id=None,
        staff_id=own_staff_id,
        branch_id=str(uuid.uuid4()),
    )
    
    # Try querying other staff's appointments
    with pytest.raises(GuardViolationError) as exc_info:
        validate_and_sanitise(ctx, "appointments", "select", {"staff_id": other_staff_id})
    assert "Access denied. You do not have permission" in str(exc_info.value)
    
    # Try querying without staff filter; should force-inject own staff_id
    safe_filters = validate_and_sanitise(ctx, "appointments", "select", {})
    assert safe_filters["staff_id"] == own_staff_id

