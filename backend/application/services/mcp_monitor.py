"""
MCP Monitor — Observability tracking for all MCP operations.

Tracks per-agent, per-resource performance metrics including:
    * Agent name
    * Resource accessed
    * Operation performed
    * Execution time (ms)
    * Success / error counts
    * User role
    * Table accessed

All metrics are stored in-memory (fast) and also written to a JSONL log
file at: backend/data/mcp_monitor.jsonl

This is Phase 2 observability infrastructure — useful for debugging
the migration from old CRUD tools to MCP and identifying slow queries.
"""

from __future__ import annotations

import json
import logging
import time
import threading
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Monitor log file
# ---------------------------------------------------------------------------

from core.config import get_settings
settings = get_settings()

_MONITOR_LOG_FILE = Path(settings.data_dir) / "mcp_monitor.jsonl"


def _ensure_dir():
    _MONITOR_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# In-memory metrics store (thread-safe)
# ---------------------------------------------------------------------------

class _MetricsStore:
    """Thread-safe in-memory accumulator for MCP operation metrics."""

    def __init__(self):
        self._lock = threading.Lock()
        self._records: List[Dict[str, Any]] = []
        # Per-agent aggregates
        self._agent_counts: Dict[str, int] = defaultdict(int)
        self._agent_errors: Dict[str, int] = defaultdict(int)
        self._agent_total_ms: Dict[str, float] = defaultdict(float)
        # Per-resource aggregates
        self._resource_counts: Dict[str, int] = defaultdict(int)
        # Per-role aggregates
        self._role_counts: Dict[str, int] = defaultdict(int)
        # Total operations
        self._total_ops = 0
        self._total_errors = 0

    def record(self, entry: Dict[str, Any]) -> None:
        with self._lock:
            self._records.append(entry)
            # Trim to last 1000 records in memory
            if len(self._records) > 1000:
                self._records = self._records[-1000:]

            agent = entry.get("agent", "unknown")
            resource = entry.get("resource", "unknown")
            role = entry.get("role", "unknown")
            elapsed = entry.get("elapsed_ms", 0.0)
            success = entry.get("success", True)

            self._agent_counts[agent] += 1
            self._agent_total_ms[agent] += elapsed
            self._resource_counts[resource] += 1
            self._role_counts[role] += 1
            self._total_ops += 1

            if not success:
                self._agent_errors[agent] += 1
                self._total_errors += 1

    def get_summary(self) -> Dict[str, Any]:
        with self._lock:
            agent_stats = {}
            for agent in self._agent_counts:
                calls = self._agent_counts[agent]
                avg_ms = (
                    round(self._agent_total_ms[agent] / calls, 2)
                    if calls > 0 else 0
                )
                agent_stats[agent] = {
                    "calls": calls,
                    "errors": self._agent_errors.get(agent, 0),
                    "avg_ms": avg_ms,
                }

            return {
                "total_operations": self._total_ops,
                "total_errors": self._total_errors,
                "error_rate_pct": round(self._total_errors / max(self._total_ops, 1) * 100, 2),
                "per_agent": agent_stats,
                "per_resource": dict(self._resource_counts),
                "per_role": dict(self._role_counts),
                "recent_operations": self._records[-20:],
            }

    def get_recent(self, n: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            return self._records[-n:]


_store = _MetricsStore()


# ---------------------------------------------------------------------------
# Public Monitor class
# ---------------------------------------------------------------------------

class MCPMonitor:
    """
    MCP Observability Monitor.

    Usage — call record() after every mcp_execute() call::

        monitor = MCPMonitor()
        monitor.record(
            agent="Clara",
            resource="appointments",
            operation="select",
            elapsed_ms=42.3,
            role="CUSTOMER",
            success=True,
        )
    """

    def __init__(self):
        _ensure_dir()

    def record(
        self,
        agent: str,
        resource: str,
        operation: str,
        elapsed_ms: float,
        role: str = "unknown",
        success: bool = True,
        error: Optional[str] = None,
        filters_used: Optional[List[str]] = None,
        rows_returned: int = 0,
    ) -> None:
        """
        Record a single MCP operation metric.

        Parameters
        ----------
        agent:          Name of the calling agent (e.g. "Clara", "Atlas")
        resource:       MCP resource name (e.g. "appointments")
        operation:      Operation type (e.g. "select", "aggregate")
        elapsed_ms:     Wall-clock execution time in milliseconds
        role:           Caller role (CUSTOMER/STAFF/ADMIN)
        success:        Whether the operation succeeded
        error:          Error message if not successful
        filters_used:   List of filter keys applied
        rows_returned:  Number of rows/records in the result
        """
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": agent,
            "resource": resource,
            "operation": operation,
            "elapsed_ms": round(elapsed_ms, 2),
            "role": role,
            "success": success,
            "error": error,
            "filters_used": filters_used or [],
            "rows_returned": rows_returned,
        }

        # In-memory
        _store.record(entry)

        # File log (non-blocking — best effort)
        try:
            with open(_MONITOR_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except Exception as exc:
            logger.debug("[MCPMonitor] Failed to write to monitor log: %s", exc)

        log_level = logging.INFO if success else logging.WARNING
        logger.log(
            log_level,
            "[MCPMonitor] agent=%s resource=%s op=%s role=%s success=%s elapsed=%.1fms rows=%d%s",
            agent, resource, operation, role, success, elapsed_ms, rows_returned,
            f" err={error}" if error else "",
        )

    def get_summary(self) -> Dict[str, Any]:
        """Return aggregated performance statistics."""
        return _store.get_summary()

    def get_recent(self, n: int = 20) -> List[Dict[str, Any]]:
        """Return the n most recent operation records."""
        return _store.get_recent(n)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_monitor_instance: Optional[MCPMonitor] = None


def get_monitor() -> MCPMonitor:
    """Return the shared MCPMonitor singleton."""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = MCPMonitor()
    return _monitor_instance

