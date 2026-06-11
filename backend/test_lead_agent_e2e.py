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
from db.models import Lead
from agents.lead_followup_agent import LeadFollowupAgent

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_test():
    logger.info("Initializing LeadFollowupAgent...")
    agent = LeadFollowupAgent()

    # Find a lead from the seeded DB
    db = SessionLocal()
    try:
        lead_member = db.query(Lead).first()
        if not lead_member:
            logger.error("No lead found in database. Please run seed script first.")
            return False
        lead_id = str(lead_member.id)
        lead_name = lead_member.full_name
        logger.info(f"Testing with seeded Lead: {lead_name} (ID: {lead_id})")
    finally:
        db.close()

    # Define system context and user queries
    context = (
        f"[SYSTEM TIME CONTEXT: Current system time is 2026-06-06 12:00:00 (Today is Saturday, June 06, 2026).]\n"
        f"[SYSTEM LEAD CONTEXT: Target lead for follow-up is '{lead_name}' (ID: {lead_id}).]"
    )

    test_queries = [
        "Show current lead pipeline snapshot.",
        f"Draft a warm email follow-up message for lead '{lead_name}' using ID {lead_id}.",
        "Search follow-up history or templates in lead campaign memory."
    ]

    for q in test_queries:
        query_payload = f"{context}\nLatest User Message: {q}"
        logger.info(f"\n========================================\nProcessing Query: {q}\n========================================")
        
        # Run agent process method
        res = await agent.process({
            "query": query_payload,
            "session_id": "test-session-lead-123",
            "chat_history": []
        })
        
        logger.info("Response received:")
        logger.info(res.get("response", "No response content"))
        assert res.get("success") is True, f"Agent failed to process query: {res.get('error')}"
        logger.info("✓ Success: query processed successfully.")

    logger.info("\n✓ E2E Lead Agent test completed successfully!")
    return True

if __name__ == "__main__":
    success = asyncio.run(run_test())
    sys.exit(0 if success else 1)
