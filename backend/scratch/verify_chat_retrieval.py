import os
import sys
import asyncio
import logging

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from db.database import SessionLocal
from db.models import Customer
from agents.orchestrator import MultiAgentOrchestrator

# Setup logging to be clean
logging.basicConfig(level=logging.WARNING)

async def test_agent_chat():
    db = SessionLocal()
    try:
        # Get customer Alice Smith's ID (seeded earlier)
        cust = db.query(Customer).filter(Customer.email == "customer@example.com").first()
        if not cust:
            print("ERROR: customer@example.com not found. Seed the database first.")
            return
        
        customer_id = str(cust.id)
        customer_name = cust.full_name
        print(f"Testing with Customer: {customer_name} (ID: {customer_id})")
        
        orch = MultiAgentOrchestrator()
        
        # Craft a query that specifically asks about styling preferences and previous chats
        query = (
            f"[SYSTEM TIME CONTEXT: Current system time is 2026-06-07 15:00:00 (Today is Sunday, June 7, 2026).]\n"
            f"[SYSTEM CUSTOMER CONTEXT: Logged in as Customer '{customer_name}' (ID: {customer_id}).]\n"
            f"Latest User Message: Hi! What styling note or service preference did you record for my haircut appointment today, and "
            f"what did my previous chat log say about future treatments I would love to try? Please check my customer memory."
        )
        
        print("\n--- Running Orchestrator Agent Chat ---")
        res = await orch.process({
            "query": query,
            "intent_override": "booking",
            "session_id": "test-session-memory-1",
            "chat_history": []
        })
        
        print("\n--- Agent Response ---")
        print("Success:", res.get("success"))
        print("Agent Name:", res.get("agent_name"))
        print("Response Text:")
        response_text = res.get("response", "")
        print(response_text.encode("ascii", "ignore").decode("ascii"))
                    
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_agent_chat())
