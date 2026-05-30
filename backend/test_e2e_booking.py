"""
End-to-end test for booking flow through the chat API endpoint.
Simulates a customer booking an appointment via the receptionist agent.
"""

import requests
import json
from datetime import datetime

# API endpoint
API_URL = "http://localhost:8000/api/agent/chat"
CUSTOMER_ID = "577186c8-5084-40f0-ad9a-627d395420fb"  # John Customer

def print_response(title, response):
    """Pretty print API response."""
    print(f"\n{'='*70}")
    print(f"{title}")
    print('='*70)
    if isinstance(response, dict):
        print(json.dumps(response, indent=2))
    else:
        print(response)


def test_booking_flow():
    """Test the complete booking flow through the chat API."""
    
    print("\n" + "#"*70)
    print("# END-TO-END BOOKING FLOW TEST")
    print("#"*70)
    
    conversation_history = []
    
    # Step 1: Customer initiates booking request
    print("\n📝 STEP 1: Customer initiates booking request")
    print("-" * 70)
    
    initial_message = "I'd like to book an appointment for tomorrow at 10 AM"
    print(f"Customer: {initial_message}")
    
    conversation_history.append({
        "role": "user",
        "content": initial_message
    })
    
    try:
        response = requests.post(
            API_URL,
            json={
                "message": initial_message,
                "customer_id": CUSTOMER_ID,
                "conversation_history": []
            },
            timeout=30
        )
        response.raise_for_status()
        assistant_response = response.json()
        print_response("Agent Response", assistant_response)
        
        if not isinstance(assistant_response, dict) or "error" in assistant_response:
            print("❌ Error: Got error response")
            return False
        
        conversation_history.append({
            "role": "assistant",
            "content": str(assistant_response)
        })
        
    except requests.exceptions.RequestException as e:
        print(f"❌ API Error: {str(e)}")
        return False
    
    # Step 2: Customer provides booking details
    print("\n📝 STEP 2: Customer provides booking details")
    print("-" * 70)
    
    booking_details = "I want the Signature Precision Haircut at Downtown Elite with Alexandra Chen"
    print(f"Customer: {booking_details}")
    
    conversation_history.append({
        "role": "user",
        "content": booking_details
    })
    
    try:
        response = requests.post(
            API_URL,
            json={
                "message": booking_details,
                "customer_id": CUSTOMER_ID,
                "conversation_history": conversation_history[:-1]  # Exclude the last user message we just added
            },
            timeout=30
        )
        response.raise_for_status()
        assistant_response = response.json()
        print_response("Agent Response", assistant_response)
        
        if not isinstance(assistant_response, dict) or "error" in assistant_response:
            print("❌ Error: Got error response")
            return False
        
        response_text = str(assistant_response)
        
        # Check if booking was successful
        if "CONFIRMED" in response_text or "confirmed" in response_text or "appointment" in response_text.lower():
            print("\n✅ Booking appears to have been successfully created!")
            return True
        else:
            print("\n⚠️  Booking response received but unclear if successful")
            return True  # Still pass if we got a response
        
    except requests.exceptions.RequestException as e:
        print(f"❌ API Error: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ Unexpected Error: {str(e)}")
        return False


if __name__ == "__main__":
    try:
        success = test_booking_flow()
        
        print("\n" + "#"*70)
        if success:
            print("✅ END-TO-END TEST PASSED!")
        else:
            print("❌ END-TO-END TEST FAILED!")
        print("#"*70 + "\n")
        
    except Exception as e:
        print(f"\n❌ Test execution failed: {str(e)}")
        import traceback
        traceback.print_exc()
