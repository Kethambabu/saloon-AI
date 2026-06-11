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

# ============================================================================
# HUGGING FACE PROVIDER CONFIGURATION
# ============================================================================
_settings = get_settings()
HUGGINGFACE_API_BASE_URL = _settings.huggingface_api_base_url
HUGGINGFACE_MODEL = _settings.huggingface_model
HUGGINGFACE_ENABLED = _settings.huggingface_enabled
HUGGINGFACE_API_KEY = _settings.huggingface_api_key or os.environ.get("HUGGINGFACE_API_KEY") or os.environ.get("HF_TOKEN", "")

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
        # Determine primary provider based on environment
        self.huggingface_available = HUGGINGFACE_ENABLED
        if self.huggingface_available:
            self.current_provider = "huggingface"
            self.primary_model = HUGGINGFACE_MODEL
            self.base_url = HUGGINGFACE_API_BASE_URL
        else:
            self.current_provider = "groq"
            self.primary_model = self._get_primary_model()
            self.base_url = GROQ_API_BASE_URL
        self.fallback_model = DEFAULT_FALLBACK_MODEL
        self.api_key = self._get_api_key()
        self.is_mock_mode = False
        
        # Check for Gemini availability
        self.gemini_available = check_gemini_key_available()
        self.gemini_api_key = self.settings.gemini_api_key or self.settings.google_api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")
        
        logger.info(f"LLM Config initialized: provider={self.current_provider}, primary={self.primary_model}, fallback={self.fallback_model}, gemini={self.gemini_available}")
    
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
        Get complete LLM configuration for the current provider.

        Args:
            use_fallback: If True, use fallback model (Groq fallback or Gemini) instead of primary.

        Returns:
            Dictionary with 'model', 'api_key', 'base_url', 'model_info', 'provider'.
        """
        if self.current_provider == "huggingface":
            model = self.primary_model if not use_fallback else self.fallback_model
            api_key = HUGGINGFACE_API_KEY or "huggingface"
        else:
            model = self.fallback_model if use_fallback else self.primary_model
            api_key = self.api_key

        return {
            "model": model,
            "api_key": api_key,
            "base_url": self.base_url,
            "model_info": get_model_info_dict(model),
            "provider": self.current_provider,
        }
    
    @staticmethod
    def detect_rate_limit_error(error: Exception) -> bool:
        """Detect if error is a Groq rate limit (HTTP 429) or a tool calling error (tool_use_failed)."""
        error_str = str(error)
        is_rate_limit = "429" in error_str or "rate_limit" in error_str.lower() or "Rate limit reached" in error_str
        is_tool_failure = "tool_use_failed" in error_str or "failed_generation" in error_str.lower() or "failed to call a function" in error_str.lower()
        return is_rate_limit or is_tool_failure
    
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
    
    def get_provider_chain(self) -> list:
        """
        Return a fresh, ordered list of provider configuration dicts for the
        current request.  Order: Hugging Face -> Groq (primary) -> Groq (fallback) -> Gemini.
        This is called once per request so the singleton's state is NEVER mutated
        permanently; Hugging Face will always be tried first on the next request.

        Returns:
            List of dicts with keys: provider, model, api_key, base_url, model_info
        """
        chain: list = []

        # --- Tier 1: Hugging Face model ---
        if HUGGINGFACE_ENABLED:
            chain.append({
                "provider": "huggingface",
                "model": HUGGINGFACE_MODEL,
                "api_key": HUGGINGFACE_API_KEY or "huggingface",
                "base_url": HUGGINGFACE_API_BASE_URL,
                "model_info": {
                    "vision": False,
                    "function_calling": True,
                    "json_output": True,
                    "family": "qwen" if "qwen" in HUGGINGFACE_MODEL.lower() else "llama-3.3" if "llama" in HUGGINGFACE_MODEL.lower() else "unknown",
                    "structured_output": False,
                },
            })

        # --- Tier 2: Groq primary (llama-3.3-70b-versatile) ---
        groq_key = self.settings.groq_api_key or os.environ.get("GROQ_API_KEY", "")
        if groq_key and groq_key.strip() and groq_key != "your-groq-key-here":
            chain.append({
                "provider": "groq",
                "model": DEFAULT_PRIMARY_MODEL,
                "api_key": groq_key,
                "base_url": GROQ_API_BASE_URL,
                "model_info": get_model_info_dict(DEFAULT_PRIMARY_MODEL),
            })
            # --- Tier 3: Groq fallback (llama-3.1-8b-instant) ---
            chain.append({
                "provider": "groq",
                "model": DEFAULT_FALLBACK_MODEL,
                "api_key": groq_key,
                "base_url": GROQ_API_BASE_URL,
                "model_info": get_model_info_dict(DEFAULT_FALLBACK_MODEL),
            })

        # --- Tier 4: Gemini ---
        gemini_key = (
            self.settings.gemini_api_key
            or self.settings.google_api_key
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY", "")
        )
        if gemini_key and gemini_key.strip() and gemini_key != "your-gemini-key-here":
            chain.append({
                "provider": "gemini",
                "model": GEMINI_MODEL,
                "api_key": gemini_key,
                "base_url": GEMINI_API_BASE_URL,
                "model_info": {
                    "vision": False,
                    "function_calling": True,
                    "json_output": True,
                    "family": "gemini-2.0",
                    "structured_output": False,
                },
            })

        return chain

    def get_next_fallback_config(self, error: Exception) -> Optional[Dict[str, Any]]:
        """
        Transition to the next fallback provider in the chain (Hugging Face -> Groq -> Gemini)
        and return the configuration, or None if no fallbacks remain.

        NOTE: This method intentionally does NOT mutate self.current_provider so that
        the singleton always starts fresh with Hugging Face on the next request.

        Args:
            error: The exception that triggered the fallback.

        Returns:
            Dictionary with next configuration or None.
        """
        logger.warning(f"🚨 Provider error or rate limit detected on '{self.current_provider}': {str(error)[:150]}")

        if self.current_provider == "huggingface":
            logger.info("🔄 Switching from Hugging Face to Groq fallback...")
            groq_key = self.settings.groq_api_key or os.environ.get("GROQ_API_KEY", "")
            if groq_key and groq_key.strip() and groq_key != "your-groq-key-here":
                self.current_provider = "groq"
                return {
                    "provider": "groq",
                    "model": DEFAULT_PRIMARY_MODEL,
                    "api_key": groq_key,
                    "base_url": GROQ_API_BASE_URL,
                    "model_info": get_model_info_dict(DEFAULT_PRIMARY_MODEL),
                }
            # No Groq key → fall straight through to Gemini
            logger.warning("⚠️ No Groq key available, skipping Groq tier.")
            self.current_provider = "gemini"

        if self.current_provider == "groq":
            if self.gemini_available:
                logger.info("🔄 Switching from Groq to Gemini fallback...")
                self.current_provider = "gemini"
                return {
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
                    "provider": "gemini",
                }
            else:
                logger.error("❌ Gemini fallback is not available (API key missing).")
                return None

        # Already on Gemini — no more fallbacks
        logger.error("❌ No more fallback providers in the chain.")
        return None

    def get_config_with_fallback(self, error: Optional[Exception] = None) -> Dict[str, Any]:
        """
        Get LLM configuration with automatic fallback on rate limits/errors.
        
        Args:
            error: Optional exception to check for rate limit/provider errors.
        
        Returns:
            Dictionary with 'model', 'api_key', 'base_url', 'model_info', 'provider'.
        """
        if error:
            next_config = self.get_next_fallback_config(error)
            if next_config:
                return next_config
                
        # If Gemini was previously activated due to prior rate limits
        if LLMConfigManager.RATE_LIMIT_ACTIVE and self.gemini_available:
            return {
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
                "provider": "gemini",
            }
            
        # Default to current provider
        config = self.get_config(use_fallback=False)
        config["provider"] = self.current_provider
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
        
        # Log PRIMARY provider
        if self.current_provider == "huggingface":
            logger.info("Primary Provider: Hugging Face (API)")
            logger.info(f"Hugging Face Base URL: {self.base_url}")
            logger.info(f"Hugging Face Model: {self.primary_model}")
            primary_valid = True
        else:
            logger.info("Primary Provider: Groq (https://groq.com)")
            logger.info(f"Primary Base URL: {self.base_url}")
            logger.info(f"Primary Model: {self.primary_model}")
            primary_valid = GroqModel.validate(self.primary_model)
            
        logger.info(f"Primary Fallback: {self.fallback_model}")
        
        # Log mode
        if self.is_mock_mode:
            logger.warning("⚠️  MOCK MODE ENABLED - Using test API key for development/testing only")
        else:
            logger.info("✅ Production Mode - Using real Groq API key")
        
        # Validate Groq models
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
