import os
import sys
import pytest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.receptionist_agent import ReceptionistAgent


@pytest.mark.asyncio
async def test_receptionist_asks_for_details_when_missing():
    """Verify that receptionist asks for missing details instead of booking immediately with defaults."""
    agent = ReceptionistAgent()
    
    # 1. Mock the LLM client's create response for intent extraction
    mock_llm_res = AsyncMock()
    mock_llm_res.content = '{"intent": "book", "service": null, "branch": null, "stylist": null, "date": "tomorrow", "time": null}'
    
    with patch("core.openai_client_adapter.OpenAIChatCompletionClient.create", return_value=mock_llm_res):
        res = await agent.process({
            "query": "book an appointment tomorrow",
            "customer_id": "some-customer-id"
        })
        
        # 2. Check that the agent did not confirm booking, but instead requested the missing details
        assert res["success"] is True
        assert "which service you would like to book" in res["response"].lower()
        assert "at which branch location" in res["response"].lower()
        assert "at what time" in res["response"].lower()
        assert "confirmed" not in res["response"].lower()
        assert "appointment summary" not in res["response"].lower()


@pytest.mark.asyncio
async def test_receptionist_books_when_all_details_provided():
    """Verify that receptionist attempts to check availability and book when all parameters are provided."""
    agent = ReceptionistAgent()
    
    from datetime import datetime, timedelta, timezone
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
    
    # Mock the LLM client's create response to return all required details
    mock_llm_res = AsyncMock()
    mock_llm_res.content = f'{{"intent": "book", "service": "Bridal Makeup", "branch": "Main Salon", "stylist": "Marcus Johnson", "date": "{tomorrow}", "time": "17:00"}}'
    
    # Mock check_stylist_availability to indicate slot is free
    mock_availability = f'{{"slots": [{{"start_time": "{tomorrow}T17:00:00Z"}}]}}'
    
    # Mock book_new_appointment to return success
    mock_booking = '{"success": true, "appointment_id": "appt-123"}'
    
    with patch("core.openai_client_adapter.OpenAIChatCompletionClient.create", return_value=mock_llm_res), \
         patch("agents.receptionist_agent.check_stylist_availability", return_value=mock_availability), \
         patch("agents.receptionist_agent.book_new_appointment", return_value=mock_booking):
         
        res = await agent.process({
            "query": "book Bridal Makeup at Main Salon with Marcus Johnson tomorrow at 17:00"
        })
        
        assert res["success"] is True
        assert "bridal makeup" in res["response"].lower()
        assert "main salon" in res["response"].lower()
        assert "marcus johnson" in res["response"].lower()
        assert "confirmed" in res["response"].lower()
        assert "appointment summary" in res["response"].lower()
