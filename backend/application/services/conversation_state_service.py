"""
Conversation State Service for SalonAI Workforce Platform.

Phase 1 Architecture — Multi-Turn Conversation Management.

Stores per-session:
  - conversation history (role + content + timestamp)
  - unresolved slots (service, date, staff, etc.)
  - pending booking context (partially collected fields)
  - session metadata (agent, role, user_id)

Designed for in-process use.  All state is held in memory (dict-based).
For production scale-out, swap _store to Redis/Supabase with minimal changes.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


from enum import Enum

class BookingState(str, Enum):
    IDLE = "IDLE"
    COLLECTING = "COLLECTING"
    VALIDATING = "VALIDATING"
    AVAILABILITY = "AVAILABILITY"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    BOOKING = "BOOKING"
    CONFIRMED = "CONFIRMED"
    CLOSED = "CLOSED"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class ConversationTurn:
    """A single message in the conversation history."""

    __slots__ = ("role", "content", "agent_name", "timestamp")

    def __init__(self, role: str, content: str, agent_name: str = ""):
        self.role = role              # "user" | "assistant" | "system"
        self.content = content
        self.agent_name = agent_name
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "content": self.content,
            "agent_name": self.agent_name,
            "timestamp": self.timestamp,
        }


class SessionState:
    """
    Full conversation state for a single session.

    Attributes:
        session_id:       Unique identifier for this conversation session.
        user_id:          Authenticated user ID.
        user_role:        Role of the authenticated user (CUSTOMER, STAFF, ADMIN …).
        agent_name:       Last agent that handled this session.
        history:          Ordered list of ConversationTurn objects.
        unresolved_slots: Fields the agent still needs from the user
                          (e.g. {"service": None, "date": None}).
        pending_booking:  Partially collected booking intent dict.
        booking_state:    Deterministic state machine (IDLE, COLLECTING, VALIDATING, etc.).
        metadata:         Arbitrary key-value metadata (branch_id, preferred_lang …).
        created_at:       ISO timestamp when the session was created.
        updated_at:       ISO timestamp of last state change.
    """

    def __init__(
        self,
        session_id: str,
        user_id: str = "anonymous",
        user_role: str = "CUSTOMER",
        agent_name: str = "",
    ):
        self.session_id = session_id
        self.user_id = user_id
        self.user_role = user_role
        self.agent_name = agent_name
        self.history: List[ConversationTurn] = []
        self.unresolved_slots: Dict[str, Optional[Any]] = {}
        self.pending_booking: Dict[str, Any] = {}
        self.last_booking: Dict[str, Any] = {}
        self.booking_state: BookingState = BookingState.IDLE
        self.metadata: Dict[str, Any] = {}
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.updated_at = self.created_at

    def set_booking_state(self, state: str | BookingState) -> None:
        """Update the deterministic booking state machine state."""
        if isinstance(state, str):
            try:
                state = BookingState(state.upper())
            except ValueError:
                state = BookingState.IDLE
        self.booking_state = state
        self.updated_at = datetime.now(timezone.utc).isoformat()

    # ---- History helpers -------------------------------------------------

    def add_turn(self, role: str, content: str, agent_name: str = "") -> None:
        """Append a message to the conversation history."""
        self.history.append(ConversationTurn(role=role, content=content, agent_name=agent_name))
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def get_recent_history(self, n: int = 10) -> List[Dict[str, Any]]:
        """Return the last *n* turns as plain dicts."""
        return [turn.to_dict() for turn in self.history[-n:]]

    def build_context_string(self, n: int = 6) -> str:
        """Build a compact context string for injecting into agent prompts."""
        recent = self.get_recent_history(n)
        if not recent:
            return ""
        lines = ["Conversation history so far:"]
        for t in recent:
            role_label = t["role"].capitalize()
            lines.append(f"- {role_label}: {t['content']}")
        lines.append("")
        return "\n".join(lines)

    # ---- Slot helpers ----------------------------------------------------

    def set_unresolved_slots(self, slots: Dict[str, Optional[Any]]) -> None:
        """Mark a set of fields as unresolved (agent needs to collect them)."""
        self.unresolved_slots.update(slots)
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def resolve_slot(self, key: str, value: Any) -> None:
        """Mark a previously unresolved slot as collected."""
        if key in self.unresolved_slots:
            self.unresolved_slots[key] = value
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def has_unresolved_slots(self) -> bool:
        """Return True if any slot still lacks a value."""
        return any(v is None for v in self.unresolved_slots.values())

    def missing_slots(self) -> List[str]:
        """Return keys of slots that are still None."""
        return [k for k, v in self.unresolved_slots.items() if v is None]

    # ---- Pending booking helpers -----------------------------------------

    def update_pending_booking(self, data: Dict[str, Any]) -> None:
        """Merge new fields into the pending booking context."""
        self.pending_booking.update({k: v for k, v in data.items() if v is not None})
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def clear_pending_booking(self) -> None:
        """Reset the pending booking context after confirmation or abandonment."""
        if self.pending_booking:
            self.last_booking = dict(self.pending_booking)
            self.metadata["last_appointment"] = dict(self.pending_booking)
        self.pending_booking = {}
        self.unresolved_slots = {}
        self.booking_state = BookingState.CLOSED
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def update_customer_preferences(
        self,
        preferred_stylist: Optional[str] = None,
        preferred_service: Optional[str] = None,
        preferred_branch: Optional[str] = None,
        booking_preferences: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update and retain customer preferences in session memory."""
        prefs = self.metadata.setdefault("customer_preferences", {})
        if preferred_stylist:
            prefs["preferred_stylist"] = preferred_stylist
        if preferred_service:
            prefs["preferred_service"] = preferred_service
        if preferred_branch:
            prefs["preferred_branch"] = preferred_branch
        if booking_preferences:
            prefs.setdefault("booking_preferences", {}).update(booking_preferences)
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def get_customer_preferences(self) -> Dict[str, Any]:
        """Return customer preferences from session memory."""
        return self.metadata.get("customer_preferences", {})

    def update_last_appointment(self, appointment_data: Dict[str, Any]) -> None:
        """Store the details of the most recent confirmed/rescheduled appointment."""
        self.metadata["last_appointment"] = dict(appointment_data)
        self.updated_at = datetime.now(timezone.utc).isoformat()

    # ---- Serialization ---------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "user_role": self.user_role,
            "agent_name": self.agent_name,
            "booking_state": self.booking_state.value if isinstance(self.booking_state, BookingState) else str(self.booking_state),
            "history": self.get_recent_history(50),
            "unresolved_slots": dict(self.unresolved_slots),
            "pending_booking": dict(self.pending_booking),
            "last_booking": dict(self.last_booking),
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ---------------------------------------------------------------------------
# In-Memory State Store
# ---------------------------------------------------------------------------

class ConversationStateService:
    """
    Database-backed conversation state manager.
    """

    def _save_session(self, session: SessionState) -> None:
        """Write session state back to database."""
        from infrastructure.db.database import SessionLocal
        from infrastructure.db.models import ConversationSession
        import json

        db = SessionLocal()
        try:
            db_session = db.query(ConversationSession).filter(
                ConversationSession.session_id == session.session_id
            ).first()
            
            meta = dict(session.metadata)
            meta["_booking_state"] = session.booking_state.value if isinstance(session.booking_state, BookingState) else str(session.booking_state)
            meta["_last_booking"] = session.last_booking

            history_json = json.dumps([turn.to_dict() for turn in session.history])
            slots_json = json.dumps(session.unresolved_slots)
            booking_json = json.dumps(session.pending_booking)
            meta_json = json.dumps(meta)

            if db_session:
                db_session.user_id = str(session.user_id) if session.user_id else "anonymous"
                db_session.user_role = session.user_role
                db_session.agent_name = session.agent_name
                db_session.history = history_json
                db_session.unresolved_slots = slots_json
                db_session.pending_booking = booking_json
                db_session.metadata_json = meta_json
                db_session.updated_at = datetime.now(timezone.utc)
            else:
                db_session = ConversationSession(
                    session_id=session.session_id,
                    user_id=str(session.user_id) if session.user_id else "anonymous",
                    user_role=session.user_role,
                    agent_name=session.agent_name,
                    history=history_json,
                    unresolved_slots=slots_json,
                    pending_booking=booking_json,
                    metadata_json=meta_json,
                )
                db.add(db_session)
            db.commit()
            logger.debug("[ConvState] Persisted session %s to DB", session.session_id)
        except Exception as e:
            logger.error("[ConvState] Failed to persist session %s: %s", session.session_id, e)
            db.rollback()
        finally:
            db.close()

    def _load_session(self, session_id: str) -> Optional[SessionState]:
        """Read session state from database."""
        from infrastructure.db.database import SessionLocal
        from infrastructure.db.models import ConversationSession
        import json

        db = SessionLocal()
        try:
            db_session = db.query(ConversationSession).filter(
                ConversationSession.session_id == session_id
            ).first()
            if not db_session:
                return None

            session = SessionState(
                session_id=db_session.session_id,
                user_id=db_session.user_id or "anonymous",
                user_role=db_session.user_role or "CUSTOMER",
                agent_name=db_session.agent_name or "",
            )
            
            if db_session.history:
                try:
                    history_list = json.loads(db_session.history)
                    for turn_data in history_list:
                        turn = ConversationTurn(
                            role=turn_data["role"],
                            content=turn_data["content"],
                            agent_name=turn_data.get("agent_name", "")
                        )
                        if "timestamp" in turn_data:
                            turn.timestamp = turn_data["timestamp"]
                        session.history.append(turn)
                except Exception as e:
                    logger.error("Failed to parse history JSON: %s", e)

            if db_session.unresolved_slots:
                try:
                    session.unresolved_slots = json.loads(db_session.unresolved_slots)
                except Exception:
                    pass

            if db_session.pending_booking:
                try:
                    session.pending_booking = json.loads(db_session.pending_booking)
                except Exception:
                    pass

            if db_session.metadata_json:
                try:
                    session.metadata = json.loads(db_session.metadata_json)
                    st_val = session.metadata.pop("_booking_state", None)
                    if st_val:
                        session.set_booking_state(st_val)
                    last_b = session.metadata.pop("_last_booking", None)
                    if last_b and isinstance(last_b, dict):
                        session.last_booking = last_b
                except Exception:
                    pass

            return session
        except Exception as e:
            logger.error("[ConvState] Failed to load session %s: %s", session_id, e)
            return None
        finally:
            db.close()

    # ---- CRUD ------------------------------------------------------------

    def create_session(
        self,
        session_id: Optional[str] = None,
        user_id: str = "anonymous",
        user_role: str = "CUSTOMER",
        agent_name: str = "",
    ) -> SessionState:
        """Create a fresh session, optionally with a caller-specified ID."""
        sid = session_id or str(uuid.uuid4())
        state = SessionState(
            session_id=sid,
            user_id=user_id,
            user_role=user_role,
            agent_name=agent_name,
        )
        self._save_session(state)
        logger.debug("[ConvState] Created session %s for user %s", sid, user_id)
        return state

    def get_session(self, session_id: str) -> Optional[SessionState]:
        """Return an existing session or None."""
        return self._load_session(session_id)

    def get_or_create(
        self,
        session_id: str,
        user_id: str = "anonymous",
        user_role: str = "CUSTOMER",
        agent_name: str = "",
    ) -> SessionState:
        """
        Return an existing session or create a new one.

        session_id is client-supplied (see api/routes/agent_routes.py), so a
        session that already exists under this id but belongs to a DIFFERENT
        authenticated user must never be handed back — that would leak the
        original owner's conversation history/pending-booking/customer_id to
        whoever guessed or replayed the id. Internal/system callers
        ("anonymous"/"system", used by scheduled jobs and tests with no real
        end user) are exempt from this check.
        """
        session = self.get_session(session_id)
        if not session:
            return self.create_session(
                session_id=session_id,
                user_id=user_id,
                user_role=user_role,
                agent_name=agent_name,
            )

        privileged_caller = user_id in ("anonymous", "system") or (user_role or "").upper() in ("ADMIN",)
        if session.user_id not in ("anonymous", "system", user_id) and not privileged_caller:
            logger.warning(
                "[ConvState] session_id %s requested by user_id=%s but belongs to user_id=%s — "
                "refusing to reuse; starting a fresh (unpersisted-until-saved) session state.",
                session_id, user_id, session.user_id,
            )
            return SessionState(
                session_id=session_id,
                user_id=user_id,
                user_role=user_role,
                agent_name=agent_name,
            )
        return session

    def delete_session(self, session_id: str) -> bool:
        """Remove a session entirely. Returns True if it existed."""
        from infrastructure.db.database import SessionLocal
        from infrastructure.db.models import ConversationSession
        db = SessionLocal()
        try:
            db_session = db.query(ConversationSession).filter(
                ConversationSession.session_id == session_id
            ).first()
            if db_session:
                db.delete(db_session)
                db.commit()
                logger.debug("[ConvState] Deleted session %s", session_id)
                return True
            return False
        except Exception as e:
            logger.error("Failed to delete session %s: %s", session_id, e)
            db.rollback()
            return False
        finally:
            db.close()

    def list_sessions(self) -> List[str]:
        """Return all active session IDs."""
        from infrastructure.db.database import SessionLocal
        from infrastructure.db.models import ConversationSession
        db = SessionLocal()
        try:
            rows = db.query(ConversationSession.session_id).all()
            return [r.session_id for r in rows]
        except Exception:
            return []
        finally:
            db.close()

    # ---- Convenience wrappers -------------------------------------------

    def add_user_message(self, session_id: str, content: str) -> None:
        """Append a user message to the session history."""
        session = self.get_session(session_id)
        if session:
            session.add_turn("user", content)
            self._save_session(session)

    def add_assistant_message(
        self, session_id: str, content: str, agent_name: str = ""
    ) -> None:
        """Append an assistant message to the session history."""
        session = self.get_session(session_id)
        if session:
            session.add_turn("assistant", content, agent_name=agent_name)
            self._save_session(session)

    def get_context_string(self, session_id: str, n: int = 6) -> str:
        """Return the conversation context string for prompt injection."""
        session = self.get_session(session_id)
        return session.build_context_string(n) if session else ""

    def get_pending_booking(self, session_id: str) -> Dict[str, Any]:
        """Return the pending booking dict for this session."""
        session = self.get_session(session_id)
        return dict(session.pending_booking) if session else {}

    def update_pending_booking(self, session_id: str, data: Dict[str, Any]) -> None:
        """Merge new data into the pending booking context."""
        session = self.get_session(session_id)
        if session:
            session.update_pending_booking(data)
            self._save_session(session)

    def clear_pending_booking(self, session_id: str) -> None:
        """Reset pending booking state after completion or abandonment."""
        session = self.get_session(session_id)
        if session:
            session.clear_pending_booking()
            self._save_session(session)

    def get_state_snapshot(self, session_id: str) -> Dict[str, Any]:
        """Return the full serialized state of a session."""
        session = self.get_session(session_id)
        return session.to_dict() if session else {}



# ---------------------------------------------------------------------------
# Module-level singleton (imported by agents and orchestrator)
# ---------------------------------------------------------------------------

_state_service_instance: Optional[ConversationStateService] = None


def get_state_service() -> ConversationStateService:
    """Return the process-level ConversationStateService singleton."""
    global _state_service_instance
    if _state_service_instance is None:
        _state_service_instance = ConversationStateService()
        logger.info("[ConvState] ConversationStateService singleton created.")
    return _state_service_instance

