"""
RecommendationWorkflow — Phase 1 Capability Workflow for Max (Upsell).

Agents call recommendation_workflow() instead of constructing raw tool calls.

Covers:
  - fetch customer recommendations
  - accept recommendation
  - reject recommendation
  - get upsell analytics
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class RecommendationWorkflow:
    """
    Phase 1 workflow encapsulating all upsell / recommendation operations for Max.
    """

    @staticmethod
    def get_recommendations(customer_id: str) -> Dict[str, Any]:
        """Fetch personalized service recommendations for a customer."""
        logger.info("[RecommendationWorkflow] get_recommendations: customer=%s", customer_id)
        try:
            from ai.workflows.upsell_workflow import get_customer_recommendations_workflow
            return get_customer_recommendations_workflow(customer_id=customer_id)
        except Exception as exc:
            logger.error("[RecommendationWorkflow] get_recommendations failed: %s", exc)
            return {"success": False, "error": str(exc)}

    @staticmethod
    def accept_recommendation(
        customer_id: str,
        service_id: str,
        appointment_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record that a customer accepted an upsell recommendation."""
        logger.info(
            "[RecommendationWorkflow] accept_recommendation: customer=%s service=%s",
            customer_id, service_id
        )
        try:
            from ai.workflows.upsell_workflow import accept_recommendation_workflow
            return accept_recommendation_workflow(
                customer_id=customer_id,
                service_id=service_id,
                appointment_id=appointment_id,
            )
        except Exception as exc:
            logger.error("[RecommendationWorkflow] accept_recommendation failed: %s", exc)
            return {"success": False, "error": str(exc)}

    @staticmethod
    def reject_recommendation(
        customer_id: str,
        service_id: str,
        appointment_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Record that a customer rejected an upsell recommendation."""
        logger.info(
            "[RecommendationWorkflow] reject_recommendation: customer=%s service=%s",
            customer_id, service_id
        )
        try:
            from ai.workflows.upsell_workflow import reject_recommendation_workflow
            return reject_recommendation_workflow(
                customer_id=customer_id,
                service_id=service_id,
                appointment_id=appointment_id,
            )
        except Exception as exc:
            logger.error("[RecommendationWorkflow] reject_recommendation failed: %s", exc)
            return {"success": False, "error": str(exc)}

    @staticmethod
    def get_analytics() -> Dict[str, Any]:
        """Retrieve upsell performance analytics scorecard."""
        logger.info("[RecommendationWorkflow] get_analytics")
        try:
            from ai.workflows.upsell_workflow import get_upsell_analytics_workflow
            return get_upsell_analytics_workflow()
        except Exception as exc:
            logger.error("[RecommendationWorkflow] get_analytics failed: %s", exc)
            return {"success": False, "error": str(exc)}

