"""SalonAI Backend Utilities Package."""

from utils.entity_resolver import (
    resolve_branch,
    resolve_customer,
    resolve_service,
    resolve_staff,
    resolve_appointment,
    list_branches,
    list_services,
    list_staff,
    search_customers,
)
from utils.typed_responses import TypedAgentResponse
from utils.renderer import render_response

__all__ = [
    "resolve_branch",
    "resolve_customer",
    "resolve_service",
    "resolve_staff",
    "resolve_appointment",
    "list_branches",
    "list_services",
    "list_staff",
    "search_customers",
    # New in v2
    "TypedAgentResponse",
    "render_response",
]
