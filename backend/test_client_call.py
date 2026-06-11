import os
import sys
import asyncio
import logging

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from core.llm_config import get_llm_config
from core.openai_client_adapter import OpenAIChatCompletionClient
from autogen_core.models import SystemMessage, UserMessage

async def main():
    llm_config = get_llm_config()
    config = llm_config.get_config()
    
    client = OpenAIChatCompletionClient(
        model=config["model"],
        api_key=config["api_key"],
        base_url=config["base_url"],
        model_info=config["model_info"],
    )
    
    # We want to format a mock raw tool output
    raw_output = "{'success': True, 'customer_id': '577186c8-5084-40f0-ad9a-627d395420fb', 'customer_name': 'John Customer', 'email': 'customer@example.com', 'phone': '+1-212-555-9002', 'appointment_count': 0, 'history': []}"
    
    sys_msg = SystemMessage(
        content="You are Clara, the elegant and warm AI Receptionist at SalonAI. Translate the raw system tool result into a warm, professional conversational reply for John Customer. Explain that they don't have any bookings yet and invite them to book a premium haircut or hot stone massage. Keep it to 2 sentences."
    )
    user_msg = UserMessage(
        content=f"Raw result: {raw_output}",
        source="user"
    )
    
    print("Calling model client directly...")
    result = await client.create(messages=[sys_msg, user_msg])
    print("\n--- Direct Call Response ---")
    print(result.content)

if __name__ == "__main__":
    asyncio.run(main())
