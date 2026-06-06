import sys
import os
import asyncio
import logging

# Set up logging to stdout
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("debug_group_chat")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from agents.orchestrator import MultiAgentOrchestrator

async def main():
    print("STEP 1: Initializing orchestrator...", flush=True)
    orch = MultiAgentOrchestrator()
    agent = orch.agents[orch.classifier.system_message.lower().find("business_intelligence") != -1 and list(orch.agents.keys())[0]] # Get first agent
    # Actually, let's get Atlas_BI agent
    from agents.orchestrator import AgentIntent
    agent = orch.agents[AgentIntent.BUSINESS_INTELLIGENCE]
    print(f"STEP 2: Selected agent '{agent.name}'", flush=True)
    
    print("STEP 3: Running _run_group_chat for query 'hi'...", flush=True)
    try:
        response_text = await orch._run_group_chat(agent, "hi")
        print(f"SUCCESS: Response is:\n{response_text}", flush=True)
    except Exception as e:
        print(f"FAILED with exception: {e}", flush=True)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
