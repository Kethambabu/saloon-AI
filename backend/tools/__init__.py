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
    get_customer_history,
)

# Register booking tools in the global registry
_tool_registry.register(Tool("create_appointment", "Creates a new salon appointment with validation and overlap checking.", create_appointment))
_tool_registry.register(Tool("get_available_slots", "Retrieves all available time slots for a branch, date, stylist, and service.", get_available_slots))
_tool_registry.register(Tool("cancel_appointment", "Cancels an existing appointment, shifting its status to CANCELLED.", cancel_appointment))
_tool_registry.register(Tool("reschedule_appointment", "Reschedules an existing appointment to a new date and time, running validations.", reschedule_appointment))
_tool_registry.register(Tool("get_customer_history", "Gets complete past and upcoming booking history for a specific customer.", get_customer_history))

# Import lead CRM tools
from tools.lead_tools import (
    detect_abandoned_bookings,
    get_all_leads,
    create_lead,
    update_lead_status,
    create_followup_reminder,
    generate_followup_message,
    get_lead_conversion_analytics,
    get_lead_pipeline_summary,
)

# Register lead tools in the global registry
_tool_registry.register(Tool("detect_abandoned_bookings", "Detects customers with cancelled/no-show appointments who haven't rebooked.", detect_abandoned_bookings))
_tool_registry.register(Tool("get_all_leads", "Retrieves leads from the CRM database with optional filtering.", get_all_leads))
_tool_registry.register(Tool("create_lead", "Creates a new lead entry in the CRM pipeline.", create_lead))
_tool_registry.register(Tool("update_lead_status", "Advances a lead through the CRM pipeline by updating its status.", update_lead_status))
_tool_registry.register(Tool("create_followup_reminder", "Schedules a follow-up reminder for a lead via email, SMS, or phone.", create_followup_reminder))
_tool_registry.register(Tool("generate_followup_message", "Generates a personalised follow-up message based on customer/lead history.", generate_followup_message))
_tool_registry.register(Tool("get_lead_conversion_analytics", "Generates lead conversion analytics with pipeline distribution and rates.", get_lead_conversion_analytics))
_tool_registry.register(Tool("get_lead_pipeline_summary", "Returns a quick snapshot of the current lead pipeline counts.", get_lead_pipeline_summary))

# Import BI tools
from tools.bi_tools import (
    get_revenue_analytics,
    get_staff_performance_analytics,
    get_retention_analytics,
    get_service_popularity_analytics,
    execute_bi_sql_query,
)

# Register BI tools in the global registry
_tool_registry.register(Tool("get_revenue_analytics", "Retrieves complete revenue report metrics and line chart daily datasets.", get_revenue_analytics))
_tool_registry.register(Tool("get_staff_performance_analytics", "Retrieves performance benchmarks, utilization rates, and ratings per staff member.", get_staff_performance_analytics))
_tool_registry.register(Tool("get_retention_analytics", "Retrieves customer cohorts, repeat visitor rates, and lifetime value lists.", get_retention_analytics))
_tool_registry.register(Tool("get_service_popularity_analytics", "Retrieves popularity metrics and revenue share statistics per service item.", get_service_popularity_analytics))
_tool_registry.register(Tool("execute_bi_sql_query", "Executes raw SQL select queries inside a secure read-only sandboxed database session.", execute_bi_sql_query))

# Import reputation tools
from tools.reputation_tools import (
    fetch_reviews,
    get_review_analytics,
    detect_critical_reviews,
    generate_review_response,
    get_reputation_scorecard,
)

# Register reputation tools in the global registry
_tool_registry.register(Tool("fetch_reviews", "Fetches customer reviews from the database with optional branch, status, and rating filtering.", fetch_reviews))
_tool_registry.register(Tool("get_review_analytics", "Generates aggregated review analytics including star distribution, sentiment, and themes.", get_review_analytics))
_tool_registry.register(Tool("detect_critical_reviews", "Detects negative reviews requiring immediate attention and escalation.", detect_critical_reviews))
_tool_registry.register(Tool("generate_review_response", "Generates brand-safe professional responses to customer reviews with tone control.", generate_review_response))
_tool_registry.register(Tool("get_reputation_scorecard", "Generates NPS-style reputation scorecard with branch-level comparisons.", get_reputation_scorecard))


__all__ = [
    "Tool",
    "ToolRegistry",
    "get_tool_registry",
    "create_appointment",
    "get_available_slots",
    "cancel_appointment",
    "reschedule_appointment",
    "get_customer_history",
    "detect_abandoned_bookings",
    "get_all_leads",
    "create_lead",
    "update_lead_status",
    "create_followup_reminder",
    "generate_followup_message",
    "get_lead_conversion_analytics",
    "get_lead_pipeline_summary",
    "get_revenue_analytics",
    "get_staff_performance_analytics",
    "get_retention_analytics",
    "get_service_popularity_analytics",
    "execute_bi_sql_query",
    "fetch_reviews",
    "get_review_analytics",
    "detect_critical_reviews",
    "generate_review_response",
    "get_reputation_scorecard",
]

