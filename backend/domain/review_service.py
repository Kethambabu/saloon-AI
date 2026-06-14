"""
domain/review_service.py
=========================
Domain service layer for customer review management and quality analytics.

Responsibilities
----------------
* Retrieve, filter, and aggregate reviews via MCP.
* Orchestrate review response and escalation workflows.
* Publish domain events for critical review actions.

Author: SalonAI Platform Team
Phase:  2 – Enterprise Architecture
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Internal imports – review workflows
# ---------------------------------------------------------------------------
from backend.workflows.review_workflow import (
    respond_to_review_workflow,
    escalate_review_workflow,
)  # type: ignore

# ---------------------------------------------------------------------------
# Internal imports – MCP execution helper
# ---------------------------------------------------------------------------
from backend.tools.mcp_tool import mcp_execute  # type: ignore

# ---------------------------------------------------------------------------
# Internal imports – event bus
# ---------------------------------------------------------------------------
from backend.core.event_bus import (
    get_event_bus,
    ReviewSubmittedEvent,
)  # type: ignore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton holder
# ---------------------------------------------------------------------------
_review_service_instance: Optional["ReviewService"] = None


class ReviewService:
    """Domain service for review retrieval, response, and analytics.

    All public methods return a uniform ``Dict``::

        {"success": bool, "data": Any}   # success
        {"success": False, "error": str} # failure

    Use :func:`get_review_service` to obtain the singleton.
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        self._event_bus = get_event_bus()
        logger.info("ReviewService initialised.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_reviews(
        self,
        customer_id: Optional[str] = None,
        staff_id: Optional[str] = None,
        sentiment: Optional[str] = None,
        rating: Optional[int] = None,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Fetch reviews with optional filters.

        Parameters
        ----------
        customer_id:
            Optional filter by reviewing customer.
        staff_id:
            Optional filter by reviewed staff member.
        sentiment:
            Optional sentiment label (e.g., ``"POSITIVE"``, ``"NEGATIVE"``,
            ``"CRITICAL"``).
        rating:
            Optional numeric rating filter (1–5).
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            ``{"success": True, "data": [<review>, ...]}``
        """
        logger.info(
            "ReviewService.get_reviews | customer_id=%s staff_id=%s sentiment=%s "
            "rating=%s tenant_id=%s",
            customer_id,
            staff_id,
            sentiment,
            rating,
            tenant_id,
        )
        try:
            filters: Dict[str, Any] = {"tenant_id": tenant_id}
            if customer_id:
                filters["customer_id"] = customer_id
            if staff_id:
                filters["staff_id"] = staff_id
            if sentiment:
                filters["sentiment"] = sentiment
            if rating is not None:
                filters["rating"] = rating

            result = mcp_execute(
                resource="reviews",
                action="list",
                filters=filters,
            )
            reviews = result.get("data", [])
            logger.info(
                "ReviewService.get_reviews | %d review(s) fetched | filters=%s",
                len(reviews) if isinstance(reviews, list) else 0,
                filters,
            )
            return {"success": True, "data": reviews}

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "ReviewService.get_reviews | error | tenant_id=%s | %s",
                tenant_id,
                exc,
            )
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------

    def get_critical(
        self,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Retrieve all reviews classified with ``CRITICAL`` sentiment.

        Parameters
        ----------
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            ``{"success": True, "data": [<critical_review>, ...]}``
        """
        logger.info(
            "ReviewService.get_critical | tenant_id=%s",
            tenant_id,
        )
        try:
            result = mcp_execute(
                resource="reviews",
                action="list",
                filters={"tenant_id": tenant_id, "sentiment": "CRITICAL"},
            )
            critical = result.get("data", [])
            logger.info(
                "ReviewService.get_critical | %d critical review(s) | tenant_id=%s",
                len(critical) if isinstance(critical, list) else 0,
                tenant_id,
            )
            return {"success": True, "data": critical}

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "ReviewService.get_critical | error | tenant_id=%s | %s",
                tenant_id,
                exc,
            )
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------

    def draft_response(
        self,
        review_id: str,
        custom_response: Optional[str] = None,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Draft and persist a response to a review, then publish a domain event.

        Calls :func:`respond_to_review_workflow` which handles AI-assisted
        response generation (or uses ``custom_response`` if provided) and
        persists the reply. On success a :class:`ReviewSubmittedEvent` is
        published with ``responded=True`` to notify downstream consumers.

        Parameters
        ----------
        review_id:
            The review to respond to.
        custom_response:
            Optional pre-written response text; AI generation is skipped
            when provided.
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            ``{"success": True, "data": <response_record>}``
        """
        logger.info(
            "ReviewService.draft_response | review_id=%s custom=%s tenant_id=%s",
            review_id,
            bool(custom_response),
            tenant_id,
        )
        try:
            result = respond_to_review_workflow(
                review_id=review_id,
                custom_response=custom_response,
                tenant_id=tenant_id,
            )

            if not result.get("success"):
                logger.warning(
                    "ReviewService.draft_response | workflow failed | review_id=%s | error=%s",
                    review_id,
                    result.get("error"),
                )
                return result

            # Publish event: review has been responded to
            event = ReviewSubmittedEvent(
                tenant_id=tenant_id,
                payload={
                    "review_id": review_id,
                    "responded": True,
                    "tenant_id": tenant_id,
                    "responded_at": datetime.utcnow().isoformat(),
                }
            )
            self._event_bus.publish(event)
            logger.info(
                "ReviewService.draft_response | ReviewSubmittedEvent published | review_id=%s",
                review_id,
            )

            return {"success": True, "data": result.get("data", {})}

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "ReviewService.draft_response | error | review_id=%s | %s",
                review_id,
                exc,
            )
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------

    def escalate(
        self,
        review_id: str,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Escalate a critical review to management.

        Parameters
        ----------
        review_id:
            The review to escalate.
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            ``{"success": True, "data": <escalation_record>}``
        """
        logger.info(
            "ReviewService.escalate | review_id=%s tenant_id=%s",
            review_id,
            tenant_id,
        )
        try:
            result = escalate_review_workflow(
                review_id=review_id,
                tenant_id=tenant_id,
            )
            logger.info(
                "ReviewService.escalate | escalation complete | review_id=%s",
                review_id,
            )
            return result if isinstance(result, dict) else {"success": True, "data": result}

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "ReviewService.escalate | error | review_id=%s | %s",
                review_id,
                exc,
            )
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------

    def get_scorecard(
        self,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Return an aggregated review count breakdown grouped by sentiment.

        Parameters
        ----------
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            ``{"success": True, "data": [{"sentiment": str, "count": int}, ...]}``
        """
        logger.info("ReviewService.get_scorecard | tenant_id=%s", tenant_id)
        try:
            result = mcp_execute(
                resource="reviews",
                action="aggregate",
                filters={"tenant_id": tenant_id},
                aggregation={"group_by": "sentiment", "count": True},
            )
            scorecard = result.get("data", [])
            logger.info(
                "ReviewService.get_scorecard | %d sentiment bucket(s) | tenant_id=%s",
                len(scorecard) if isinstance(scorecard, list) else 0,
                tenant_id,
            )
            return {"success": True, "data": scorecard}

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "ReviewService.get_scorecard | error | tenant_id=%s | %s",
                tenant_id,
                exc,
            )
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------

    def get_analytics(
        self,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Return aggregate average rating and distribution analytics.

        Parameters
        ----------
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            ``{"success": True, "data": {"avg_rating": float, ...}}``
        """
        logger.info("ReviewService.get_analytics | tenant_id=%s", tenant_id)
        try:
            result = mcp_execute(
                resource="reviews",
                action="aggregate",
                filters={"tenant_id": tenant_id},
                aggregation={"avg": "rating"},
            )
            analytics = result.get("data", {})
            logger.info(
                "ReviewService.get_analytics | analytics fetched | tenant_id=%s",
                tenant_id,
            )
            return {"success": True, "data": analytics}

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "ReviewService.get_analytics | error | tenant_id=%s | %s",
                tenant_id,
                exc,
            )
            return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------


def get_review_service() -> ReviewService:
    """Return the process-level singleton :class:`ReviewService`."""
    global _review_service_instance  # pylint: disable=global-statement
    if _review_service_instance is None:
        _review_service_instance = ReviewService()
    return _review_service_instance
