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

from agents.bi_agent import BIAgent

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_test():
    logger.info("Initializing BIAgent (Atlas)...")
    agent = BIAgent()

    # Define system context and user queries
    context = (
        "[SYSTEM TIME CONTEXT: Current system time is 2026-06-06 12:00:00 (Today is Saturday, June 06, 2026).]\n"
    )

    test_queries = [
        "Show me today's core business performance indicators and dashboard summary.",
        "Retrieve the revenue summary and how it's distributed by service.",
        "Search general policies in the salon knowledge base RAG."
    ]

    for q in test_queries:
        query_payload = f"{context}\nLatest User Message: {q}"
        logger.info(f"\n========================================\nProcessing Query: {q}\n========================================")
        
        # Run agent process method
        res = await agent.process({
            "query": query_payload,
            "session_id": "test-session-bi-123",
            "chat_history": []
        })
        
        logger.info("Response received:")
        logger.info(res.get("response", "No response content"))
        assert res.get("success") is True, f"Agent failed to process query: {res.get('error')}"
        logger.info("✓ Success: query processed successfully.")

    logger.info("\n✓ E2E Business Intelligence Agent test completed successfully!")
    return True

if __name__ == "__main__":
    success = asyncio.run(run_test())
    sys.exit(0 if success else 1)
