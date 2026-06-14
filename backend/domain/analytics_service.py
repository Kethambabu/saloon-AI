"""
domain/analytics_service.py
============================
Domain service layer for business intelligence and analytics.

Responsibilities
----------------
* Expose a unified analytics API backed by the BI agent.
* Subscribe to domain events and persist metric increments for real-time
  analytics tracking.
* Return rich BI summaries, forecasts, and AI-generated insights.

Author: SalonAI Platform Team
Phase:  2 – Enterprise Architecture
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Internal imports – BI agent
# ---------------------------------------------------------------------------
from backend.agents.bi_agent import (
    get_dashboard_summary,
    get_revenue_summary,
    get_customer_summary,
    get_staff_summary,
    get_lead_summary,
    get_review_summary,
    get_upsell_summary,
    forecast_revenue,
    generate_ai_insights,
)  # type: ignore

# ---------------------------------------------------------------------------
# Internal imports – MCP execution helper (for metric persistence)
# ---------------------------------------------------------------------------
from backend.tools.mcp_tool import mcp_execute  # type: ignore

# ---------------------------------------------------------------------------
# Internal imports – event bus
# ---------------------------------------------------------------------------
from backend.core.event_bus import (
    get_event_bus,
    AppointmentBookedEvent,
)  # type: ignore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Singleton holder
# ---------------------------------------------------------------------------
_analytics_service_instance: Optional["AnalyticsService"] = None


class AnalyticsService:
    """Domain service for business analytics and BI reporting.

    All public methods return a uniform ``Dict``::

        {"success": bool, "data": Any}   # success
        {"success": False, "error": str} # failure

    Use :func:`get_analytics_service` to obtain the singleton and call
    :func:`register_event_subscribers` to enable event-driven metric
    tracking.
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        self._event_bus = get_event_bus()
        logger.info("AnalyticsService initialised.")

    # ------------------------------------------------------------------
    # Public BI API
    # ------------------------------------------------------------------

    def get_dashboard(
        self,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Return the high-level KPI dashboard summary.

        Parameters
        ----------
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            ``{"success": True, "data": <dashboard_summary>}``
        """
        logger.info("AnalyticsService.get_dashboard | tenant_id=%s", tenant_id)
        try:
            data = get_dashboard_summary(tenant_id=tenant_id)
            return {"success": True, "data": data}
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "AnalyticsService.get_dashboard | error | tenant_id=%s | %s",
                tenant_id,
                exc,
            )
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------

    def get_revenue(
        self,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Return a revenue summary across all branches and periods.

        Parameters
        ----------
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            ``{"success": True, "data": <revenue_summary>}``
        """
        logger.info("AnalyticsService.get_revenue | tenant_id=%s", tenant_id)
        try:
            data = get_revenue_summary(tenant_id=tenant_id)
            return {"success": True, "data": data}
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "AnalyticsService.get_revenue | error | tenant_id=%s | %s",
                tenant_id,
                exc,
            )
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------

    def get_customer_metrics(
        self,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Return customer acquisition, retention, and churn metrics.

        Parameters
        ----------
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            ``{"success": True, "data": <customer_summary>}``
        """
        logger.info("AnalyticsService.get_customer_metrics | tenant_id=%s", tenant_id)
        try:
            data = get_customer_summary(tenant_id=tenant_id)
            return {"success": True, "data": data}
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "AnalyticsService.get_customer_metrics | error | tenant_id=%s | %s",
                tenant_id,
                exc,
            )
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------

    def get_staff_performance(
        self,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Return aggregated performance metrics across all staff members.

        Parameters
        ----------
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            ``{"success": True, "data": <staff_summary>}``
        """
        logger.info("AnalyticsService.get_staff_performance | tenant_id=%s", tenant_id)
        try:
            data = get_staff_summary(tenant_id=tenant_id)
            return {"success": True, "data": data}
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "AnalyticsService.get_staff_performance | error | tenant_id=%s | %s",
                tenant_id,
                exc,
            )
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------

    def get_lead_analytics(
        self,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Return lead pipeline and conversion analytics.

        Parameters
        ----------
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            ``{"success": True, "data": <lead_summary>}``
        """
        logger.info("AnalyticsService.get_lead_analytics | tenant_id=%s", tenant_id)
        try:
            data = get_lead_summary(tenant_id=tenant_id)
            return {"success": True, "data": data}
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "AnalyticsService.get_lead_analytics | error | tenant_id=%s | %s",
                tenant_id,
                exc,
            )
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------

    def get_review_analytics(
        self,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Return review sentiment and rating analytics.

        Parameters
        ----------
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            ``{"success": True, "data": <review_summary>}``
        """
        logger.info("AnalyticsService.get_review_analytics | tenant_id=%s", tenant_id)
        try:
            data = get_review_summary(tenant_id=tenant_id)
            return {"success": True, "data": data}
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "AnalyticsService.get_review_analytics | error | tenant_id=%s | %s",
                tenant_id,
                exc,
            )
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------

    def get_upsell_analytics(
        self,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Return upsell opportunity and conversion analytics.

        Parameters
        ----------
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            ``{"success": True, "data": <upsell_summary>}``
        """
        logger.info("AnalyticsService.get_upsell_analytics | tenant_id=%s", tenant_id)
        try:
            data = get_upsell_summary(tenant_id=tenant_id)
            return {"success": True, "data": data}
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "AnalyticsService.get_upsell_analytics | error | tenant_id=%s | %s",
                tenant_id,
                exc,
            )
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------

    def get_forecast(
        self,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Return a revenue forecast for the coming period.

        Parameters
        ----------
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            ``{"success": True, "data": <forecast>}``
        """
        logger.info("AnalyticsService.get_forecast | tenant_id=%s", tenant_id)
        try:
            data = forecast_revenue(tenant_id=tenant_id)
            return {"success": True, "data": data}
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "AnalyticsService.get_forecast | error | tenant_id=%s | %s",
                tenant_id,
                exc,
            )
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------

    def get_insights(
        self,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """Generate AI-powered business insights.

        Parameters
        ----------
        tenant_id:
            Multi-tenant discriminator.

        Returns
        -------
        Dict
            ``{"success": True, "data": [<insight>, ...]}``
        """
        logger.info("AnalyticsService.get_insights | tenant_id=%s", tenant_id)
        try:
            data = generate_ai_insights(tenant_id=tenant_id)
            return {"success": True, "data": data}
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "AnalyticsService.get_insights | error | tenant_id=%s | %s",
                tenant_id,
                exc,
            )
            return {"success": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # Event bus subscriber handler
    # ------------------------------------------------------------------

    def handle_appointment_booked_event(self, event: AppointmentBookedEvent) -> None:
        """Event bus subscriber for :class:`AppointmentBookedEvent`.

        Increments the appointment count metric in the ``AnalyticsRecords``
        MCP resource each time a booking is confirmed.

        Parameters
        ----------
        event:
            The fired ``AppointmentBookedEvent`` instance.
        """
        logger.info(
            "AnalyticsService.handle_appointment_booked_event | event_id=%s",
            getattr(event, "event_id", "?"),
        )
        try:
            payload: Dict[str, Any] = event.payload or {}
            tenant_id = payload.get("tenant_id", "default")
            appointment_id = payload.get("appointment_id")

            # Persist metric increment record
            mcp_execute(
                resource="analytics_records",
                action="create",
                payload={
                    "metric": "appointment_booked",
                    "value": 1,
                    "appointment_id": appointment_id,
                    "tenant_id": tenant_id,
                    "recorded_at": datetime.utcnow().isoformat(),
                },
            )
            logger.info(
                "AnalyticsService.handle_appointment_booked_event | metric incremented | "
                "appointment_id=%s tenant_id=%s",
                appointment_id,
                tenant_id,
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception(
                "AnalyticsService.handle_appointment_booked_event | error | %s",
                exc,
            )


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------


def get_analytics_service() -> AnalyticsService:
    """Return the process-level singleton :class:`AnalyticsService`."""
    global _analytics_service_instance  # pylint: disable=global-statement
    if _analytics_service_instance is None:
        _analytics_service_instance = AnalyticsService()
    return _analytics_service_instance


# ---------------------------------------------------------------------------
# Event subscriber registration
# ---------------------------------------------------------------------------


def register_event_subscribers() -> None:
    """Subscribe :class:`AnalyticsService` handlers to the event bus.

    Call once during application start-up to enable real-time metric
    tracking via domain events.

    Subscribed events
    -----------------
    * :class:`~backend.core.event_bus.AppointmentBookedEvent`
    """
    svc = get_analytics_service()
    bus = get_event_bus()

    bus.subscribe(AppointmentBookedEvent, svc.handle_appointment_booked_event)

    logger.info(
        "AnalyticsService | registered subscriber for AppointmentBookedEvent"
    )
