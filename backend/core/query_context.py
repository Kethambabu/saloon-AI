import contextvars
import uuid
from typing import Any, Optional

_query_context = contextvars.ContextVar("query_context", default="")

def set_query_context(context: str) -> None:
    """Set the current query context for the active thread/coroutine."""
    _query_context.set(context)

def get_query_context() -> str:
    """Retrieve the current query context for the active thread/coroutine."""
    return _query_context.get()

def check_staff_access(target_staff_id: Any) -> Optional[str]:
    """
    Check if the currently logged-in user has permission to access the target staff details.
    Regular staff can only access their own details.
    """
    try:
        target_uuid = uuid.UUID(str(target_staff_id))
    except ValueError:
        return None  # Let it fail downstream in resolver
        
    context = get_query_context()
    if not context:
        # Fallback to class-level tracking variables in case ContextVar is lost in AutoGen thread/task pool
        fallback_contexts = []
        try:
            from ai.agents.receptionist_agent import ReceptionistAgent
            fallback_contexts.append(getattr(ReceptionistAgent, "CURRENT_QUERY_CONTEXT", "") or "")
        except ImportError:
            pass
        try:
            from ai.agents.staff_assistant_agent import StaffAssistantAgent
            fallback_contexts.append(getattr(StaffAssistantAgent, "CURRENT_QUERY_CONTEXT", "") or "")
        except ImportError:
            pass
        context = "\n".join([c for c in fallback_contexts if c])
        
    if not context:
        return None  # Allow if no context is set (e.g., manual backend tests/scripts)
        
    logged_in_id = None
    logged_in_role = None
    
    if "ID: " in context:
        try:
            parts = context.split("ID: ")
            if len(parts) > 1:
                logged_in_id = parts[1].split(",")[0].strip()
        except Exception:
            pass
            
    if "Role: " in context:
        try:
            parts = context.split("Role: ")
            if len(parts) > 1:
                logged_in_role = parts[1].split(",")[0].strip().upper()
        except Exception:
            pass
            
    if logged_in_id:
        try:
            logged_in_uuid = uuid.UUID(logged_in_id)
            # If not admin/manager/owner, enforce matching ID
            allowed_roles = ["ADMIN", "MANAGER", "OWNER"]
            is_privileged = False
            if logged_in_role:
                for role in allowed_roles:
                    if role in logged_in_role:
                        is_privileged = True
                        break
            
            if not is_privileged and logged_in_uuid != target_uuid:
                return "Access denied. You do not have permission to view details of other staff members."
        except Exception:
            pass
            
    return None

