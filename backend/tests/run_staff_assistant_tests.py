import os
import sys
import asyncio
import logging
from datetime import datetime, timezone, date
from typing import Dict, Any, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv()

from infrastructure.db.database import SessionLocal
from infrastructure.db.models import Staff, StaffLeave, Appointment, Customer
from ai.agents.staff_assistant_agent import StaffAssistantAgent
from core.query_context import set_query_context

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("StaffAssistantTestRunner")

# Target Staff details
STAFF_ID = "40e8cef6-f095-4f84-80e3-239d7f748efd"  # Priya Sharma (Hair Specialist)
STAFF_EMAIL = "priya@salonai.com"
STAFF_NAME = "Priya Sharma"

# We will define 10 best staff assistant queries to test
TEST_QUERIES = [
    {
        "id": 1,
        "category": "Leave Request Transaction",
        "query": "I need to request a leave of absence for next Tuesday, August 4th, due to a doctors appointment.",
        "verify_db": True,
        "db_verifier": lambda db: db.query(StaffLeave).filter(
            StaffLeave.staff_id == STAFF_ID, 
            StaffLeave.leave_date == date(2026, 8, 4)
        ).first() is not None,
        "expected_action": "Should trigger execute_transaction with create_leave_request action."
    },
    {
        "id": 2,
        "category": "Send Reminders Transaction",
        "query": "Can you send automated reminders to all of my customers who have appointments tomorrow?",
        "verify_db": False,
        "expected_action": "Should trigger execute_transaction with send_customer_reminders action."
    },
    {
        "id": 3,
        "category": "Today's Schedule Lookup",
        "query": "Show me my schedule for today. Who is my first appointment?",
        "verify_db": False,
        "expected_action": "Should call mcp_read for today_schedule or schedule."
    },
    {
        "id": 4,
        "category": "Customer Preferences Lookup",
        "query": "Who is my next customer, and what are their customer preferences?",
        "verify_db": False,
        "expected_action": "Should call mcp_read or search_knowledge_base for customer details."
    },
    {
        "id": 5,
        "category": "Performance Metrics Summary",
        "query": "What is my average rating and total appointments completed this month?",
        "verify_db": False,
        "expected_action": "Should call mcp_read for staff_performance."
    },
    {
        "id": 6,
        "category": "Revenue & Commissions Summary",
        "query": "How much service revenue and commission did I generate last week?",
        "verify_db": False,
        "expected_action": "Should call mcp_read for staff_revenue."
    },
    {
        "id": 7,
        "category": "Policy RAG (Late Client)",
        "query": "What is the official salon policy for a client who is late by more than 15 minutes?",
        "verify_db": False,
        "expected_action": "Should call search_knowledge_base on policies."
    },
    {
        "id": 8,
        "category": "Policy RAG (Employee Discount)",
        "query": "What is the policy for employee discounts on retail products and services?",
        "verify_db": False,
        "expected_action": "Should call search_knowledge_base on policies."
    },
    {
        "id": 9,
        "category": "Check Leave Status",
        "query": "Check if I have any registered staff_leaves for next Tuesday, August 4th.",
        "verify_db": False,
        "expected_action": "Should query leaves and confirm the leave requested in Query 1."
    },
    {
        "id": 10,
        "category": "Pending Appointments Lookup",
        "query": "Are there any pending appointments assigned to me that need confirmation?",
        "verify_db": False,
        "expected_action": "Should call mcp_read for pending_appointments."
    }
]

async def cleanup_db_for_testing(db):
    """Remove target leave of absence to ensure clean verification."""
    print("[CLEANUP] Cleaning up pre-existing test data in DB...")
    db.query(StaffLeave).filter(
        StaffLeave.staff_id == STAFF_ID, 
        StaffLeave.leave_date == date(2026, 8, 4)
    ).delete()
    db.commit()
    print("[CLEANUP] DB Cleanup done.")

async def run_evaluation():
    db = SessionLocal()
    await cleanup_db_for_testing(db)
    
    context_header = (
        f"[SYSTEM STAFF CONTEXT: ID: {STAFF_ID}, Role: STAFF, Email: {STAFF_EMAIL}]\n"
        f"[SYSTEM TIME CONTEXT: Current system time is 2026-07-27 12:00:00]"
    )
    
    print("\n" + "="*80)
    print(f"STARTING STAFF ASSISTANT AGENT (ATLAS) TEST SUITE")
    print(f"Staff Context: {STAFF_NAME} ({STAFF_EMAIL})")
    print("="*80 + "\n")
    
    results = []
    
    for tc in TEST_QUERIES:
        print(f"[{tc['id']}/10] Category: {tc['category']}")
        print(f"Query: \"{tc['query']}\"")
        print(f"Expected: {tc['expected_action']}")
        
        # Instantiate a clean agent per query to avoid state leakage
        agent = StaffAssistantAgent()
        
        # Format the query with user/system context prepended
        full_query = f"{context_header}\n{tc['query']}"
        
        # Execute the agent
        start_time = datetime.now()
        try:
            response = await agent.process({
                "query": full_query,
                "latest_message": tc["query"],
                "session_id": f"test-session-{tc['id']}"
            })
            duration = (datetime.now() - start_time).total_seconds()
            
            success = response.get("success", False)
            response_text = response.get("response", "") or ""
            
            print(f"Duration: {duration:.2f}s | Success: {success}")
            print("Response:")
            print("-"*50)
            print(response_text)
            print("-"*50)
            
            # Verify DB if required
            db_verified = True
            db_status = "N/A"
            if tc.get("verify_db"):
                db.expire_all()
                db_verified = tc["db_verifier"](db)
                db_status = "PASSED" if db_verified else "FAILED"
                print(f"Database Verification: {db_status}")
            
            # Simple heuristic checks to verify if the agent did what was expected
            passed = success and db_verified
            results.append({
                "id": tc["id"],
                "category": tc["category"],
                "query": tc["query"],
                "success": success,
                "db_status": db_status,
                "duration": duration,
                "passed": passed,
                "response": response_text
            })
            
        except Exception as e:
            print(f"[ERROR] Error executing query: {e}")
            results.append({
                "id": tc["id"],
                "category": tc["category"],
                "query": tc["query"],
                "success": False,
                "db_status": "ERROR",
                "duration": 0,
                "passed": False,
                "response": f"Error: {str(e)}"
            })
            
        print("\n" + "-"*80 + "\n")
        
    db.close()
    
    # Print Summary Table
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"{'ID':<3} | {'Category':<30} | {'Status':<8} | {'DB':<8} | {'Time (s)':<8}")
    print("-"*80)
    total_passed = 0
    for r in results:
        status_str = "SUCCESS" if r["success"] else "FAILED"
        pass_str = "PASS" if r["passed"] else "FAIL"
        if r["passed"]:
            total_passed += 1
        print(f"{r['id']:<3} | {r['category']:<30} | {status_str:<8} | {r['db_status']:<8} | {r['duration']:<8.2f}")
    print("-"*80)
    print(f"Overall Result: {total_passed}/10 Queries Passed.")
    print("="*80 + "\n")

if __name__ == "__main__":
    asyncio.run(run_evaluation())
