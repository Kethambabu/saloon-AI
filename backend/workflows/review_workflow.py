"""
Review Workflows — Orchestrating review responses and critical escalations.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from tools.review_tools import (
    generate_response_tool,
    escalate_review_tool,
)

logger = logging.getLogger(__name__)


def respond_to_review_workflow(
    review_id: str,
    custom_response: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Workflow to draft and register a response to a review."""
    logger.info("[Workflow] Starting respond_to_review_workflow for review=%s", review_id)
    # The legacy tool returns a string result, let's wrap it in a dict for consistency
    try:
        response_str = generate_response_tool(review_id=review_id, custom_response=custom_response)
        return {"success": "Error" not in response_str, "result": response_str}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def escalate_review_workflow(
    review_id: str,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Workflow to escalate a critical negative review."""
    logger.info("[Workflow] Starting escalate_review_workflow for review=%s", review_id)
    try:
        response_str = escalate_review_tool(review_id=review_id)
        return {"success": "Error" not in response_str, "result": response_str}
    except Exception as exc:
        return {"success": False, "error": str(exc)}
