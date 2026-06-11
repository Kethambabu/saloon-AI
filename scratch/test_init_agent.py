import sys
import os

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../backend")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.config import get_settings
from core.llm_config import get_llm_config
from agents.receptionist_agent import ReceptionistAgent

print("Loading settings...")
settings = get_settings()
print("HUGGINGFACE_ENABLED:", settings.huggingface_enabled)
print("HUGGINGFACE_MODEL:", settings.huggingface_model)
print("HUGGINGFACE_API_BASE_URL:", settings.huggingface_api_base_url)
print("GROQ_API_KEY:", settings.groq_api_key)
print("GEMINI_API_KEY:", settings.gemini_api_key)

print("\nFetching LLM config...")
llm_config = get_llm_config()
print("current_provider:", llm_config.current_provider)
print("config:", llm_config.get_config())

print("\nInitializing ReceptionistAgent...")
try:
    agent = ReceptionistAgent()
    print("ReceptionistAgent initialized successfully!")
except Exception as e:
    import traceback
    print("Error initializing ReceptionistAgent:")
    traceback.print_exc()
