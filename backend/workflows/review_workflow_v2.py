"""
ReviewWorkflow — Phase 1 Capability Workflow for Olivia (Reputation).

Agents call reputation_workflow() instead of raw mcp_read/execute_transaction.

Covers:
  - view customer reviews
  - view review analytics
  - find critical reviews
  - draft review response
  - view reputation scorecard
  - escalate customer review
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ReviewWorkflow:
    """
    Phase 1 workflow encapsulating all reputation / review operations for Olivia.
    """

    @staticmethod
    def get_reviews(
        customer_id: Optional[str] = None,
        staff_id: Optional[str] = None,
        sentiment: Optional[str] = None,
        rating: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Retrieve customer reviews matching filter criteria."""
        logger.info(
            "[ReviewWorkflow] get_reviews: customer=%s staff=%s sentiment=%s rating=%s",
            customer_id, staff_id, sentiment, rating
        )
        try:
            from tools.mcp_tool import mcp_execute
            filters: Dict[str, Any] = {}
            if customer_id:
                filters["customer_id"] = customer_id
            if staff_id:
                filters["staff_id"] = staff_id
            if sentiment:
                filters["sentiment"] = sentiment.upper()
            if rating:
                filters["rating"] = rating
            return mcp_execute(
                resource="reviews",
                operation="select",
                filters=filters,
                agent_name="Olivia_Reputation",
            )
        except Exception as exc:
            logger.error("[ReviewWorkflow] get_reviews failed: %s", exc)
            return {"success": False, "error": str(exc)}

    @staticmethod
    def get_analytics() -> Dict[str, Any]:
        """Generate comprehensive reputation analytics."""
        logger.info("[ReviewWorkflow] get_analytics")
        try:
            from tools.mcp_tool import mcp_execute
            return mcp_execute(
                resource="reviews",
                operation="aggregate",
                metric="avg",
                agent_name="Olivia_Reputation",
            )
        except Exception as exc:
            logger.error("[ReviewWorkflow] get_analytics failed: %s", exc)
            return {"success": False, "error": str(exc)}

    @staticmethod
    def get_critical_reviews() -> Dict[str, Any]:
        """Retrieve all critical-sentiment reviews requiring urgent attention."""
        logger.info("[ReviewWorkflow] get_critical_reviews")
        try:
            from tools.mcp_tool import mcp_execute
            return mcp_execute(
                resource="reviews",
                operation="select",
                filters={"sentiment": "CRITICAL"},
                agent_name="Olivia_Reputation",
            )
        except Exception as exc:
            logger.error("[ReviewWorkflow] get_critical_reviews failed: %s", exc)
            return {"success": False, "error": str(exc)}

    @staticmethod
    def draft_response(
        review_id: str,
        custom_response: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Draft or register a salon response to a specific customer review."""
        logger.info("[ReviewWorkflow] draft_response: review=%s", review_id)
        try:
            from workflows.review_workflow import respond_to_review_workflow
            return respond_to_review_workflow(
                review_id=review_id,
                custom_response=custom_response,
            )
        except Exception as exc:
            logger.error("[ReviewWorkflow] draft_response failed: %s", exc)
            return {"success": False, "error": str(exc)}

    @staticmethod
    def get_scorecard() -> Dict[str, Any]:
        """Generate the overall reputation metrics scorecard."""
        logger.info("[ReviewWorkflow] get_scorecard")
        try:
            from tools.mcp_tool import mcp_execute
            return mcp_execute(
                resource="reviews",
                operation="aggregate",
                metric="count",
                group_by="sentiment",
                agent_name="Olivia_Reputation",
            )
        except Exception as exc:
            logger.error("[ReviewWorkflow] get_scorecard failed: %s", exc)
            return {"success": False, "error": str(exc)}

    @staticmethod
    def escalate_review(review_id: str) -> Dict[str, Any]:
        """Escalate a critical customer review to management."""
        logger.info("[ReviewWorkflow] escalate_review: review=%s", review_id)
        try:
            from workflows.review_workflow import escalate_review_workflow
            return escalate_review_workflow(review_id=review_id)
        except Exception as exc:
            logger.error("[ReviewWorkflow] escalate_review failed: %s", exc)
            return {"success": False, "error": str(exc)}
