"""
Centralized LLM Configuration Management for Groq API.
Handles model validation, fallback logic, and startup diagnostics.
"""

import os
import logging
from typing import Optional, Dict, Any
from enum import Enum

from core.config import get_settings

logger = logging.getLogger(__name__)

# ============================================================================
# GROQ SUPPORTED MODELS - Keep updated with Groq's available models
# https://console.groq.com/docs/models
# ============================================================================

class GroqModel(str, Enum):
    """Valid Groq models available in the API."""
    # Latest stable models (recommended)
    LLAMA_3_3_70B_VERSATILE = "llama-3.3-70b-versatile"  # PRIMARY - Best balance
    LLAMA_3_1_8B_INSTANT = "llama-3.1-8b-instant"  # FALLBACK - Fast, lightweight
    MIXTRAL_8X7B = "mixtral-8x7b-32768"  # ALTERNATIVE - Good reasoning
    
    # Latest Llama 3.1 variants
    LLAMA_3_1_70B = "llama-3.1-70b-versatile"  # Stable variant
    
    @staticmethod
    def validate(model: str) -> bool:
        """Check if model is valid and currently supported."""
        valid_models = {m.value for m in GroqModel}
        return model in valid_models
    
    @staticmethod
    def list_supported() -> list:
        """Return list of all supported models."""
        return [m.value for m in GroqModel]


# ============================================================================
# LLM CONFIGURATION CONSTANTS
# ============================================================================

DEFAULT_PRIMARY_MODEL = GroqModel.LLAMA_3_3_70B_VERSATILE.value
DEFAULT_FALLBACK_MODEL = GroqModel.LLAMA_3_1_8B_INSTANT.value
GROQ_API_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_TIMEOUT_SECONDS = 30


# ============================================================================
# MODEL INFO DICTIONARY FOR AUTOGEN
# ============================================================================

def get_model_info_dict(model: str) -> Dict[str, Any]:
    """
    Returns model capability information for AutoGen.
    
    Args:
        model: Model identifier (e.g., "llama-3.3-70b-versatile")
    
    Returns:
        Dictionary with vision, function_calling, json_output capabilities
    """
    return {
        "vision": False,
        "function_calling": True,
        "json_output": True,
        "family": "llama-3.3-70b" if "3.3" in model else "llama-3.1",
        "structured_output": False,
    }


# ============================================================================
# LLM CONFIGURATION VALIDATOR & SELECTOR
# ============================================================================

class LLMConfigManager:
    """
    Centralized manager for LLM configuration with validation and fallback.
    Handles model selection, startup validation, and graceful degradation.
    """
    
    def __init__(self):
        """Initialize LLM configuration manager."""
        self.settings = get_settings()
        self.primary_model = self._get_primary_model()
        self.fallback_model = DEFAULT_FALLBACK_MODEL
        self.api_key = self._get_api_key()
        self.base_url = GROQ_API_BASE_URL
        self.is_mock_mode = False
        
        logger.info(f"LLM Config initialized: primary={self.primary_model}, fallback={self.fallback_model}")
    
    def _get_api_key(self) -> str:
        """Get Groq API key from settings or environment."""
        key = self.settings.groq_api_key or os.environ.get("GROQ_API_KEY", "")
        if not key or key == "your-groq-key-here":
            logger.warning("⚠️  GROQ_API_KEY not set - using mock mode for testing")
            self.is_mock_mode = True
            return "mock-groq-key-for-testing"
        return key
    
    def _get_primary_model(self) -> str:
        """
        Determine primary model from environment or use default.
        Validates that the model is supported.
        """
        model = os.environ.get("GROQ_MODEL", DEFAULT_PRIMARY_MODEL)
        
        if not GroqModel.validate(model):
            logger.warning(
                f"⚠️  Model '{model}' not supported. Falling back to '{DEFAULT_PRIMARY_MODEL}'. "
                f"Supported models: {', '.join(GroqModel.list_supported())}"
            )
            return DEFAULT_PRIMARY_MODEL
        
        return model
    
    def get_config(self, use_fallback: bool = False) -> Dict[str, Any]:
        """
        Get complete LLM configuration for instantiating OpenAI client.
        
        Args:
            use_fallback: If True, use fallback model instead of primary
        
        Returns:
            Dictionary with 'model', 'api_key', 'base_url', 'model_info'
        """
        model = self.fallback_model if use_fallback else self.primary_model
        
        return {
            "model": model,
            "api_key": self.api_key,
            "base_url": self.base_url,
            "model_info": get_model_info_dict(model),
        }
    
    def validate_at_startup(self) -> bool:
        """
        Validate LLM configuration at application startup.
        Logs configuration details and checks model support.
        
        Returns:
            True if configuration is valid, False otherwise
        """
        logger.info("=" * 70)
        logger.info("🔧 LLM CONFIGURATION STARTUP DIAGNOSTICS")
        logger.info("=" * 70)
        
        # Log environment
        logger.info(f"Environment: {self.settings.environment}")
        logger.info(f"Debug Mode: {self.settings.debug}")
        logger.info(f"Provider: Groq (https://groq.com)")
        logger.info(f"Base URL: {self.base_url}")
        
        # Log mode
        if self.is_mock_mode:
            logger.warning("⚠️  MOCK MODE ENABLED - Using test API key for development/testing only")
        else:
            logger.info("✅ Production Mode - Using real Groq API key")
        
        # Log models
        logger.info(f"Primary Model: {self.primary_model}")
        logger.info(f"Fallback Model: {self.fallback_model}")
        
        # Validate models
        primary_valid = GroqModel.validate(self.primary_model)
        fallback_valid = GroqModel.validate(self.fallback_model)
        
        logger.info(f"Primary Valid: {'✅ Yes' if primary_valid else '❌ No'}")
        logger.info(f"Fallback Valid: {'✅ Yes' if fallback_valid else '❌ No'}")
        
        # Supported models
        logger.info(f"Supported Models: {', '.join(GroqModel.list_supported())}")
        
        logger.info("=" * 70)
        
        return primary_valid and fallback_valid
    
    def print_diagnostics(self):
        """Print detailed diagnostics for debugging (called at app startup)."""
        self.validate_at_startup()


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_llm_config_manager: Optional[LLMConfigManager] = None


def get_llm_config() -> LLMConfigManager:
    """Get or create LLM configuration manager singleton."""
    global _llm_config_manager
    if _llm_config_manager is None:
        _llm_config_manager = LLMConfigManager()
    return _llm_config_manager


def validate_llm_startup() -> bool:
    """Validate LLM configuration at application startup."""
    manager = get_llm_config()
    return manager.validate_at_startup()
