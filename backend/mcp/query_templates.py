"""
MCP Query Templates — Predefined, safe parameterized query templates.

This module provides a registry of named templates to prevent agents from needing
to formulate complex filters or raw queries themselves. All templates are validated
and mapped to standard MCP operations with strict parameter schemas.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple
from mcp.schemas import MCPContext

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Template Registry
# ---------------------------------------------------------------------------

TEMPLATES: Dict[str, Dict[str, Any]] = {
    "GET_MY_APPOINTMENTS": {
        "resource": "appointments",
        "operation": "select",
        "required_params": [],
        "description": "Fetch active appointments for the current context owner.",
    },
    "GET_BRANCH_STAFF": {
        "resource": "staff",
        "operation": "select",
        "required_params": ["branch_id"],
        "description": "Fetch all staff members associated with a specific branch.",
    },
    "GET_SERVICES_BY_PRICE": {
        "resource": "services",
        "operation": "select",
        "required_params": ["max_price"],
        "description": "Fetch active services cheaper than or equal to max_price.",
    },
    "GET_REVIEWS_BY_RATING": {
        "resource": "reviews",
        "operation": "select",
        "required_params": ["min_rating"],
        "description": "Fetch reviews with rating greater than or equal to min_rating.",
    },
    "GET_ACTIVE_LEADS_BY_BRANCH": {
        "resource": "leads",
        "operation": "select",
        "required_params": ["branch_id"],
        "description": "Fetch active new/contacted leads for a specific branch.",
    }
}


def list_templates() -> List[Dict[str, Any]]:
    """Return all registered templates and their specifications."""
    return [
        {"name": name, **spec}
        for name, spec in TEMPLATES.items()
    ]


def resolve_template(
    name: str,
    params: Dict[str, Any],
    context: MCPContext
) -> Tuple[str, str, Dict[str, Any]]:
    """
    Resolve a template name and its input parameters to a safe (resource, operation, filters) tuple.

    Raises:
        ValueError: if the template is unknown or required parameters are missing.
    """
    template_name = name.upper()
    if template_name not in TEMPLATES:
        raise ValueError(f"Unknown query template: '{name}'")

    spec = TEMPLATES[template_name]
    resource = spec["resource"]
    operation = spec["operation"]

    # Validate parameters
    for param in spec["required_params"]:
        if param not in params:
            raise ValueError(f"Template '{name}' requires parameter '{param}'.")

    # Map parameters to safe filters
    filters: Dict[str, Any] = {}

    if template_name == "GET_MY_APPOINTMENTS":
        # Scoped automatically by role context
        if context.role == "CUSTOMER":
            filters["customer_id"] = context.customer_id
        elif context.role == "STAFF":
            filters["staff_id"] = context.staff_id
        elif "customer_id" in params:
            filters["customer_id"] = params["customer_id"]
        elif "staff_id" in params:
            filters["staff_id"] = params["staff_id"]

    elif template_name == "GET_BRANCH_STAFF":
        filters["branch_id"] = params["branch_id"]
        filters["is_active"] = True

    elif template_name == "GET_SERVICES_BY_PRICE":
        # SalonMCP handles basic filtering; custom logic can be added in resource resolver
        filters["price"] = {"op": "le", "value": float(params["max_price"])}

    elif template_name == "GET_REVIEWS_BY_RATING":
        filters["rating"] = {"op": "ge", "value": int(params["min_rating"])}

    elif template_name == "GET_ACTIVE_LEADS_BY_BRANCH":
        filters["branch_id"] = params["branch_id"]
        filters["status"] = params.get("status", "NEW")

    # Merge any other safe optional filters passed
    for k, v in params.items():
        if k not in spec["required_params"] and k != "limit" and k != "offset":
            filters[k] = v

    return resource, operation, filters
