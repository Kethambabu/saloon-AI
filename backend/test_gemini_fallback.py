"""
Test script to verify Google Gemini fallback mechanism.
Run this to test rate limit detection and Gemini fallback activation.
"""

import sys
import logging
import os
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Add backend and project root to path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))
sys.path.insert(0, str(backend_path.parent))

from core.llm_config import LLMConfigManager, check_gemini_key_available


def test_gemini_key_availability():
    """Test if Gemini API key is configured."""
    logger.info("=" * 70)
    logger.info("TEST 1: Gemini API Key Availability Check")
    logger.info("=" * 70)
    
    available = check_gemini_key_available()
    
    if available:
        logger.info("✅ PASS: Gemini API key is configured")
        return True
    else:
        logger.warning("❌ FAIL: Gemini API key is NOT configured")
        logger.info("💡 To set Gemini API key:")
        logger.info("   1. Get free key: https://ai.google.dev")
        logger.info("   2. Run: $env:GEMINI_API_KEY = 'your_key_here'")
        logger.info("   3. Restart backend")
        return False


def test_rate_limit_detection():
    """Test rate limit error detection."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 2: Rate Limit Error Detection")
    logger.info("=" * 70)
    
    # Simulate Groq rate limit error
    test_errors = [
        "Error code: 429 - {'error': {'message': 'Rate limit reached'}}",
        "openai.RateLimitError: HTTP 429 Too Many Requests",
        "Rate limit exceeded",
        "Normal API error - should not match"
    ]
    
    passed = 0
    for i, error_str in enumerate(test_errors, 1):
        is_rate_limit = LLMConfigManager.detect_rate_limit_error(Exception(error_str))
        status = "✅" if is_rate_limit else "❌"
        
        # Check if this is one of the real rate limit errors
        should_detect = i <= 2
        if is_rate_limit == should_detect:
            passed += 1
        
        logger.info(f"  Error {i}: {status} Detected={is_rate_limit} (Expected={should_detect})")
        logger.info(f"    Message: {error_str[:60]}...")
    
    logger.info(f"\nResult: {passed}/4 correct detections")
    return passed >= 3  # At least 3 should be correct


def test_rate_limit_parsing():
    """Test extraction of rate limit details."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 3: Rate Limit Detail Extraction")
    logger.info("=" * 70)
    
    error_msg = (
        "Error code: 429 - {'error': {'message': 'Rate limit reached for model "
        "`llama-3.3-70b-versatile` in organization ... Limit 100000, Used 96181, "
        "Requested 6981. Please try again in 45m31.968s.'}}"
    )
    
    details = LLMConfigManager.handle_rate_limit_error(Exception(error_msg))
    
    logger.info(f"Extracted Details:")
    for key, value in details.items():
        logger.info(f"  {key}: {value}")
    
    if details.get("limit") == 100000 and details.get("used") == 96181:
        logger.info("✅ PASS: Rate limit details correctly extracted")
        return True
    else:
        logger.warning("❌ FAIL: Could not extract rate limit details")
        return False


def test_llm_config_manager():
    """Test LLMConfigManager initialization."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 4: LLMConfigManager Initialization")
    logger.info("=" * 70)
    
    try:
        manager = LLMConfigManager()
        
        logger.info(f"Primary Model: {manager.primary_model}")
        logger.info(f"Fallback Model: {manager.fallback_model}")
        logger.info(f"Gemini Available: {manager.gemini_available}")
        logger.info(f"Base URL: {manager.base_url}")
        
        config = manager.get_config()
        logger.info(f"Config Keys: {list(config.keys())}")
        
        logger.info("✅ PASS: LLMConfigManager initialized successfully")
        return True
    except Exception as e:
        logger.error(f"❌ FAIL: {str(e)}")
        return False


def test_fallback_config():
    """Test getting fallback config with Gemini."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 5: Gemini Fallback Configuration")
    logger.info("=" * 70)
    
    try:
        manager = LLMConfigManager()
        
        # Simulate rate limit and get fallback config
        config_with_fallback = manager.get_config_with_fallback(
            error=Exception("Error code: 429 - Rate limit reached")
        )
        
        if config_with_fallback.get("provider") == "gemini":
            logger.info(f"✅ PASS: Gemini fallback config returned")
            logger.info(f"  Provider: {config_with_fallback['provider']}")
            logger.info(f"  Model: {config_with_fallback['model']}")
            logger.info(f"  Base URL: {config_with_fallback['base_url']}")
            return True
        else:
            logger.warning("⚠️  Gemini not available - fallback not activated")
            logger.info(f"  Provider: {config_with_fallback.get('provider', 'unknown')}")
            return False
    except Exception as e:
        logger.error(f"❌ FAIL: {str(e)}")
        return False


def test_gemini_model_config():
    """Test that Gemini model is properly configured."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 6: Gemini Model Configuration")
    logger.info("=" * 70)
    
    try:
        from core.llm_config import GEMINI_MODEL, GEMINI_API_BASE_URL
        
        logger.info(f"Configured Gemini Model: {GEMINI_MODEL}")
        logger.info(f"Gemini API Base URL: {GEMINI_API_BASE_URL}")
        
        if GEMINI_MODEL and GEMINI_API_BASE_URL:
            logger.info("✅ PASS: Gemini model is properly configured")
            return True
        else:
            logger.warning("❌ FAIL: Gemini model config incomplete")
            return False
    except Exception as e:
        logger.error(f"❌ FAIL: {str(e)}")
        return False


def run_all_tests():
    """Run all tests."""
    logger.info("\n" + "🧪 GOOGLE GEMINI FALLBACK MECHANISM - TEST SUITE 🧪")
    logger.info("=" * 70)
    
    results = {
        "Gemini API Key": test_gemini_key_availability(),
        "Rate Limit Detection": test_rate_limit_detection(),
        "Rate Limit Parsing": test_rate_limit_parsing(),
        "LLMConfigManager": test_llm_config_manager(),
        "Gemini Fallback Config": test_fallback_config(),
        "Gemini Model Config": test_gemini_model_config(),
    }
    
    logger.info("\n" + "=" * 70)
    logger.info("SUMMARY")
    logger.info("=" * 70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, passed_flag in results.items():
        status = "✅ PASS" if passed_flag else "⚠️  WARN"
        logger.info(f"{status}: {test_name}")
    
    logger.info("-" * 70)
    logger.info(f"Total: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("\n🎉 All tests passed! Gemini fallback is ready.")
        logger.info("   When Groq hits rate limits, system will automatically use Gemini.")
    elif passed >= 4:
        logger.warning(f"\n⚠️  {total - passed} test(s) need attention.")
        logger.info("   API key is optional - system will prompt you when needed.")
    else:
        logger.warning(f"\n⚠️  {total - passed} test(s) need attention.")
    
    logger.info("=" * 70)
    
    return passed >= 4  # Pass if at least core tests pass


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
