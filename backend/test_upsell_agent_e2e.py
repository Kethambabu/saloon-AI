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
from db.models import Customer
from agents.upsell_agent import UpsellAgent

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_test():
    logger.info("Initializing UpsellAgent...")
    agent = UpsellAgent()

    # Find a customer from the seeded DB
    db = SessionLocal()
    try:
        cust = db.query(Customer).first()
        if not cust:
            logger.error("No customer found in database. Please run seed script first.")
            return False
        customer_id = str(cust.id)
        customer_name = cust.full_name
        logger.info(f"Testing with seeded Customer: {customer_name} (ID: {customer_id})")
    finally:
        db.close()

    # Define system context and user queries
    context = (
        f"[SYSTEM TIME CONTEXT: Current system time is 2026-06-06 12:00:00 (Today is Saturday, June 06, 2026).]\n"
        f"[SYSTEM CUSTOMER CONTEXT: The user chatting with you is logged in as Customer '{customer_name}' (ID: {customer_id}).]"
    )

    test_queries = [
        f"Generate upsell recommendations for customer ID: {customer_id}.",
        "What active offers or special discounts are available?",
        "Find ravi sharma's haircut preferences from the customer styling memory."
    ]

    for q in test_queries:
        query_payload = f"{context}\nLatest User Message: {q}"
        logger.info(f"\n========================================\nProcessing Query: {q}\n========================================")
        
        # Run agent process method
        res = await agent.process({
            "query": query_payload,
            "session_id": "test-session-upsell-123",
            "chat_history": []
        })
        
        logger.info("Response received:")
        logger.info(res.get("response", "No response content"))
        assert res.get("success") is True, f"Agent failed to process query: {res.get('error')}"
        logger.info("✓ Success: query processed successfully.")

    logger.info("\n✓ E2E Upsell Agent test completed successfully!")
    return True

if __name__ == "__main__":
    success = asyncio.run(run_test())
    sys.exit(0 if success else 1)
