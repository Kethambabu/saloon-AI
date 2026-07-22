"""
Upsell Workflows — Orchestrating customer recommendations, acceptance, and rejection.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from application.services.recommendation_service import (
    get_customer_recommendations_tool,
    accept_recommendation_tool,
    reject_recommendation_tool,
    get_upsell_analytics_tool,
)

logger = logging.getLogger(__name__)


def get_customer_recommendations_workflow(customer_id: str) -> Dict[str, Any]:
    """Workflow to generate service suggestions for a customer."""
    try:
        res_str = get_customer_recommendations_tool(customer_id)
        return {"success": "Error" not in res_str, "result": res_str}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def accept_recommendation_workflow(
    customer_id: str,
    service_id: str,
    appointment_id: Optional[str] = None
) -> Dict[str, Any]:
    """Workflow to accept an upsell suggestion."""
    try:
        res_str = accept_recommendation_tool(customer_id, service_id, appointment_id)
        return {"success": "Error" not in res_str, "result": res_str}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def reject_recommendation_workflow(
    customer_id: str,
    service_id: str,
    appointment_id: Optional[str] = None
) -> Dict[str, Any]:
    """Workflow to reject an upsell suggestion."""
    try:
        res_str = reject_recommendation_tool(customer_id, service_id, appointment_id)
        return {"success": "Error" not in res_str, "result": res_str}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def get_upsell_analytics_workflow() -> Dict[str, Any]:
    """Workflow to retrieve upsell analytics scorecard."""
    try:
        res_str = get_upsell_analytics_tool()
        return {"success": "Error" not in res_str, "result": res_str}
    except Exception as exc:
        return {"success": False, "error": str(exc)}

