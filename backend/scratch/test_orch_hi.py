import asyncio
import json
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.orchestrator import MultiAgentOrchestrator

async def main():
    try:
        print("Initializing orchestrator...")
        orch = MultiAgentOrchestrator()
        print("Processing query...")
        res = await orch.process({
            "query": "hi",
            "intent_override": "business_intelligence",
            "session_id": "test_session_hi",
            "chat_history": []
        })
        print("Writing response to file...")
        with open("scratch/res_hi.json", "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2, ensure_ascii=False)
        print("Done!")
    except Exception as e:
        print(f"Error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
