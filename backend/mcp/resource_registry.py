"""
MCP Resource Registry — Central mapping of resource names to SQLAlchemy models.

Eliminates hardcoded model references scattered across MCP methods.
Every part of the codebase references RESOURCE_MAP instead of importing
individual models.

Phase 2 addition: AGGREGATE_MAP defines what metrics each resource supports
for Atlas's analytics operations.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Type


# ---------------------------------------------------------------------------
# Lazy model loader — avoids circular imports at module level
# ---------------------------------------------------------------------------

def _get_models():
    """Import DB models lazily."""
    from db import models as M
    return M


# ---------------------------------------------------------------------------
# Resource Map  (resource_name → SQLAlchemy model class)
# ---------------------------------------------------------------------------

def get_resource_map() -> Dict[str, Any]:
    """
    Return the canonical resource → model mapping.

    Loaded lazily to avoid circular imports on module load.
    """
    M = _get_models()
    return {
        "appointments":   M.Appointment,
        "customers":      M.Customer,
        "reviews":        M.Review,
        "services":       M.Service,
        "staff":          M.Staff,
        "leads":          M.Lead,
        "branches":       M.Branch,
        "loyalty_points": M.LoyaltyTransaction,
        "offers":         M.SpecialOffer,
        "knowledge":      M.KnowledgeDocument,
    }


# ---------------------------------------------------------------------------
# Aggregate Operation Definitions
# ---------------------------------------------------------------------------

#: Supported aggregate metrics per resource.
#: Used by SalonMCP.aggregate() and Atlas BI agent.
AGGREGATE_SUPPORT: Dict[str, List[str]] = {
    "appointments": ["count", "sum", "avg", "group_by"],
    "reviews":      ["count", "avg", "group_by"],
    "customers":    ["count", "group_by"],
    "services":     ["count", "sum", "avg"],
    "staff":        ["count", "group_by"],
    "leads":        ["count", "group_by"],
    "branches":     ["count"],
    "loyalty_points": ["count", "sum", "avg"],
}


#: Human-readable description of what each aggregate metric means per resource.
AGGREGATE_DESCRIPTIONS: Dict[str, Dict[str, str]] = {
    "appointments": {
        "count":    "Total number of appointments",
        "sum":      "Sum of a numeric column (e.g. service price)",
        "avg":      "Average of a numeric column",
        "group_by": "Group appointment counts by a field (e.g. status, branch_id, staff_id)",
    },
    "reviews": {
        "count":    "Total number of reviews",
        "avg":      "Average rating across all reviews",
        "group_by": "Group reviews by sentiment, rating, or branch_id",
    },
    "customers": {
        "count":    "Total active customer count",
        "group_by": "Group customers by city, is_active, or loyalty tier",
    },
    "leads": {
        "count":    "Total lead count",
        "group_by": "Group leads by status (NEW/CONTACTED/CONVERTED/LOST) or branch",
    },
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def resolve_model(resource: str) -> Optional[Any]:
    """
    Return the SQLAlchemy model class for a given resource name.

    Returns None if the resource is not in the registry.
    """
    return get_resource_map().get(resource.lower().strip())


def list_resources() -> List[str]:
    """Return sorted list of all registered resource names."""
    return sorted(get_resource_map().keys())


def supports_aggregate(resource: str, metric: str) -> bool:
    """
    Return True if the resource supports the given aggregate metric.
    """
    resource = resource.lower().strip()
    metric = metric.lower().strip()
    return metric in AGGREGATE_SUPPORT.get(resource, [])
