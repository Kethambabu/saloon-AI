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

from infrastructure.db.database import SessionLocal
from infrastructure.db import models as M
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
                agent_name=agent_name,
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
            "analytics_records": M.AnalyticsRecord,
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
        # 3. Perform database operations within transaction block or delegate to services
        db: Session = SessionLocal()
        try:
            if resource_lower == "appointments":
                if operation_lower in ("insert", "update"):
                    from application.services.datetime_validation import validate_appointment_datetime
                    req_dt_val = (data or {}).get("start_time") or (data or {}).get("new_start_time")
                    val = validate_appointment_datetime(req_dt_val)
                    if not val["valid"]:
                        return MCPResponse(success=False, resource=resource, operation=operation, error=val["reason"], error_code="PAST_DATETIME_INVALID")

                from application.services.appointment_service import get_appointment_service
                svc = get_appointment_service()
                if operation_lower == "insert":
                    if not data:
                        raise ValueError("No data provided for appointment booking.")
                    res = svc.book(
                        customer_id=data.get("customer_id"),
                        branch_id=data.get("branch_id"),
                        service_id=data.get("service_id"),
                        start_time=data.get("start_time"),
                        staff_id=data.get("staff_id"),
                        notes=data.get("notes"),
                        tenant_id=context.tenant_id or "default",
                    )
                    if not res.get("success"):
                        return MCPResponse(success=False, resource=resource, operation=operation, error=res.get("error"), error_code="WRITE_ERROR")
                    res_data = [res.get("data")]
                elif operation_lower == "update":
                    if not filters and not data:
                        raise ValueError("Filters or data required for update.")
                    appt_id = filters.get("id") if filters else data.get("id")
                    res = svc.reschedule(
                        appointment_id=str(appt_id),
                        new_start_time=data.get("start_time") or data.get("new_start_time"),
                        new_staff_id=data.get("staff_id") or data.get("new_staff_id"),
                        tenant_id=context.tenant_id or "default",
                    )
                    if not res.get("success"):
                        return MCPResponse(success=False, resource=resource, operation=operation, error=res.get("error"), error_code="WRITE_ERROR")
                    res_data = [res.get("data")]
                elif operation_lower == "delete":
                    if not filters:
                        raise ValueError("Filters required to locate appointment for cancellation.")
                    appt_id = filters.get("id")
                    res = svc.cancel(
                        appointment_id=str(appt_id),
                        tenant_id=context.tenant_id or "default",
                    )
                    if not res.get("success"):
                        return MCPResponse(success=False, resource=resource, operation=operation, error=res.get("error"), error_code="WRITE_ERROR")
                    res_data = []
                else:
                    raise ValueError(f"Unsupported write operation on appointments: '{operation}'")

            elif resource_lower == "reviews":
                from application.services.review_service import ReviewService
                if operation_lower == "insert":
                    if not data:
                        raise ValueError("No data provided for review submission.")
                    res = ReviewService.submit_review(
                        db=db,
                        customer_id=data.get("customer_id"),
                        rating=int(data.get("rating", 5)),
                        comment=data.get("comment") or data.get("review_text", ""),
                        appointment_id=data.get("appointment_id"),
                        staff_id=data.get("staff_id"),
                    )
                    if not res.get("success"):
                        return MCPResponse(success=False, resource=resource, operation=operation, error=res.get("error"), error_code="WRITE_ERROR")
                    res_data = [res]
                elif operation_lower == "update":
                    if not filters:
                        raise ValueError("Filters required to locate review.")
                    review_id = filters.get("id")
                    if data and (data.get("ai_response") or data.get("custom_response")):
                        res = ReviewService.generate_response(
                            db=db,
                            review_id=str(review_id),
                            custom_response=data.get("custom_response") or data.get("ai_response"),
                        )
                    elif data and data.get("escalation_required"):
                        res = ReviewService.escalate_review(
                            db=db,
                            review_id=str(review_id),
                        )
                    else:
                        res = {"success": True, "message": "No specific review action requested."}
                    if not res.get("success"):
                        return MCPResponse(success=False, resource=resource, operation=operation, error=res.get("error"), error_code="WRITE_ERROR")
                    res_data = [res]
                else:
                    raise ValueError(f"Unsupported write operation on reviews: '{operation}'")

            elif resource_lower == "leads" and operation_lower == "update" and data and (
                data.get("send_followup") or data.get("status") == "CONTACTED"
            ):
                from application.services.lead_service import send_lead_followup
                if not filters:
                    raise ValueError("Filters required to locate lead.")
                lead_id = filters.get("id")
                res = send_lead_followup(
                    lead_id=uuid.UUID(str(lead_id)),
                    db=db,
                )
                if not res.get("success"):
                    return MCPResponse(success=False, resource=resource, operation=operation, error=res.get("error"), error_code="WRITE_ERROR")
                res_data = [res]
            else:
                # 4. Fallback for direct database writes of other resources
                if operation_lower == "insert":
                    if not data:
                        raise ValueError("No data provided for insert operation.")
                    
                    processed_data = {}
                    for k, v in data.items():
                        if (k == "id" or k.endswith("_id")) and isinstance(v, str) and v:
                            try:
                                processed_data[k] = uuid.UUID(v)
                            except ValueError:
                                processed_data[k] = v
                        else:
                            processed_data[k] = v

                    if "id" not in processed_data:
                        processed_data["id"] = uuid.uuid4()
                    elif isinstance(processed_data["id"], str):
                        processed_data["id"] = uuid.UUID(processed_data["id"])

                    db_obj = model_class(**processed_data)
                    db.add(db_obj)
                    db.commit()
                    db.refresh(db_obj)
                    res_data = [_model_to_dict(db_obj)]

                elif operation_lower == "update":
                    if not filters or not data:
                        raise ValueError("Filters and data required for update.")

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
                else:
                    raise ValueError(f"Unsupported write operation: '{operation}'")

            error_msg = None

            elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)
            
            # Log audit and metrics
            self.audit_logger.log_action(
                user_id=context.user_id,
                role=role_str,
                agent_name=agent_name,
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
                agent_name=agent_name,
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

