"""
MCP Schemas — Pydantic models for all MCP request/response types.

Every interaction with SalonMCP is typed through these schemas
to ensure consistent validation and serialisation across agents,
API endpoints, and the audit pipeline.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Role Enum
# ---------------------------------------------------------------------------

class MCPRole(str, Enum):
    """Roles recognised by the MCP permission system."""
    CUSTOMER = "CUSTOMER"
    STAFF = "STAFF"
    ADMIN = "ADMIN"


# ---------------------------------------------------------------------------
# MCP Context — attached to every request
# ---------------------------------------------------------------------------

class MCPContext(BaseModel):
    """
    Role-aware context injected into every MCP request.

    The context is built by context_builder.py from the authenticated user
    object and is the single source of truth for identity within the MCP layer.
    """

    user_id: str = Field(..., description="Primary key of the authenticated User record")
    role: MCPRole = Field(..., description="Role of the caller (CUSTOMER | STAFF | ADMIN)")

    # Optional identity references — populated depending on role
    customer_id: Optional[str] = Field(
        default=None,
        description="Associated customer profile ID (populated for CUSTOMER role)"
    )
    staff_id: Optional[str] = Field(
        default=None,
        description="Associated staff profile ID (populated for STAFF role)"
    )
    branch_id: Optional[str] = Field(
        default=None,
        description="Branch ID the staff member belongs to (STAFF only)"
    )

    # Request metadata
    session_id: Optional[str] = Field(
        default=None,
        description="Conversation/session ID from the calling agent or API"
    )
    request_timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="UTC timestamp when the context was created"
    )

    class Config:
        use_enum_values = True


# ---------------------------------------------------------------------------
# MCP Request
# ---------------------------------------------------------------------------

class MCPRequest(BaseModel):
    """
    Structured request sent to SalonMCP.

    Example — customer fetching own appointments::

        {
            "resource": "appointments",
            "operation": "select",
            "filters": {"customer_id": "abc-123"},
            "context": { ... }
        }
    """

    resource: str = Field(
        ...,
        description="Target resource/table (e.g. 'appointments', 'services', 'leads')"
    )
    operation: str = Field(
        default="select",
        description="Database operation: 'select' | 'insert' | 'update' | 'delete'"
    )
    filters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Key-value pairs used to filter the query (e.g. customer_id, branch_id)"
    )
    fields: Optional[List[str]] = Field(
        default=None,
        description="Optional list of specific fields/columns to return"
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Maximum number of rows to return"
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Row offset for pagination"
    )
    context: Optional[MCPContext] = Field(
        default=None,
        description="Caller context (role, ids). Injected automatically by the MCP layer."
    )

    class Config:
        use_enum_values = True


# ---------------------------------------------------------------------------
# MCP Response
# ---------------------------------------------------------------------------

class MCPResponse(BaseModel):
    """
    Standardised response envelope returned by every SalonMCP method.
    """

    success: bool = Field(..., description="True if the operation completed without errors")
    resource: str = Field(..., description="The resource that was queried")
    operation: str = Field(..., description="The operation that was executed")
    data: Any = Field(
        default=None,
        description="Query results — list of dicts, single dict, or None"
    )
    count: int = Field(
        default=0,
        description="Number of records in `data`"
    )
    error: Optional[str] = Field(
        default=None,
        description="Human-readable error message if success=False"
    )
    error_code: Optional[str] = Field(
        default=None,
        description="Machine-readable error code (e.g. PERMISSION_DENIED, GUARD_VIOLATION)"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Optional metadata (e.g. execution_time_ms, role used)"
    )


# ---------------------------------------------------------------------------
# MCP Test Endpoint models (used by /agent/mcp-test)
# ---------------------------------------------------------------------------

class MCPTestRequest(BaseModel):
    """
    Lightweight request model for the /agent/mcp-test endpoint.
    The caller provides resource + operation + optional filters.
    The endpoint injects the full MCPContext from the auth token.
    """
    resource: str = Field(..., description="Target resource, e.g. 'appointments'")
    operation: str = Field(default="select", description="'select' | 'insert' | 'update' | 'delete'")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Optional filters")
    limit: int = Field(default=20, ge=1, le=200)


class MCPTestResponse(BaseModel):
    """Response shape for the /agent/mcp-test endpoint."""
    success: bool
    resource: str
    operation: str
    role_used: str
    data: Any = None
    count: int = 0
    error: Optional[str] = None
    error_code: Optional[str] = None
    permission_granted: bool = False
    guard_passed: bool = False
    audit_logged: bool = False
