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
from db.models import Review
from agents.reputation_agent import ReputationAgent

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_test():
    logger.info("Initializing ReputationAgent...")
    agent = ReputationAgent()

    # Find a review from the seeded DB
    db = SessionLocal()
    try:
        rev = db.query(Review).first()
        if not rev:
            logger.error("No reviews found in database. Please run seed script first.")
            return False
        review_id = str(rev.id)
        logger.info(f"Testing with seeded Review ID: {review_id} (Rating: {rev.rating}, Comment: {rev.comment})")
    finally:
        db.close()

    # Define system context and user queries
    context = (
        f"[SYSTEM TIME CONTEXT: Current system time is 2026-06-06 12:00:00 (Today is Saturday, June 06, 2026).]\n"
        f"[SYSTEM REPUTATION CONTEXT: Target review for response drafting is Review ID: {review_id}.]"
    )

    test_queries = [
        "Show the reputation scorecard/analytics summary.",
        f"Draft a response to customer review ID: {review_id}.",
        "Search reputation templates or response guidelines in the reputation memory RAG."
    ]

    for q in test_queries:
        query_payload = f"{context}\nLatest User Message: {q}"
        logger.info(f"\n========================================\nProcessing Query: {q}\n========================================")
        
        # Run agent process method
        res = await agent.process({
            "query": query_payload,
            "session_id": "test-session-reputation-123",
            "chat_history": []
        })
        
        logger.info("Response received:")
        logger.info(res.get("response", "No response content"))
        assert res.get("success") is True, f"Agent failed to process query: {res.get('error')}"
        logger.info("✓ Success: query processed successfully.")

    logger.info("\n✓ E2E Reputation Agent test completed successfully!")
    return True

if __name__ == "__main__":
    success = asyncio.run(run_test())
    sys.exit(0 if success else 1)
