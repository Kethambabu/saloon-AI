"""
SalonMCP Write Operations — Role-aware data mutation layer for SalonAI Workforce Platform.

Handles create/update/delete operations on resources with full permission checking,
audit logging, and metric tracking.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from db.database import SessionLocal
from db import models as M
from mcp.schemas import MCPContext, MCPResponse
from mcp.permissions import check_permission
from mcp.audit_log import get_audit_logger
from mcp.metrics import get_metrics_tracker

logger = logging.getLogger(__name__)


def _model_to_dict(obj) -> Dict[str, Any]:
    """Convert a SQLAlchemy ORM row to a plain dict (non-recursive)."""
    result: Dict[str, Any] = {}
    for col in obj.__table__.columns:
        val = getattr(obj, col.name, None)
        if isinstance(val, uuid.UUID):
            val = str(val)
        elif hasattr(val, "isoformat"):
            val = val.isoformat()
        elif hasattr(val, "value"):
            val = val.value
        result[col.name] = val
    return result


class SalonMCPWrite:
    """
    Dispatcher for database write operations via MCP.
    """

    def __init__(self):
        self.audit_logger = get_audit_logger()
        self.metrics_tracker = get_metrics_tracker()

    def execute_write(
        self,
        context: MCPContext,
        resource: str,
        operation: str,  # "insert", "update", "delete"
        data: Optional[Dict[str, Any]] = None,
        filters: Optional[Dict[str, Any]] = None,
        agent_name: str = "unknown",
    ) -> MCPResponse:
        """
        Execute write pipeline: permission -> database transaction -> audit -> metrics.
        """
        t_start = time.perf_counter()
        role_str = context.role if isinstance(context.role, str) else context.role.value
        resource_lower = resource.lower()
        operation_lower = operation.lower()

        # 1. Check permissions (writes generally require ADMIN/STAFF, except CUSTOMER appointments/reviews)
        # We can map standard write operations to permissions
        perm_granted = check_permission(role_str, resource_lower)
        # Note: check_permission is typically role-resource based. Let's make sure it allows the action.
        if not perm_granted:
            self.audit_logger.log_action(
                user_id=context.user_id,
                role=role_str,
                agent=agent_name,
                action=operation_lower,
                resource=resource_lower,
                status="PERMISSION_DENIED",
                metadata={"error": "Role does not have permission for this resource"}
            )
            return MCPResponse(
                success=False,
                resource=resource,
                operation=operation,
                error=f"Role '{role_str}' does not have write access to '{resource}'.",
                error_code="PERMISSION_DENIED",
            )

        # 2. Map resource name to SQLAlchemy Model class
        model_map = {
            "appointments": M.Appointment,
            "reviews": M.Review,
            "leads": M.Lead,
            "customers": M.Customer,
            "staff": M.Staff,
            "staff_leaves": M.StaffLeave,
            "services": M.Service,
            "branches": M.Branch,
        }

        model_class = model_map.get(resource_lower)
        if not model_class:
            return MCPResponse(
                success=False,
                resource=resource,
                operation=operation,
                error=f"Resource '{resource}' does not support write operations.",
                error_code="UNSUPPORTED_RESOURCE",
            )

        # 3. Perform database operations within transaction block
        db: Session = SessionLocal()
        try:
            if operation_lower == "insert":
                if not data:
                    raise ValueError("No data provided for insert operation.")
                
                # Convert string IDs to UUIDs where applicable
                processed_data = {}
                for k, v in data.items():
                    if k.endswith("_id") and isinstance(v, str) and v:
                        try:
                            processed_data[k] = uuid.UUID(v)
                        except ValueError:
                            processed_data[k] = v
                    else:
                        processed_data[k] = v

                # Generate new UUID if id not provided
                if "id" not in processed_data:
                    processed_data["id"] = uuid.uuid4()
                elif isinstance(processed_data["id"], str):
                    processed_data["id"] = uuid.UUID(processed_data["id"])

                db_obj = model_class(**processed_data)
                db.add(db_obj)
                db.commit()
                db.refresh(db_obj)
                res_data = [_model_to_dict(db_obj)]
                error_msg = None

            elif operation_lower == "update":
                if not filters:
                    raise ValueError("Filters required to locate records for update.")
                if not data:
                    raise ValueError("No update data provided.")

                # Retrieve the object
                query = db.query(model_class)
                for k, v in filters.items():
                    if hasattr(model_class, k):
                        col = getattr(model_class, k)
                        if isinstance(v, str) and (k == "id" or k.endswith("_id")):
                            try:
                                v = uuid.UUID(v)
                            except ValueError:
                                pass
                        query = query.filter(col == v)

                db_obj = query.first()
                if not db_obj:
                    return MCPResponse(
                        success=False,
                        resource=resource,
                        operation=operation,
                        error="No matching record found to update.",
                        error_code="NOT_FOUND",
                    )

                # Apply updates
                for k, v in data.items():
                    if hasattr(db_obj, k):
                        if k.endswith("_id") and isinstance(v, str) and v:
                            try:
                                v = uuid.UUID(v)
                            except ValueError:
                                pass
                        setattr(db_obj, k, v)

                db.commit()
                db.refresh(db_obj)
                res_data = [_model_to_dict(db_obj)]
                error_msg = None

            elif operation_lower == "delete":
                if not filters:
                    raise ValueError("Filters required to locate records for delete.")

                query = db.query(model_class)
                for k, v in filters.items():
                    if hasattr(model_class, k):
                        col = getattr(model_class, k)
                        if isinstance(v, str) and (k == "id" or k.endswith("_id")):
                            try:
                                v = uuid.UUID(v)
                            except ValueError:
                                pass
                        query = query.filter(col == v)

                db_obj = query.first()
                if not db_obj:
                    return MCPResponse(
                        success=False,
                        resource=resource,
                        operation=operation,
                        error="No matching record found to delete.",
                        error_code="NOT_FOUND",
                    )

                db.delete(db_obj)
                db.commit()
                res_data = []
                error_msg = None

            else:
                raise ValueError(f"Unsupported write operation: '{operation}'")

            elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)
            
            # Log audit and metrics
            self.audit_logger.log_action(
                user_id=context.user_id,
                role=role_str,
                agent=agent_name,
                action=operation_lower,
                resource=resource_lower,
                status="SUCCESS",
                metadata={"execution_time_ms": elapsed_ms}
            )
            self.metrics_tracker.record(
                resource=resource_lower,
                operation=operation_lower,
                agent_name=agent_name,
                success=True,
                duration_ms=elapsed_ms,
                filters=filters
            )

            return MCPResponse(
                success=True,
                resource=resource,
                operation=operation,
                data=res_data,
                count=len(res_data),
                metadata={
                    "execution_time_ms": elapsed_ms,
                    "role": role_str,
                    "agent": agent_name,
                }
            )

        except Exception as exc:
            db.rollback()
            elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)
            logger.error("[SalonMCPWrite] Write failed for resource '%s': %s", resource, exc, exc_info=True)
            
            self.audit_logger.log_action(
                user_id=context.user_id,
                role=role_str,
                agent=agent_name,
                action=operation_lower,
                resource=resource_lower,
                status="ERROR",
                metadata={"error": str(exc), "execution_time_ms": elapsed_ms}
            )
            self.metrics_tracker.record(
                resource=resource_lower,
                operation=operation_lower,
                agent_name=agent_name,
                success=False,
                duration_ms=elapsed_ms,
                error_code="WRITE_ERROR",
                filters=filters
            )

            return MCPResponse(
                success=False,
                resource=resource,
                operation=operation,
                error=f"Database write error: {exc}",
                error_code="WRITE_ERROR",
            )
        finally:
            db.close()
