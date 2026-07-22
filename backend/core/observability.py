"""
SalonAI Workforce - Observability & Structured Tracing Module.

Provides:
  - Per-request correlation/trace ID via contextvars
  - Clean [REQ][AGENT][RAG][LLM][TOOL][MCP] terminal trace format
  - Rotating file log for DEBUG/full stack traces
  - Suppression of noisy third-party library loggers
  - One-shot warning registry (log a key only once)

Usage:
    from core.observability import trace, emit
    trace.set("a1b2c3")
    emit.req("POST /api/v1/agent/chat", user="alice@example.com")
    emit.agent_selected("Clara_Receptionist", intent="greeting")
    emit.llm("huggingface", "Qwen2.5-72B-Instruct", prompt=1200, completion=80, duration_s=3.2)
    emit.agent_done(status="OK", duration_s=3.5)
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
import time
from contextvars import ContextVar
from typing import Optional

# ---------------------------------------------------------------------------
# Trace ID context variable (propagated per HTTP request)
# ---------------------------------------------------------------------------
_trace_id_var: ContextVar[str] = ContextVar("trace_id", default="--------")


class _TraceContext:
    """Simple accessor for the current request trace ID."""

    def set(self, tid: str) -> str:
        _trace_id_var.set(tid[:8] if tid else "--------")
        return _trace_id_var.get()

    def get(self) -> str:
        return _trace_id_var.get()


trace = _TraceContext()


# ---------------------------------------------------------------------------
# One-shot warning registry (Bug 4 fix: avoid repeated FAISS warning spam)
# ---------------------------------------------------------------------------
_WARNED_ONCE: set[str] = set()


def warn_once(logger: logging.Logger, key: str, message: str, *args) -> None:
    """Emit a warning exactly once for a given key across the process lifetime."""
    if key not in _WARNED_ONCE:
        _WARNED_ONCE.add(key)
        logger.warning(message, *args)


# ---------------------------------------------------------------------------
# Plain-text trace formatter (no emojis — renders safely in PowerShell)
# ---------------------------------------------------------------------------
class _PlainFormatter(logging.Formatter):
    """%(asctime)s [%(levelname)s] %(message)s — plain, UTF-8 safe."""

    LEVEL_MAP = {
        "DEBUG": "DEBUG",
        "INFO": "INFO ",
        "WARNING": "WARN ",
        "ERROR": "ERROR",
        "CRITICAL": "CRIT ",
    }

    def format(self, record: logging.LogRecord) -> str:
        ts = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        lvl = self.LEVEL_MAP.get(record.levelname, record.levelname)
        msg = record.getMessage()
        base = f"{ts} [{lvl}] {msg}"
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


# ---------------------------------------------------------------------------
# Emit helpers — produce the structured trace lines
# ---------------------------------------------------------------------------
_trace_logger = logging.getLogger("salon.trace")


class _Emit:
    """Namespace for all structured trace log emitters."""

    @staticmethod
    def _tid() -> str:
        return trace.get()

    def req(self, method_path: str, **kv) -> None:
        extras = " | ".join(f"{k}={v}" for k, v in kv.items() if v is not None)
        msg = f"[REQ][{self._tid()}] {method_path}"
        if extras:
            msg += f" | {extras}"
        _trace_logger.info(msg)

    def req_done(self, status: int, duration_s: float) -> None:
        _trace_logger.info(
            "[REQ][%s] response=%d | duration=%.1fs",
            self._tid(), status, duration_s,
        )

    def agent_selected(self, agent_name: str, intent: Optional[str] = None) -> None:
        suffix = f" | intent={intent}" if intent else ""
        _trace_logger.info("[AGENT][%s] selected=%s%s", self._tid(), agent_name, suffix)

    def rag(self, domains: str, results: int, duration_ms: float) -> None:
        _trace_logger.info(
            "[RAG][%s] domains=%s | results=%d | %.0fms",
            self._tid(), domains, results, duration_ms,
        )

    def llm(
        self,
        provider: str,
        model: str,
        prompt: int,
        completion: int,
        duration_s: float,
    ) -> None:
        total = prompt + completion
        _trace_logger.info(
            "[LLM][%s] provider=%s | model=%s | prompt=%d | completion=%d | total=%d | %.1fs",
            self._tid(), provider, model, prompt, completion, total, duration_s,
        )

    def tool(self, agent: str, name: str, action: Optional[str] = None) -> None:
        suffix = f" | action={action}" if action else ""
        _trace_logger.info("[TOOL][%s] agent=%s | name=%s%s", self._tid(), agent, name, suffix)

    def mcp(
        self,
        resource: str,
        action: str,
        guard: str = "ALLOW",
        status: str = "OK",
        rows: Optional[int] = None,
        duration_ms: Optional[float] = None,
    ) -> None:
        parts = [
            f"[MCP][{self._tid()}]",
            f"resource={resource}",
            f"action={action}",
            f"guard={guard}",
            f"status={status}",
        ]
        if rows is not None:
            parts.append(f"rows={rows}")
        if duration_ms is not None:
            parts.append(f"{duration_ms:.0f}ms")
        _trace_logger.info(" | ".join(parts))

    def agent_done(self, status: str, duration_s: float, error: Optional[str] = None) -> None:
        msg = f"[AGENT][{self._tid()}] completed | status={status} | duration={duration_s:.1f}s"
        if error:
            msg += f" | error={error[:120]}"
        _trace_logger.info(msg)


emit = _Emit()


# ---------------------------------------------------------------------------
# Master setup function — call once at startup from main.py
# ---------------------------------------------------------------------------
def configure_logging(
    log_level: str = "INFO",
    third_party_level: str = "WARNING",
    trace_enabled: bool = True,
    log_file: Optional[str] = None,
) -> None:
    """
    Configure the root logger, trace logger, rotating file handler, and
    silence noisy third-party libraries.

    Args:
        log_level:         Root/app logger level (default INFO).
        third_party_level: Level applied to noisy third-party loggers (default WARNING).
        trace_enabled:     If False, set salon.trace to WARNING (effectively silent).
        log_file:          Optional path for rotating file log at DEBUG level.
    """
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    third_numeric = getattr(logging, third_party_level.upper(), logging.WARNING)

    # --- Root logger ---
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.DEBUG)  # Let handlers filter

    # Console handler — plain text, no emojis
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(numeric_level)
    console.setFormatter(_PlainFormatter())
    # Force UTF-8 output for Windows PowerShell
    if hasattr(console.stream, "reconfigure"):
        try:
            console.stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    root.addHandler(console)

    # Optional rotating file handler at DEBUG level
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        root.addHandler(file_handler)

    # --- Trace logger — always goes to console ---
    tl = logging.getLogger("salon.trace")
    tl.propagate = True
    if not trace_enabled:
        tl.setLevel(logging.WARNING)
    else:
        tl.setLevel(logging.DEBUG)

    # --- Suppress noisy third-party loggers ---
    _NOISY_LOGGERS = [
        "sqlalchemy.engine",
        "sqlalchemy.pool",
        "sqlalchemy.orm",
        "httpx",
        "httpcore",
        "huggingface_hub",
        "huggingface_hub.utils",
        "sentence_transformers",
        "faiss",
        "apscheduler",
        "uvicorn.access",
        "uvicorn.error",
        "watchfiles",
        "watchfiles.main",
        "watchgod",
        "langchain",
        "langchain_core",
        "langchain_community",
        "langchain_huggingface",
        "openai",
        "groq",
        "filelock",
    ]
    for name in _NOISY_LOGGERS:
        lg = logging.getLogger(name)
        lg.setLevel(third_numeric)
        lg.propagate = True  # Let the root handler decide formatting

    # Keep uvicorn startup messages visible
    logging.getLogger("uvicorn").setLevel(logging.INFO)

    logging.getLogger(__name__).info(
        "[Observability] Logging configured: app=%s | third_party=%s | trace=%s",
        log_level.upper(),
        third_party_level.upper(),
        "ON" if trace_enabled else "OFF",
    )
