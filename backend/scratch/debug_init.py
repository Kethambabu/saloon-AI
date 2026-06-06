import sys
import os
import time

print("STEP 1: Starting script", flush=True)

# Add parent directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
print("STEP 2: Path updated", flush=True)

print("STEP 3: Importing get_settings", flush=True)
from core.config import get_settings
settings = get_settings()
print(f"Settings loaded: Host={settings.host}, Port={settings.port}", flush=True)

print("STEP 4: Importing get_llm_config", flush=True)
from core.llm_config import get_llm_config
config_manager = get_llm_config()
print("LLM Config Manager instantiated", flush=True)

print("STEP 5: Importing MultiAgentOrchestrator", flush=True)
from agents.orchestrator import MultiAgentOrchestrator
print("Imported MultiAgentOrchestrator", flush=True)

print("STEP 6: Instantiating MultiAgentOrchestrator", flush=True)
orch = MultiAgentOrchestrator()
print("Orchestrator instantiated successfully!", flush=True)

print("STEP 7: Running a dummy query classification test", flush=True)
import asyncio
intent = asyncio.run(orch._classify_intent("hi"))
print(f"Classified intent: {intent}", flush=True)
print("Done diagnostics!", flush=True)
