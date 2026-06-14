"""
domain/customer_service.py
===========================
Domain service layer for customer profile, loyalty, and preference management.

Responsibilities
----------------
* Expose a unified API for customer search, profile retrieval, loyalty
  management, booking history, and preference queries.
* Delegate storage operations to MCP tools and retrieval to RAG memory.

Author: SalonAI Platform Team
Phase:  2 – Enterprise Architecture
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Internal imports – discovery tools
# ---------------------------------------------------------------------------
from backend.tools.discovery_tools import search_for_customers  # type: ignore

# ---------------------------------------------------------------------------
# Internal imports – MCP execution helper
# ---------------------------------------------------------------------------
from backend.tools.mcp_tool import mcp_execute  # type: ignore

# ---------------------------------------------------------------------------
# Internal imports – RAG retriever for preference / memory queries
# ---------------------------------------------------------------------------
from backend.rag.retriever import search_customer_memory  # type: ignore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton holder
# ---------------------------------------------------------------------------
_customer_service_instance: Optional["CustomerService"] = None


class CustomerService:
    """Domain service for customer-facing operations.

    All public methods return a uniform ``Dict``::

        {"success": bool, "data": Any}   # success
        {"success": False, "error": str} # failure

    Use :func:`get_customer_service` to obtain the singleton.
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        logger.info("CustomerService initialised.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Search for customers matching a free-text query.

        Parameters
        ----------
        query:
            Name, phone number, or email fragment to search for.
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            ``{"success": True, "data": [<customer>, ...]}``
        """
        logger.info(
            "CustomerService.search | query=%r tenant_id=%s",
            query,
            tenant_id,
        )
        try:
            customers = search_for_customers(query=query, tenant_id=tenant_id)
            logger.info(
                "CustomerService.search | %d result(s) found | query=%r",
                len(customers) if isinstance(customers, list) else 0,
                query,
            )
            return {"success": True, "data": customers}

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "CustomerService.search | error | query=%r | %s",
                query,
                exc,
            )
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------

    def get_profile(
        self,
        customer_id: str,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Fetch the full profile record for a customer.

        Parameters
        ----------
        customer_id:
            Unique customer identifier.
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            ``{"success": True, "data": <customer_profile>}``
        """
        logger.info(
            "CustomerService.get_profile | customer_id=%s tenant_id=%s",
            customer_id,
            tenant_id,
        )
        try:
            result = mcp_execute(
                resource="customers",
                action="get",
                filters={"id": customer_id, "tenant_id": tenant_id},
            )
            profile = result.get("data") or result
            logger.debug(
                "CustomerService.get_profile | profile fetched | customer_id=%s",
                customer_id,
            )
            return {"success": True, "data": profile}

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "CustomerService.get_profile | error | customer_id=%s | %s",
                customer_id,
                exc,
            )
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------

    def get_loyalty_balance(
        self,
        customer_id: str,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Return the current loyalty points balance for a customer.

        Parameters
        ----------
        customer_id:
            Unique customer identifier.
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            ``{"success": True, "data": {"customer_id": ..., "loyalty_points": int}}``
        """
        logger.info(
            "CustomerService.get_loyalty_balance | customer_id=%s tenant_id=%s",
            customer_id,
            tenant_id,
        )
        try:
            result = mcp_execute(
                resource="customers",
                action="get",
                filters={"id": customer_id, "tenant_id": tenant_id},
            )
            profile = result.get("data") or result
            loyalty_points = (
                profile.get("loyalty_points") if isinstance(profile, dict) else 0
            )
            logger.info(
                "CustomerService.get_loyalty_balance | customer_id=%s points=%s",
                customer_id,
                loyalty_points,
            )
            return {
                "success": True,
                "data": {
                    "customer_id": customer_id,
                    "loyalty_points": loyalty_points,
                },
            }

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "CustomerService.get_loyalty_balance | error | customer_id=%s | %s",
                customer_id,
                exc,
            )
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------

    def award_loyalty_points(
        self,
        customer_id: str,
        points: int,
        reason: str,
        appointment_id: Optional[str] = None,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Award loyalty points and record a transaction.

        Parameters
        ----------
        customer_id:
            Customer receiving the points.
        points:
            Number of points to award (must be positive).
        reason:
            Human-readable reason for the award.
        appointment_id:
            Optional linked appointment identifier.
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            ``{"success": True, "data": {"transaction_id": ..., "points_awarded": int}}``
        """
        logger.info(
            "CustomerService.award_loyalty_points | customer_id=%s points=%d "
            "reason=%r appointment_id=%s tenant_id=%s",
            customer_id,
            points,
            reason,
            appointment_id,
            tenant_id,
        )
        try:
            if points <= 0:
                raise ValueError(f"points must be positive, got {points}")

            transaction_payload: Dict[str, Any] = {
                "customer_id": customer_id,
                "points": points,
                "reason": reason,
                "transaction_type": "AWARD",
                "recorded_at": datetime.utcnow().isoformat(),
                "tenant_id": tenant_id,
            }
            if appointment_id:
                transaction_payload["appointment_id"] = appointment_id

            result = mcp_execute(
                resource="loyalty_transactions",
                action="create",
                payload=transaction_payload,
            )

            transaction_id = (
                result.get("data", {}).get("id")
                if isinstance(result.get("data"), dict)
                else result.get("id")
            )
            logger.info(
                "CustomerService.award_loyalty_points | awarded %d pts | "
                "customer_id=%s transaction_id=%s",
                points,
                customer_id,
                transaction_id,
            )
            return {
                "success": True,
                "data": {
                    "transaction_id": transaction_id,
                    "customer_id": customer_id,
                    "points_awarded": points,
                    "reason": reason,
                },
            }

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "CustomerService.award_loyalty_points | error | customer_id=%s | %s",
                customer_id,
                exc,
            )
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------

    def get_booking_history(
        self,
        customer_id: str,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Return all appointment records for a customer.

        Parameters
        ----------
        customer_id:
            Customer whose history is requested.
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            ``{"success": True, "data": [<appointment>, ...]}``
        """
        logger.info(
            "CustomerService.get_booking_history | customer_id=%s tenant_id=%s",
            customer_id,
            tenant_id,
        )
        try:
            result = mcp_execute(
                resource="appointments",
                action="list",
                filters={"customer_id": customer_id, "tenant_id": tenant_id},
            )
            bookings = result.get("data", [])
            logger.info(
                "CustomerService.get_booking_history | %d record(s) | customer_id=%s",
                len(bookings) if isinstance(bookings, list) else 0,
                customer_id,
            )
            return {"success": True, "data": bookings}

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "CustomerService.get_booking_history | error | customer_id=%s | %s",
                customer_id,
                exc,
            )
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------

    def get_preferences(
        self,
        customer_id: str,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Retrieve stored preferences and memory fragments for a customer.

        Delegates to the RAG retriever's :func:`search_customer_memory`
        which queries the vector store for past interaction context.

        Parameters
        ----------
        customer_id:
            Customer whose preferences are requested.
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            ``{"success": True, "data": [<memory_fragment>, ...]}``
        """
        logger.info(
            "CustomerService.get_preferences | customer_id=%s tenant_id=%s",
            customer_id,
            tenant_id,
        )
        try:
            memories = search_customer_memory(
                customer_id=customer_id,
                tenant_id=tenant_id,
            )
            logger.info(
                "CustomerService.get_preferences | %d memory fragment(s) | customer_id=%s",
                len(memories) if isinstance(memories, list) else 0,
                customer_id,
            )
            return {"success": True, "data": memories}

        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "CustomerService.get_preferences | error | customer_id=%s | %s",
                customer_id,
                exc,
            )
            return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------


def get_customer_service() -> CustomerService:
    """Return the process-level singleton :class:`CustomerService`."""
    global _customer_service_instance  # pylint: disable=global-statement
    if _customer_service_instance is None:
        _customer_service_instance = CustomerService()
    return _customer_service_instance
