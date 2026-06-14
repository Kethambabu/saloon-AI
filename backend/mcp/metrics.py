"""
MCP Metrics Dashboard Tracker.

Tracks resource usage, query response times, slow queries, and agent usage
to provide diagnostic insight into SalonMCP performance.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Threshold for marking a query as "slow" (in milliseconds)
SLOW_QUERY_THRESHOLD_MS = 200.0


class MCPMetricsTracker:
    """
    Thread-safe metrics aggregator for MCP operations.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._total_requests = 0
        self._success_count = 0
        self._failure_count = 0

        # resource -> call count
        self._resource_calls: Dict[str, int] = defaultdict(int)

        # agent_name -> call count
        self._agent_calls: Dict[str, int] = defaultdict(int)

        # error_code -> count
        self._errors: Dict[str, int] = defaultdict(int)

        # Slow query logs: list of dicts with query info
        self._slow_queries: List[Dict[str, Any]] = []

        # Latency statistics: resource -> list of execution times
        self._latencies: Dict[str, List[float]] = defaultdict(list)

    def record(
        self,
        resource: str,
        operation: str,
        agent_name: str,
        success: bool,
        duration_ms: float,
        error_code: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a single MCP operation execution."""
        with self._lock:
            self._total_requests += 1
            if success:
                self._success_count += 1
            else:
                self._failure_count += 1
                if error_code:
                    self._errors[error_code] += 1

            res_lower = resource.lower()
            self._resource_calls[res_lower] += 1
            self._agent_calls[agent_name or "unknown"] += 1

            # Store latencies (cap at 1000 items per resource to save memory)
            durations = self._latencies[res_lower]
            if len(durations) >= 1000:
                durations.pop(0)
            durations.append(duration_ms)

            # Record slow queries
            if duration_ms >= SLOW_QUERY_THRESHOLD_MS:
                slow_entry = {
                    "timestamp": time.time(),
                    "resource": resource,
                    "operation": operation,
                    "agent": agent_name,
                    "duration_ms": duration_ms,
                    "filters": filters or {},
                    "success": success,
                    "error_code": error_code,
                }
                # Keep last 100 slow queries
                if len(self._slow_queries) >= 100:
                    self._slow_queries.pop(0)
                self._slow_queries.append(slow_entry)

                logger.warning(
                    "[MCPMetrics] SLOW QUERY: resource=%s op=%s duration=%.2fms agent=%s",
                    resource, operation, duration_ms, agent_name
                )

    def get_dashboard(self) -> Dict[str, Any]:
        """Compile and return current performance metrics dashboard."""
        with self._lock:
            # Calculate averages
            avg_latencies = {}
            for res, times in self._latencies.items():
                if times:
                    avg_latencies[res] = round(sum(times) / len(times), 2)
                else:
                    avg_latencies[res] = 0.0

            success_rate = (
                round(self._success_count / self._total_requests, 4)
                if self._total_requests > 0
                else 1.0
            )

            return {
                "summary": {
                    "total_requests": self._total_requests,
                    "success_count": self._success_count,
                    "failure_count": self._failure_count,
                    "success_rate": success_rate,
                },
                "resource_distribution": dict(self._resource_calls),
                "agent_distribution": dict(self._agent_calls),
                "average_latencies_ms": avg_latencies,
                "error_rates": dict(self._errors),
                "slow_queries": list(reversed(self._slow_queries)),
            }

    def clear(self) -> None:
        """Reset all metrics."""
        with self._lock:
            self._total_requests = 0
            self._success_count = 0
            self._failure_count = 0
            self._resource_calls.clear()
            self._agent_calls.clear()
            self._errors.clear()
            self._slow_queries.clear()
            self._latencies.clear()
            logger.info("[MCPMetrics] Metrics tracker reset.")


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_tracker: Optional[MCPMetricsTracker] = None


def get_metrics_tracker() -> MCPMetricsTracker:
    """Return the shared MCPMetricsTracker singleton."""
    global _tracker
    if _tracker is None:
        _tracker = MCPMetricsTracker()
    return _tracker
