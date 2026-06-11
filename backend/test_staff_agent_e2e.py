import os
import sys
import asyncio
import logging

# Add backend directory and parent directory to path
backend_dir = os.path.abspath(os.path.dirname(__file__))
parent_dir = os.path.dirname(backend_dir)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from db.database import SessionLocal
from db.models import Staff
from agents.staff_assistant_agent import StaffAssistantAgent

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_test():
    logger.info("Initializing StaffAssistantAgent...")
    agent = StaffAssistantAgent()

    # Find stylists from the seeded DB
    db = SessionLocal()
    try:
        staff_members = db.query(Staff).filter(Staff.is_active == True).all()
        if not staff_members:
            logger.error("No staff member found in database. Please run seed script first.")
            return False
        
        staff_member = staff_members[0]
        staff_id = str(staff_member.id)
        staff_name = staff_member.full_name
        staff_role = staff_member.role
        logger.info(f"Testing with logged-in Staff member: {staff_name} (ID: {staff_id}, Role: {staff_role})")

        # Find another staff member for cross-access test
        other_staff = None
        for sm in staff_members:
            if sm.id != staff_member.id:
                other_staff = sm
                break

        if other_staff:
            logger.info(f"Cross-staff target for access restriction test: {other_staff.full_name} (ID: {other_staff.id})")
        else:
            logger.warning("Only one active staff member found. Cross-access test might be limited.")
    finally:
        db.close()

    # Define system context and user queries
    context = (
        f"[SYSTEM TIME CONTEXT: Current system time is 2026-06-06 12:00:00 (Today is Saturday, June 06, 2026).]\n"
        f"[SYSTEM STAFF CONTEXT: The user chatting with you is logged in as Staff member '{staff_name}' (ID: {staff_id}, Role: {staff_role}, Branch ID: 'default'). Use this Staff ID ({staff_id}) when they query their own schedule, revenue, performance, or leaves. If they ask about another staff member's details, resolve the correct staff ID using list_available_staff or by name, and do NOT use the logged-in user's Staff ID. Do NOT ask them for their ID.]"
    )

    test_queries = [
        "Show my appointments today.",
        "i want yesterday revenue only",
        f"Search the staff memory logs for {staff_name} to summarize productivity and revenue performance"
    ]

    # Run authorized queries
    for idx, q in enumerate(test_queries):
        query_payload = f"{context}\nLatest User Message: {q}"
        logger.info(f"\n========================================\nProcessing Query: {q}\n========================================")
        
        # Retry loop for rate limits
        res = None
        for attempt in range(1, 4):
            try:
                res = await agent.process({
                    "query": query_payload,
                    "session_id": f"test-session-{idx}",
                    "chat_history": []
                })
                if res.get("success") is True:
                    break
                else:
                    error_msg = res.get("error", "")
                    if "429" in error_msg or "rate limit" in error_msg.lower() or "resource_exhausted" in error_msg.lower():
                        logger.warning(f"Attempt {attempt} failed due to rate limits: {error_msg}. Retrying in {attempt * 15}s...")
                        await asyncio.sleep(attempt * 15)
                    else:
                        break
            except Exception as e:
                logger.error(f"Attempt {attempt} raised exception: {e}")
                if attempt < 3:
                    await asyncio.sleep(attempt * 15)
                else:
                    raise
        
        logger.info("Response received:")
        logger.info(res.get("response", "No response content"))
        assert res.get("success") is True, f"Agent failed to process query: {res.get('error')}"
        logger.info("✓ Success: query processed successfully.")
        await asyncio.sleep(15)

    # Run cross-access restricted query
    if other_staff:
        restricted_query = f"Search the staff memory logs for {other_staff.full_name} to summarize stylist productivity"
        query_payload = f"{context}\nLatest User Message: {restricted_query}"
        logger.info(f"\n========================================\nProcessing Restricted Query: {restricted_query}\n========================================")
        await asyncio.sleep(15)
        
        # Retry loop for rate limits
        res = None
        for attempt in range(1, 4):
            try:
                res = await agent.process({
                    "query": query_payload,
                    "session_id": "test-session-restricted",
                    "chat_history": []
                })
                if res.get("success") is True:
                    break
                else:
                    error_msg = res.get("error", "")
                    if "429" in error_msg or "rate limit" in error_msg.lower() or "resource_exhausted" in error_msg.lower():
                        logger.warning(f"Attempt {attempt} failed due to rate limits: {error_msg}. Retrying in {attempt * 15}s...")
                        await asyncio.sleep(attempt * 15)
                    else:
                        break
            except Exception as e:
                logger.error(f"Attempt {attempt} raised exception: {e}")
                if attempt < 3:
                    await asyncio.sleep(attempt * 15)
                else:
                    raise
        
        response_text = res.get("response", "")
        logger.info("Response received:")
        logger.info(response_text)
        assert res.get("success") is True, f"Agent failed to process query: {res.get('error')}"
        
        # Verify that access was denied
        assert "access denied" in response_text.lower() or "permission" in response_text.lower(), \
            f"Expected access restriction error message, but got: {response_text}"
        logger.info("✓ Success: Cross-staff query was correctly restricted and denied access!")

    logger.info("\n✓ E2E Staff Assistant Agent test completed successfully!")
    return True

if __name__ == "__main__":
    success = asyncio.run(run_test())
    sys.exit(0 if success else 1)
