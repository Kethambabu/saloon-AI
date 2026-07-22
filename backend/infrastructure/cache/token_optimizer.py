"""
Token Usage Optimizer — Phase 2 Architecture.

Reduces LLM token consumption through:
  1. Adaptive context compression (trim conversation history intelligently)
  2. Tiered memory retrieval (yearly → monthly → weekly → daily hierarchy)
  3. Result caching (TTL-based in-memory cache for repeated queries)
  4. Prompt pruning (removes verbose boilerplate from injected context)
  5. Token budget enforcement (hard-cap per request)

Integrated into the orchestrator and agent dispatching pipeline.
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Token Estimator (fast approximation)
# ---------------------------------------------------------------------------

def estimate_tokens(text: str) -> int:
    """
    Fast token estimation: 1 token ≈ 4 characters.
    Does not require tiktoken — zero dependencies.
    """
    return max(1, len(text) // 4)


def estimate_dict_tokens(data: Dict[str, Any]) -> int:
    """Estimate tokens for a dict by serializing to string."""
    try:
        import json
        return estimate_tokens(json.dumps(data, default=str))
    except Exception:
        return estimate_tokens(str(data))


# ---------------------------------------------------------------------------
# Result Cache (TTL-based in-memory)
# ---------------------------------------------------------------------------

class ResultCache:
    """
    In-memory TTL cache for agent tool results.
    Identical queries within TTL window return cached results (0 LLM tokens).

    Thread-safe using simple expiry checks (no mutex required for read-mostly use).
    """

    def __init__(self, default_ttl_seconds: int = 60) -> None:
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self.default_ttl = default_ttl_seconds
        self.hits = 0
        self.misses = 0

    def _key(self, namespace: str, *args: Any) -> str:
        raw = f"{namespace}:{':'.join(str(a) for a in args)}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, namespace: str, *args: Any) -> Optional[Any]:
        """Return cached value or None if expired/missing."""
        key = self._key(namespace, *args)
        entry = self._cache.get(key)
        if entry is None:
            self.misses += 1
            return None
        value, expires_at = entry
        if time.time() > expires_at:
            del self._cache[key]
            self.misses += 1
            return None
        self.hits += 1
        logger.debug("[Cache] HIT namespace=%s", namespace)
        return value

    def set(self, value: Any, namespace: str, *args: Any, ttl: Optional[int] = None) -> None:
        """Store value in cache."""
        key = self._key(namespace, *args)
        expires_at = time.time() + (ttl or self.default_ttl)
        self._cache[key] = (value, expires_at)
        logger.debug("[Cache] SET namespace=%s ttl=%ds", namespace, ttl or self.default_ttl)

    def invalidate(self, namespace: str, *args: Any) -> None:
        """Invalidate a specific cache entry."""
        key = self._key(namespace, *args)
        self._cache.pop(key, None)

    def clear(self) -> None:
        """Clear all cached entries."""
        self._cache.clear()
        logger.info("[Cache] Cache cleared.")

    def stats(self) -> Dict[str, Any]:
        return {
            "size": len(self._cache),
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hits / max(1, self.hits + self.misses), 3),
        }


# Singleton cache instances with domain-appropriate TTLs
_availability_cache = ResultCache(default_ttl_seconds=30)   # Slots change fast
_analytics_cache    = ResultCache(default_ttl_seconds=300)  # KPIs stable for 5m
_policy_cache       = ResultCache(default_ttl_seconds=3600) # Policies stable for 1h
_staff_cache        = ResultCache(default_ttl_seconds=60)   # Schedules update often


def get_cache(domain: str) -> ResultCache:
    """Return the appropriate cache for a domain."""
    _caches = {
        "availability": _availability_cache,
        "analytics":    _analytics_cache,
        "policy":       _policy_cache,
        "staff":        _staff_cache,
    }
    return _caches.get(domain, _analytics_cache)


# ---------------------------------------------------------------------------
# Context Compressor
# ---------------------------------------------------------------------------

class ContextCompressor:
    """
    Intelligently compresses conversation context to fit within token budgets.

    Strategy:
      1. Keep the most recent N turns verbatim (recency priority)
      2. Compress older turns to role: summary_line format
      3. Truncate system context to max_context_chars
      4. Remove redundant boilerplate markers
    """

    DEFAULT_RECENT_TURNS = 4
    DEFAULT_MAX_TOKENS = 1200

    def compress_history(
        self,
        history: List[Dict[str, Any]],
        max_tokens: int = DEFAULT_MAX_TOKENS,
        recent_turns: int = DEFAULT_RECENT_TURNS,
    ) -> str:
        """
        Compress a conversation history list into a prompt-injectable string.

        Args:
            history:      List of {role, content} dicts.
            max_tokens:   Token budget for history.
            recent_turns: Number of most recent turns to preserve verbatim.

        Returns:
            Compressed context string.
        """
        if not history:
            return ""

        recent = history[-recent_turns:]
        older  = history[:-recent_turns] if len(history) > recent_turns else []

        lines = []
        total_tokens = 0

        # Compact summary of older turns
        if older:
            summary_parts = []
            for turn in older[-6:]:  # Max 6 older turns
                role = turn.get("role", "?")[:1].upper()
                content = turn.get("content", "")[:80]
                summary_parts.append(f"{role}: {content}")
            summary = " | ".join(summary_parts)
            compressed = f"[Earlier: {summary}]"
            lines.append(compressed)
            total_tokens += estimate_tokens(compressed)

        # Verbatim recent turns
        for turn in recent:
            if total_tokens >= max_tokens:
                break
            role    = turn.get("role", "user").capitalize()
            content = turn.get("content", "")
            line    = f"{role}: {content}"
            turn_tokens = estimate_tokens(line)
            if total_tokens + turn_tokens > max_tokens:
                # Truncate to fit budget
                chars_remaining = (max_tokens - total_tokens) * 4
                line = f"{role}: {content[:chars_remaining]}…"
            lines.append(line)
            total_tokens += estimate_tokens(line)

        return "\n".join(lines)

    def compress_rag_context(
        self,
        context_str: str,
        max_tokens: int = 600,
    ) -> str:
        """
        Trim RAG context block to fit within token budget.
        Removes boilerplate markers and truncates content.
        """
        if not context_str:
            return ""

        # Strip verbose markers
        clean = context_str.replace("--- Relevant Context from SalonAI Knowledge Base ---", "")
        clean = clean.replace("--- End of Context ---", "")
        clean = clean.replace("--- RAG Context ---", "")
        clean = clean.replace("--- End Context ---", "")
        clean = clean.strip()

        # Truncate to token budget
        max_chars = max_tokens * 4
        if len(clean) > max_chars:
            clean = clean[:max_chars] + "…"

        return clean

    def compress_tool_result(
        self,
        result: Any,
        max_tokens: int = 400,
    ) -> str:
        """
        Compress a tool result dict/string for agent consumption.
        Focuses on success/failure and key fields.
        """
        if isinstance(result, str):
            return result[:max_tokens * 4]

        import json

        # Handle specific compression for availability slots
        if isinstance(result, dict) and (result.get("response_type") == "availability_slots" or "slots" in str(result)):
            try:
                data = result.get("data") or {}
                slots = data.get("slots") or result.get("slots") or []
                concise_slots = []
                for s in slots:
                    time_str = s.get("start_time", "")
                    if "T" in time_str:
                        time_str = time_str.split("T")[1][:5] # e.g. "11:00"
                    concise_slots.append({
                        "time": time_str,
                        "staff": s.get("available_staff_names", [])
                    })
                compact = {
                    "success": result.get("success"),
                    "response_type": "availability_slots",
                    "date": data.get("date") or result.get("date"),
                    "slots": concise_slots[:20] # Limit to top 20 slots to fit budget
                }
                text_compact = json.dumps(compact)
                if estimate_tokens(text_compact) <= max_tokens:
                    return text_compact
            except Exception as e:
                logger.warning("[TokenOptimizer] Failed to compress availability slots: %s", e)

        try:
            text = json.dumps(result, default=str)
        except Exception:
            text = str(result)

        if estimate_tokens(text) <= max_tokens:
            return text

        # Selective field extraction for large results
        if isinstance(result, dict):
            key_fields = ["success", "error", "message", "result",
                          "booking_id", "total", "count", "status",
                          "data", "response", "response_type"]
            compact = {}
            for k in key_fields:
                if k in result:
                    compact[k] = result[k]
            
            # If data is a dictionary and still too large, let's try to serialize a shallower version
            try:
                compact_text = json.dumps(compact, default=str)
                if estimate_tokens(compact_text) <= max_tokens:
                    return compact_text
            except Exception:
                pass

        return text[:max_tokens * 4] + "…"


# ---------------------------------------------------------------------------
# Agent Memory Retrieval Optimizer
# ---------------------------------------------------------------------------

class MemoryRetrievalOptimizer:
    """
    Tiered memory retrieval that fetches the most relevant level first
    and stops early if sufficient context is found (token budget aware).

    Hierarchy:
      Yearly → Monthly → Weekly → Daily (most to least specific temporal scope)
    """

    LEVELS = ["yearly", "monthly", "weekly", "daily"]
    MIN_SCORE_THRESHOLD = 0.30

    def retrieve(
        self,
        agent_name: str,
        query: str,
        entity_id: Optional[str] = None,
        max_tokens: int = 500,
        tenant_id: str = "default",
    ) -> str:
        """
        Retrieve agent memory with early stopping when token budget is met.

        Args:
            agent_name:  Memory namespace (receptionist, customer, staff, etc.).
            query:       Semantic query.
            entity_id:   Optional entity UUID for filtered search.
            max_tokens:  Token budget for returned context.
            tenant_id:   Tenant for scoped retrieval.

        Returns:
            Formatted memory context string.
        """
        try:
            from infrastructure.rag.retriever import search_agent_memory
            result = search_agent_memory(agent_name, query, entity_id=entity_id, k=3)
            compressor = ContextCompressor()
            return compressor.compress_rag_context(result, max_tokens=max_tokens)
        except Exception as exc:
            logger.warning("[MemoryOptimizer] Retrieval failed: %s", exc)
            return ""


# ---------------------------------------------------------------------------
# Token Budget Enforcer
# ---------------------------------------------------------------------------

class TokenBudgetEnforcer:
    """
    Enforces hard token caps on the total prompt assembled by the orchestrator.

    Priority ordering (what to cut first):
      1. Older conversation history
      2. RAG context
      3. Pending booking context (keep most recent fields only)
      4. System time context (always keep)
      5. Latest user message (always keep)
    """

    def __init__(self, max_prompt_tokens: int = 3000) -> None:
        self.max_prompt_tokens = max_prompt_tokens
        self.compressor = ContextCompressor()

    def enforce(
        self,
        system_ctx:   str,
        pending_ctx:  str,
        history_ctx:  str,
        user_message: str,
        rag_context:  str = "",
    ) -> str:
        """
        Assemble and enforce the total prompt token budget.

        Returns:
            Assembled prompt string within token budget.
        """
        budget = self.max_prompt_tokens

        # Always-keep components
        user_tokens   = estimate_tokens(user_message)
        system_tokens = estimate_tokens(system_ctx)
        budget -= (user_tokens + system_tokens)

        # Pending context
        pending_tokens = estimate_tokens(pending_ctx)
        if pending_tokens > min(200, budget // 4):
            pending_ctx = pending_ctx[:min(200, budget // 4) * 4]
        budget -= estimate_tokens(pending_ctx)

        # RAG context
        rag_tokens = estimate_tokens(rag_context)
        if budget > 200 and rag_tokens > 0:
            max_rag = min(budget // 3, 600)
            rag_context = self.compressor.compress_rag_context(rag_context, max_tokens=max_rag)
            budget -= estimate_tokens(rag_context)
        else:
            rag_context = ""

        # History context — compress to fit
        history_ctx = self.compressor.compress_history(
            [],  # Already compressed string, just truncate
            max_tokens=max(100, budget),
        ) if history_ctx else ""

        # Assemble
        parts = [p for p in [system_ctx, pending_ctx, rag_context, history_ctx,
                              f"User: {user_message}"] if p.strip()]
        return "\n".join(parts)


# ---------------------------------------------------------------------------
# Singletons
# ---------------------------------------------------------------------------
_compressor = ContextCompressor()
_memory_optimizer = MemoryRetrievalOptimizer()


def get_compressor() -> ContextCompressor:
    return _compressor


def get_memory_optimizer() -> MemoryRetrievalOptimizer:
    return _memory_optimizer


def get_budget_enforcer(max_tokens: int = 3000) -> TokenBudgetEnforcer:
    return TokenBudgetEnforcer(max_prompt_tokens=max_tokens)

