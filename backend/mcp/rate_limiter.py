"""
MCP Rate Limiter — Per-role request throttling.

Customer:  100 requests/hour
Staff:     500 requests/hour
Admin:     unlimited

Implemented as a sliding window counter using in-memory storage.
Thread-safe via threading.Lock.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rate limit configuration per role
# ---------------------------------------------------------------------------

RATE_LIMITS: Dict[str, Optional[int]] = {
    "CUSTOMER": 100,   # requests per hour
    "STAFF": 500,      # requests per hour
    "ADMIN": None,     # unlimited
    "MANAGER": None,   # unlimited
    "OWNER": None,     # unlimited
}

_WINDOW_SECONDS = 3600  # 1 hour sliding window


class RateLimitExceeded(Exception):
    """Raised when a caller exceeds their allowed request rate."""
    def __init__(self, role: str, limit: int, reset_in: int):
        self.role = role
        self.limit = limit
        self.reset_in = reset_in
        super().__init__(
            f"Rate limit exceeded for role '{role}': {limit} requests/hour. "
            f"Resets in {reset_in}s."
        )


class MCPRateLimiter:
    """
    Sliding-window rate limiter for MCP requests.

    Usage::

        limiter = get_rate_limiter()
        try:
            limiter.check(user_id="u-123", role="CUSTOMER")
        except RateLimitExceeded as e:
            # Return 429 to caller
            ...
    """

    def __init__(self):
        self._lock = threading.Lock()
        # user_id -> deque of request timestamps
        self._windows: Dict[str, deque] = defaultdict(deque)

    def check(self, user_id: str, role: str) -> Tuple[int, int]:
        """
        Check if user is within rate limits. Raises RateLimitExceeded if not.

        Returns (requests_made, requests_remaining) tuple.
        """
        role_upper = role.upper()
        limit = RATE_LIMITS.get(role_upper)

        # Unlimited roles
        if limit is None:
            return (0, 999999)

        now = time.time()
        window_start = now - _WINDOW_SECONDS

        with self._lock:
            q = self._windows[user_id]

            # Evict timestamps outside the window
            while q and q[0] < window_start:
                q.popleft()

            requests_made = len(q)
            remaining = limit - requests_made

            if requests_made >= limit:
                # When will the oldest request fall out of the window?
                oldest = q[0] if q else now
                reset_in = int((oldest + _WINDOW_SECONDS) - now) + 1
                logger.warning(
                    "[RateLimiter] user=%s role=%s BLOCKED (%d/%d reqs). Reset in %ds",
                    user_id, role_upper, requests_made, limit, reset_in
                )
                raise RateLimitExceeded(role=role_upper, limit=limit, reset_in=reset_in)

            # Record this request
            q.append(now)
            logger.debug(
                "[RateLimiter] user=%s role=%s %d/%d requests used",
                user_id, role_upper, requests_made + 1, limit
            )
            return (requests_made + 1, remaining - 1)

    def get_status(self, user_id: str, role: str) -> Dict:
        """Return current usage status without incrementing counter."""
        role_upper = role.upper()
        limit = RATE_LIMITS.get(role_upper)

        if limit is None:
            return {"role": role_upper, "limit": "unlimited", "used": 0, "remaining": 999999}

        now = time.time()
        window_start = now - _WINDOW_SECONDS

        with self._lock:
            q = self._windows.get(user_id, deque())
            recent = sum(1 for t in q if t >= window_start)
            return {
                "role": role_upper,
                "limit": limit,
                "used": recent,
                "remaining": max(0, limit - recent),
                "window_seconds": _WINDOW_SECONDS,
            }

    def reset(self, user_id: str) -> None:
        """Reset rate limit counter for a user (admin action)."""
        with self._lock:
            self._windows[user_id] = deque()


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_limiter: Optional[MCPRateLimiter] = None


def get_rate_limiter() -> MCPRateLimiter:
    """Return the shared MCPRateLimiter singleton."""
    global _limiter
    if _limiter is None:
        _limiter = MCPRateLimiter()
    return _limiter

