"""
Services Layer — Phase 1 Architecture.

Exports Phase 1 services alongside all existing services.
"""

# ---------------------------------------------------------------------------
# Phase 1 Services
# ---------------------------------------------------------------------------
from services.entity_resolver_service import (
    resolve_entity_context,
    resolve_relative_date,
    resolve_relative_time,
    resolve_service_name,
    resolve_staff_name,
    resolve_customer_name,
    resolve_branch_name,
)

from services.conversation_state_service import (
    ConversationStateService,
    SessionState,
    ConversationTurn,
    get_state_service,
)

from services.permission_guard import (
    validate_workflow_permission,
    permission_check,
    get_allowed_actions,
    PermissionDeniedError,
)

__all__ = [
    # Entity Resolver
    "resolve_entity_context",
    "resolve_relative_date",
    "resolve_relative_time",
    "resolve_service_name",
    "resolve_staff_name",
    "resolve_customer_name",
    "resolve_branch_name",
    # Conversation State
    "ConversationStateService",
    "SessionState",
    "ConversationTurn",
    "get_state_service",
    # Permission Guard
    "validate_workflow_permission",
    "permission_check",
    "get_allowed_actions",
    "PermissionDeniedError",
]
