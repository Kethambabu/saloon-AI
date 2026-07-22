"""
Centralized LLM Configuration Management with Gemini Fallback.
Handles Groq API with automatic fallback to Google Gemini on rate limits.
"""

import os
import logging
from typing import Optional, Dict, Any, Tuple, List
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
def get_hf_base_url() -> str:
    return get_settings().huggingface_api_base_url

def get_hf_model() -> str:
    return get_settings().huggingface_model

def is_hf_enabled() -> bool:
    return get_settings().huggingface_enabled

def get_hf_api_key() -> str:
    s = get_settings()
    return s.huggingface_api_key or os.environ.get("HUGGINGFACE_API_KEY") or os.environ.get("HF_TOKEN", "")

HUGGINGFACE_API_BASE_URL = get_settings().huggingface_api_base_url
HUGGINGFACE_MODEL = get_settings().huggingface_model
HUGGINGFACE_ENABLED = get_settings().huggingface_enabled
HUGGINGFACE_API_KEY = get_settings().huggingface_api_key or os.environ.get("HUGGINGFACE_API_KEY") or os.environ.get("HF_TOKEN", "")

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
    _cooldowns: Dict[str, float] = {}
    _groq_keys: List[str] = []
    _gemini_keys: List[str] = []
    _huggingface_keys: List[str] = []
    _current_groq_idx: int = 0
    _current_gemini_idx: int = 0
    _current_huggingface_idx: int = 0
    _exhausted_providers: set = set()  # Providers with daily quota = 0, skip until server restart

    @classmethod
    def rotate_key(cls, provider: str) -> str:
        """Rotate to the next API key in the pool for the provider."""
        if provider == "groq" and cls._groq_keys:
            cls._current_groq_idx = (cls._current_groq_idx + 1) % len(cls._groq_keys)
            new_key = cls._groq_keys[cls._current_groq_idx]
            logger.warning(f"🔄 [llm_config] Rotated Groq API key to next in pool (index {cls._current_groq_idx}/{len(cls._groq_keys)}).")
            return new_key
        elif provider == "gemini" and cls._gemini_keys:
            cls._current_gemini_idx = (cls._current_gemini_idx + 1) % len(cls._gemini_keys)
            new_key = cls._gemini_keys[cls._current_gemini_idx]
            logger.warning(f"🔄 [llm_config] Rotated Gemini API key to next in pool (index {cls._current_gemini_idx}/{len(cls._gemini_keys)}).")
            return new_key
        elif provider == "huggingface" and cls._huggingface_keys:
            cls._current_huggingface_idx = (cls._current_huggingface_idx + 1) % len(cls._huggingface_keys)
            new_key = cls._huggingface_keys[cls._current_huggingface_idx]
            logger.warning(f"🔄 [llm_config] Rotated Hugging Face API key to next in pool (index {cls._current_huggingface_idx}/{len(cls._huggingface_keys)}).")
            return new_key
        return ""

    @property
    def current_groq_key(self) -> str:
        if not self.__class__._groq_keys:
            return self.api_key
        return self.__class__._groq_keys[self.__class__._current_groq_idx]

    @property
    def current_gemini_key(self) -> str:
        if not self.__class__._gemini_keys:
            return self.gemini_api_key
        return self.__class__._gemini_keys[self.__class__._current_gemini_idx]

    @property
    def current_huggingface_key(self) -> str:
        if not self.__class__._huggingface_keys:
            return HUGGINGFACE_API_KEY
        return self.__class__._huggingface_keys[self.__class__._current_huggingface_idx]

    @classmethod
    def set_cooldown(cls, provider: str, model: str, duration: float):
        """Set a cooldown for a specific provider and model."""
        import time
        cls._cooldowns[f"{provider}:{model}"] = time.time() + duration
        logger.warning(f"🔒 [llm_config] Model '{model}' on '{provider}' put on cooldown for {duration}s.")

    @classmethod
    def is_on_cooldown(cls, provider: str, model: str) -> bool:
        """Check if a model is currently on cooldown."""
        import time
        key = f"{provider}:{model}"
        if key in cls._cooldowns:
            if time.time() < cls._cooldowns[key]:
                return True
            else:
                del cls._cooldowns[key]
        return False
    
    def __init__(self):
        """Initialize LLM configuration manager."""
        self.settings = get_settings()
        # Determine primary provider based on environment
        self.huggingface_available = is_hf_enabled()
        if self.huggingface_available:
            self.current_provider = "huggingface"
            self.primary_model = get_hf_model()
            self.base_url = get_hf_base_url()
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
        
        # Scan env files for all keys
        self.__class__._groq_keys, self.__class__._gemini_keys, self.__class__._huggingface_keys = self._extract_keys_from_env()
        # Ensure default keys are in the pool if not already there
        if self.api_key and self.api_key.strip() and self.api_key != "your-groq-key-here" and self.api_key not in self.__class__._groq_keys:
            self.__class__._groq_keys.append(self.api_key)
        if self.gemini_api_key and self.gemini_api_key.strip() and self.gemini_api_key != "your-gemini-key-here" and self.gemini_api_key not in self.__class__._gemini_keys:
            self.__class__._gemini_keys.append(self.gemini_api_key)
        if HUGGINGFACE_API_KEY and HUGGINGFACE_API_KEY.strip() and HUGGINGFACE_API_KEY not in self.__class__._huggingface_keys:
            self.__class__._huggingface_keys.append(HUGGINGFACE_API_KEY)
            
        # Override availability if pool keys exist
        if self.__class__._gemini_keys:
            self.gemini_available = True
            
        logger.info(f"🔑 [llm_config] Loaded {len(self.__class__._groq_keys)} Groq keys, {len(self.__class__._gemini_keys)} Gemini keys, and {len(self.__class__._huggingface_keys)} Hugging Face keys from env.")
        logger.info(f"LLM Config initialized: provider={self.current_provider}, primary={self.primary_model}, fallback={self.fallback_model}, gemini={self.gemini_available}")

    def _extract_keys_from_env(self) -> Tuple[List[str], List[str], List[str]]:
        """Extract main and pool API keys for each provider."""
        from dotenv import dotenv_values, find_dotenv
        env_dict = dict(os.environ)
        try:
            dot_path = find_dotenv(usecwd=True)
            if dot_path:
                env_dict.update({k: v for k, v in dotenv_values(dot_path).items() if v is not None})
        except Exception:
            pass

        groq_keys = []
        main_groq = self.settings.groq_api_key or env_dict.get("GROQ_API_KEY", "")
        if main_groq and main_groq.strip() and main_groq != "your-groq-key-here":
            groq_keys.append(main_groq.strip())
        for k, v in env_dict.items():
            if k.startswith("GROQ_API_KEY_POOL_") and v and v.strip() and v.strip() not in groq_keys:
                groq_keys.append(v.strip())

        gemini_keys = []
        main_gemini = self.settings.gemini_api_key or self.settings.google_api_key or env_dict.get("GEMINI_API_KEY") or env_dict.get("GOOGLE_API_KEY", "")
        if main_gemini and main_gemini.strip() and main_gemini != "your-gemini-key-here":
            gemini_keys.append(main_gemini.strip())
        for k, v in env_dict.items():
            if k.startswith("GEMINI_API_KEY_POOL_") and v and v.strip() and v.strip() not in gemini_keys:
                gemini_keys.append(v.strip())

        huggingface_keys = []
        main_hf = self.settings.huggingface_api_key or env_dict.get("HUGGINGFACE_API_KEY") or env_dict.get("HF_TOKEN", "")
        if main_hf and main_hf.strip() and main_hf != "your-huggingface-key-here":
            huggingface_keys.append(main_hf.strip())
        for k, v in env_dict.items():
            if k.startswith("HUGGINGFACE_API_KEY_POOL_") and v and v.strip() and v.strip() not in huggingface_keys:
                huggingface_keys.append(v.strip())

        return groq_keys, gemini_keys, huggingface_keys
    
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
        if is_hf_enabled():
            model = get_hf_model() if not use_fallback else self.fallback_model
            api_key = self.current_huggingface_key or get_hf_api_key() or "huggingface"
            base_url = get_hf_base_url()
            provider = "huggingface"
        elif self.current_provider == "huggingface":
            model = self.primary_model if not use_fallback else self.fallback_model
            api_key = self.current_huggingface_key or get_hf_api_key() or "huggingface"
            base_url = self.base_url
            provider = "huggingface"
        else:
            model = self.fallback_model if use_fallback else self.primary_model
            api_key = self.current_groq_key
            base_url = self.base_url
            provider = self.current_provider

        return {
            "model": model,
            "api_key": api_key,
            "base_url": base_url,
            "model_info": get_model_info_dict(model),
            "provider": provider,
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
    
    def get_provider_chain(self, skip_cooldowns: bool = True) -> list:
        """
        Return a fresh, ordered list of provider configuration dicts for the
        current request.  Order: Hugging Face -> Groq (primary) -> Groq (fallback) -> Gemini.
        This is called once per request so the singleton's state is NEVER mutated
        permanently; Hugging Face will always be tried first on the next request.

        Returns:
            List of dicts with keys: provider, model, api_key, base_url, model_info
        """
        raw_chain: list = []

        # --- Tier 1: Hugging Face model ---
        if is_hf_enabled():
            hf_model = get_hf_model()
            raw_chain.append({
                "provider": "huggingface",
                "model": hf_model,
                "api_key": self.current_huggingface_key or get_hf_api_key() or "huggingface",
                "base_url": get_hf_base_url(),
                "model_info": {
                    "vision": False,
                    "function_calling": True,
                    "json_output": True,
                    "family": "qwen" if "qwen" in hf_model.lower() else "llama-3.3" if "llama" in hf_model.lower() else "unknown",
                    "structured_output": False,
                },
            })

        # --- Tier 2: Groq primary (llama-3.3-70b-versatile) ---
        groq_key = self.current_groq_key
        if groq_key and groq_key.strip() and groq_key != "your-groq-key-here":
            raw_chain.append({
                "provider": "groq",
                "model": DEFAULT_PRIMARY_MODEL,
                "api_key": groq_key,
                "base_url": GROQ_API_BASE_URL,
                "model_info": get_model_info_dict(DEFAULT_PRIMARY_MODEL),
            })
            # --- Tier 3: Groq fallback (llama-3.1-8b-instant) ---
            raw_chain.append({
                "provider": "groq",
                "model": DEFAULT_FALLBACK_MODEL,
                "api_key": groq_key,
                "base_url": GROQ_API_BASE_URL,
                "model_info": get_model_info_dict(DEFAULT_FALLBACK_MODEL),
            })

        # --- Tier 4: Gemini ---
        gemini_key = self.current_gemini_key
        if gemini_key and gemini_key.strip() and gemini_key != "your-gemini-key-here":
            raw_chain.append({
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

        if not skip_cooldowns:
            return raw_chain

        # Filter out providers that are both on cooldown OR have hit daily quota exhaustion
        active_chain = [
            cfg for cfg in raw_chain
            if not self.is_on_cooldown(cfg["provider"], cfg["model"])
            and cfg["provider"] not in self.__class__._exhausted_providers
        ]
        
        # If all configured providers are on cooldown, reset cooldowns to avoid a complete failure
        if not active_chain and raw_chain:
            logger.warning("⚠️ All configured LLM providers are on cooldown. Resetting cooldowns to retry.")
            for cfg in raw_chain:
                key = f"{cfg['provider']}:{cfg['model']}"
                self._cooldowns.pop(key, None)
            # Still respect daily-exhausted providers even after cooldown reset
            active_chain = [cfg for cfg in raw_chain if cfg["provider"] not in self.__class__._exhausted_providers]
            if not active_chain:
                active_chain = raw_chain  # Last resort: try everything

        return active_chain

    def get_next_fallback_config(self, error: Exception) -> Optional[Dict[str, Any]]:
        """
        Return the configuration for the next fallback provider in the chain
        (Hugging Face -> Groq -> Gemini) without mutating singleton state.

        This is STATELESS per-request: it reads self.current_provider to determine
        the current fallback position, but does NOT permanently mutate it. This
        ensures each new request always starts from the top of the provider chain.

        Args:
            error: The exception that triggered the fallback.

        Returns:
            Dictionary with next configuration or None.
        """
        logger.warning("🚨 Provider error or rate limit detected on '%s': %s", self.current_provider, str(error)[:150])

        # Build a stateless fallback sequence based on current position
        _current = self.current_provider
        groq_key = self.settings.groq_api_key or os.environ.get("GROQ_API_KEY", "")
        has_groq = bool(groq_key and groq_key.strip() and groq_key != "your-groq-key-here")
        
        # Check if the error is a hard daily-quota exhaustion (limit: 0)
        err_str = str(error)
        is_daily_exhausted = "limit: 0" in err_str or ("quota exceeded" in err_str.lower() and "per_day" in err_str.lower())
        if is_daily_exhausted:
            self.__class__._exhausted_providers.add(_current)
            logger.warning(f"🚫 [{_current}] Daily quota exhausted — marking as skip-provider for this session.")

        if _current == "huggingface":
            logger.info("🔄 Falling back from Hugging Face → Groq for THIS request.")
            if has_groq and "groq" not in self.__class__._exhausted_providers:
                return {
                    "provider": "groq",
                    "model": DEFAULT_PRIMARY_MODEL,
                    "api_key": groq_key,
                    "base_url": GROQ_API_BASE_URL,
                    "model_info": get_model_info_dict(DEFAULT_PRIMARY_MODEL),
                }
            logger.warning("⚠️ No Groq key available or Groq daily-exhausted, skipping Groq tier.")
            # Fall through to Gemini

        if _current in ("huggingface", "groq"):
            if self.gemini_available and "gemini" not in self.__class__._exhausted_providers:
                logger.info("🔄 Falling back → Gemini for THIS request.")
                return {
                    "model": GEMINI_MODEL,
                    "api_key": self.current_gemini_key,
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
                logger.error("❌ Gemini fallback not available or daily-exhausted — no further fallback.")
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
                "api_key": self.current_gemini_key,
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

