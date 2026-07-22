"""
Error Recovery Service — Phase 2 Architecture.

Provides error recovery, exception masking, and automatic retry wrappers.
Guarantees that customers never see stack traces, SQL errors, or internal exceptions.
"""

from __future__ import annotations

import logging
import time
import functools
from typing import Callable, Any, Dict, Optional, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar('F', bound=Callable[..., Any])

FRIENDLY_ERROR_MESSAGE = (
    "I'm sorry, I ran into a temporary hiccup while processing your request. "
    "Please try again or let me know if you'd like to check another time slot or service."
)

FRIENDLY_BOOKING_ERROR = (
    "I'm sorry, I was unable to complete your booking at this moment due to a scheduling constraint. "
    "Would you like me to check available slots for another time or with another stylist?"
)


class ErrorRecoveryService:
    """
    Error recovery engine ensuring zero technical leakage to end users.
    """

    @staticmethod
    def mask_error(error_or_exc: Any, custom_context: Optional[str] = None) -> str:
        """
        Convert technical exception or error string into a customer-friendly response.
        Logs full technical details internally.
        """
        logger.error(f"[ErrorRecoveryService] Internal error caught ({custom_context or 'General'}): {error_or_exc}")
        
        err_str = str(error_or_exc).lower()

        # Check for specific expected validation messages that ARE user-facing
        known_user_messages = [
            "on leave",
            "already passed",
            "future dates",
            "maximum limit",
            "business hours",
            "duplicate appointment",
            "already booked",
            "not found",
            "unavailable",
            "invalid date",
            "inactive",
        ]

        for known in known_user_messages:
            if known in err_str:
                return str(error_or_exc)

        # If it's a raw technical error (SQL, AttributeError, TypeError, etc.), sanitize it
        if any(tech in err_str for tech in ["traceback", "typeerror", "valueerror", "sqlalchemy", "operationalerror", "syntaxerror", "attributeerror", "keyerror", "none_type"]):
            return FRIENDLY_ERROR_MESSAGE

        return FRIENDLY_ERROR_MESSAGE

    @staticmethod
    def retry_with_fallback(
        func: Callable[..., Any],
        max_attempts: int = 3,
        delay_seconds: float = 0.2,
        fallback_return: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Executes a function with retry logic.
        """
        last_exception = None
        for attempt in range(1, max_attempts + 1):
            try:
                return func()
            except Exception as exc:
                last_exception = exc
                logger.warning(f"[ErrorRecoveryService] Attempt {attempt}/{max_attempts} failed: {exc}")
                if attempt < max_attempts:
                    time.sleep(delay_seconds)

        logger.error(f"[ErrorRecoveryService] All {max_attempts} attempts failed. Last error: {last_exception}")
        if fallback_return is not None:
            return fallback_return

        return {
            "success": False,
            "error": FRIENDLY_ERROR_MESSAGE,
            "internal_error_logged": True
        }
