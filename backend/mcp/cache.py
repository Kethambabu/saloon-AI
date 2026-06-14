"""
MCP Cache — In-memory TTL cache for frequently requested read-only data.

Cached resources:
    services   — TTL: 5 minutes
    branches   — TTL: 5 minutes
    offers     — TTL: 2 minutes
    policies   — TTL: 10 minutes
    knowledge  — TTL: 10 minutes

All other resources bypass the cache and go directly to database.
Thread-safe via threading.RLock.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cache TTL configuration (seconds)
# ---------------------------------------------------------------------------

CACHE_TTL: Dict[str, int] = {
    "services":   300,   # 5 minutes
    "branches":   300,   # 5 minutes
    "offers":     120,   # 2 minutes
    "knowledge":  600,   # 10 minutes
    "policies":   600,   # 10 minutes
}

# Resources that MUST NOT be cached (always fresh from DB)
NO_CACHE_RESOURCES = {
    "appointments", "customers", "staff", "leads",
    "reviews", "loyalty_points", "audit_logs",
}


class CacheEntry:
    __slots__ = ("data", "created_at", "ttl", "hits")

    def __init__(self, data: Any, ttl: int):
        self.data = data
        self.created_at = time.monotonic()
        self.ttl = ttl
        self.hits = 0

    def is_valid(self) -> bool:
        return (time.monotonic() - self.created_at) < self.ttl

    def touch(self) -> Any:
        self.hits += 1
        return self.data


class MCPCache:
    """
    In-memory TTL cache for MCP read operations.

    Usage::

        cache = get_cache()
        hit = cache.get(resource="services", filters={})
        if hit is None:
            data = fetch_from_db(...)
            cache.set(resource="services", filters={}, data=data)
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._store: Dict[str, CacheEntry] = {}
        self._hits = 0
        self._misses = 0

    def _make_key(self, resource: str, filters: Dict[str, Any], limit: int, offset: int) -> str:
        """Create a deterministic cache key from resource + filters."""
        try:
            filters_str = json.dumps(filters, sort_keys=True, default=str)
        except Exception:
            filters_str = str(sorted(filters.items()))
        return f"{resource.lower()}:{filters_str}:limit={limit}:offset={offset}"

    def is_cacheable(self, resource: str) -> bool:
        """Return True if this resource should be cached."""
        res_lower = resource.lower()
        return (
            res_lower in CACHE_TTL
            and res_lower not in NO_CACHE_RESOURCES
        )

    def get(self, resource: str, filters: Dict[str, Any], limit: int = 100, offset: int = 0) -> Optional[Any]:
        """Return cached data or None on miss/expired."""
        if not self.is_cacheable(resource):
            return None

        key = self._make_key(resource, filters, limit, offset)
        with self._lock:
            entry = self._store.get(key)
            if entry is not None:
                if entry.is_valid():
                    self._hits += 1
                    logger.debug("[MCPCache] HIT for key: %s", key)
                    return entry.touch()
                else:
                    # Expired
                    logger.debug("[MCPCache] EXPIRED entry for key: %s", key)
                    self._store.pop(key, None)

            self._misses += 1
            logger.debug("[MCPCache] MISS for key: %s", key)
            return None

    def set(self, resource: str, filters: Dict[str, Any], data: Any, limit: int = 100, offset: int = 0) -> None:
        """Cache data if resource is cacheable."""
        if not self.is_cacheable(resource):
            return

        res_lower = resource.lower()
        ttl = CACHE_TTL.get(res_lower, 300)
        key = self._make_key(resource, filters, limit, offset)

        with self._lock:
            self._store[key] = CacheEntry(data, ttl)
            logger.debug("[MCPCache] CACHED key: %s with TTL %ds", key, ttl)

    def clear(self, resource: Optional[str] = None) -> None:
        """Clear cache. If resource is provided, clear only keys for that resource."""
        with self._lock:
            if resource:
                res_prefix = f"{resource.lower()}:"
                keys_to_remove = [k for k in self._store if k.startswith(res_prefix)]
                for k in keys_to_remove:
                    self._store.pop(k, None)
                logger.info("[MCPCache] Cleared cache for resource: %s", resource)
            else:
                self._store.clear()
                logger.info("[MCPCache] Entire cache cleared.")

    def get_stats(self) -> Dict[str, Any]:
        """Return cache hits, misses, and current active keys count."""
        with self._lock:
            active_keys = {}
            for k, entry in self._store.items():
                if entry.is_valid():
                    resource = k.split(":")[0]
                    active_keys[resource] = active_keys.get(resource, 0) + 1

            total_requests = self._hits + self._misses
            hit_ratio = round(self._hits / total_requests, 4) if total_requests > 0 else 0.0

            return {
                "hits": self._hits,
                "misses": self._misses,
                "hit_ratio": hit_ratio,
                "active_keys_by_resource": active_keys,
                "total_cached_entries": len(self._store),
            }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_cache: Optional[MCPCache] = None


def get_cache() -> MCPCache:
    """Return the shared MCPCache singleton."""
    global _cache
    if _cache is None:
        _cache = MCPCache()
    return _cache
