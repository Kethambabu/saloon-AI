"""
MCP Audit Log — Dedicated auditing layer for MCP actions.
Logs are written to an append-only JSONL file in backend/data/mcp_audit.jsonl.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Output log path
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_AUDIT_LOG_FILE = _BACKEND_DIR / "data" / "mcp_audit.jsonl"


def _ensure_audit_dir():
    _AUDIT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)


class MCPAuditLogger:
    """
    Append-only audit logger tracking user context and operations.
    """

    def __init__(self):
        _ensure_audit_dir()

    def log_action(
        self,
        user_id: str,
        role: str,
        agent_name: str,
        action: str,
        resource: str,
        status: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Write a single audit entry.
        """
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "role": role,
            "agent": agent_name,
            "action": action,
            "resource": resource,
            "status": status,
            "metadata": metadata or {},
        }

        # 1. Log to console
        log_level = logging.INFO if status.upper() == "SUCCESS" else logging.WARNING
        logger.log(
            log_level,
            "[MCP Audit] agent=%s user=%s role=%s action=%s resource=%s status=%s",
            agent_name, user_id, role, action, resource, status
        )

        # 2. Append to JSONL file
        try:
            with open(_AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except Exception as exc:
            logger.warning("[MCPAuditLogger] Failed to write audit to file: %s", exc)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_audit_logger: Optional[MCPAuditLogger] = None


def get_audit_logger() -> MCPAuditLogger:
    """Return the shared MCPAuditLogger singleton."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = MCPAuditLogger()
    return _audit_logger
