"""Tools module for agent capabilities"""

from typing import Dict, Any, Callable, Optional


class Tool:
    """Base tool class"""

    def __init__(self, name: str, description: str, func: Callable):
        """Initialize tool"""
        self.name = name
        self.description = description
        self.func = func

    async def execute(self, **kwargs) -> Any:
        """Execute tool"""
        return await self.func(**kwargs) if hasattr(self.func, '__await__') else self.func(**kwargs)


class ToolRegistry:
    """Registry for managing tools"""

    def __init__(self):
        """Initialize tool registry"""
        self.tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool"""
        self.tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name"""
        return self.tools.get(name)

    def list_tools(self) -> Dict[str, str]:
        """List all registered tools with descriptions"""
        return {name: tool.description for name, tool in self.tools.items()}


# Global tool registry
_tool_registry = ToolRegistry()


def get_tool_registry() -> ToolRegistry:
    """Get the global tool registry"""
    return _tool_registry


# Import booking tools
from tools.booking_tools import (
    create_appointment,
    get_available_slots,
    cancel_appointment,
    reschedule_appointment,
)

# Register booking tools in the global registry
_tool_registry.register(Tool("create_appointment", "Creates a new salon appointment with validation and overlap checking.", create_appointment))
_tool_registry.register(Tool("get_available_slots", "Retrieves all available time slots for a branch, date, stylist, and service.", get_available_slots))
_tool_registry.register(Tool("cancel_appointment", "Cancels an existing appointment, shifting its status to CANCELLED.", cancel_appointment))
_tool_registry.register(Tool("reschedule_appointment", "Reschedules an existing appointment to a new date and time, running validations.", reschedule_appointment))

# Import lead CRM tools
from tools.lead_tools import (
    detect_abandoned_bookings,
    create_lead,
    update_lead_status,
    create_followup_reminder,
    generate_followup_message,
)

# Register lead tools in the global registry
_tool_registry.register(Tool("detect_abandoned_bookings", "Detects customers with cancelled/no-show appointments who haven't rebooked.", detect_abandoned_bookings))
_tool_registry.register(Tool("create_lead", "Creates a new lead entry in the CRM pipeline.", create_lead))
_tool_registry.register(Tool("update_lead_status", "Advances a lead through the CRM pipeline by updating its status.", update_lead_status))
_tool_registry.register(Tool("create_followup_reminder", "Schedules a follow-up reminder for a lead via email, SMS, or phone.", create_followup_reminder))
_tool_registry.register(Tool("generate_followup_message", "Generates a personalised follow-up message based on customer/lead history.", generate_followup_message))

# Import BI tools
from tools.bi_tools import (
    execute_bi_sql_query,
)

# Register BI tools in the global registry
_tool_registry.register(Tool("execute_bi_sql_query", "Executes raw SQL select queries inside a secure read-only sandboxed database session.", execute_bi_sql_query))

# Import reputation tools
from tools.review_tools import (
    generate_response_tool,
    escalate_review_tool,
)

# Register reputation tools in the global registry
_tool_registry.register(Tool("generate_response_tool", "Generates brand-safe professional responses to customer reviews with tone control.", generate_response_tool))
_tool_registry.register(Tool("escalate_review_tool", "Escalate a review to the salon manager for review. Required for all critical reviews.", escalate_review_tool))

# Import MCP tools (unchanged — backward-compatible)
from tools.mcp_tool import (
    mcp_execute,
    mcp_write,
)

# Register MCP tools in the global registry
_tool_registry.register(Tool("mcp_execute", "Primary tool for executing role-aware read operations on database resources.", mcp_execute))
_tool_registry.register(Tool("mcp_write", "Primary tool for executing role-aware write operations on database resources.", mcp_write))

# ---------------------------------------------------------------------------
# Phase 1 — Capability Tools (one tool per agent)
# ---------------------------------------------------------------------------
from tools.capability_tools import (
    appointment_workflow,
    crm_workflow,
    recommendation_workflow,
    reputation_workflow,
    staff_workflow,
    analytics_workflow,
)

# Register Phase 1 capability tools
_tool_registry.register(Tool("appointment_workflow", "Unified appointment capability tool for Clara (Receptionist). Actions: check_availability, book, cancel, reschedule, history, list_services, list_staff, search_customers.", appointment_workflow))
_tool_registry.register(Tool("crm_workflow", "Unified CRM capability tool for Mia (Lead Follow-up). Actions: search_leads, create_lead, advance_lead, send_followup, generate_message, abandoned_bookings, conversion_analytics, pipeline_snapshot.", crm_workflow))
_tool_registry.register(Tool("recommendation_workflow", "Unified recommendation capability tool for Max (Upsell). Actions: get_recommendations, accept, reject, analytics.", recommendation_workflow))
_tool_registry.register(Tool("reputation_workflow", "Unified reputation capability tool for Olivia (Reputation). Actions: get_reviews, analytics, critical, respond, scorecard, escalate.", reputation_workflow))
_tool_registry.register(Tool("staff_workflow", "Unified staff capability tool for Atlas Staff. Actions: get_schedule, today_schedule, next_customer, customer_history, customer_preferences, staff_revenue, staff_performance, pending_appointments, create_leave, send_reminders.", staff_workflow))
_tool_registry.register(Tool("analytics_workflow", "Unified analytics capability tool for Atlas BI. Actions: dashboard, revenue, customers, staff, leads, reviews, upsell, insights, forecast, business_context, raw_sql, cohort_reminders.", analytics_workflow))


__all__ = [
    "Tool",
    "ToolRegistry",
    "get_tool_registry",
    # Booking tools (backward-compatible)
    "create_appointment",
    "get_available_slots",
    "cancel_appointment",
    "reschedule_appointment",
    # Lead tools (backward-compatible)
    "detect_abandoned_bookings",
    "create_lead",
    "update_lead_status",
    "create_followup_reminder",
    "generate_followup_message",
    # BI tools (backward-compatible)
    "execute_bi_sql_query",
    # Review tools (backward-compatible)
    "generate_response_tool",
    "escalate_review_tool",
    # MCP tools (backward-compatible)
    "mcp_execute",
    "mcp_write",
    # Phase 1 Capability Tools
    "appointment_workflow",
    "crm_workflow",
    "recommendation_workflow",
    "reputation_workflow",
    "staff_workflow",
    "analytics_workflow",
]
