"""
backend/core/event_bus.py
=========================
Production-quality in-process event bus for SalonAI Phase 2.

Provides:
- SalonEvent base dataclass
- Concrete domain events for appointments, reviews, leads, and recommendations
- Thread-safe EventBus with synchronous and async publish
- Singleton factory via get_event_bus()

Usage::

    from infrastructure.events.event_bus import get_event_bus, AppointmentBookedEvent

    bus = get_event_bus()

    def on_booked(event):
        print(f"Booked: {event.payload}")

    bus.subscribe("appointment.booked", on_booked)
    bus.publish(AppointmentBookedEvent(tenant_id="t1", payload={"appointment_id": 42}))
"""

from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Type alias
# ---------------------------------------------------------------------------
EventHandler = Callable[["SalonEvent"], None]


# ---------------------------------------------------------------------------
# Base event
# ---------------------------------------------------------------------------
@dataclass
class SalonEvent:
    """Base class for all SalonAI domain events.

    Attributes:
        event_id:   Unique identifier auto-generated per event instance.
        event_type: String discriminator (e.g. "appointment.booked").
        tenant_id:  Owning tenant – always populated.
        timestamp:  UTC creation time.
        payload:    Arbitrary dict carrying domain-specific data.
    """

    tenant_id: str
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = field(default="salon.event")
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    payload: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Concrete events – Appointments
# ---------------------------------------------------------------------------
@dataclass
class AppointmentBookedEvent(SalonEvent):
    """Fired when a new appointment is successfully booked.

    Payload keys (recommended):
        appointment_id, customer_id, staff_id, service_id, starts_at
    """

    event_type: str = field(default="appointment.booked")
    appointment_id: Optional[str] = field(default=None)
    customer_id: Optional[str] = field(default=None)
    staff_id: Optional[str] = field(default=None)
    service_id: Optional[str] = field(default=None)
    starts_at: Optional[datetime] = field(default=None)


@dataclass
class AppointmentCancelledEvent(SalonEvent):
    """Fired when an appointment is cancelled.

    Payload keys (recommended):
        appointment_id, cancelled_by, reason
    """

    event_type: str = field(default="appointment.cancelled")
    appointment_id: Optional[str] = field(default=None)
    customer_id: Optional[str] = field(default=None)
    cancelled_by: Optional[str] = field(default=None)
    reason: Optional[str] = field(default=None)


@dataclass
class AppointmentRescheduledEvent(SalonEvent):
    """Fired when an appointment is moved to a new time slot.

    Payload keys (recommended):
        appointment_id, old_starts_at, new_starts_at, rescheduled_by
    """

    event_type: str = field(default="appointment.rescheduled")
    appointment_id: Optional[str] = field(default=None)
    customer_id: Optional[str] = field(default=None)
    old_starts_at: Optional[datetime] = field(default=None)
    new_starts_at: Optional[datetime] = field(default=None)
    rescheduled_by: Optional[str] = field(default=None)


# ---------------------------------------------------------------------------
# Concrete events – Reviews
# ---------------------------------------------------------------------------
@dataclass
class ReviewSubmittedEvent(SalonEvent):
    """Fired when a customer submits a review.

    Payload keys (recommended):
        review_id, customer_id, rating, platform
    """

    event_type: str = field(default="review.submitted")
    review_id: Optional[str] = field(default=None)
    customer_id: Optional[str] = field(default=None)
    rating: Optional[float] = field(default=None)
    platform: Optional[str] = field(default=None)


# ---------------------------------------------------------------------------
# Concrete events – Leads / CRM
# ---------------------------------------------------------------------------
@dataclass
class LeadCreatedEvent(SalonEvent):
    """Fired when a new lead record is created.

    Payload keys (recommended):
        lead_id, source, phone, name
    """

    event_type: str = field(default="lead.created")
    lead_id: Optional[str] = field(default=None)
    source: Optional[str] = field(default=None)
    phone: Optional[str] = field(default=None)
    name: Optional[str] = field(default=None)


@dataclass
class LeadConvertedEvent(SalonEvent):
    """Fired when a lead is converted to a paying customer.

    Payload keys (recommended):
        lead_id, customer_id, converted_by, appointment_id
    """

    event_type: str = field(default="lead.converted")
    lead_id: Optional[str] = field(default=None)
    customer_id: Optional[str] = field(default=None)
    converted_by: Optional[str] = field(default=None)
    appointment_id: Optional[str] = field(default=None)


# ---------------------------------------------------------------------------
# Concrete events – Recommendations
# ---------------------------------------------------------------------------
@dataclass
class RecommendationAcceptedEvent(SalonEvent):
    """Fired when a staff member or customer accepts an AI recommendation.

    Payload keys (recommended):
        recommendation_id, recommendation_type, accepted_by
    """

    event_type: str = field(default="recommendation.accepted")
    recommendation_id: Optional[str] = field(default=None)
    recommendation_type: Optional[str] = field(default=None)
    accepted_by: Optional[str] = field(default=None)


@dataclass
class RecommendationRejectedEvent(SalonEvent):
    """Fired when a recommendation is explicitly rejected.

    Payload keys (recommended):
        recommendation_id, recommendation_type, rejected_by, rejection_reason
    """

    event_type: str = field(default="recommendation.rejected")
    recommendation_id: Optional[str] = field(default=None)
    recommendation_type: Optional[str] = field(default=None)
    rejected_by: Optional[str] = field(default=None)
    rejection_reason: Optional[str] = field(default=None)


@dataclass
class CustomerPreferenceEvent(SalonEvent):
    """Fired when a customer explicitly gives a preference or restriction."""
    event_type: str = field(default="customer.preference")
    customer_id: Optional[str] = field(default=None)
    preference_key: Optional[str] = field(default=None)
    preference_value: Optional[str] = field(default=None)
    is_durable: bool = field(default=True)


@dataclass
class LeadStatusChangedEvent(SalonEvent):
    """Fired when a lead status changes."""
    event_type: str = field(default="lead.status_changed")
    lead_id: Optional[str] = field(default=None)
    old_status: Optional[str] = field(default=None)
    new_status: Optional[str] = field(default=None)
    notes: Optional[str] = field(default=None)


@dataclass
class UpsellOutcomeEvent(SalonEvent):
    """Fired when an upsell offer is accepted or rejected."""
    event_type: str = field(default="upsell.outcome")
    customer_id: Optional[str] = field(default=None)
    recommendation_id: Optional[str] = field(default=None)
    service_id: Optional[str] = field(default=None)
    accepted: bool = field(default=False)
    rejection_reason: Optional[str] = field(default=None)


@dataclass
class ReviewIssueEvent(SalonEvent):
    """Fired when a review is submitted and a service issue is identified/resolved."""
    event_type: str = field(default="review.issue")
    review_id: Optional[str] = field(default=None)
    customer_id: Optional[str] = field(default=None)
    rating: Optional[int] = field(default=None)
    issue_detected: bool = field(default=False)
    comment: Optional[str] = field(default=None)


@dataclass
class StaffFeedbackEvent(SalonEvent):
    """Fired when staff performance/coaching feedback is recorded."""
    event_type: str = field(default="staff.feedback")
    staff_id: Optional[str] = field(default=None)
    feedback_type: Optional[str] = field(default=None)
    comment: Optional[str] = field(default=None)


@dataclass
class CampaignDecisionEvent(SalonEvent):
    """Fired when an important campaign/business decision and outcome is recorded."""
    event_type: str = field(default="campaign.decision")
    campaign_name: Optional[str] = field(default=None)
    decision: Optional[str] = field(default=None)
    outcome: Optional[str] = field(default=None)


@dataclass
class AppointmentCompletedEvent(SalonEvent):
    """Fired when an appointment is completed."""
    event_type: str = field(default="appointment.completed")
    appointment_id: Optional[str] = field(default=None)
    customer_id: Optional[str] = field(default=None)
    staff_id: Optional[str] = field(default=None)
    service_id: Optional[str] = field(default=None)
    notes: Optional[str] = field(default=None)


# ---------------------------------------------------------------------------
# EventBus
# ---------------------------------------------------------------------------
class EventBus:
    """Thread-safe in-process event bus.

    Handlers are registered per *event_type* string.  When an event is
    published every matching handler is called synchronously in registration
    order.  ``publish_async`` wraps the synchronous dispatch in
    ``asyncio.get_event_loop().run_in_executor`` so it can be awaited from
    async contexts without blocking the caller's event loop.

    Thread safety:
        A :class:`threading.Lock` guards the internal handler registry so
        that ``subscribe`` calls from multiple threads are safe.  Dispatch
        itself releases the lock before invoking handlers to avoid deadlocks
        caused by re-entrant publishes inside a handler.
    """

    def __init__(self) -> None:
        self._handlers: Dict[str, List[EventHandler]] = defaultdict(list)
        self._lock: threading.Lock = threading.Lock()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    def subscribe(self, event_type_str: Any, handler_func: EventHandler) -> None:
        """Register *handler_func* to be called for every event of *event_type_str*.

        Args:
            event_type_str: The ``event_type`` discriminator string
                            (e.g. ``"appointment.booked"``) or a SalonEvent subclass type.
            handler_func:   Callable that accepts a single
                            :class:`SalonEvent` argument.

        Example::

            bus.subscribe("appointment.booked", my_handler)
            # or
            bus.subscribe(AppointmentBookedEvent, my_handler)
        """
        if not isinstance(event_type_str, str):
            # Try to resolve string event type from class
            resolved = None
            if isinstance(event_type_str, type):
                # If it's a dataclass, check fields
                if hasattr(event_type_str, "__dataclass_fields__"):
                    f_obj = event_type_str.__dataclass_fields__.get("event_type")
                    if f_obj is not None:
                        resolved = f_obj.default
            
            if resolved is None and hasattr(event_type_str, "event_type"):
                resolved = getattr(event_type_str, "event_type")

            if isinstance(resolved, str):
                event_type_str = resolved
            else:
                raise TypeError(
                    f"[EventBus] Invalid event type: {event_type_str}. Must be a string "
                    f"or a SalonEvent subclass with a default event_type."
                )

        with self._lock:
            self._handlers[event_type_str].append(handler_func)
        logger.info(
            "[EventBus] Subscribed handler '%s' to event_type='%s'",
            getattr(handler_func, "__qualname__", repr(handler_func)),
            event_type_str,
        )

    # ------------------------------------------------------------------
    # Synchronous dispatch
    # ------------------------------------------------------------------
    def publish(self, event: SalonEvent) -> None:
        """Dispatch *event* to all registered handlers synchronously.

        Handlers are invoked in registration order.  Exceptions raised by
        individual handlers are caught and logged so that a single failing
        handler does not prevent subsequent handlers from running.

        Args:
            event: Any :class:`SalonEvent` subclass instance.
        """
        # Persist event to PostgreSQL outbox table for transactional reliability
        try:
            from infrastructure.db.database import SessionLocal
            from infrastructure.db.models import OutboxEvent
            import json

            db = SessionLocal()
            payload_dict = {}
            if hasattr(event, "payload") and event.payload:
                payload_dict = dict(event.payload)
            
            # Extract attributes from specific event classes
            for f_name in getattr(event, "__dataclass_fields__", {}):
                if f_name not in ("event_id", "event_type", "tenant_id", "timestamp", "payload"):
                    val = getattr(event, f_name, None)
                    if val is not None:
                        if hasattr(val, "isoformat"):
                            val = val.isoformat()
                        payload_dict[f_name] = str(val)

            outbox = OutboxEvent(
                id=uuid.UUID(event.event_id) if hasattr(event, "event_id") and event.event_id else uuid.uuid4(),
                event_type=event.event_type,
                tenant_id=event.tenant_id or "default",
                payload=json.dumps(payload_dict),
                status="PENDING",
            )
            db.add(outbox)
            db.commit()
            db.close()
            logger.info("[EventBus] Persisted event %s to Outbox table.", event.event_id)
        except Exception as exc:
            logger.warning("[EventBus] Failed to persist outbox event: %s", exc)

        with self._lock:
            handlers = list(self._handlers.get(event.event_type, []))

        logger.info(
            "[EventBus] Publishing event_type='%s' event_id='%s' tenant_id='%s' "
            "handler_count=%d",
            event.event_type,
            event.event_id,
            event.tenant_id,
            len(handlers),
        )

        for handler in handlers:
            try:
                logger.debug(
                    "[EventBus] Invoking handler '%s' for event_type='%s' "
                    "event_id='%s' tenant_id='%s'",
                    getattr(handler, "__qualname__", repr(handler)),
                    event.event_type,
                    event.event_id,
                    event.tenant_id,
                )
                handler(event)
            except Exception:  # pylint: disable=broad-except
                logger.exception(
                    "[EventBus] Handler '%s' raised an exception for "
                    "event_type='%s' event_id='%s' tenant_id='%s'",
                    getattr(handler, "__qualname__", repr(handler)),
                    event.event_type,
                    event.event_id,
                    event.tenant_id,
                )

    # ------------------------------------------------------------------
    # Asynchronous dispatch
    # ------------------------------------------------------------------
    async def publish_async(self, event: SalonEvent) -> None:
        """Dispatch *event* asynchronously via a thread-pool executor.

        The synchronous :meth:`publish` method is off-loaded to a worker
        thread so the calling coroutine's event loop is not blocked.

        Args:
            event: Any :class:`SalonEvent` subclass instance.

        Example::

            await bus.publish_async(AppointmentBookedEvent(tenant_id="t1"))
        """
        logger.info(
            "[EventBus] Async publish event_type='%s' event_id='%s' tenant_id='%s'",
            event.event_type,
            event.event_id,
            event.tenant_id,
        )
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self.publish, event)

    # ------------------------------------------------------------------
    # Debugging helpers
    # ------------------------------------------------------------------
    def list_handlers(self) -> Dict[str, List[str]]:
        """Return a snapshot of registered handlers keyed by event_type.

        Returns:
            Dict mapping ``event_type`` → list of handler qualified names.

        Example::

            import pprint
            pprint.pprint(bus.list_handlers())
        """
        with self._lock:
            return {
                evt_type: [
                    getattr(h, "__qualname__", repr(h)) for h in handlers
                ]
                for evt_type, handlers in self._handlers.items()
            }


# ---------------------------------------------------------------------------
# Singleton factory
# ---------------------------------------------------------------------------
_event_bus_instance: Optional[EventBus] = None
_event_bus_lock: threading.Lock = threading.Lock()


def get_event_bus() -> EventBus:
    """Return the process-wide singleton :class:`EventBus`.

    Thread-safe double-checked locking ensures exactly one instance is
    created even under concurrent initialisation.

    Returns:
        The global :class:`EventBus` instance.

    Example::

        bus = get_event_bus()
    """
    global _event_bus_instance  # pylint: disable=global-statement
    if _event_bus_instance is None:
        with _event_bus_lock:
            if _event_bus_instance is None:
                _event_bus_instance = EventBus()
                logger.info("[EventBus] Singleton EventBus created.")
    return _event_bus_instance

