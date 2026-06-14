"""
MCP Audit Service — Logs every MCP request for observability and compliance.

Every SalonMCP call is audited with:
    * user_id       — Who made the request
    * role          — Their role at the time of the request
    * resource      — Which data resource was accessed
    * operation     — What operation was attempted (select / insert / etc.)
    * success       — Whether the operation succeeded
    * error         — Error message if failed
    * timestamp     — UTC timestamp of the log entry

Phase 1 strategy
----------------
Audit logs are written to:
    1. Python logging (always)         — visible in server logs
    2. A flat JSONL file               — `backend/data/mcp_audit.jsonl`
    3. Database audit table (optional) — created if it doesn't exist

The DB table approach is opt-in to keep Phase 1 light; file logging is
the guaranteed fallback so nothing blocks if the DB write fails.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Audit log file path
# ---------------------------------------------------------------------------

# Store audit logs alongside other backend data
_BACKEND_DIR = Path(__file__).resolve().parent.parent   # backend/
_AUDIT_LOG_FILE = _BACKEND_DIR / "data" / "mcp_audit.jsonl"


def _ensure_audit_dir():
    _AUDIT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Audit Logger class
# ---------------------------------------------------------------------------

class MCPAuditLogger:
    """
    Writes an immutable audit trail for every MCP request.

    Usage (called automatically by SalonMCP)::

        audit = MCPAuditLogger()
        audit.log(
            user_id="abc",
            role="CUSTOMER",
            resource="appointments",
            operation="select",
            success=True,
        )
    """

    def __init__(self):
        _ensure_audit_dir()
        self._db_available: Optional[bool] = None   # lazy probe

    # ------------------------------------------------------------------
    # Main logging method
    # ------------------------------------------------------------------

    def log(
        self,
        user_id: str,
        role: str,
        resource: str,
        operation: str,
        success: bool = True,
        error: Optional[str] = None,
        session_id: Optional[str] = None,
        extra: Optional[dict] = None,
    ) -> None:
        """
        Record an MCP audit entry.

        Parameters
        ----------
        user_id:   Authenticated user ID
        role:      Role string (CUSTOMER/STAFF/ADMIN)
        resource:  MCP resource name
        operation: Operation type (select/insert/update/delete)
        success:   Whether the operation completed successfully
        error:     Error message if not successful
        session_id: Optional session/conversation ID
        extra:     Optional additional key-value metadata
        """
        entry = {
            "audit_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "role": role,
            "resource": resource,
            "operation": operation,
            "success": success,
            "error": error,
            "session_id": session_id,
            **(extra or {}),
        }

        # 1. Always log to Python logger (shows in server console/log files)
        level = logging.INFO if success else logging.WARNING
        logger.log(
            level,
            "[MCP Audit] user=%s role=%s resource=%s operation=%s success=%s%s",
            user_id, role, resource, operation, success,
            f" error={error}" if error else "",
        )

        # 2. Append to JSONL audit file
        self._write_to_file(entry)

        # 3. Try to write to DB audit table (best-effort)
        self._write_to_db(entry)

    # ------------------------------------------------------------------
    # File writer
    # ------------------------------------------------------------------

    def _write_to_file(self, entry: dict) -> None:
        """Append the audit entry as a JSON line to the audit JSONL file."""
        try:
            with open(_AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")
        except Exception as exc:
            logger.warning("[MCPAuditLogger] Failed to write audit to file: %s", exc)

    # ------------------------------------------------------------------
    # DB writer (lazy, best-effort)
    # ------------------------------------------------------------------

    def _write_to_db(self, entry: dict) -> None:
        """
        Attempt to persist the audit entry to the database.

        Creates the mcp_audit_logs table on first use if it doesn't exist.
        Never raises — if DB is unavailable, we fall back silently.
        """
        if self._db_available is False:
            # Already failed once — skip DB attempt
            return

        try:
            from db.database import SessionLocal
            from sqlalchemy import text

            db = SessionLocal()
            try:
                # Ensure table exists (lightweight idempotent DDL)
                db.execute(text("""
                    CREATE TABLE IF NOT EXISTS mcp_audit_logs (
                        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        audit_id    TEXT NOT NULL,
                        timestamp   TIMESTAMPTZ NOT NULL,
                        user_id     TEXT,
                        role        TEXT,
                        resource    TEXT,
                        operation   TEXT,
                        success     BOOLEAN,
                        error       TEXT,
                        session_id  TEXT,
                        extra       JSONB
                    )
                """))

                db.execute(
                    text("""
                        INSERT INTO mcp_audit_logs
                            (id, audit_id, timestamp, user_id, role, resource, operation, success, error, session_id)
                        VALUES
                            (gen_random_uuid(), :audit_id, :timestamp, :user_id, :role, :resource,
                             :operation, :success, :error, :session_id)
                    """),
                    {
                        "audit_id":   entry["audit_id"],
                        "timestamp":  entry["timestamp"],
                        "user_id":    entry.get("user_id"),
                        "role":       entry.get("role"),
                        "resource":   entry.get("resource"),
                        "operation":  entry.get("operation"),
                        "success":    entry.get("success"),
                        "error":      entry.get("error"),
                        "session_id": entry.get("session_id"),
                    }
                )
                db.commit()
                self._db_available = True
            except Exception as exc:
                db.rollback()
                logger.debug("[MCPAuditLogger] DB audit write failed (will retry next call): %s", exc)
                self._db_available = None   # Allow retry next time
            finally:
                db.close()

        except Exception as exc:
            # Cannot even import DB — mark as unavailable
            logger.debug("[MCPAuditLogger] DB unavailable for audit logging: %s", exc)
            self._db_available = False


# ---------------------------------------------------------------------------
# Module-level singleton (imported by SalonMCP)
# ---------------------------------------------------------------------------

_audit_logger_instance: Optional[MCPAuditLogger] = None


def get_audit_logger() -> MCPAuditLogger:
    """Return the shared MCPAuditLogger singleton."""
    global _audit_logger_instance
    if _audit_logger_instance is None:
        _audit_logger_instance = MCPAuditLogger()
    return _audit_logger_instance
