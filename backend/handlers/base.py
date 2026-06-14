"""
Base Handler — Phase 2 Architecture.

All handlers implement this interface. The WorkflowRegistry dispatches
to handlers by action name using a dict lookup instead of if/else chains.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class HandlerContext:
    """
    Carries the full request context from orchestrator to handler.

    Attributes:
        params:      Action-specific parameters dict.
        tenant_id:   Tenant (salon chain) UUID for multi-tenant isolation.
        user_id:     Authenticated user UUID.
        user_role:   Role string (CUSTOMER | STAFF | MANAGER | OWNER | ADMIN).
        session_id:  Conversation session ID.
        branch_id:   Resolved branch UUID (optional).
        trace_id:    Unique request trace ID for logging/observability.
    """

    def __init__(
        self,
        params: Dict[str, Any],
        tenant_id: str = "default",
        user_id: str = "anonymous",
        user_role: str = "CUSTOMER",
        session_id: str = "default",
        branch_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> None:
        self.params = params
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.user_role = user_role
        self.session_id = session_id
        self.branch_id = branch_id
        self.trace_id = trace_id or self._generate_trace_id()

    @staticmethod
    def _generate_trace_id() -> str:
        import uuid
        return str(uuid.uuid4())[:8]

    def get(self, key: str, default: Any = None) -> Any:
        """Convenience accessor for params dict."""
        return self.params.get(key, default)

    def __repr__(self) -> str:
        return (
            f"<HandlerContext tenant={self.tenant_id} user={self.user_id} "
            f"role={self.user_role} trace={self.trace_id}>"
        )


class BaseHandler(ABC):
    """
    Abstract base class for all Phase 2 handlers.

    Subclasses implement `handle(ctx)` and optionally override
    `validate(ctx)` for parameter validation.
    """

    #: Human-readable name for logging and registry display.
    name: str = "BaseHandler"

    #: Permission action key validated before execution.
    permission_action: Optional[str] = None

    def __init__(self) -> None:
        self.logger = logging.getLogger(f"handler.{self.name}")

    def execute(self, ctx: HandlerContext) -> Dict[str, Any]:
        """
        Main dispatch method. Runs validate → permission check → handle.

        Returns:
            Result dict with at minimum {"success": bool, ...}.
        """
        # 1. Validate inputs
        validation_error = self.validate(ctx)
        if validation_error:
            self.logger.warning(
                "[%s] Validation failed (trace=%s): %s",
                self.name, ctx.trace_id, validation_error
            )
            return {"success": False, "error": validation_error, "handler": self.name}

        # 2. Permission check
        if self.permission_action:
            try:
                from services.permission_guard import validate_workflow_permission
                validate_workflow_permission(self.permission_action, ctx.user_role)
            except Exception as exc:
                self.logger.warning(
                    "[%s] Permission denied (trace=%s): %s",
                    self.name, ctx.trace_id, exc
                )
                return {"success": False, "error": str(exc), "handler": self.name}

        # 3. Execute handler
        try:
            self.logger.info(
                "[%s] Executing (trace=%s tenant=%s)",
                self.name, ctx.trace_id, ctx.tenant_id
            )
            result = self.handle(ctx)
            result["handler"] = self.name
            result["trace_id"] = ctx.trace_id
            return result
        except Exception as exc:
            self.logger.error(
                "[%s] Unhandled error (trace=%s): %s",
                self.name, ctx.trace_id, exc, exc_info=True
            )
            return {
                "success": False,
                "error": f"{self.name} failed: {exc}",
                "handler": self.name,
                "trace_id": ctx.trace_id,
            }

    @abstractmethod
    def handle(self, ctx: HandlerContext) -> Dict[str, Any]:
        """Implement business logic. Must return a dict with 'success' key."""
        ...

    def validate(self, ctx: HandlerContext) -> Optional[str]:
        """
        Optional input validation.
        Return an error string if invalid, or None if valid.
        """
        return None
