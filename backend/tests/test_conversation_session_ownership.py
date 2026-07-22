"""
Regression tests for the Phase 3 conversation-session-hijack fix:
session_id is client-supplied (api/routes/agent_routes.py), so
ConversationStateService.get_or_create() must never hand an existing
session's history/pending_booking/metadata to a DIFFERENT authenticated
user who happens to supply (guesses/replays) the same session_id.
"""
import os
import sys
import uuid

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")

from application.services.conversation_state_service import ConversationStateService


def test_get_or_create_refuses_foreign_session_ownership():
    svc = ConversationStateService()
    session_id = f"test-session-{uuid.uuid4()}"
    owner_id = f"user-{uuid.uuid4()}"
    attacker_id = f"user-{uuid.uuid4()}"

    owner_session = svc.create_session(session_id=session_id, user_id=owner_id, user_role="CUSTOMER")
    owner_session.add_turn("user", "my allergy is to keratin, please note it")
    svc._save_session(owner_session)

    hijacked = svc.get_or_create(session_id=session_id, user_id=attacker_id, user_role="CUSTOMER")

    assert hijacked.user_id == attacker_id
    assert hijacked.history == []  # must NOT see the owner's prior turns

    svc.delete_session(session_id)


def test_get_or_create_allows_the_real_owner_to_continue():
    svc = ConversationStateService()
    session_id = f"test-session-{uuid.uuid4()}"
    owner_id = f"user-{uuid.uuid4()}"

    owner_session = svc.create_session(session_id=session_id, user_id=owner_id, user_role="CUSTOMER")
    owner_session.add_turn("user", "book me a haircut")
    svc._save_session(owner_session)

    reloaded = svc.get_or_create(session_id=session_id, user_id=owner_id, user_role="CUSTOMER")

    assert len(reloaded.history) == 1
    assert reloaded.history[0].content == "book me a haircut"

    svc.delete_session(session_id)
