import uuid
from typing import Any, Optional

def test_check_staff_access(context: str, target_staff_id: Any) -> Optional[str]:
    try:
        target_uuid = uuid.UUID(str(target_staff_id))
    except ValueError:
        return "invalid target uuid"
        
    logged_in_id = None
    logged_in_role = None
    
    if "ID: " in context:
        try:
            parts = context.split("ID: ")
            if len(parts) > 1:
                logged_in_id = parts[1].split(",")[0].strip()
        except Exception as e:
            return f"id parsing error: {e}"
            
    if "Role: " in context:
        try:
            parts = context.split("Role: ")
            if len(parts) > 1:
                logged_in_role = parts[1].split(",")[0].strip().upper()
        except Exception as e:
            return f"role parsing error: {e}"
            
    print(f"Parsed logged_in_id: {logged_in_id}")
    print(f"Parsed logged_in_role: {logged_in_role}")
    
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
        except Exception as e:
            return f"uuid conversion error: {e}"
            
    return "allowed"

context = (
    "[SYSTEM TIME CONTEXT: Current system time is 2026-06-06 12:00:00 (Today is Saturday, June 06, 2026).]\n"
    "[SYSTEM STAFF CONTEXT: The user chatting with you is logged in as Staff member 'Priya Sharma' (ID: af91c917-dab8-4fb4-8645-c8fa3b5f4264, Role: Hair Specialist, Branch ID: 'default'). Use this Staff ID (af91c917-dab8-4fb4-8645-c8fa3b5f4264) when they query their own schedule, revenue, performance, or leaves. If they ask about another staff member's details, resolve the correct staff ID using list_available_staff or by name, and do NOT use the logged-in user's Staff ID. Do NOT ask them for their ID.]"
)
target_id = "87129b93-bd7f-4680-b8b5-3f1d5466b08e"

res = test_check_staff_access(context, target_id)
print(f"Result: {res}")
