import os
import sys
import logging
from pathlib import Path

# Add project root to PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Set env variables for test
os.environ["HUGGINGFACE_ENABLED"] = "true"
os.environ["HUGGINGFACE_MODEL"] = "Qwen/Qwen2.5-72B-Instruct"

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

from backend.core.llm_config import get_llm_config, LLMConfigManager
from backend.core.openai_client_adapter import OpenAIChatCompletionClient
from autogen_core.models import UserMessage, SystemMessage

def test_full_fallback_chain():
    logger.info("======================================================================")
    logger.info("TESTING HUGGING FACE -> GROQ -> GEMINI FALLBACK CHAIN")
    logger.info("======================================================================")
    
    # Reset LLM config manager singleton state
    import backend.core.llm_config as lc
    lc._llm_config_manager = None
    
    manager = get_llm_config()
    logger.info(f"Initial provider: {manager.current_provider}")
    assert manager.current_provider == "huggingface", f"Expected 'huggingface', got {manager.current_provider}"
    
    # 1. Simulate Hugging Face failure (e.g. connection refused)
    logger.info("\n--- Simulating Hugging Face failure ---")
    err = ConnectionError("Failed to establish a new connection: [Errno 111] Connection refused")
    next_config = manager.get_next_fallback_config(err)
    
    logger.info(f"Next provider config: {next_config['provider']} (model: {next_config['model']})")
    assert manager.current_provider == "groq", f"Expected 'groq', got {manager.current_provider}"
    assert next_config["provider"] == "groq"
    
    # 2. Simulate Groq failure (e.g. rate limit 429)
    logger.info("\n--- Simulating Groq failure ---")
    err_groq = Exception("Error code: 429 - Rate limit reached")
    next_config_2 = manager.get_next_fallback_config(err_groq)
    
    logger.info(f"Next provider config: {next_config_2['provider']} (model: {next_config_2['model']})")
    assert manager.current_provider == "gemini", f"Expected 'gemini', got {manager.current_provider}"
    assert next_config_2["provider"] == "gemini"
    
    # 3. Simulate Gemini failure (no more fallback)
    logger.info("\n--- Simulating Gemini failure ---")
    err_gemini = Exception("Error code: 503 - Service Unavailable")
    next_config_3 = manager.get_next_fallback_config(err_gemini)
    
    logger.info(f"Next provider config: {next_config_3}")
    assert next_config_3 is None, "Expected None (no more fallbacks)"
    
    logger.info("\n✅ FALLBACK CHAIN DIAGNOSTICS PASSED")

if __name__ == "__main__":
    test_full_fallback_chain()
