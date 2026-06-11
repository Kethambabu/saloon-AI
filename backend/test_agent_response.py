import os
import sys
import asyncio
import logging

# Add backend directory and parent directory to path
backend_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, backend_dir)
sys.path.insert(0, os.path.abspath(os.path.join(backend_dir, "..")))

from db.database import SessionLocal
from agents.receptionist_agent import ReceptionistAgent

# Setup logging
logging.basicConfig(level=logging.INFO)

async def main():
    agent = ReceptionistAgent()
    
    # Define the query
    query = "[SYSTEM TIME CONTEXT: Current system time is 2026-05-31 00:04:58 (Today is Sunday, May 31, 2026).]\n[SYSTEM CUSTOMER CONTEXT: Logged in as Customer 'John Customer' (ID: 577186c8-5084-40f0-ad9a-627d395420fb).]\nLatest User Message: Can you check my booking history?"

    print("\n--- Running Clara Receptionist Agent in RoundRobinGroupChat ---")
    from autogen_agentchat.teams import RoundRobinGroupChat
    from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
    
    termination = MaxMessageTermination(max_messages=6) | TextMentionTermination("TERMINATE")
    team = RoundRobinGroupChat(
        participants=[agent.assistant],
        termination_condition=termination,
    )
    result = await team.run(task=query)
    
    print("\n--- Inspecting result.messages ---")
    print(f"Total messages: {len(result.messages)}")
    for idx, msg in enumerate(result.messages):
        msg_type = type(msg).__name__
        source = getattr(msg, "source", "N/A")
        content = getattr(msg, "content", "N/A")
        print(f"\nMessage {idx}:")
        print(f"  Type: {msg_type}")
        print(f"  Source: {source}")
        print(f"  Content Type: {type(content).__name__}")
        print(f"  Content: {repr(content)[:300]}")

if __name__ == "__main__":
    asyncio.run(main())
