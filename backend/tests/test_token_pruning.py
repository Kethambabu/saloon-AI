import json
import pytest
from core.openai_client_adapter import OpenAIChatCompletionClient
from agents.receptionist_agent import compress_history_for_prompt

def test_compress_history_for_prompt():
    # Mock a large customer booking history payload containing 10 appointments
    mock_history = {
        "success": True,
        "customer_id": "c-123",
        "customer_name": "NEELAM VENKATA SRI LAKSHMI",
        "email": "balu@gmail.com",
        "phone": "+916281664336",
        "appointment_count": 10,
        "history": [
            {
                "appointment_id": f"appt-{i}",
                "branch_name": "Main Salon",
                "branch_city": "New York",
                "service_name": "Bridal Makeup" if i % 2 == 0 else "Precision Haircut",
                "service_price": 220.0 if i % 2 == 0 else 85.0,
                "service_duration": 120 if i % 2 == 0 else 60,
                "service": {
                    "name": "Bridal Makeup" if i % 2 == 0 else "Precision Haircut",
                    "price": 220.0 if i % 2 == 0 else 85.0,
                    "duration_minutes": 120 if i % 2 == 0 else 60
                },
                "staff_name": "Marcus Johnson",
                "staff": {
                    "name": "Marcus Johnson"
                },
                "start_time": f"2026-06-{10+i:02d}T10:00:00Z",
                "end_time": f"2026-06-{10+i:02d}T12:00:00Z",
                "status": "COMPLETED" if i < 8 else "CANCELLED",
                "notes": "Some long redundant note details here",
                "rating": 5 if i < 8 else None,
                "review_comment": "Excellent service!" if i < 8 else None
            }
            for i in range(10)
        ]
    }

    compressed_str = compress_history_for_prompt(mock_history)
    compressed_data = json.loads(compressed_str)

    # Assert basic stats
    assert compressed_data["customer_name"] == "NEELAM VENKATA SRI LAKSHMI"
    assert compressed_data["total_appointments"] == 10
    assert compressed_data["completed"] == 8
    assert compressed_data["cancelled"] == 2
    assert compressed_data["total_spent_on_completed"] == (4 * 220.0 + 4 * 85.0) # 8 completed (4 index even, 4 index odd)

    # Check pruning count (limit 8)
    assert len(compressed_data["recent_appointments"]) == 8
    assert "note" in compressed_data

    # Assert redundant nested dicts and verbose keys are stripped
    for appt in compressed_data["recent_appointments"]:
        # The nested "staff" dict must be removed (replaced by flat "stylist")
        assert "staff" not in appt
        # Verbose keys should be stripped
        assert "notes" not in appt
        assert "review_comment" not in appt
        # Expected flat keys should exist
        assert "id" in appt
        assert "date" in appt
        assert "time" in appt
        assert "service" in appt  # holds service name directly as a string
        assert isinstance(appt["service"], str), "service should be a flat string, not a nested dict"
        assert "price" in appt
        assert "stylist" in appt
        assert "status" in appt


def test_openai_client_adapter_message_pruning():
    # Instantiate client in mock mode
    client = OpenAIChatCompletionClient(
        model="llama-3.1-8b-instant",
        api_key="mock-key",
        base_url="https://api.groq.com/openai/v1"
    )

    # Create dummy messages
    messages = [
        {"role": "system", "content": "You are Clara, a helpful salon assistant."},
        {"role": "user", "content": "Hello! I would like to check my history."},
        {"role": "assistant", "content": "Sure! Here it is."},
        {"role": "user", "content": "Wow, that's a lot. Can you show me the next slots?"},
        {"role": "assistant", "content": "Yes, tomorrow at 3pm, 4pm, and 5pm are available."},
        {"role": "user", "content": "Perfect, let's book 3pm please."}
    ]

    # Test under a high token budget (should not prune)
    unpruned = client._prune_messages(messages, max_tokens=1000)
    assert len(unpruned) == len(messages)

    # Test under a tight token budget (should prune older conversational history)
    # Estimate: messages have total ~200 characters -> ~50 tokens.
    # Let's set budget to 25 tokens (~100 chars).
    pruned = client._prune_messages(messages, max_tokens=25)
    
    # Pruned list must:
    # 1. Be shorter than original list
    assert len(pruned) < len(messages)
    # 2. Keep the system prompt at index 0
    assert pruned[0]["role"] == "system"
    assert pruned[0]["content"] == "You are Clara, a helpful salon assistant."
    # 3. Keep the very last user query
    assert pruned[-1]["role"] == "user"
    assert pruned[-1]["content"] == "Perfect, let's book 3pm please."
