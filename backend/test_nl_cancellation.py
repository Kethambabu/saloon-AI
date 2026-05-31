"""
Direct test of natural language appointment cancellation through ReceptionistAgent.
Tests the enhanced appointment resolution with fuzzy matching.
"""

import os
import sys
import asyncio
import logging
from datetime import datetime, timezone

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from db.database import SessionLocal
from agents.receptionist_agent import ReceptionistAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination

# Setup logging
logging.basicConfig(level=logging.WARNING)  # Reduce noise

CUSTOMER_ID = "577186c8-5084-40f0-ad9a-627d395420fb"  # John Customer

async def test_natural_language_cancellation():
    """Test appointment cancellation with natural language description."""
    
    print("\n" + "#"*70)
    print("# NATURAL LANGUAGE APPOINTMENT CANCELLATION TEST")
    print("#"*70)
    
    print("\nInitializing ReceptionistAgent...")
    try:
        agent = ReceptionistAgent()
        print("[OK] Agent initialized successfully")
    except Exception as e:
        print(f"[FAIL] Could not initialize agent: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    current_time = datetime.now(timezone.utc)
    
    # First, let's book an appointment that we can then cancel
    print("\n[1/2] Creating an appointment to cancel...")
    print("-" * 70)
    
    query_book = f"""[SYSTEM TIME CONTEXT: Current system time is {current_time.strftime('%Y-%m-%d %H:%M:%S')} (Today is {current_time.strftime('%A, %B %d, %Y')}).]\n[SYSTEM CUSTOMER CONTEXT: Logged in as Customer 'John Customer' (ID: {CUSTOMER_ID}).]\nLatest User Message: Please book me a Signature Precision Haircut appointment at Downtown Elite with Alexandra Chen for tomorrow at 2:00 PM."""
    
    print("Customer: Please book me a Signature Precision Haircut appointment at Downtown Elite with Alexandra Chen for tomorrow at 2:00 PM.")
    
    try:
        termination = MaxMessageTermination(max_messages=12) | TextMentionTermination("TERMINATE")
        team = RoundRobinGroupChat(
            participants=[agent.assistant],
            termination_condition=termination,
        )
        result = await team.run(task=query_book)
        
        if result.messages:
            full_response = ""
            for msg in result.messages:
                content = getattr(msg, 'content', str(msg))
                full_response += str(content) + "\n"
            
            print("[Agent Response (first 800 chars)]:")
            print("-" * 70)
            print(full_response[:800])
            
            if "created" in full_response.lower() or "confirmed" in full_response.lower():
                print("\n[OK] Appointment created successfully!")
            else:
                print("\n[OK] Booking step completed (check details above)")
            
    except Exception as e:
        print(f"[FAIL] Error in booking: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    # Now test the cancellation with natural language
    print("\n\n[2/2] Testing NATURAL LANGUAGE appointment cancellation...")
    print("-" * 70)
    
    # This is the exact request from the user that was failing before
    query_cancel = f"""[SYSTEM TIME CONTEXT: Current system time is {current_time.strftime('%Y-%m-%d %H:%M:%S')} (Today is {current_time.strftime('%A, %B %d, %Y')}).]\n[SYSTEM CUSTOMER CONTEXT: Logged in as Customer 'John Customer' (ID: {CUSTOMER_ID}).]\nLatest User Message: cancel Downtown Elite on May 31st at 2:00 PM - Signature Precision Haircut with Alexandra Chen"""
    
    print("Customer: cancel Downtown Elite on May 31st at 2:00 PM - Signature Precision Haircut with Alexandra Chen")
    
    try:
        termination = MaxMessageTermination(max_messages=10) | TextMentionTermination("TERMINATE")
        team = RoundRobinGroupChat(
            participants=[agent.assistant],
            termination_condition=termination,
        )
        result = await team.run(task=query_cancel)
        
        if result.messages:
            full_response = ""
            for msg in result.messages:
                content = getattr(msg, 'content', str(msg))
                full_response += str(content) + "\n"
            
            print("[Agent Response]:")
            print("-" * 70)
            print(full_response)
            
            # Check for success indicators
            if "cancelled" in full_response.lower() or "canceled" in full_response.lower():
                print("\n[SUCCESS] Appointment cancellation succeeded with natural language!")
                return True
            elif "not found" in full_response.lower() or "invalid identifier" in full_response.lower():
                print("\n[FAIL] Appointment not found or invalid identifier error")
                return False
            else:
                print("\n[UNCLEAR] Response unclear - check output above")
                return None
            
    except Exception as e:
        print(f"[FAIL] Error in cancellation: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_natural_language_cancellation())
    
    if success is True:
        print("\n" + "="*70)
        print("FINAL RESULT: [SUCCESS] NATURAL LANGUAGE CANCELLATION TEST PASSED")
        print("="*70)
        sys.exit(0)
    elif success is False:
        print("\n" + "="*70)
        print("FINAL RESULT: [FAIL] NATURAL LANGUAGE CANCELLATION TEST FAILED")
        print("="*70)
        sys.exit(1)
    else:
        print("\n" + "="*70)
        print("FINAL RESULT: [UNCLEAR] NATURAL LANGUAGE CANCELLATION TEST INCONCLUSIVE")
        print("="*70)
        sys.exit(2)
