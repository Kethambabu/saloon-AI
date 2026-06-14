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
        self.metadata: Dict[str, Any] = {}
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.updated_at = self.created_at

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
        self.pending_booking = {}
        self.unresolved_slots = {}
        self.updated_at = datetime.now(timezone.utc).isoformat()

    # ---- Serialization ---------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "user_role": self.user_role,
            "agent_name": self.agent_name,
            "history": self.get_recent_history(50),
            "unresolved_slots": dict(self.unresolved_slots),
            "pending_booking": dict(self.pending_booking),
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ---------------------------------------------------------------------------
# In-Memory State Store
# ---------------------------------------------------------------------------

class ConversationStateService:
    """
    Singleton-style in-memory conversation state manager.

    Usage:
        from services.conversation_state_service import get_state_service

        state_svc = get_state_service()
        session = state_svc.get_or_create("ses-abc-123", user_id="u1", user_role="CUSTOMER")
        session.add_turn("user", "I want to book a haircut")
        session.update_pending_booking({"service": "haircut"})
    """

    def __init__(self) -> None:
        self._store: Dict[str, SessionState] = {}

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
        self._store[sid] = state
        logger.debug("[ConvState] Created session %s for user %s", sid, user_id)
        return state

    def get_session(self, session_id: str) -> Optional[SessionState]:
        """Return an existing session or None."""
        return self._store.get(session_id)

    def get_or_create(
        self,
        session_id: str,
        user_id: str = "anonymous",
        user_role: str = "CUSTOMER",
        agent_name: str = "",
    ) -> SessionState:
        """Return an existing session or create a new one."""
        if session_id not in self._store:
            return self.create_session(
                session_id=session_id,
                user_id=user_id,
                user_role=user_role,
                agent_name=agent_name,
            )
        return self._store[session_id]

    def delete_session(self, session_id: str) -> bool:
        """Remove a session entirely. Returns True if it existed."""
        existed = session_id in self._store
        self._store.pop(session_id, None)
        if existed:
            logger.debug("[ConvState] Deleted session %s", session_id)
        return existed

    def list_sessions(self) -> List[str]:
        """Return all active session IDs."""
        return list(self._store.keys())

    # ---- Convenience wrappers -------------------------------------------

    def add_user_message(self, session_id: str, content: str) -> None:
        """Append a user message to the session history."""
        session = self._store.get(session_id)
        if session:
            session.add_turn("user", content)

    def add_assistant_message(
        self, session_id: str, content: str, agent_name: str = ""
    ) -> None:
        """Append an assistant message to the session history."""
        session = self._store.get(session_id)
        if session:
            session.add_turn("assistant", content, agent_name=agent_name)

    def get_context_string(self, session_id: str, n: int = 6) -> str:
        """Return the conversation context string for prompt injection."""
        session = self._store.get(session_id)
        return session.build_context_string(n) if session else ""

    def get_pending_booking(self, session_id: str) -> Dict[str, Any]:
        """Return the pending booking dict for this session."""
        session = self._store.get(session_id)
        return dict(session.pending_booking) if session else {}

    def update_pending_booking(self, session_id: str, data: Dict[str, Any]) -> None:
        """Merge new data into the pending booking context."""
        session = self._store.get(session_id)
        if session:
            session.update_pending_booking(data)

    def clear_pending_booking(self, session_id: str) -> None:
        """Reset pending booking state after completion or abandonment."""
        session = self._store.get(session_id)
        if session:
            session.clear_pending_booking()

    def get_state_snapshot(self, session_id: str) -> Dict[str, Any]:
        """Return the full serialized state of a session."""
        session = self._store.get(session_id)
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
