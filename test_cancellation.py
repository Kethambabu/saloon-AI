#!/usr/bin/env python
"""Test script for natural language appointment cancellation."""

import httpx
import json
import sys

# Test the receptionist agent endpoint with a natural language cancellation request
test_cases = [
    "cancel Downtown Elite on May 31st at 2:00 PM - Signature Precision Haircut with Alexandra Chen",
    "I want to cancel my appointment at Downtown Elite tomorrow at 2 PM with stylist Alexandra",
    "Cancel the Haircut with Alexandra at Downtown Elite",
]

for test_input in test_cases:
    payload = {
        "user_id": "test-user-123",
        "query": test_input
    }

    try:
        print(f"\n{'='*70}")
        print(f"Testing: {test_input}")
        print('='*70)
        response = httpx.post(
            "http://localhost:8000/api/agent/chat",
            json={
                "message": test_input,
                "session_id": "test-session-123",
                "chat_history": []
            },
            timeout=30.0
        )
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"Response: {json.dumps(result, indent=2)}")
        else:
            print(f"Error Response: {response.text}")
    except Exception as e:
        print(f"Request Error: {e}")
        sys.exit(1)

print(f"\n{'='*70}")
print("✅ All tests completed")
print('='*70)
