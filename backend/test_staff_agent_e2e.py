import os
import sys
import asyncio
import logging

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from db.database import SessionLocal
from db.models import Staff
from agents.staff_assistant_agent import StaffAssistantAgent

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_test():
    logger.info("Initializing StaffAssistantAgent...")
    agent = StaffAssistantAgent()

    # Find a stylist from the seeded DB
    db = SessionLocal()
    try:
        staff_member = db.query(Staff).first()
        if not staff_member:
            logger.error("No staff member found in database. Please run seed script first.")
            return False
        staff_id = str(staff_member.id)
        staff_name = staff_member.full_name
        staff_role = staff_member.role
        logger.info(f"Testing with seeded Staff member: {staff_name} (ID: {staff_id}, Role: {staff_role})")
    finally:
        db.close()

    # Define system context and user queries
    context = (
        f"[SYSTEM TIME CONTEXT: Current system time is 2026-06-06 12:00:00 (Today is Saturday, June 06, 2026).]\n"
        f"[SYSTEM STAFF CONTEXT: The user chatting with you is logged in as Staff '{staff_name}' (ID: {staff_id}, Role: {staff_role}). ALWAYS use this Staff ID ({staff_id}) for schedule and performance queries.]"
    )

    test_queries = [
        "Show my appointments today.",
        "How am I performing?"
    ]

    for q in test_queries:
        query_payload = f"{context}\nLatest User Message: {q}"
        logger.info(f"\n========================================\nProcessing Query: {q}\n========================================")
        
        # We can run the agent process method directly which wraps the autogen team
        res = await agent.process({
            "query": query_payload,
            "session_id": "test-session-123",
            "chat_history": []
        })
        
        logger.info("Response received:")
        logger.info(res.get("response", "No response content"))
        assert res.get("success") is True, f"Agent failed to process query: {res.get('error')}"
        logger.info("✓ Success: query processed successfully.")

    logger.info("\n✓ E2E Staff Assistant Agent test completed successfully!")
    return True

if __name__ == "__main__":
    success = asyncio.run(run_test())
    sys.exit(0 if success else 1)
