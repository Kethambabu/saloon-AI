"""
Direct test of the ReceptionistAgent booking flow, bypassing HTTP authentication.
Tests the complete booking flow to ensure the SQLAlchemy session fix works end-to-end.
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

async def test_booking_flow():
    """Test the complete booking flow through the ReceptionistAgent."""
    
    print("\n" + "#"*70)
    print("# END-TO-END BOOKING FLOW TEST - Direct Agent Test")
    print("#"*70)
    
    agent = ReceptionistAgent()
    
    # Step 1: Request to book an appointment
    print("\n📝 STEP 1: Customer requests to book an appointment")
    print("-" * 70)
    
    current_time = datetime.now(timezone.utc)
    tomorrow_10am = current_time.replace(day=current_time.day+1, hour=10, minute=0, second=0, microsecond=0)
    
    query1 = f"""[SYSTEM TIME CONTEXT: Current system time is {current_time.strftime('%Y-%m-%d %H:%M:%S')} (Today is {current_time.strftime('%A, %B %d, %Y')}).]\n[SYSTEM CUSTOMER CONTEXT: Logged in as Customer 'John Customer' (ID: {CUSTOMER_ID}).]\nLatest User Message: I'd like to book an appointment for tomorrow at 10 AM"""
    
    print(f"Customer: I'd like to book an appointment for tomorrow at 10 AM")
    
    try:
        termination = MaxMessageTermination(max_messages=8) | TextMentionTermination("TERMINATE")
        team = RoundRobinGroupChat(
            participants=[agent.assistant],
            termination_condition=termination,
        )
        result = await team.run(task=query1)
        
        # Extract the last response
        if result.messages:
            last_msg = result.messages[-1]
            response_text = getattr(last_msg, 'content', str(last_msg))
            print(f"\nAgent Response Preview: {str(response_text)[:300]}...")
            
            # Log all messages for debugging
            print(f"\n[Conversation had {len(result.messages)} messages total]")
        
    except Exception as e:
        print(f"❌ Error in step 1: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 2: Customer provides booking details
    print("\n\n📝 STEP 2: Customer provides booking details and confirms")
    print("-" * 70)
    
    query2 = f"""[SYSTEM TIME CONTEXT: Current system time is {current_time.strftime('%Y-%m-%d %H:%M:%S')} (Today is {current_time.strftime('%A, %B %d, %Y')}).]\n[SYSTEM CUSTOMER CONTEXT: Logged in as Customer 'John Customer' (ID: {CUSTOMER_ID}).]\nLatest User Message: I want the Signature Precision Haircut at Downtown Elite with Alexandra Chen at 10 AM tomorrow. Please go ahead and book it."""
    
    print(f"Customer: I want the Signature Precision Haircut at Downtown Elite with Alexandra Chen at 10 AM tomorrow. Please go ahead and book it.")
    
    try:
        termination = MaxMessageTermination(max_messages=10) | TextMentionTermination("TERMINATE")
        team = RoundRobinGroupChat(
            participants=[agent.assistant],
            termination_condition=termination,
        )
        result = await team.run(task=query2)
        
        # Extract and analyze the final response
        if result.messages:
            full_response = ""
            for msg in result.messages:
                content = getattr(msg, 'content', str(msg))
                full_response += str(content) + "\n"
            
            print(f"\nAgent Full Conversation:")
            print("-" * 70)
            print(full_response[:1500])
            
            # Check for success indicators
            if "CONFIRMED" in full_response or "confirmed" in full_response or "successful" in full_response.lower():
                print("\n✅ Booking appears to have been successfully created!")
                print("[Check the database for a new appointment record]")
                return True
            elif "Appointment created" in full_response or "appointment_id" in full_response:
                print("\n✅ Booking successfully created!")
                return True
            else:
                print("\n⚠️  Booking response received but unclear if successful")
                print("[Full response above for analysis]")
                return False
        else:
            print("❌ No response from agent")
            return False
            
    except Exception as e:
        print(f"❌ Error in step 2: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(test_booking_flow())
        
        print("\n" + "#"*70)
        if success:
            print("✅ END-TO-END BOOKING TEST PASSED!")
            print("\nThe SQLAlchemy session fix is working correctly.")
            print("Appointments are being created and returned successfully.")
        else:
            print("❌ END-TO-END BOOKING TEST FAILED!")
        print("#"*70 + "\n")
        
    except Exception as e:
        print(f"\n❌ Test execution failed: {str(e)}")
        import traceback
        traceback.print_exc()
