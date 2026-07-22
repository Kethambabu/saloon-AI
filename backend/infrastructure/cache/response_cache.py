"""
core/response_cache.py
======================
Lightweight in-memory response cache for deterministic, read-only salon queries.
Eliminates redundant LLM and DB calls for repeated reads (availability, services, staff).

Usage:
    from infrastructure.cache.response_cache import response_cache
    cached = response_cache.get("availability:branch-id:2026-06-20")
    if cached is None:
        result = expensive_compute()
        response_cache.set("availability:branch-id:2026-06-20", result, ttl=120)
"""

from __future__ import annotations

import time
import threading
import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class ResponseCache:
    """
    Thread-safe, TTL-based in-memory cache.
    Keys are strings; values are any JSON-serializable objects.
    Expired entries are lazily evicted on access.
    """

    def __init__(self, default_ttl: int = 120, max_size: int = 500) -> None:
        """
        Args:
            default_ttl: Default time-to-live in seconds.
            max_size: Maximum number of entries before LRU eviction.
        """
        self._store: Dict[str, Tuple[Any, float]] = {}  # key -> (value, expiry_ts)
        self._lock = threading.RLock()
        self.default_ttl = default_ttl
        self.max_size = max_size
        self._hits = 0
        self._misses = 0

    # ------------------------------------------------------------------
    def get(self, key: str) -> Optional[Any]:
        """Return cached value or None if missing/expired."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None
            value, expiry = entry
            if time.time() > expiry:
                del self._store[key]
                self._misses += 1
                return None
            self._hits += 1
            return value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Store value with TTL (seconds). Evicts oldest entry when full."""
        ttl = ttl if ttl is not None else self.default_ttl
        expiry = time.time() + ttl
        with self._lock:
            if len(self._store) >= self.max_size and key not in self._store:
                # Evict the oldest (earliest expiry) entry
                oldest_key = min(self._store, key=lambda k: self._store[k][1])
                del self._store[oldest_key]
            self._store[key] = (value, expiry)

    def invalidate(self, key: str) -> bool:
        """Explicitly remove a key. Returns True if key existed."""
        with self._lock:
            return self._store.pop(key, None) is not None

    def invalidate_prefix(self, prefix: str) -> int:
        """Invalidate all keys that start with prefix. Returns count removed."""
        with self._lock:
            keys = [k for k in self._store if k.startswith(prefix)]
            for k in keys:
                del self._store[k]
            return len(keys)

    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._store.clear()

    def stats(self) -> Dict[str, Any]:
        """Return cache performance statistics."""
        total = self._hits + self._misses
        hit_rate = round(self._hits / total * 100, 1) if total > 0 else 0.0
        with self._lock:
            size = len(self._store)
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate_pct": hit_rate,
            "size": size,
            "max_size": self.max_size,
        }


# ---------------------------------------------------------------------------
# Module-level singletons
# ---------------------------------------------------------------------------

# Short-lived cache for availability/slot checks (2 minutes)
response_cache = ResponseCache(default_ttl=120, max_size=500)

# Longer-lived catalog cache (services, staff, branches — 10 minutes)
catalog_cache = ResponseCache(default_ttl=600, max_size=200)

# Customer history cache (5 minutes — invalidated on new bookings)
history_cache = ResponseCache(default_ttl=300, max_size=300)


def make_availability_key(branch_id: str, date_str: str, staff_id: Optional[str] = None, service_id: Optional[str] = None) -> str:
    return f"avail:{branch_id}:{date_str}:{staff_id or 'any'}:{service_id or 'any'}"


def make_history_key(customer_id: str) -> str:
    return f"history:{customer_id}"


def make_services_key() -> str:
    return "catalog:services"


def make_staff_key(branch_id: Optional[str] = None) -> str:
    return f"catalog:staff:{branch_id or 'all'}"


def invalidate_customer_cache(customer_id: str) -> None:
    """Call this after any appointment mutation for a customer."""
    history_cache.invalidate(make_history_key(customer_id))
    logger.debug("[ResponseCache] Invalidated history cache for customer %s", customer_id)


def invalidate_availability_cache(branch_id: str, date_str: str) -> None:
    """Call this after booking/cancellation for a branch+date."""
    prefix = f"avail:{branch_id}:{date_str}"
    removed = response_cache.invalidate_prefix(prefix)
    logger.debug("[ResponseCache] Invalidated %d availability cache entries for %s on %s", removed, branch_id, date_str)


def log_cache_stats() -> None:
    """Log cache performance stats to INFO."""
    logger.info("[ResponseCache] response_cache stats: %s", response_cache.stats())
    logger.info("[ResponseCache] catalog_cache stats: %s", catalog_cache.stats())
    logger.info("[ResponseCache] history_cache stats: %s", history_cache.stats())
