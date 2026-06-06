"""
Centralized LLM Configuration Management with Gemini Fallback.
Handles Groq API with automatic fallback to Google Gemini on rate limits.
"""

import os
import logging
from typing import Optional, Dict, Any, Tuple
from enum import Enum

from core.config import get_settings

logger = logging.getLogger(__name__)


# ============================================================================
# GOOGLE GEMINI FALLBACK PROVIDER CONFIGURATION
# ============================================================================

GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_MODEL = "gemini-2.0-flash"  # Fast, free tier available

def check_gemini_key_available() -> bool:
    """Check if Gemini API key is configured."""
    settings = get_settings()
    key = settings.gemini_api_key or settings.google_api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")
    available = bool(key and key.strip() and key != "your-gemini-key-here")
    if available:
        logger.info("✅ Gemini API key detected - fallback ready")
    return available

# ============================================================================
# GROQ SUPPORTED MODELS - Keep updated with Groq's available models
# https://console.groq.com/docs/models
# ============================================================================

class GroqModel(str, Enum):
    """Valid Groq models available in the API."""
    # Latest stable models (recommended)
    LLAMA_3_3_70B_VERSATILE = "llama-3.3-70b-versatile"  # PRIMARY - Best balance
    LLAMA_3_1_8B_INSTANT = "llama-3.1-8b-instant"  # FALLBACK - Fast, lightweight
    LLAMA_3_1_70B = "llama-3.1-70b-versatile"  # Alternative - Good for complex tasks
    
    # DEPRECATED - DO NOT USE:
    # "mixtral-8x7b-32768" - DECOMMISSIONED as of May 2026
    # Use llama-3.3-70b-versatile instead
    
    @staticmethod
    def validate(model: str) -> bool:
        """Check if model is valid and currently supported."""
        valid_models = {m.value for m in GroqModel}
        return model in valid_models
    
    @staticmethod
    def list_supported() -> list:
        """Return list of all supported models."""
        return [m.value for m in GroqModel]
    
    @staticmethod
    def is_deprecated(model: str) -> bool:
        """Check if a model has been deprecated"""
        deprecated_models = {
            "mixtral-8x7b-32768",  # Groq decommissioned this
            "llama-3.1-405b",  # Also decommissioned
            "llama-3.1-405b-reasoning",  # Decommissioned
        }
        return model in deprecated_models


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
    Supports Groq API with automatic fallback to Google Gemini on rate limits.
    Handles model selection, startup validation, and graceful degradation.
    """
    
    # Track rate limit state
    RATE_LIMIT_ACTIVE = False
    FALLBACK_PROVIDER = None  # "gemini" or "groq"
    
    def __init__(self):
        """Initialize LLM configuration manager."""
        self.settings = get_settings()
        self.primary_model = self._get_primary_model()
        self.fallback_model = DEFAULT_FALLBACK_MODEL
        self.api_key = self._get_api_key()
        self.base_url = GROQ_API_BASE_URL
        self.is_mock_mode = False
        
        # Check for Gemini availability
        self.gemini_available = check_gemini_key_available()
        self.gemini_api_key = self.settings.gemini_api_key or self.settings.google_api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")
        
        logger.info(f"LLM Config initialized: primary={self.primary_model}, fallback={self.fallback_model}, gemini={self.gemini_available}")
    
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
        Determine primary model from environment/settings or use default.
        Validates that the model is supported.
        """
        model = self.settings.groq_model or os.environ.get("GROQ_MODEL", DEFAULT_PRIMARY_MODEL)
        
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
    
    @staticmethod
    def detect_rate_limit_error(error: Exception) -> bool:
        """Detect if error is a Groq rate limit (HTTP 429) error."""
        error_str = str(error)
        return "429" in error_str or "rate_limit" in error_str.lower() or "Rate limit reached" in error_str
    
    @staticmethod
    def handle_rate_limit_error(error: Exception) -> Dict[str, Any]:
        """
        Extract rate limit information from Groq error response.
        
        Returns:
            Dictionary with 'limit', 'used', 'requested', 'retry_after'
        """
        error_str = str(error)
        try:
            # Try to extract tokens info: "Limit 100000, Used 96181, Requested 6981"
            parts = error_str.split("Limit ")
            if len(parts) > 1:
                limits_str = parts[1].split(",")[0]
                used_str = parts[1].split("Used ")[1].split(",")[0]
                requested_str = parts[1].split("Requested ")[1].split(".")[0]
                
                return {
                    "limit": int(limits_str),
                    "used": int(used_str),
                    "requested": int(requested_str),
                    "retry_after": "Check error message for retry time"
                }
        except Exception as e:
            logger.debug(f"Could not parse rate limit error details: {e}")
        
        return {"error": "Rate limit encountered", "details": error_str[:200]}
    
    @classmethod
    def switch_to_gemini_fallback(cls) -> Tuple[bool, Dict[str, Any]]:
        """
        Attempt to switch to Gemini fallback provider.
        
        Returns:
            Tuple of (success: bool, config: Dict)
        """
        logger.warning("🔄 Switching to Gemini fallback provider due to Groq rate limit...")
        
        settings = get_settings()
        gemini_key = settings.gemini_api_key or settings.google_api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")
        
        if not gemini_key or gemini_key == "your-gemini-key-here":
            logger.error("❌ Gemini API key not configured")
            return False, {}
        
        try:
            cls.RATE_LIMIT_ACTIVE = True
            cls.FALLBACK_PROVIDER = "gemini"
            
            config = {
                "model": GEMINI_MODEL,
                "api_key": gemini_key,
                "base_url": GEMINI_API_BASE_URL,
                "model_info": {
                    "vision": False,
                    "function_calling": True,
                    "json_output": True,
                    "family": "gemini-2.0",
                    "structured_output": False,
                }
            }
            
            logger.info(f"✅ Successfully switched to Gemini fallback ({GEMINI_MODEL})")
            return True, config
        
        except Exception as e:
            logger.error(f"❌ Gemini fallback error: {str(e)}")
            return False, {}
    
    def get_config_with_fallback(self, error: Optional[Exception] = None) -> Dict[str, Any]:
        """
        Get LLM configuration with automatic fallback on rate limits.
        
        Args:
            error: Optional exception to check for rate limit errors
        
        Returns:
            Dictionary with 'model', 'api_key', 'base_url', 'model_info', 'provider'
        """
        # Check if error is rate limit and try Gemini
        if error and self.detect_rate_limit_error(error):
            logger.warning(f"🚨 Rate limit detected: {str(error)[:100]}")
            
            success, gemini_config = self.switch_to_gemini_fallback()
            if success:
                gemini_config["provider"] = "gemini"
                return gemini_config
        
        # Use Gemini if rate limit was previously detected
        if LLMConfigManager.RATE_LIMIT_ACTIVE and self.gemini_available:
            config = {
                "model": GEMINI_MODEL,
                "api_key": self.gemini_api_key,
                "base_url": GEMINI_API_BASE_URL,
                "model_info": {
                    "vision": False,
                    "function_calling": True,
                    "json_output": True,
                    "family": "gemini-2.0",
                    "structured_output": False,
                },
                "provider": "gemini"
            }
            return config
        
        # Default to Groq
        config = self.get_config(use_fallback=False)
        config["provider"] = "groq"
        return config
    
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
        
        # Log PRIMARY provider (Groq)
        logger.info(f"Primary Provider: Groq (https://groq.com)")
        logger.info(f"Primary Base URL: {self.base_url}")
        logger.info(f"Primary Model: {self.primary_model}")
        logger.info(f"Primary Fallback: {self.fallback_model}")
        
        # Log mode
        if self.is_mock_mode:
            logger.warning("⚠️  MOCK MODE ENABLED - Using test API key for development/testing only")
        else:
            logger.info("✅ Production Mode - Using real Groq API key")
        
        # Validate Groq models
        primary_valid = GroqModel.validate(self.primary_model)
        fallback_valid = GroqModel.validate(self.fallback_model)
        
        logger.info(f"Primary Valid: {'✅ Yes' if primary_valid else '❌ No'}")
        logger.info(f"Fallback Valid: {'✅ Yes' if fallback_valid else '❌ No'}")
        
        # Supported Groq models
        logger.info(f"Supported Groq Models: {', '.join(GroqModel.list_supported())}")
        
        # Log FALLBACK provider (Gemini)
        logger.info("-" * 70)
        logger.info(f"Fallback Provider: Google Gemini API")
        logger.info(f"Gemini Model: {GEMINI_MODEL}")
        logger.info(f"Gemini Available: {'✅ Yes' if self.gemini_available else '❌ No'}")
        
        if not self.gemini_available:
            logger.info("💡 To enable Gemini fallback:")
            logger.info("   1. Get free API key: https://ai.google.dev")
            logger.info("   2. Set environment variable: GEMINI_API_KEY=your_key_here")
            logger.info("   3. Restart backend - system will auto-detect")
        
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
