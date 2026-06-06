import os
import sys
import asyncio

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.orchestrator import MultiAgentOrchestrator

async def main():
    orch = MultiAgentOrchestrator()
    queries = [
        "hi",
        "show me today's revenue",
        "how many returning cohort customers do we have?",
    ]
    for q in queries:
        print(f"\nQUERY: {q}")
        res = await orch.process({
            "query": q,
            "intent_override": "business_intelligence",
            "session_id": "test_session",
            "chat_history": []
        })
        print(f"SUCCESS: {res.get('success')}")
        print(f"AGENT: {res.get('agent_name')}")
        print(f"RESPONSE:\n{res.get('response')}")
        print("-" * 50)

if __name__ == "__main__":
    asyncio.run(main())
