import os
import sys
import asyncio
import logging
from datetime import datetime

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from db.database import SessionLocal
from db.models import Customer, Service, Branch, Staff
from agents.receptionist_agent import ReceptionistAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_booking_test():
    logger.info("Initializing ReceptionistAgent...")
    agent = ReceptionistAgent()

    db = SessionLocal()
    try:
        # Check if John Customer exists
        customer = db.query(Customer).filter(Customer.email == "john@example.com").first()
        if not customer:
            customer = db.query(Customer).first()
        if not customer:
            logger.error("No customer found in database. Run seeding first.")
            return False
        
        customer_id = str(customer.id)
        customer_name = customer.full_name
        customer_email = customer.email
        logger.info(f"Testing with Customer: {customer_name} (ID: {customer_id}, Email: {customer_email})")
        
        # Get Marcus Johnson or another staff member
        staff = db.query(Staff).filter(Staff.full_name == "Marcus Johnson").first()
        if not staff:
            staff = db.query(Staff).first()
        staff_name = staff.full_name if staff else "Professional Stylist"
        
        # Get Bridal Makeup or another service
        service = db.query(Service).filter(Service.name == "Bridal Makeup").first()
        if not service:
            service = db.query(Service).first()
        service_name = service.name if service else "Bridal Makeup"
        
        # Get Main Salon or another branch
        branch = db.query(Branch).filter(Branch.name == "Main Salon").first()
        if not branch:
            branch = db.query(Branch).first()
        branch_name = branch.name if branch else "Main Salon"
        
    finally:
        db.close()

    # System contexts
    system_time_ctx = "[SYSTEM TIME CONTEXT: Current system time is 2026-06-06 12:00:00 (Today is Saturday, June 06, 2026). Use this to calculate exact dates like 'tomorrow', 'next Tuesday', etc.]"
    customer_ctx = f"[SYSTEM CUSTOMER CONTEXT: The user chatting with you is logged in as Customer '{customer_name}' (ID: {customer_id}, Email: {customer_email}). Always use this Customer ID directly for bookings and customer history lookups. Do NOT ask them to search or provide their details.]"
    
    # 1. First turn: user asks to book
    query_1 = f"{system_time_ctx}\n{customer_ctx}\nLatest User Message: book an appointment for june 8th 2026 10 am slot \"{service_name} {branch_name} {staff_name}\""
    
    logger.info(f"\n--- STEP 1: Sending user booking request for June 8, 2026 ---")
    res_1 = await agent.process({
        "query": query_1,
        "session_id": "test-session-receptionist-1",
        "chat_history": []
    })
    
    logger.info("Agent Response:")
    logger.info(res_1.get("response", ""))
    
    # Assert successful booking or direct response
    assert res_1.get("success") is True, f"Agent failed to process first query: {res_1.get('error')}"
    response_text = res_1.get("response", "")
    
    # Confirm that 'Welcome back' is in the first response
    assert "Welcome back" in response_text, "Welcome back greeting should be prepended to the first response."
    
    # 2. Second turn: simulate follow up query with chat history
    chat_history = [
        {"role": "user", "content": f"book an appointment for june 8th 2026 10 am slot \"{service_name} {branch_name} {staff_name}\""},
        {"role": "assistant", "content": response_text}
    ]
    
    query_2 = f"{system_time_ctx}\n{customer_ctx}\nHere is the conversation history so far for context:\n- User: book an appointment...\n- Assistant: {response_text}\n\nLatest User Message: Can you confirm the stylist name?"
    
    logger.info(f"\n--- STEP 2: Sending follow-up query (checking for prepended stats loop) ---")
    res_2 = await agent.process({
        "query": query_2,
        "session_id": "test-session-receptionist-1",
        "chat_history": chat_history
    })
    
    logger.info("Agent Response:")
    logger.info(res_2.get("response", ""))
    
    # Confirm that 'Welcome back' stats block is NOT in the second response
    assert "Welcome back" not in res_2.get("response", ""), "Welcome back greeting must NOT be repeated in follow-up messages!"
    
    logger.info("\nSUCCESS: All booking flow test validations passed successfully!")
    return True

if __name__ == "__main__":
    success = asyncio.run(run_booking_test())
    sys.exit(0 if success else 1)
