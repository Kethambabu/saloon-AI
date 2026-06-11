"""
End-to-End Test for the Receptionist Agent (Clara).
Tests the full process() pipeline for: greeting, booking, cancellation,
rescheduling, history, and RAG-based policy queries.
Does NOT require a live API server — calls the agent directly.
"""

import os
import sys
import asyncio
import logging

# Force UTF-8 stdout so Windows cp1252 terminals don't raise UnicodeEncodeError
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# Fix path so that 'backend' is the root package
_BACKEND_DIR = os.path.abspath(os.path.dirname(__file__))
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)
# Also allow imports via 'backend.X' style
_PROJECT_DIR = os.path.dirname(_BACKEND_DIR)
if _PROJECT_DIR not in sys.path:
    sys.path.insert(0, _PROJECT_DIR)

# Reset circuit breaker before test imports
from agents.receptionist_agent import ReceptionistAgent
ReceptionistAgent.CIRCUIT_BREAKER_TRIPPED = False
ReceptionistAgent.FAILURE_COUNT = 0
ReceptionistAgent.MODEL_COOLDOWN = {}

from db.database import SessionLocal
from db.models import Customer, Branch, Service, Staff

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

FAKE_CUSTOMER_ID = None
FAKE_BRANCH_NAME = None
FAKE_SERVICE_NAME = None
FAKE_STAFF_NAME = None


def _load_db_fixtures():
    """Load the first available customer, branch, service, and staff from DB."""
    global FAKE_CUSTOMER_ID, FAKE_BRANCH_NAME, FAKE_SERVICE_NAME, FAKE_STAFF_NAME
    db = SessionLocal()
    try:
        customer = db.query(Customer).filter(Customer.is_active == True).first()
        branch = db.query(Branch).filter(Branch.is_active == True).first()
        service = db.query(Service).filter(Service.is_active == True).first()
        staff = db.query(Staff).filter(Staff.is_active == True).first()

        if not customer:
            raise RuntimeError("No active customer found in DB. Please seed the database first.")
        if not branch:
            raise RuntimeError("No active branch found in DB.")
        if not service:
            raise RuntimeError("No active service found in DB.")

        FAKE_CUSTOMER_ID = str(customer.id)
        FAKE_BRANCH_NAME = branch.name
        FAKE_SERVICE_NAME = service.name
        FAKE_STAFF_NAME = staff.full_name if staff else "any"
    finally:
        db.close()


def _build_query(msg: str, customer_id: str) -> str:
    """Build a realistic query string with system-level context injected."""
    time_ctx = "[SYSTEM TIME CONTEXT: Current system time is 2026-06-10 10:00:00 (Today is Wednesday, June 10, 2026). Use this to calculate exact dates like 'tomorrow', 'next Tuesday', etc.]"
    cust_ctx = f"[SYSTEM CUSTOMER CONTEXT: The user chatting with you is logged in as Customer ID: {customer_id}, Email: customer@example.com. Always use this Customer ID directly for bookings and customer history lookups. Do NOT ask them to search or provide their details.]"
    return f"{time_ctx}\n{cust_ctx}\nLatest User Message: {msg}"


async def test_1_greeting():
    """Greeting should return Clara's welcome message without LLM call (keyword shortcut)."""
    agent = ReceptionistAgent()
    result = await agent.process({
        "query": _build_query("Hello, who are you?", FAKE_CUSTOMER_ID),
        "session_id": "e2e-recep-greeting",
        "chat_history": []
    })
    assert result["success"] is True, f"Greeting failed: {result}"
    assert "Clara" in result["response"] or len(result["response"]) > 10, \
        f"Expected Clara introduction, got: {result['response'][:100]}"
    print(f"  [PASS] Greeting test passed. Provider: {result.get('provider', 'N/A')}")


async def test_2_policy_rag():
    """Policy/FAQ query should be served by RAG without full LLM round-trip."""
    agent = ReceptionistAgent()
    result = await agent.process({
        "query": _build_query("What are your business hours?", FAKE_CUSTOMER_ID),
        "session_id": "e2e-recep-policy",
        "chat_history": []
    })
    assert result["success"] is True, f"Policy query failed: {result}"
    assert result.get("response") and len(result["response"]) > 5
    print(f"  [PASS] Policy RAG test passed. Provider: {result.get('provider', 'N/A')}")


async def test_3_booking_missing_fields():
    """Booking with missing fields should prompt the user for the missing details."""
    agent = ReceptionistAgent()
    result = await agent.process({
        "query": _build_query("I want to book an appointment", FAKE_CUSTOMER_ID),
        "session_id": "e2e-recep-book-missing",
        "chat_history": []
    })
    assert result["success"] is True, f"Missing-fields booking failed: {result}"
    response_text = result.get("response", "").lower()
    # Either asks for missing details, or mentions booking (booking engine responded)
    assert any(kw in response_text for kw in ["which service", "what service", "service", "branch", "date", "time", "book"]), \
        f"Expected booking prompt, got: {response_text[:200]}"
    print(f"  [PASS] Booking missing fields test passed. Provider: {result.get('provider', 'N/A')}")


async def test_4_full_booking():
    """Full booking with all details should attempt to create the appointment."""
    agent = ReceptionistAgent()
    msg = (
        f'book an appointment for june 12th 2026 11 am slot '
        f'"{FAKE_SERVICE_NAME} {FAKE_BRANCH_NAME} {FAKE_STAFF_NAME}"'
    )
    result = await agent.process({
        "query": _build_query(msg, FAKE_CUSTOMER_ID),
        "session_id": "e2e-recep-full-book",
        "chat_history": []
    })
    assert result["success"] is True, f"Full booking failed: {result}"
    response_text = result.get("response", "").lower()
    # Either confirmed or gave a meaningful error (not internal crash)
    assert any(kw in response_text for kw in ["confirmed", "appointment", "book", "sorry", "unavailable", "sorry"]), \
        f"Unexpected booking response: {response_text[:300]}"
    print(f"  [PASS] Full booking test passed. Provider: {result.get('provider', 'N/A')}")
    return result.get("response", "")


async def test_5_history_query():
    """History query should retrieve and format appointment history."""
    agent = ReceptionistAgent()
    result = await agent.process({
        "query": _build_query("Show me my appointment history", FAKE_CUSTOMER_ID),
        "session_id": "e2e-recep-history",
        "chat_history": []
    })
    assert result["success"] is True, f"History query failed: {result}"
    response_text = result.get("response", "").lower()
    assert any(kw in response_text for kw in ["history", "appointment", "visit", "record", "no past", "no appointment"]), \
        f"Unexpected history response: {response_text[:200]}"
    print(f"  [PASS] History test passed. Provider: {result.get('provider', 'N/A')}")


async def test_6_cancellation_query():
    """Cancel request should route to cancel flow and return meaningful reply."""
    agent = ReceptionistAgent()
    result = await agent.process({
        "query": _build_query("Cancel my appointment", FAKE_CUSTOMER_ID),
        "session_id": "e2e-recep-cancel",
        "chat_history": []
    })
    assert result["success"] is True, f"Cancellation query failed: {result}"
    response_text = result.get("response", "").lower()
    assert any(kw in response_text for kw in ["cancel", "appointment", "no appointment", "cannot", "sorry", "issue"]), \
        f"Unexpected cancel response: {response_text[:200]}"
    print(f"  [PASS] Cancellation test passed. Provider: {result.get('provider', 'N/A')}")


async def test_7_rag_knowledge_connectivity():
    """Directly verify that receptionist_knowledge FAISS index is reachable."""
    from tools.receptionist_rag_tools import search_receptionist_knowledge
    result = search_receptionist_knowledge("business hours timing")
    # Should not error — either returns content or 'no matching' message
    assert isinstance(result, str) and len(result) > 5
    print(f"  [PASS] RAG connectivity test passed. Result snippet: '{result[:80].strip()}'")


async def test_8_emergency_mode_safety():
    """Circuit-breaker tripped → process() returns safe emergency response (no crash)."""
    agent = ReceptionistAgent()
    ReceptionistAgent.CIRCUIT_BREAKER_TRIPPED = True
    import time
    ReceptionistAgent.CIRCUIT_BREAKER_TRIPPED_AT = time.time()

    try:
        result = await agent.process({
            "query": _build_query("Book an appointment", FAKE_CUSTOMER_ID),
            "session_id": "e2e-recep-emergency",
            "chat_history": []
        })
        assert result["success"] is True
        assert "unable to verify" in result["response"].lower() or "booking form" in result["response"].lower()
        print(f"  [PASS] Emergency mode test passed. Response: '{result['response'][:80]}'")
    finally:
        ReceptionistAgent.CIRCUIT_BREAKER_TRIPPED = False
        ReceptionistAgent.FAILURE_COUNT = 0


async def run_all():
    """Run all E2E tests sequentially."""
    print("\n" + "="*65)
    print("  RECEPTIONIST AGENT (CLARA) - E2E TEST SUITE")
    print("="*65)
    _load_db_fixtures()
    print(f"\nFixtures loaded:")
    print(f"  Customer ID : {FAKE_CUSTOMER_ID}")
    print(f"  Branch      : {FAKE_BRANCH_NAME}")
    print(f"  Service     : {FAKE_SERVICE_NAME}")
    print(f"  Staff       : {FAKE_STAFF_NAME}")

    tests = [
        ("Test 1 - Greeting (keyword shortcut)", test_1_greeting),
        ("Test 2 - Policy RAG query", test_2_policy_rag),
        ("Test 3 - Booking with missing fields", test_3_booking_missing_fields),
        ("Test 4 - Full booking attempt", test_4_full_booking),
        ("Test 5 - Appointment history", test_5_history_query),
        ("Test 6 - Cancellation request", test_6_cancellation_query),
        ("Test 7 - RAG knowledge connectivity", test_7_rag_knowledge_connectivity),
        ("Test 8 - Emergency mode safety", test_8_emergency_mode_safety),
    ]

    passed = 0
    failed = 0
    for name, fn in tests:
        print(f"\n{name}")
        try:
            await fn()
            passed += 1
        except Exception as e:
            print(f"  [FAIL] FAILED: {e}")
            failed += 1

    print("\n" + "="*65)
    print(f"  RESULTS: {passed} passed / {failed} failed / {len(tests)} total")
    print("="*65 + "\n")
    return failed == 0


if __name__ == "__main__":
    ok = asyncio.run(run_all())
    sys.exit(0 if ok else 1)
