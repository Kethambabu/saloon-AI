
"""
AI Receptionist Agent for SalonAI Workforce Platform.
Built using Microsoft AutoGen.
Provides professional booking automation with discovery tools and intelligent entity resolution.
"""

import os
import logging
import time
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple

# AutoGen modern imports
from autogen_agentchat.agents import AssistantAgent
from core.openai_client_adapter import OpenAIChatCompletionClient

# Project imports
from agents import Agent
from core.config import get_settings
from core.llm_config import get_llm_config
from tools.booking_tools import (
    create_appointment,
    get_available_slots,
    cancel_appointment,
    reschedule_appointment,
    get_customer_history,
)
from tools.discovery_tools import (
    list_available_branches,
    list_available_services,
    list_available_staff,
    search_for_customers,
)
from db.database import SessionLocal
from utils.entity_resolver import (
    resolve_branch,
    resolve_customer,
    resolve_service,
    resolve_staff,
)
from db import Branch, Customer, Service, Staff

logger = logging.getLogger(__name__)


def compress_history_for_prompt(history_data: Any) -> str:
    """
    Compresses booking history data to make it extremely compact for the LLM prompt context,
    preventing token bloat while keeping all critical semantic details.
    """
    if not history_data:
        return "No history available."

    import json
    import ast

    data = None
    if isinstance(history_data, str):
        raw_clean = history_data.strip()
        try:
            data = ast.literal_eval(raw_clean)
        except Exception:
            try:
                data = json.loads(raw_clean)
            except Exception:
                pass
    elif isinstance(history_data, dict):
        data = history_data

    if not isinstance(data, dict):
        return str(history_data)

    history = data.get("history", [])
    if not history:
        return "No past styling appointments on record."

    total_count = len(history)
    completed_count = sum(1 for a in history if str(a.get("status")).upper() == "COMPLETED")
    cancelled_count = sum(1 for a in history if str(a.get("status")).upper() == "CANCELLED")
    confirmed_count = sum(1 for a in history if str(a.get("status")).upper() == "CONFIRMED")

    total_spent = sum(float(a.get("service_price") or 0.0) for a in history if str(a.get("status")).upper() == "COMPLETED")

    compressed_records = []
    # Keep details for the 8 most recent appointments to prevent prompt token bloat
    for appt in history[:8]:
        start_time = appt.get("start_time", "")
        date_part = start_time.split("T")[0] if "T" in start_time else start_time
        time_part = ""
        if "T" in start_time:
            time_part = start_time.split("T")[1][:5]

        compressed_records.append({
            "id": appt.get("appointment_id"),
            "date": date_part,
            "time": time_part,
            "service": appt.get("service_name"),
            "price": appt.get("service_price"),
            "stylist": appt.get("staff_name"),
            "status": appt.get("status")
        })

    compressed_data = {
        "customer_name": data.get("customer_name"),
        "total_appointments": total_count,
        "completed": completed_count,
        "cancelled": cancelled_count,
        "confirmed": confirmed_count,
        "total_spent_on_completed": total_spent,
        "recent_appointments": compressed_records
    }

    if total_count > 8:
        compressed_data["note"] = f"Showing 8 most recent appointments of {total_count} total appointments. Older appointments are omitted."

    return json.dumps(compressed_data, indent=2)


def _is_valid_uuid(val: Any) -> bool:
    """Verify if value is a valid UUID."""
    try:
        import uuid
        uuid.UUID(str(val))
        return True
    except ValueError:
        return False


def _is_placeholder_value(value: Any) -> bool:
    """Detect if an identifier is a placeholder/hallucinated value from LLM."""
    if value is None or value == "":
        return False
    value_str = str(value).strip().lower()
    placeholders = {
        "first_branch_id", "first_service_id", "first_staff_id", "first_customer_id",
        "second_branch_id", "second_service_id", "second_staff_id", 
        "default_branch_id", "default_service_id", "default_staff_id",
        "placeholder", "first", "second", "default", "example", "test",
        "branch_id", "service_id", "staff_id", "customer_id", "appointment_id",
        "your_branch", "your_service", "your_staff", "your_customer",
        "select_branch", "select_service", "select_staff",
        "none_specified", "not_specified", "unspecified", "any", "none", "null", "undefined"
    }
    if value_str in placeholders:
        return True
    if any(p in value_str for p in ["first_", "second_", "default_", "select_", "example_", "your_", "xxxx", "1111", "0000"]):
        return True
    return False


def get_query_base_date() -> str:
    """Extract system date from current query context."""
    context = getattr(ReceptionistAgent, "CURRENT_QUERY_CONTEXT", "")
    if "[SYSTEM TIME CONTEXT:" in context:
        try:
            parts = context.split("Current system time is ")
            if len(parts) > 1:
                dt_str = parts[1].split()[0]
                return dt_str
        except Exception:
            pass
    return datetime.utcnow().strftime("%Y-%m-%d")


def get_query_customer_id() -> Optional[str]:
    """Extract logged-in customer ID from system context."""
    context = getattr(ReceptionistAgent, "CURRENT_QUERY_CONTEXT", "")
    if "[SYSTEM CUSTOMER CONTEXT:" in context:
        try:
            parts = context.split("ID: ")
            if len(parts) > 1:
                cust_id = parts[1].split(",")[0].strip()
                return cust_id
        except Exception:
            pass
    return None


def get_query_system_datetime() -> Optional[datetime]:
    """Extract full system datetime from current query context."""
    context = getattr(ReceptionistAgent, "CURRENT_QUERY_CONTEXT", "")
    if "[SYSTEM TIME CONTEXT:" in context:
        try:
            parts = context.split("Current system time is ")
            if len(parts) > 1:
                tokens = parts[1].split()
                if len(tokens) > 1:
                    dt_str = f"{tokens[0]} {tokens[1].split('(')[0].split(')')[0]}"
                    return datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
        except Exception:
            pass
    return None


def adjust_past_date_today(date_str: str, time_str: str) -> str:
    """Do not adjust past times/dates to tomorrow. Return the requested date as-is so validation stops the process."""
    return date_str


def repair_date(date_input: Any) -> str:
    """Automatically resolve relative date keywords and absolute date strings (e.g., 'june 8th 2026', '08-06-2026') to YYYY-MM-DD."""
    if not date_input:
        return get_query_base_date()
    
    date_str = str(date_input).strip()
    if _is_valid_uuid(date_str):
        return get_query_base_date()
        
    import re
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        return date_str
        
    base_date_str = get_query_base_date()
    try:
        base_date = datetime.strptime(base_date_str, "%Y-%m-%d")
    except Exception:
        base_date = datetime.utcnow()
        
    date_clean = date_str.lower()
    
    if "today" in date_clean:
        return base_date.strftime("%Y-%m-%d")
    elif "day after tomorrow" in date_clean:
        target = base_date + timedelta(days=2)
        return target.strftime("%Y-%m-%d")
    elif "tomorrow" in date_clean:
        tomorrow = base_date + timedelta(days=1)
        return tomorrow.strftime("%Y-%m-%d")
    elif "next week" in date_clean:
        next_week = base_date + timedelta(days=7)
        return next_week.strftime("%Y-%m-%d")
        
    days = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}
    for day_name, day_idx in days.items():
        if day_name in date_clean:
            days_ahead = day_idx - base_date.weekday()
            if days_ahead <= 0:
                days_ahead += 7
            target = base_date + timedelta(days=days_ahead)
            return target.strftime("%Y-%m-%d")
            
    # Try parsing month names (e.g. "june 8th 2026", "June 8, 2026")
    months = {
        "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, 
        "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
    }
    
    found_month = None
    for m_name, m_val in months.items():
        if re.search(r"\b" + re.escape(m_name) + r"\b", date_clean):
            found_month = m_val
            break
            
    if found_month:
        text_without_month = re.sub(r"\b" + re.escape(m_name) + r"\b", "", date_clean)
        digits = re.findall(r"\d+", text_without_month)
        day = None
        year = base_date.year
        for d in digits:
            val = int(d)
            if 1 <= val <= 31:
                if day is None:
                    day = val
                elif val > 31 and val > 1900:
                    year = val
            elif val > 1900:
                year = val
        if day is not None:
            return f"{year:04d}-{found_month:02d}-{day:02d}"

    # Try matching common numeric patterns like "08-06-2026", "8/6/26", etc.
    num_str = re.sub(r"\s+", "", date_clean)
    match_dmy = re.match(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$", num_str)
    if match_dmy:
        day = int(match_dmy.group(1))
        month = int(match_dmy.group(2))
        year = int(match_dmy.group(3))
        if 1 <= month <= 12 and 1 <= day <= 31:
            return f"{year:04d}-{month:02d}-{day:02d}"
            
    match_ymd = re.match(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$", num_str)
    if match_ymd:
        year = int(match_ymd.group(1))
        month = int(match_ymd.group(2))
        day = int(match_ymd.group(3))
        if 1 <= month <= 12 and 1 <= day <= 31:
            return f"{year:04d}-{month:02d}-{day:02d}"

    return base_date.strftime("%Y-%m-%d")


def repair_time(time_input: Any) -> str:
    """Convert relative time slots (e.g. 5pm, 3-4pm, 3-4pm slot) to standard HH:MM format (start time)."""
    if not time_input:
        return "17:00"
        
    time_str = str(time_input).strip()
    import re
    
    # Already in HH:MM format
    if re.match(r"^\d{2}:\d{2}$", time_str):
        return time_str
    if re.match(r"^\d{2}:\d{2}:\d{2}$", time_str):
        return time_str[:5]
        
    time_clean = time_str.lower().replace(" ", "")
    is_pm = "pm" in time_clean
    is_am = "am" in time_clean
    
    # Handle time ranges like "3-4pm", "3-4", "03-04pm", etc.
    # Extract ONLY the first number for the start time
    time_no_text = re.sub(r"[^0-9:\-]", "", time_clean)
    
    # Split by dash/hyphen to get the start time (first part)
    if "-" in time_no_text:
        start_part = time_no_text.split("-")[0]
    else:
        start_part = time_no_text
    
    # Extract digits from the start part
    digits = "".join([c for c in start_part if c.isdigit() or c == ":"])
    
    if ":" in digits:
        parts = digits.split(":")
        try:
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
        except ValueError:
            hour, minute = 12, 0
    else:
        try:
            hour = int(digits) if digits else 12
            minute = 0
        except ValueError:
            hour, minute = 12, 0
    
    # Handle AM/PM
    if is_pm and hour < 12:
        hour += 12
    elif is_am and hour == 12:
        hour = 0
        
    hour = max(0, min(23, hour))
    minute = max(0, min(59, minute))
    return f"{hour:02d}:{minute:02d}"


def repair_branch(branch_id: Any) -> str:
    """Validate and resolve branch UUID."""
    if not branch_id or _is_placeholder_value(branch_id):
        db = SessionLocal()
        try:
            first_b = db.query(Branch).filter(Branch.is_active == True).first()
            if first_b:
                return str(first_b.id)
        finally:
            db.close()
        return "4f3d1b64-884c-4c6e-a342-6a0b985c4bf1"
        
    db = SessionLocal()
    try:
        resolved = resolve_branch(branch_id, db, raise_on_missing=False)
        if resolved:
            return str(resolved)
        first_b = db.query(Branch).filter(Branch.is_active == True).first()
        return str(first_b.id) if first_b else str(branch_id)
    finally:
        db.close()


def repair_service(service_id: Any) -> str:
    """Validate and resolve service UUID."""
    if not service_id or _is_placeholder_value(service_id):
        db = SessionLocal()
        try:
            first_s = db.query(Service).filter(Service.is_active == True).first()
            if first_s:
                return str(first_s.id)
        finally:
            db.close()
        return "s1"
        
    db = SessionLocal()
    try:
        resolved = resolve_service(service_id, db, raise_on_missing=False)
        if resolved:
            return str(resolved)
        first_s = db.query(Service).filter(Service.is_active == True).first()
        return str(first_s.id) if first_s else str(service_id)
    finally:
        db.close()


def repair_staff(staff_id: Any, branch_id: str = None) -> Optional[str]:
    """Validate and resolve staff UUID."""
    if not staff_id or _is_placeholder_value(staff_id) or str(staff_id).lower() in ["any", "none", "auto", "default"]:
        return None
        
    db = SessionLocal()
    try:
        resolved = resolve_staff(staff_id, db, raise_on_missing=False)
        if resolved:
            return str(resolved)
        return None
    finally:
        db.close()


def repair_customer(customer_id: Any) -> str:
    """Validate and resolve customer UUID."""
    sys_cust_id = get_query_customer_id()
    if sys_cust_id:
        return sys_cust_id
        
    if not customer_id or _is_placeholder_value(customer_id):
        db = SessionLocal()
        try:
            first_c = db.query(Customer).filter(Customer.is_active == True).first()
            if first_c:
                return str(first_c.id)
        finally:
            db.close()
        return "577186c8-5084-40f0-ad9a-627d395420fb"
        
    db = SessionLocal()
    try:
        resolved = resolve_customer(customer_id, db, raise_on_missing=False)
        if resolved:
            return str(resolved)
        first_c = db.query(Customer).filter(Customer.is_active == True).first()
        return str(first_c.id) if first_c else str(customer_id)
    finally:
        db.close()


def _get_customer_memory(customer_id: str) -> Tuple[str, Optional[str], Optional[str]]:
    """Retrieve warm welcome-back string with preferred stylist and service counts from SQLite history (Priority 7)."""
    if not customer_id or _is_placeholder_value(customer_id):
        return "Welcome back valued client!", None, None
    db = SessionLocal()
    try:
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        name = customer.first_name if customer else "valued client"
        
        # Load completed appointments to count preferences
        from db.models import Appointment, AppointmentStatus
        appts = db.query(Appointment).filter(
            Appointment.customer_id == customer_id,
            Appointment.status == AppointmentStatus.COMPLETED
        ).all()
        
        if not appts:
            return f"Welcome back {name}!", None, None
            
        total_visits = len(appts)
        last_visit_str = "N/A"
        if appts:
            sorted_appts = sorted(appts, key=lambda a: a.start_time, reverse=True)
            last_visit_str = sorted_appts[0].start_time.strftime("%B %d, %Y")
            
        services_counts = {}
        staff_counts = {}
        for a in appts:
            services_counts[a.service_id] = services_counts.get(a.service_id, 0) + 1
            if a.staff_id:
                staff_counts[a.staff_id] = staff_counts.get(a.staff_id, 0) + 1
                
        pref_service_name = None
        pref_staff_name = None
        
        if services_counts:
            top_service_id = max(services_counts, key=services_counts.get)
            top_service = db.query(Service).filter(Service.id == top_service_id).first()
            if top_service:
                pref_service_name = top_service.name
                
        if staff_counts:
            top_staff_id = max(staff_counts, key=staff_counts.get)
            top_staff = db.query(Staff).filter(Staff.id == top_staff_id).first()
            if top_staff:
                pref_staff_name = f"{top_staff.first_name} {top_staff.last_name}"
                
        pref_str = f"Welcome back {name}."
        pref_str += f"\nTotal Visits: {total_visits} | Last Visit: {last_visit_str}"
        if pref_staff_name:
            pref_str += f"\nPreferred Stylist: {pref_staff_name}"
        if pref_service_name:
            pref_str += f"\nPreferred Service: {pref_service_name}"
            
        return pref_str, pref_service_name, pref_staff_name
    except Exception:
        return "Welcome back!", None, None
    finally:
        db.close()


def find_matching_active_appointment(customer_id: str, intent_json: Dict[str, Any], query_text: str) -> Optional[str]:
    """
    Intelligently searches the database for a customer's active appointment (CONFIRMED or PENDING)
    that matches the provided criteria (service, branch, stylist, date, time) to resolve contexts.
    """
    if not customer_id:
        return None
        
    db = SessionLocal()
    try:
        from db import Appointment, AppointmentStatus, Service, Branch, Staff
        
        # Get all confirmed or pending appointments for this customer
        appts = db.query(Appointment).filter(
            Appointment.customer_id == customer_id,
            Appointment.status.in_([AppointmentStatus.CONFIRMED, AppointmentStatus.PENDING])
        ).all()
        
        if not appts:
            return None
            
        # Parse targets from intent_json
        target_service_id = None
        target_branch_id = None
        target_staff_id = None
        target_date = None
        target_time = None
        
        if intent_json.get("service"):
            try:
                target_service_id = resolve_service(intent_json.get("service"), db, raise_on_missing=False)
            except Exception:
                pass
        if intent_json.get("branch"):
            try:
                target_branch_id = resolve_branch(intent_json.get("branch"), db, raise_on_missing=False)
            except Exception:
                pass
        if intent_json.get("stylist"):
            try:
                target_staff_id = resolve_staff(intent_json.get("stylist"), db, raise_on_missing=False)
            except Exception:
                pass
                
        if intent_json.get("date"):
            try:
                target_date = repair_date(intent_json.get("date"))
            except Exception:
                pass
        if intent_json.get("time"):
            try:
                target_time = repair_time(intent_json.get("time"))
            except Exception:
                pass
                
        query_lower = query_text.lower()
        best_appt = None
        best_score = -1
        
        for appt in appts:
            score = 0
            
            # Compare service
            if target_service_id and appt.service_id == target_service_id:
                score += 10
            elif intent_json.get("service") and intent_json.get("service").lower() in appt.service.name.lower():
                score += 8
            elif appt.service.name.lower() in query_lower:
                score += 5
                
            # Compare branch
            if target_branch_id and appt.branch_id == target_branch_id:
                score += 10
            elif intent_json.get("branch") and intent_json.get("branch").lower() in appt.branch.name.lower():
                score += 8
            elif appt.branch.name.lower() in query_lower:
                score += 5
                
            # Compare staff
            if target_staff_id and appt.staff_id == target_staff_id:
                score += 10
            elif intent_json.get("stylist") and appt.staff and intent_json.get("stylist").lower() in appt.staff.full_name.lower():
                score += 8
            elif appt.staff and appt.staff.full_name.lower() in query_lower:
                score += 5
                
            # Compare date
            appt_date_str = appt.start_time.strftime("%Y-%m-%d")
            if target_date and appt_date_str == target_date:
                score += 15
            elif intent_json.get("date") and str(intent_json.get("date")) in query_lower:
                score += 10
                
            # Compare time
            appt_time_str = appt.start_time.strftime("%H:%M")
            if target_time and appt_time_str == target_time:
                score += 15
            elif intent_json.get("time") and str(intent_json.get("time")) in query_lower:
                score += 10
                
            if score > best_score:
                best_score = score
                best_appt = appt
                
        if best_appt and best_score >= 10:
            return str(best_appt.id)
            
        # Fallback to the most recently created confirmed appointment
        sorted_appts = sorted(appts, key=lambda a: a.created_at if hasattr(a, "created_at") else a.start_time, reverse=True)
        if sorted_appts:
            return str(sorted_appts[0].id)
            
        return None
    except Exception as e:
        logger.warning(f"Error in find_matching_active_appointment: {e}")
        return None
    finally:
        db.close()


def format_receptionist_tool_output(intent: str, raw_res_str: str) -> str:
    """
    Format raw JSON or single quoted dict representations of tool outputs to beautiful, clear, natural language.
    """
    if not raw_res_str:
        return "Your request has been successfully processed."
        
    raw_res_clean = raw_res_str.strip()
    
    data = None
    if raw_res_clean.startswith("{") or raw_res_clean.startswith("[") or raw_res_clean.startswith("{'"):
        import ast
        try:
            data = ast.literal_eval(raw_res_clean)
        except Exception:
            try:
                import json
                data = json.loads(raw_res_clean)
            except Exception:
                pass
                
    if not isinstance(data, dict):
        if "error" in raw_res_str.lower() and "cancelled" in raw_res_str.lower():
            return "I apologize, but we cannot reschedule a cancelled appointment. Please book a new styling session instead."
        return raw_res_str
        
    if intent == "cancel":
        if data.get("success"):
            return "Your appointment has been successfully cancelled. The database has been updated accordingly."
        else:
            err = data.get("error") or "Cancellation failed."
            return f"I apologize, but we encountered an issue cancelling your appointment: {err}"
            
    elif intent == "reschedule":
        if data.get("success"):
            start_str = data.get("start_time", "")
            try:
                dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                nice_dt = dt.strftime("%A, %B %d, %Y at %I:%M %p")
            except Exception:
                nice_dt = start_str
            return f"Your appointment has been successfully rescheduled to {nice_dt}."
        else:
            err = data.get("error") or "Rescheduling failed."
            if "cancelled" in str(err).lower():
                return "I apologize, but we cannot reschedule a cancelled appointment. Please book a new styling session instead."
            return f"I apologize, but we encountered an issue rescheduling your appointment: {err}"
            
    elif intent == "history":
        history = data.get("history", [])
        if not history:
            return "You do not have any past styling appointments on record with us."
        
        lines = []
        for appt in history:
            start_str = appt.get("start_time", "")
            try:
                dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                nice_time = dt.strftime("%B %d, %Y at %I:%M %p")
            except Exception:
                nice_time = start_str
                
            svc = appt.get("service_name") or "Styling Treatment"
            staff = appt.get("staff_name") or "Professional Stylist"
            branch = appt.get("branch_name") or "SalonAI Lounge"
            status = appt.get("status", "CONFIRMED").upper()
            
            lines.append(f"• **{svc}** with {staff} at our {branch} lounge on {nice_time} ({status})")
            
        return "Here is your styling history:\n" + "\n".join(lines)
        
    elif intent == "availability":
        if data.get("staff_on_leave"):
            staff_name = data.get("staff_name") or "The requested stylist"
            date_str = data.get("date", "your selected date")
            slots = data.get("slots", [])
            if not slots:
                return f"{staff_name} is on leave on {date_str}. Please choose another staff member. Unfortunately, no other stylists are available on this date."
            
            lines = []
            for slot in slots:
                start_str = slot.get("start_time", "")
                try:
                    dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                    nice_time = dt.strftime("%I:%M %p")
                except Exception:
                    nice_time = start_str
                names = slot.get("available_staff_names", [])
                if names:
                    lines.append(f"• {nice_time} (Available: {', '.join(names)})")
                else:
                    lines.append(f"• {nice_time}")
            
            return f"{staff_name} is on leave on {date_str}. Please choose another staff member. Here are the available stylists and their slots:\n" + "\n".join(lines)

        slots = data.get("slots", [])
        if not slots:
            return f"I'm sorry, but there are no available slots for {data.get('date', 'your selected date')}."
        
        lines = []
        for slot in slots:
            start_str = slot.get("start_time", "")
            try:
                dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                nice_time = dt.strftime("%I:%M %p")
            except Exception:
                nice_time = start_str
            lines.append(nice_time)
            
        return f"The following slots are available for your selected styling session: {', '.join(lines)}."
        
    return raw_res_str


# ============================================================================
# INTERCEPTOR WRAPPER TOOLS WITH AUTO-SANITIZATION & TIMEOUTS
# ============================================================================

def sanitize_tool_arguments(func_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize tool arguments to only keep parameters approved by the schema.
    Removes unknown fields, invalid properties, and extra keys.
    """
    import inspect
    func_obj = globals().get(func_name)
    if not func_obj:
        return arguments
    try:
        sig = inspect.signature(func_obj)
        valid_params = set(sig.parameters.keys())
        return {k: v for k, v in arguments.items() if k in valid_params}
    except Exception:
        return arguments


def get_available_branches() -> str:
    """
    Discover all available branches at SalonAI before booking.
    Use this to learn which branches exist and their names/codes.
    """
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(list_available_branches)
        try:



            return future.result(timeout=25.0)
        except concurrent.futures.TimeoutError:
            return "Error: Tool execution timed out."


def get_available_services() -> str:
    """
    Discover all available services at SalonAI before booking.
    Use this to learn service options, pricing, and duration.
    """
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(list_available_services)
        try:
            return future.result(timeout=25.0)
        except concurrent.futures.TimeoutError:
            return "Error: Tool execution timed out."


def get_available_staff(branch_id: Optional[str] = None) -> str:
    """
    Discover all available stylists/staff members.
    Optionally filter by a specific branch.
    """
    import concurrent.futures
    repaired_branch = repair_branch(branch_id) if branch_id else None
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(list_available_staff, repaired_branch)
        try:
            return future.result(timeout=25.0)
        except concurrent.futures.TimeoutError:
            return "Error: Tool execution timed out."


def search_customers(customer_query: str) -> str:
    """
    Search for existing customers in the system before booking.
    Use this to find and verify customer identity by name, email, or phone.
    """
    import concurrent.futures
    if not customer_query or _is_placeholder_value(customer_query):
        sys_cust = get_query_customer_id()
        if sys_cust:
            customer_query = sys_cust
        else:
            customer_query = "customer@example.com"
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(search_for_customers, customer_query)
        try:
            return future.result(timeout=25.0)
        except concurrent.futures.TimeoutError:
            return "Error: Tool execution timed out."


def check_stylist_availability(
    branch_id: str,
    date: str,
    staff_id: Optional[str] = None,
    service_id: Optional[str] = None
) -> str:
    """
    Check available time slots for salon appointments.
    """
    import concurrent.futures
    def run():
        repaired_branch = repair_branch(branch_id)
        repaired_date = repair_date(date)
        repaired_staff = repair_staff(staff_id, repaired_branch)
        repaired_service = repair_service(service_id)
        return get_available_slots(
            branch_id=repaired_branch,
            date_str=repaired_date,
            staff_id=repaired_staff,
            service_id=repaired_service
        )
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run)
        try:
            return str(future.result(timeout=25.0))
        except concurrent.futures.TimeoutError:
            return "Error: Tool execution timed out."


def book_new_appointment(
    customer_id: str,
    branch_id: str,
    service_id: str,
    start_time: str,
    staff_id: Optional[str] = None,
    notes: Optional[str] = None
) -> str:
    """
    Create and confirm a new salon booking appointment.
    """
    import concurrent.futures
    def run():
        repaired_cust = repair_customer(customer_id)
        repaired_branch = repair_branch(branch_id)
        repaired_service = repair_service(service_id)
        repaired_staff = repair_staff(staff_id, repaired_branch)
        
        dt_str = str(start_time).strip()
        try:
            if "t" not in dt_str.lower():
                rep_d = repair_date(dt_str)
                rep_t = repair_time(dt_str)
                rep_d = adjust_past_date_today(rep_d, rep_t)
                repaired_time_str = f"{rep_d}T{rep_t}:00Z"
            else:
                parts = dt_str.split("T")
                rep_d = repair_date(parts[0])
                rep_t = repair_time(parts[1])
                rep_d = adjust_past_date_today(rep_d, rep_t)
                repaired_time_str = f"{rep_d}T{rep_t}:00"
                if not repaired_time_str.endswith("Z") and not "+" in repaired_time_str:
                    repaired_time_str += "Z"
        except Exception:
            repaired_time_str = f"{repair_date(None)}T17:00:00Z"
            
        return create_appointment(
            customer_id=repaired_cust,
            branch_id=repaired_branch,
            service_id=repaired_service,
            start_time=repaired_time_str,
            staff_id=repaired_staff,
            notes=notes
        )
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run)
        try:
            return str(future.result(timeout=25.0))
        except concurrent.futures.TimeoutError:
            return "Error: Tool execution timed out."


def cancel_existing_appointment(appointment_id: str) -> str:
    """
    Cancel an existing salon booking.
    """
    import concurrent.futures
    def run():
        appt_str = str(appointment_id).strip() if appointment_id else ""
        repaired_appt = appt_str
        
        if not appt_str or _is_placeholder_value(appt_str) or not _is_valid_uuid(appt_str):
            sys_c = get_query_customer_id()
            if sys_c:
                db = SessionLocal()
                try:
                    from db import Appointment, AppointmentStatus
                    active_appts = db.query(Appointment).filter(
                        Appointment.customer_id == sys_c,
                        Appointment.status.in_([AppointmentStatus.CONFIRMED, AppointmentStatus.PENDING])
                    ).order_by(Appointment.created_at.desc()).all()
                    if active_appts:
                        repaired_appt = str(active_appts[0].id)
                finally:
                    db.close()
                    
        sys_c = get_query_customer_id()
        return cancel_appointment(appointment_id=repaired_appt, customer_id=sys_c)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run)
        try:
            return str(future.result(timeout=25.0))
        except concurrent.futures.TimeoutError:
            return "Error: Tool execution timed out."


def reschedule_existing_appointment(appointment_id: str, new_start_time: str) -> str:
    """
    Reschedule an existing booking to a new date/time.
    """
    import concurrent.futures
    def run():
        appt_str = str(appointment_id).strip() if appointment_id else ""
        repaired_appt = appt_str
        
        if not appt_str or _is_placeholder_value(appt_str) or not _is_valid_uuid(appt_str):
            sys_c = get_query_customer_id()
            if sys_c:
                db = SessionLocal()
                try:
                    from db import Appointment, AppointmentStatus
                    active_appts = db.query(Appointment).filter(
                        Appointment.customer_id == sys_c,
                        Appointment.status.in_([AppointmentStatus.CONFIRMED, AppointmentStatus.PENDING])
                    ).order_by(Appointment.created_at.desc()).all()
                    if active_appts:
                        repaired_appt = str(active_appts[0].id)
                finally:
                    db.close()
                    
        dt_str = str(new_start_time).strip()
        try:
            if "t" not in dt_str.lower():
                rep_d = repair_date(dt_str)
                rep_t = repair_time(dt_str)
                rep_d = adjust_past_date_today(rep_d, rep_t)
                repaired_time_str = f"{rep_d}T{rep_t}:00Z"
            else:
                parts = dt_str.split("T")
                rep_d = repair_date(parts[0])
                rep_t = repair_time(parts[1])
                rep_d = adjust_past_date_today(rep_d, rep_t)
                repaired_time_str = f"{rep_d}T{rep_t}:00"
                if not repaired_time_str.endswith("Z") and not "+" in repaired_time_str:
                    repaired_time_str += "Z"
        except Exception:
            repaired_time_str = f"{repair_date(None)}T17:00:00Z"
            
        sys_c = get_query_customer_id()
        return reschedule_appointment(appointment_id=repaired_appt, new_start_time=repaired_time_str, customer_id=sys_c)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run)
        try:
            return str(future.result(timeout=25.0))
        except concurrent.futures.TimeoutError:
            return "Error: Tool execution timed out."


def check_customer_booking_history(customer_id: str) -> str:
    """
    Retrieve complete booking history for a specific customer.
    """
    import concurrent.futures
    def run():
        repaired_cust = repair_customer(customer_id)
        return get_customer_history(customer_id=repaired_cust)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run)
        try:
            return str(future.result(timeout=25.0))
        except concurrent.futures.TimeoutError:
            return "Error: Tool execution timed out."


# ============================================================================
# RESPONSE NORMALIZATION LAYER
# ============================================================================

def normalize_response(text: str) -> str:
    """Convert raw system JSON or stack traces into beautiful customer-facing replies."""
    if not text:
        return (
            "I am Clara, your AI Salon Receptionist. I would be delighted to assist you "
            "with booking, rescheduling, or canceling your appointments. Please let me know how I can style your schedule today!"
        )
        
    text_clean = text.strip()
    
    if text_clean.startswith("{") or text_clean.startswith("[") or text_clean.startswith("{'"):
        try:
            import json
            data = json.loads(text_clean)
            if isinstance(data, dict):
                if data.get("success") and "appointment" in str(data).lower():
                    return (
                        f"I have successfully secured your styling appointment! "
                        f"Your booking has been confirmed. Please let me know if you would like to make any other changes!"
                    )
                if data.get("error"):
                    return f"I apologize, but we encountered an issue: {data['error']}. Let's try another time slot or stylist!"
        except Exception:
            pass
            
    replacements = {
        "429": "temporary high volume",
        "rate limit": "temporary slot holds",
        "quota exceeded": "system adjustments",
        "rate_limit_exceeded": "system limits",
        "quota_exceeded": "system limits",
        "uuid": "reference number",
        "UUID": "reference number",
        "db transaction": "booking system",
        "sqlite": "system",
        "postgresql": "system",
        "supabase": "system",
        "tool execution error": "scheduling adjustment",
        "Failed to receive a valid response from Clara": "We are polishing up the details of your appointment",
        "additionalProperties": "parameter alignment"
    }
    
    for tech_term, clean_term in replacements.items():
        if tech_term.lower() in text_clean.lower():
            import re
            text_clean = re.sub(re.escape(tech_term), clean_term, text_clean, flags=re.IGNORECASE)
            
    return text_clean


# ============================================================================
# HYPER-FOCUSED 10-RULE SYSTEM PROMPT (REDUCED BY >50%)
# ============================================================================

RECEPTIONIST_SYSTEM_PROMPT = """You are Clara, a professional AI Salon Receptionist. You manage appointments and salon inquiries.
Absolute Rules:
1. NEVER INVENT DATA: If user provides service, branch, stylist, date, time, price, use those EXACT values. Never alter, replace, or suggest alternatives.
2. BOOKING REQUESTS ARE TOOL TASKS: Immediately execute the appropriate tool. DO NOT CHAT, explain, list services/branches, or greet again.
3. REQUIRED BOOKING FLOW: Extract service, branch, stylist, date, time -> Call check_stylist_availability(). If available, return booking confirmation. If not, offer alternatives.
4. REBOOKING FLOW: On "same appointment", "book again", "same service/stylist", extract last appointment from history. Reuse service, branch, staff, price. Only update changed fields.
5. STRICT EXTRACTION: Extract fields exactly as: {service, branch, stylist, date, time}. No modifications allowed.
6. NO HALLUCINATIONS: Never invent staff, branches, services, prices, availability, appointments, or bookings.
7. CONFIRMATION: Only after tool success, show exactly:
   Appointment Summary
   Service: [Service Name]
   Branch: [Branch Name]
   Stylist: [Stylist Name]
   Date: [YYYY-MM-DD]
   Time: [HH:MM]
   Price: [Price]
   Status: Confirmed
8. AVAILABILITY QUESTIONS: For "Is this slot available?", immediately call availability tool. Do not explain services or suggest options.
9. TOOL FAILURE: If tool fails, output exactly "I could not verify availability right now." Never fake availability.
10. ROLE: You are purely an appointment booking, cancellation, rescheduling, history management, and salon information/policies assistant. Never act as sales or marketing agent.
11. RECEPTIONIST KNOWLEDGE BASE: For any questions about salon policies, business hours/timings, active offers/promotions, refunds, cancellations, FAQs, or general salon information, ALWAYS execute `search_receptionist_knowledge()` first. Never invent timings, policies, or offers. If no information is found in the knowledge base, state exactly: 'I couldn't find that information in the salon knowledge base.'
For every booking-related message, TOOL EXECUTION IS MANDATORY."""


# ============================================================================
# RECEPTIONIST AGENT CLASS WITH SEQUENTIAL COOLDOWN TIMEOUT FALLBACKS
# ============================================================================

# ============================================================================
# KEYWORD-ONLY INTENT SHORTCUT — saves ~200 tokens/call for greetings & FAQs
# ============================================================================

_CHAT_KEYWORDS = [
    "hello", "hi", "hey", "thanks", "thank you", "bye", "goodbye",
    "who are you", "what can you do", "help me", "how are you",
]
_POLICY_KEYWORDS = [
    "policy", "policies", "timings", "hours", "offer", "discount",
    "promotion", "refund", "cancel policy", "faq", "working hours",
    "opening", "closing", "how much", "price list"
]
_HISTORY_KEYWORDS = ["my appointment", "my booking", "past appointment", "history", "previous visit"]
_AVAILABILITY_KEYWORDS = ["available", "availability", "free slot", "open slot", "check slot"]
_BOOK_KEYWORDS = ["book", "schedule", "reserve", "appointment at", "book me", "make appointment"]
_CANCEL_KEYWORDS = ["cancel", "delete appointment", "remove booking"]
_RESCHEDULE_KEYWORDS = ["reschedule", "move appointment", "change appointment", "postpone"]


def _fast_intent_classify(query: str) -> str:
    """
    Lightweight keyword-based intent classifier.
    Returns a detected intent string ('chat', 'policy', 'book', 'cancel',
    'reschedule', 'history', 'availability', or 'unknown' if ambiguous).
    Called BEFORE the LLM extraction to skip the LLM call entirely for obvious inputs.
    """
    q = query.lower()
    if any(kw in q for kw in _CANCEL_KEYWORDS):
        return "cancel"
    if any(kw in q for kw in _RESCHEDULE_KEYWORDS):
        return "reschedule"
    if any(kw in q for kw in _BOOK_KEYWORDS):
        return "book"
    if any(kw in q for kw in _AVAILABILITY_KEYWORDS):
        return "availability"
    if any(kw in q for kw in _HISTORY_KEYWORDS):
        return "history"
    if any(kw in q for kw in _POLICY_KEYWORDS):
        return "policy"
    if any(kw in q for kw in _CHAT_KEYWORDS):
        return "chat"
    return "unknown"


def _select_agent_tools(query: str, intent: str) -> List[Any]:
    """Dynamically select only the necessary tools for this query to minimize token footprint."""
    from tools.receptionist_rag_tools import (
        search_receptionist_knowledge,
        get_active_offers,
        get_business_timings,
        get_cancellation_policy,
        get_refund_policy,
        get_faq_answer,
    )
    
    q = query.lower()
    tools = []
    
    # Intent-specific core tools
    if intent == "book":
        tools.extend([book_new_appointment, check_stylist_availability, get_available_branches, get_available_services, get_available_staff])
    elif intent == "cancel":
        tools.extend([cancel_existing_appointment, check_customer_booking_history])
    elif intent == "reschedule":
        tools.extend([reschedule_existing_appointment, check_stylist_availability, check_customer_booking_history])
    elif intent == "availability":
        tools.extend([check_stylist_availability, get_available_branches, get_available_services, get_available_staff])
    elif intent == "history":
        tools.extend([check_customer_booking_history])
        
    # Dynamic additions based on query keywords
    if any(k in q for k in ["branch", "location", "where", "place", "address", "map"]):
        if get_available_branches not in tools:
            tools.append(get_available_branches)
            
    if any(k in q for k in ["service", "haircut", "color", "massage", "facial", "treatment", "price", "cost", "how much", "menu"]):
        if get_available_services not in tools:
            tools.append(get_available_services)
            
    if any(k in q for k in ["staff", "stylist", "who", "employee", "person", "worker", "team"]):
        if get_available_staff not in tools:
            tools.append(get_available_staff)
            
    if any(k in q for k in ["book", "schedule", "reserve", "appointment"]):
        if book_new_appointment not in tools:
            tools.append(book_new_appointment)
        if check_stylist_availability not in tools:
            tools.append(check_stylist_availability)
            
    if any(k in q for k in ["cancel", "delete", "remove"]):
        if cancel_existing_appointment not in tools:
            tools.append(cancel_existing_appointment)
            
    if any(k in q for k in ["reschedule", "move", "change", "postpone"]):
        if reschedule_existing_appointment not in tools:
            tools.append(reschedule_existing_appointment)
            
    if any(k in q for k in ["history", "previous", "past", "last appointment", "visited", "visits"]):
        if check_customer_booking_history not in tools:
            tools.append(check_customer_booking_history)
            
    if any(k in q for k in ["offer", "discount", "promotion", "deal", "special"]):
        if get_active_offers not in tools:
            tools.append(get_active_offers)
    if any(k in q for k in ["timing", "hour", "open", "close", "time", "when"]):
        if get_business_timings not in tools:
            tools.append(get_business_timings)
    if any(k in q for k in ["cancel policy", "cancellation policy", "rules for cancelling"]):
        if get_cancellation_policy not in tools:
            tools.append(get_cancellation_policy)
    if any(k in q for k in ["refund policy", "refunds", "money back"]):
        if get_refund_policy not in tools:
            tools.append(get_refund_policy)
        
    # Standard safety fallbacks
    if not tools:
        tools = [search_receptionist_knowledge, get_faq_answer]
    else:
        if search_receptionist_knowledge not in tools:
            tools.append(search_receptionist_knowledge)
        if get_faq_answer not in tools:
            tools.append(get_faq_answer)
            
    return tools


class ReceptionistAgent(Agent):
    """
    Salon Receptionist Agent powered by Microsoft AutoGen and multi-tier LLM Fallback chain.
    Provides professional, error-free booking automation.
    """

    MODEL_COOLDOWN: Dict[str, float] = {}  # model_name -> cooldown expiry timestamp
    FAILURE_COUNT = 0
    CIRCUIT_BREAKER_TRIPPED = False
    CIRCUIT_BREAKER_TRIPPED_AT: float = 0.0  # timestamp when circuit tripped
    MAX_FAILURES = 8  # raised from 5 — tolerate a few more errors before tripping
    CIRCUIT_BREAKER_RESET_SECONDS = 300  # auto-reset after 5 minutes

    CURRENT_QUERY_CONTEXT = ""

    def __init__(self, name: str = "Clara", role: str = "AI Salon Receptionist"):
        super().__init__(name=name, role=role)
        logger.info(f"Initializing AI Receptionist Agent '{name}'...")

        llm_config = get_llm_config()
        config = llm_config.get_config()
        
        self.model_client = OpenAIChatCompletionClient(
            model=config["model"],
            api_key=config["api_key"],
            base_url=config["base_url"],
            model_info=config["model_info"],
            timeout=8.0
        )

        from tools.receptionist_rag_tools import (
            search_receptionist_knowledge,
            get_active_offers,
            get_business_timings,
            get_cancellation_policy,
            get_refund_policy,
            get_faq_answer,
        )

        self.assistant = AssistantAgent(
            name=name,
            model_client=self.model_client,
            system_message=RECEPTIONIST_SYSTEM_PROMPT,
            tools=[
                get_available_branches,
                get_available_services,
                get_available_staff,
                search_customers,
                check_stylist_availability,
                book_new_appointment,
                cancel_existing_appointment,
                reschedule_existing_appointment,
                check_customer_booking_history,
                search_receptionist_knowledge,
                get_active_offers,
                get_business_timings,
                get_cancellation_policy,
                get_refund_policy,
                get_faq_answer,
            ]
        )

    def _emergency_mode_response(self) -> Dict[str, Any]:
        """Graceful response for Emergency Mode when all LLMs or APIs fail."""
        emergency_msg = (
            "I am currently unable to verify appointment availability. Please use the booking form or try again in a few moments."
        )
        return {
            "success": True,
            "agent_name": self.name,
            "response": emergency_msg,
            "provider": "emergency_mode"
        }

    @classmethod
    def _check_and_reset_circuit_breaker(cls) -> None:
        """Auto-reset circuit breaker after CIRCUIT_BREAKER_RESET_SECONDS."""
        if cls.CIRCUIT_BREAKER_TRIPPED:
            elapsed = time.time() - cls.CIRCUIT_BREAKER_TRIPPED_AT
            if elapsed >= cls.CIRCUIT_BREAKER_RESET_SECONDS:
                logger.info(f"🔄 Circuit breaker auto-reset after {elapsed:.0f}s cooldown. Resuming LLM calls.")
                cls.CIRCUIT_BREAKER_TRIPPED = False
                cls.CIRCUIT_BREAKER_TRIPPED_AT = 0.0
                cls.FAILURE_COUNT = 0
                # Also clear model cooldowns older than now so we retry immediately
                now = time.time()
                cls.MODEL_COOLDOWN = {k: v for k, v in cls.MODEL_COOLDOWN.items() if v > now}

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Processes booking queries with strict timeouts, direct database routing, and Hugging Face support."""
        query = input_data.get("query", "").strip()
        if not query:
            return {"success": False, "error": "Please provide a booking request."}

        latest_message = input_data.get("latest_message", "").strip()
        if not latest_message:
            if "Latest User Message:" in query:
                latest_message = query.split("Latest User Message:")[-1].strip()
            else:
                latest_message = query

        from core.query_context import set_query_context
        set_query_context(query)
        ReceptionistAgent.CURRENT_QUERY_CONTEXT = query

        # Auto-reset circuit breaker if enough time has passed
        ReceptionistAgent._check_and_reset_circuit_breaker()

        if ReceptionistAgent.CIRCUIT_BREAKER_TRIPPED:
            return self._emergency_mode_response()

        # ── FAST PATH: pure chat/greeting handled without LLM at all ──────────
        fast_intent = _fast_intent_classify(latest_message)
        if fast_intent == "chat":
            # Pure greeting — return canned warm response, ZERO LLM or RAG tokens spent
            # (Do NOT call get_faq_answer here — it would return raw RAG offer blocks for "hi")
            greeting = (
                "Hello! I'm Clara, your AI Salon Receptionist. I'm here to help you book, "
                "reschedule, or cancel appointments, check slot availability, and answer any questions "
                "about our services, pricing, and policies. How can I assist you today?"
            )
            return {
                "success": True,
                "agent_name": self.name,
                "response": greeting,
                "provider": "keyword_shortcut"
            }

        # ── FAST PATH: policy/FAQ handled via RAG without LLM ─────────────────
        if fast_intent == "policy":
            from tools.receptionist_rag_tools import search_receptionist_knowledge, get_business_timings, get_active_offers, get_cancellation_policy, get_refund_policy
            try:
                q_lower = latest_message.lower()
                if any(k in q_lower for k in ["timing", "hour", "open", "close", "working"]):
                    rag_result = get_business_timings()
                elif any(k in q_lower for k in ["offer", "discount", "promotion"]):
                    rag_result = get_active_offers()
                elif any(k in q_lower for k in ["cancel", "cancellation"]):
                    rag_result = get_cancellation_policy()
                elif any(k in q_lower for k in ["refund"]):
                    rag_result = get_refund_policy()
                else:
                    rag_result = search_receptionist_knowledge(latest_message)

                # Strip raw markdown wrapper — return only the document content
                if rag_result and "--- Matches found in Receptionist Knowledge Base ---" in rag_result:
                    # Extract just the page_content lines, skipping source/metadata lines
                    content_lines = []
                    skip_next = False
                    for line in rag_result.split("\n"):
                        stripped = line.strip()
                        if stripped.startswith("--- Matches found") or stripped.startswith("--- End of Context"):
                            continue
                        if stripped.startswith("[") and "Source:" in stripped:
                            skip_next = False
                            continue
                        if stripped:
                            content_lines.append(stripped)
                    rag_result = "\n".join(content_lines).strip()

                if rag_result and len(rag_result) > 20:
                    return {
                        "success": True,
                        "agent_name": self.name,
                        "response": rag_result,
                        "provider": "rag_shortcut"
                    }
            except Exception as rag_err:
                logger.warning(f"RAG fast path failed: {rag_err}")

        settings = get_settings()
        gemini_key = settings.gemini_api_key or settings.google_api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")
        groq_key = settings.groq_api_key or os.environ.get("GROQ_API_KEY", "")

        fallback_queue = []
        now = time.time()

        # Tier 1: Hugging Face (API)
        huggingface_enabled = settings.huggingface_enabled
        huggingface_model = settings.huggingface_model
        if huggingface_enabled:
            if huggingface_model in ReceptionistAgent.MODEL_COOLDOWN and now < ReceptionistAgent.MODEL_COOLDOWN[huggingface_model]:
                logger.info(f"⏭️ Skipping Hugging Face model '{huggingface_model}' due to active cooldown.")
            else:
                fallback_queue.append({
                    "provider": "huggingface",
                    "model": huggingface_model,
                    "api_key": settings.huggingface_api_key or os.environ.get("HUGGINGFACE_API_KEY") or os.environ.get("HF_TOKEN", ""),
                    "base_url": settings.huggingface_api_base_url
                })

        # Tier 2: Groq llama-3.3-70b-versatile (primary — best quality)
        if groq_key and groq_key.strip() and groq_key != "your-groq-key-here":
            model = "llama-3.3-70b-versatile"
            if model in ReceptionistAgent.MODEL_COOLDOWN and now < ReceptionistAgent.MODEL_COOLDOWN[model]:
                logger.info(f"⏭️ Skipping Groq model '{model}' due to active cooldown.")
            else:
                fallback_queue.append({
                    "provider": "groq",
                    "model": model,
                    "api_key": groq_key,
                    "base_url": "https://api.groq.com/openai/v1"
                })

        # Tier 3: Groq llama-3.1-8b-instant (fast, lightweight fallback)
        if groq_key and groq_key.strip() and groq_key != "your-groq-key-here":
            model = "llama-3.1-8b-instant"
            if model in ReceptionistAgent.MODEL_COOLDOWN and now < ReceptionistAgent.MODEL_COOLDOWN[model]:
                logger.info(f"⏭️ Skipping Groq model '{model}' due to active cooldown.")
            else:
                fallback_queue.append({
                    "provider": "groq",
                    "model": model,
                    "api_key": groq_key,
                    "base_url": "https://api.groq.com/openai/v1"
                })

        # Tier 4: Gemini Flash (gemini-2.0-flash)
        if gemini_key and gemini_key.strip() and gemini_key != "your-gemini-key-here":
            model = "gemini-2.0-flash"
            if model in ReceptionistAgent.MODEL_COOLDOWN and now < ReceptionistAgent.MODEL_COOLDOWN[model]:
                logger.info(f"⏭️ Skipping Gemini model '{model}' due to active cooldown.")
            else:
                fallback_queue.append({
                    "provider": "gemini",
                    "model": model,
                    "api_key": gemini_key,
                    "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/"
                })

        # Tier 5: Gemini Flash Lite (cheaper, higher quota limits)
        if gemini_key and gemini_key.strip() and gemini_key != "your-gemini-key-here":
            model = "gemini-2.0-flash-lite"
            if model in ReceptionistAgent.MODEL_COOLDOWN and now < ReceptionistAgent.MODEL_COOLDOWN[model]:
                logger.info(f"⏭️ Skipping Gemini model '{model}' due to active cooldown.")
            else:
                fallback_queue.append({
                    "provider": "gemini",
                    "model": model,
                    "api_key": gemini_key,
                    "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/"
                })

        if not fallback_queue:
            logger.warning("⚠️ All LLM providers are on cooldown. Returning emergency response.")
            return self._emergency_mode_response()

        # Step 1: Fast keyword-shortcut entity extraction (skips LLM for obvious intents)
        # Only call LLM extractor for 'book', 'cancel', 'reschedule', 'availability', 'history'
        # where entity extraction actually matters. 'chat' and 'policy' were handled above.
        intent_json = None

        # If fast_intent already resolved a known action intent, seed intent_json directly
        # This avoids a wasteful LLM round-trip for simple requests
        if fast_intent in ("book", "cancel", "reschedule", "availability", "history"):
            # Still need entity extraction (service/date/time/branch) — use LLM but with
            # a stripped-down prompt to save tokens
            import json as _json
            for tier in fallback_queue:
                model_name = tier["model"]
                api_key = tier["api_key"]
                base_url = tier["base_url"]

                try:
                    # Compact extraction prompt — ~40% fewer tokens than original
                    extraction_sys_prompt = (
                        'Extract booking entities as raw JSON only. No explanation.\n'
                        '{"intent":"book|cancel|reschedule|history|availability|chat",'
                        '"service":str|null,"branch":str|null,"stylist":str|null,'
                        '"date":str|null,"time":str|null,"appointment_id":str|null}\n'
                        'Time rules: extract exactly as stated. Ranges like "3-4PM" -> "3-4PM".'
                    )
                    timeout_val = 90.0 if tier["provider"] == "huggingface" else 15.0
                    client = OpenAIChatCompletionClient(
                        model=model_name,
                        api_key=api_key,
                        base_url=base_url,
                        timeout=timeout_val
                    )
                    from autogen_core.models import SystemMessage, UserMessage
                    res = await asyncio.wait_for(
                        client.create(
                            messages=[
                                SystemMessage(content=extraction_sys_prompt),
                                UserMessage(content=f"Query: {latest_message}", source="user")
                            ],
                            max_tokens=120  # reduced from 150
                        ),
                        timeout=timeout_val
                    )
                    res_content = res.content.strip()
                    if "```" in res_content:
                        res_content = res_content.split("```")[1]
                        if res_content.startswith("json"):
                            res_content = res_content[4:]
                    intent_json = _json.loads(res_content.strip())
                    break
                except Exception as e:
                    err_str = str(e)
                    is_auth_error = "401" in err_str or "unauthorized" in err_str.lower() or "invalid api key" in err_str.lower()
                    if is_auth_error:
                        # Auth errors won't resolve with retry — short cooldown only (5 min)
                        logger.error(f"🔑 Auth error for model '{model_name}' (401/Unauthorized). Short cooldown 5 min.")
                        ReceptionistAgent.MODEL_COOLDOWN[model_name] = time.time() + 300
                    else:
                        logger.warning(f"Fast extraction failed on model '{model_name}': {err_str[:120]}")
                        cooldown_secs = 15 if tier["provider"] == "huggingface" else 1800
                        ReceptionistAgent.MODEL_COOLDOWN[model_name] = time.time() + cooldown_secs
        else:
            # 'unknown' intent — use LLM to classify AND extract
            import json as _json
            for tier in fallback_queue:
                model_name = tier["model"]
                api_key = tier["api_key"]
                base_url = tier["base_url"]
                try:
                    extraction_sys_prompt = (
                        'Extract booking entities as raw JSON only. No explanation.\n'
                        '{"intent":"book|cancel|reschedule|history|availability|chat",'
                        '"service":str|null,"branch":str|null,"stylist":str|null,'
                        '"date":str|null,"time":str|null,"appointment_id":str|null}\n'
                        'Time rules: extract exactly as stated. Ranges like "3-4PM" -> "3-4PM".'
                    )
                    timeout_val = 90.0 if tier["provider"] == "huggingface" else 15.0
                    client = OpenAIChatCompletionClient(
                        model=model_name,
                        api_key=api_key,
                        base_url=base_url,
                        timeout=timeout_val
                    )
                    from autogen_core.models import SystemMessage, UserMessage
                    res = await asyncio.wait_for(
                        client.create(
                            messages=[
                                SystemMessage(content=extraction_sys_prompt),
                                UserMessage(content=f"Query: {latest_message}", source="user")
                            ],
                            max_tokens=120
                        ),
                        timeout=timeout_val
                    )
                    res_content = res.content.strip()
                    if "```" in res_content:
                        res_content = res_content.split("```")[1]
                        if res_content.startswith("json"):
                            res_content = res_content[4:]
                    intent_json = _json.loads(res_content.strip())
                    break
                except Exception as e:
                    err_str = str(e)
                    is_auth_error = "401" in err_str or "unauthorized" in err_str.lower() or "invalid api key" in err_str.lower()
                    if is_auth_error:
                        logger.error(f"🔑 Auth error for model '{model_name}' (401). Short cooldown 5 min.")
                        ReceptionistAgent.MODEL_COOLDOWN[model_name] = time.time() + 300
                    else:
                        logger.warning(f"Intent extraction failed on model '{model_name}': {err_str[:120]}")
                        cooldown_secs = 15 if tier["provider"] == "huggingface" else 1800
                        ReceptionistAgent.MODEL_COOLDOWN[model_name] = time.time() + cooldown_secs

        if not intent_json:
            intent_json = {"intent": fast_intent if fast_intent != "unknown" else "chat",
                           "service": None, "branch": None, "stylist": None,
                           "date": None, "time": None}

        intent = intent_json.get("intent", "chat")

        # ── MULTI-TURN ENTITY ACCUMULATION ─────────────────────────────────────────
        # If any booking entities are missing from the current message, scan the last
        # 3 turns of chat history and fill them in. This allows the user to provide
        # service on one turn and date/time on another without losing context.
        _history_entity_fields = ["service", "branch", "stylist", "date", "time"]
        _needs_fill = any(not intent_json.get(f) or _is_placeholder_value(intent_json.get(f, ""))
                          for f in _history_entity_fields)
        if _needs_fill and "Here is the conversation history so far for context:" in query:
            # Parse history block from query
            import re as _re
            history_block = ""
            history_match = _re.search(
                r"Here is the conversation history so far for context:\n(.*?)\nLatest User Message:",
                query, _re.DOTALL
            )
            if history_match:
                history_block = history_match.group(1)
            # Extract last 3 user turns from history
            history_user_lines = [
                line[len("- User:"):].strip()
                for line in history_block.split("\n")
                if line.strip().startswith("- User:")
            ][-3:]
            # For each missing entity, do a quick rule-based extraction from history
            _combined_history = " ".join(history_user_lines)
            import json as _json2
            for _hist_msg in reversed(history_user_lines):
                if not _hist_msg:
                    continue
                # Simple regex-based date extraction from history
                if not intent_json.get("date"):
                    _date_m = _re.search(r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]* \d{1,2}(?:st|nd|rd|th)?,? \d{4}|tomorrow|today|next \w+day)\b", _hist_msg, _re.IGNORECASE)
                    if _date_m:
                        intent_json["date"] = _date_m.group(1)
                # Simple regex-based time extraction from history
                if not intent_json.get("time"):
                    _time_m = _re.search(r"\b(\d{1,2}(?::\d{2})?\s*(?:am|pm)|slot\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\b", _hist_msg, _re.IGNORECASE)
                    if _time_m:
                        intent_json["time"] = _time_m.group(1)
                # Service/Branch/Stylist extraction from history (look for quoted combos)
                if not intent_json.get("service") or not intent_json.get("branch"):
                    _quoted_m = _re.search(r'"([^"]+)\s+([^"]+)\s+([^"]+)"', _hist_msg)
                    if _quoted_m:
                        # Format: "Service  Branch  Stylist"
                        parts = [p.strip() for p in _hist_msg.split('"') if p.strip()]
                        for part in parts:
                            sub = [s.strip() for s in part.split("\t") if s.strip()]
                            if len(sub) == 3:
                                if not intent_json.get("service"):
                                    intent_json["service"] = sub[0]
                                if not intent_json.get("branch"):
                                    intent_json["branch"] = sub[1]
                                if not intent_json.get("stylist"):
                                    intent_json["stylist"] = sub[2]
                                break
                        if not (intent_json.get("service") and intent_json.get("branch")):
                            # Fallback: plain text with tab separators
                            words = part.strip().split()
                            if len(words) >= 2 and not intent_json.get("service"):
                                intent_json["service"] = words[0]

        intent = intent_json.get("intent", "chat")
        
        # Load Customer History Memory for warm personalized greeting (Priority 7)
        cust_id = get_query_customer_id()
        pref_str, pref_service, pref_stylist = _get_customer_memory(cust_id)
        
        # Avoid prepending the welcome profile on every single chat response if there's history
        is_first_turn = "Here is the conversation history so far for context:" not in query
        if not is_first_turn:
            pref_str = ""

        # Priority 4: Direct discovery catalog browser rules
        is_discovery_query = any(k in query.lower() for k in ["show services", "show branches", "show staff", "list services", "list branches", "list staff"])

        # ROUTING & BOOKING ENGINE (Priority 2 & 3)
        if intent == "book" and not is_discovery_query:
            # Smart Repeat Booking (Rule 13)
            # If the user asks to book "same", "again", "repeat", fetch their last completed styling session
            service_input = intent_json.get("service")
            stylist_input = intent_json.get("stylist")
            
            if ("same" in query.lower() or "again" in query.lower() or "repeat" in query.lower()) and cust_id:
                db = SessionLocal()
                try:
                    from db.models import Appointment, AppointmentStatus
                    last_appt = db.query(Appointment).filter(
                        Appointment.customer_id == cust_id,
                        Appointment.status == AppointmentStatus.COMPLETED
                    ).order_by(Appointment.start_time.desc()).first()
                    if last_appt:
                        if not service_input:
                            service_input = str(last_appt.service_id)
                        if not stylist_input:
                            stylist_input = str(last_appt.staff_id)
                        if not intent_json.get("branch"):
                            intent_json["branch"] = str(last_appt.branch_id)
                except Exception as ex:
                    logger.warning(f"Error resolving repeat booking: {ex}")
                finally:
                    db.close()

            # Check if this is a repeat/again booking request
            is_repeat = ("same" in query.lower() or "again" in query.lower() or "repeat" in query.lower())
            
            service_input = intent_json.get("service")
            stylist_input = intent_json.get("stylist")
            branch_input = intent_json.get("branch")
            date_input = intent_json.get("date")
            time_input = intent_json.get("time")
            
            # If repeat request, try to load last completed appointment details
            if is_repeat and cust_id:
                db = SessionLocal()
                try:
                    from db.models import Appointment, AppointmentStatus
                    last_appt = db.query(Appointment).filter(
                        Appointment.customer_id == cust_id,
                        Appointment.status == AppointmentStatus.COMPLETED
                    ).order_by(Appointment.start_time.desc()).first()
                    if last_appt:
                        if not service_input:
                            service_input = str(last_appt.service_id)
                        if not stylist_input:
                            stylist_input = str(last_appt.staff_id)
                        if not branch_input:
                            branch_input = str(last_appt.branch_id)
                except Exception as ex:
                    logger.warning(f"Error resolving repeat booking: {ex}")
                finally:
                    db.close()

            # Identify missing required details
            missing_fields = []
            if not service_input or _is_placeholder_value(service_input):
                missing_fields.append("service")
            if not branch_input or _is_placeholder_value(branch_input):
                missing_fields.append("branch")
            if not date_input or _is_placeholder_value(date_input):
                missing_fields.append("date")
            if not time_input or _is_placeholder_value(time_input):
                missing_fields.append("time")
                
            if missing_fields:
                questions = []
                if "service" in missing_fields:
                    questions.append("which service you would like to book")
                if "branch" in missing_fields:
                    questions.append("at which branch location")
                if "date" in missing_fields:
                    questions.append("on what date")
                if "time" in missing_fields:
                    questions.append("at what time")
                    
                # Formulate natural response asking for missing details
                ask_msg = f"{pref_str}\n\nI would be happy to help you book an appointment! Could you please specify "
                if len(questions) == 1:
                    ask_msg += questions[0] + "?"
                elif len(questions) == 2:
                    ask_msg += f"{questions[0]} and {questions[1]}?"
                else:
                    ask_msg += ", ".join(questions[:-1]) + f", and {questions[-1]}?"
                    
                return {
                    "success": True,
                    "agent_name": self.name,
                    "response": ask_msg,
                    "provider": "booking_engine"
                }

            # If all required fields are present, fallback to preferences for stylist if not specified
            if not stylist_input and pref_stylist:
                stylist_input = pref_stylist
                
            repaired_cust = repair_customer(cust_id)
            repaired_branch = repair_branch(branch_input)
            repaired_service = repair_service(service_input)
            repaired_staff = repair_staff(stylist_input, repaired_branch)
            
            repaired_date = repair_date(date_input)
            repaired_time = repair_time(time_input)
            repaired_date = adjust_past_date_today(repaired_date, repaired_time)
            repaired_time_str = f"{repaired_date}T{repaired_time}:00Z"

            # Check if booking is in the past
            sys_dt = get_query_system_datetime() or datetime.now()
            if sys_dt.tzinfo is not None:
                sys_dt = sys_dt.replace(tzinfo=None)
            try:
                req_dt = datetime.strptime(f"{repaired_date} {repaired_time}", "%Y-%m-%d %H:%M")
                if req_dt < sys_dt:
                    return {
                        "success": True,
                        "agent_name": self.name,
                        "response": f"{pref_str}\n\nI apologize, but appointments must be in the future. Please select a future date and time.",
                        "provider": "booking_engine"
                    }
            except Exception as e:
                logger.warning(f"Error checking past datetime in receptionist process: {e}")

            # Check availability directly via Python tool
            slots_data = check_stylist_availability(
                branch_id=repaired_branch,
                date=repaired_date,
                staff_id=repaired_staff,
                service_id=repaired_service
            )
            
            import ast
            slots_dict = {}
            try:
                slots_dict = ast.literal_eval(slots_data)
            except Exception:
                pass

            if slots_dict.get("staff_on_leave"):
                staff_name = slots_dict.get("staff_name") or "The stylist"
                slots = slots_dict.get("slots", [])
                available_alternatives = []
                for s in slots:
                    start_iso = s.get("start_time", "")
                    if f"T{repaired_time}" in start_iso or repaired_time in start_iso:
                        available_alternatives = s.get("available_staff_names", [])
                        break
                
                if available_alternatives:
                    return {
                        "success": True,
                        "agent_name": self.name,
                        "response": f"{pref_str}\n\n{staff_name} is on leave on {repaired_date}. Please choose another staff member. At {repaired_time}, the following stylists are available: {', '.join(available_alternatives)}.",
                        "provider": "booking_engine"
                    }
                else:
                    alt_slots = []
                    for s in slots:
                        start_iso = s.get("start_time", "")
                        try:
                            dt = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
                            alt_slots.append(dt.strftime("%I:%M %p"))
                        except Exception:
                            pass
                    alt_str = ", ".join(alt_slots[:3]) if alt_slots else "none today"
                    return {
                        "success": True,
                        "agent_name": self.name,
                        "response": f"{pref_str}\n\n{staff_name} is on leave on {repaired_date}. Please choose another staff member. No other stylists are available at {repaired_time}. Other available times with stylists: {alt_str}.",
                        "provider": "booking_engine"
                    }

            if "error" in slots_data.lower() or not slots_data:
                return {
                    "success": True,
                    "agent_name": self.name,
                    "response": f"{pref_str}\n\nI could not verify availability right now.",
                    "provider": "booking_engine"
                }

            # Smart Slot Suggestions (Rule 12)
            # Parse available slots to check if the requested time is free
            import ast
            slots = []
            try:
                slots_dict = ast.literal_eval(slots_data)
                slots = slots_dict.get("slots", [])
            except Exception:
                pass
                
            is_requested_slot_available = False
            for s in slots:
                start_iso = s.get("start_time", "")
                if f"{repaired_date}T{repaired_time}" in start_iso:
                    is_requested_slot_available = True
                    break
                    
            if not is_requested_slot_available:
                alternatives = []
                for s in slots:
                    start_iso = s.get("start_time", "")
                    try:
                        dt = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
                        alt_time = dt.strftime("%I:%M %p")
                        alternatives.append(alt_time)
                    except Exception:
                        pass
                
                alt_str = ", ".join(alternatives[:3]) if alternatives else "none today"
                stylist_name = "Professional Stylist"
                if repaired_staff:
                    db = SessionLocal()
                    st = db.query(Staff).filter(Staff.id == repaired_staff).first()
                    if st:
                        stylist_name = st.full_name
                    db.close()
                return {
                    "success": True,
                    "agent_name": self.name,
                    "response": f"{pref_str}\n\nI'm sorry, but {stylist_name} is unavailable at {repaired_time} on {repaired_date}. Available alternatives:\n{alt_str}",
                    "provider": "booking_engine"
                }

            # Create appointment directly via Python tool
            booking_res_str = book_new_appointment(
                customer_id=repaired_cust,
                branch_id=repaired_branch,
                service_id=repaired_service,
                start_time=repaired_time_str,
                staff_id=repaired_staff,
                notes="Self-guided booking"
            )
            
            try:
                import ast
                booking_res = ast.literal_eval(booking_res_str)
            except Exception:
                booking_res = {"success": False, "error": booking_res_str}
                
            if not isinstance(booking_res, dict) or not booking_res.get("success"):
                error_detail = booking_res.get("error", "Unknown booking error") if isinstance(booking_res, dict) else booking_res_str
                return {
                    "success": True,
                    "agent_name": self.name,
                    "response": f"{pref_str}\n\nI apologize, but I could not book the appointment. Error: {error_detail}",
                    "provider": "booking_engine"
                }
            
            # Format confirmed response using strict summary structure
            db = SessionLocal()
            try:
                service_name = db.query(Service).filter(Service.id == repaired_service).first().name
                branch_name = db.query(Branch).filter(Branch.id == repaired_branch).first().name
                stylist_name = "Professional Stylist"
                if repaired_staff:
                    st = db.query(Staff).filter(Staff.id == repaired_staff).first()
                    if st:
                        stylist_name = f"{st.first_name} {st.last_name}"
                price_val = db.query(Service).filter(Service.id == repaired_service).first().price
            except Exception:
                service_name = "Styling Session"
                branch_name = "Main Salon"
                stylist_name = "Stylist"
                price_val = 0.0
            finally:
                db.close()

            # Dynamic Smart Upsell Recommendations (Rule 19)
            upsells = []
            if "haircut" in service_name.lower():
                upsells = ["Hair Spa ($55)", "Special Head Massage ($25)", "Professional Beard Styling ($35)"]
            elif "massage" in service_name.lower():
                upsells = ["Luxury Facial Treatment ($120)", "Himalayan Sea Salt foot wash ($30)"]
            else:
                upsells = ["Signature Precision Haircut ($85)", "Special Head Massage ($25)"]

            confirm_msg = (
                f"{pref_str}\n\n"
                f"Appointment Summary\n\n"
                f"Service: {service_name}\n"
                f"Branch: {branch_name}\n"
                f"Stylist: {stylist_name}\n"
                f"Date: {repaired_date}\n"
                f"Time: {repaired_time}\n"
                f"Price: ${price_val}\n\n"
                f"Status:\nConfirmed\n\n"
                f"🎁 Recommended Add-on Treatments (Zenoti smart upsell):\n" + 
                "\n".join([f"• {u}" for u in upsells])
            )
            
            return {
                "success": True,
                "agent_name": self.name,
                "response": confirm_msg,
                "provider": "booking_engine"
            }

        elif intent == "availability" and not is_discovery_query:
            repaired_branch = repair_branch(intent_json.get("branch"))
            repaired_service = repair_service(intent_json.get("service"))
            repaired_staff = repair_staff(intent_json.get("stylist"), repaired_branch)
            repaired_date = repair_date(intent_json.get("date"))

            slots_data = check_stylist_availability(
                branch_id=repaired_branch,
                date=repaired_date,
                staff_id=repaired_staff,
                service_id=repaired_service
            )
            
            import ast
            is_staff_leave_err = False
            try:
                data = ast.literal_eval(slots_data)
                if data.get("staff_on_leave"):
                    is_staff_leave_err = True
            except Exception:
                pass

            if ("error" in slots_data.lower() and not is_staff_leave_err) or not slots_data:
                return {
                    "success": True,
                    "agent_name": self.name,
                    "response": "I could not verify availability right now.",
                    "provider": "booking_engine"
                }

            formatted_slots = format_receptionist_tool_output("availability", slots_data)
            return {
                "success": True,
                "agent_name": self.name,
                "response": f"{pref_str}\n\n{formatted_slots}",
                "provider": "booking_engine"
            }

        elif intent == "cancel":
            appt_id = intent_json.get("appointment_id")
            repaired_cust = repair_customer(cust_id)
            
            # Resolve the correct active appointment id
            resolved_id = find_matching_active_appointment(repaired_cust, intent_json, query)
            if resolved_id:
                appt_id = resolved_id
                
            cancel_res = cancel_existing_appointment(appointment_id=appt_id)
            formatted_cancel = format_receptionist_tool_output("cancel", cancel_res)
            return {
                "success": True,
                "agent_name": self.name,
                "response": f"{pref_str}\n\n{formatted_cancel}",
                "provider": "booking_engine"
            }

        elif intent == "reschedule":
            appt_id = intent_json.get("appointment_id")
            repaired_cust = repair_customer(cust_id)
            
            # Resolve the correct active appointment id
            resolved_id = find_matching_active_appointment(repaired_cust, intent_json, query)
            if resolved_id:
                appt_id = resolved_id
                
            new_date = repair_date(intent_json.get("date"))
            new_time = repair_time(intent_json.get("time"))
            new_date = adjust_past_date_today(new_date, new_time)
            new_start_time = f"{new_date}T{new_time}:00Z"

            # Check if rescheduling is in the past
            sys_dt = get_query_system_datetime() or datetime.now()
            if sys_dt.tzinfo is not None:
                sys_dt = sys_dt.replace(tzinfo=None)
            try:
                req_dt = datetime.strptime(f"{new_date} {new_time}", "%Y-%m-%d %H:%M")
                if req_dt < sys_dt:
                    return {
                        "success": True,
                        "agent_name": self.name,
                        "response": f"{pref_str}\n\nI apologize, but appointments must be in the future. Please select a future date and time.",
                        "provider": "booking_engine"
                    }
            except Exception as e:
                logger.warning(f"Error checking past datetime in receptionist reschedule: {e}")
            
            resched_res = reschedule_existing_appointment(appointment_id=appt_id, new_start_time=new_start_time)
            formatted_resched = format_receptionist_tool_output("reschedule", resched_res)
            return {
                "success": True,
                "agent_name": self.name,
                "response": f"{pref_str}\n\n{formatted_resched}",
                "provider": "booking_engine"
            }

        elif intent == "history":
            repaired_cust = repair_customer(cust_id)
            history_data = check_customer_booking_history(customer_id=repaired_cust)
            
            # Check if this is a specific natural language query about history
            specific_keywords = ["spend", "cost", "pay", "charge", "last", "recent", "how many", "count", "this month", "this year", "year", "month", "total"]
            is_specific_query = any(k in query.lower() for k in specific_keywords)
            
            if is_specific_query:
                # Let's route to the LLM agent, but inject the history data into the query so the LLM can see it!
                query = f"{query}\n\n[USER BOOKING HISTORY DATA: {compress_history_for_prompt(history_data)}]"
            else:
                formatted_history = format_receptionist_tool_output("history", history_data)
                return {
                    "success": True,
                    "agent_name": self.name,
                    "response": f"{pref_str}\n\n{formatted_history}",
                    "provider": "booking_engine"
                }

        # Chat / Discovery queries fall back to standard Agent execution
        # ── TOKEN OPTIMISATION: Dynamically select tools based on user query keywords and intent ──
        _agent_tools = _select_agent_tools(query, intent)

        if intent in ("book", "cancel", "reschedule"):
            _agent_system_prompt = RECEPTIONIST_SYSTEM_PROMPT
        elif intent == "history":
            _agent_system_prompt = (
                "You are Clara, a professional AI Salon Receptionist. "
                "Answer questions about the customer's appointment history using the provided history data. "
                "Summarize or count appointments precisely based on the history log. "
                "Do NOT confirm any new bookings or generate an 'Appointment Summary' unless explicitly asked to book. "
                "Answer warmly and concisely under 150 words."
            )
        elif intent == "availability":
            _agent_system_prompt = (
                "You are Clara, a professional AI Salon Receptionist. "
                "Check slot availability using the appropriate tools and list the available slots. "
                "Answer warmly and concisely. Do NOT generate a confirmed 'Appointment Summary' or confirm any booking."
            )
        else:
            _agent_system_prompt = (
                "You are Clara, a professional AI Salon Receptionist. "
                "Answer salon questions warmly and concisely. "
                "Use available tools to provide accurate information about branches, services, staff, and offers. "
                "Never invent data. Keep responses under 200 words."
            )

        last_error = None
        for idx, tier in enumerate(fallback_queue, 1):
            model_name = tier["model"]
            provider = tier["provider"]
            base_url = tier["base_url"]
            api_key = tier["api_key"]

            max_attempts = 1
            for attempt in range(1, max_attempts + 1):
                start_time = time.perf_counter()
                try:
                    model_info = {
                        "vision": False,
                        "function_calling": True,
                        "json_output": True,
                        "family": (
                            "gemini-2.0" if "gemini-2.0" in model_name
                            else "gemini-1.5" if "gemini-1.5" in model_name
                            else "llama-3.3" if "3.3" in model_name
                            else "qwen" if "qwen" in model_name
                            else "llama-3.1"
                        ),
                        "structured_output": False,
                    }

                    client_timeout = 90.0 if provider == "huggingface" else 30.0
                    run_timeout = 90.0 if provider == "huggingface" else 30.0

                    model_client = OpenAIChatCompletionClient(
                        model=model_name,
                        api_key=api_key,
                        base_url=base_url,
                        model_info=model_info,
                        timeout=client_timeout
                    )

                    assistant = AssistantAgent(
                        name=self.name,
                        model_client=model_client,
                        system_message=_agent_system_prompt,
                        tools=_agent_tools
                    )

                    result = await asyncio.wait_for(assistant.run(task=query), timeout=run_timeout)
                    latency = time.perf_counter() - start_time

                    if result.messages and len(result.messages) > 0:
                        response_text = result.messages[-1].content
                    else:
                        response_text = ""

                    if not response_text.strip():
                        raise ValueError("Received empty response from assistant.")

                    response_stripped = response_text.strip()
                    if (response_stripped.startswith("{") or response_stripped.startswith("[") or response_stripped.startswith("{'")) or ("success" in response_stripped.lower() and ("true" in response_stripped.lower() or "false" in response_stripped.lower())):
                        from autogen_core.models import SystemMessage, UserMessage
                        formatter_sys_prompt = (
                            "You are Clara, a professional AI Salon Receptionist.\n"
                            "Translate this raw system/tool result into a warm, professional booking confirmation.\n"
                            "Rules:\n"
                            "- Confirm precisely using the exact values from the tool results.\n"
                            "- Follow the confirmation format: Service, Branch, Stylist, Date, Time, Price, and Status.\n"
                            "- Address the client politely.\n"
                            "- NEVER invent or alter values."
                        )
                        
                        formatter_client = OpenAIChatCompletionClient(
                            model=model_name,
                            api_key=api_key,
                            base_url=base_url,
                            model_info=model_info,
                            timeout=client_timeout
                        )
                        
                        sys_msg = SystemMessage(content=formatter_sys_prompt)
                        user_msg = UserMessage(content=f"Raw System Result:\n{response_stripped}", source="user")
                        
                        try:
                            fmt_result = await asyncio.wait_for(formatter_client.create(messages=[sys_msg, user_msg], max_tokens=250), timeout=run_timeout)
                            formatted_response = fmt_result.content.strip()
                            
                            # Validate formatter response - ensure it's not truncated or incomplete
                            if formatted_response and len(formatted_response) >= 20:
                                response_text = formatted_response
                                logger.info(f"Formatter successfully formatted response (length: {len(formatted_response)})")
                            else:
                                logger.warning(f"Formatter returned suspiciously short response: '{formatted_response}'. Using original response instead.")
                                # Fall back to original response if formatter output is too short
                                response_text = response_stripped
                        except Exception as fmt_ex:
                            logger.error(f"Formatter failed with error: {str(fmt_ex)}. Using original response instead.")
                            # Fall back to original response if formatter fails
                            response_text = response_stripped

                    ReceptionistAgent.FAILURE_COUNT = 0
                    ReceptionistAgent.CIRCUIT_BREAKER_TRIPPED = False

                    normalized_response_text = normalize_response(response_text)

                    return {
                        "success": True,
                        "agent_name": self.name,
                        "response": normalized_response_text,
                        "provider": f"{provider}_tier{idx}_attempt{attempt}"
                    }

                except Exception as ex:
                    latency = time.perf_counter() - start_time
                    err_str = str(ex)
                    logger.warning(f"⚠️ Tier {idx} ({model_name}) attempt {attempt} failed: {err_str[:150]}")
                    
                    last_error = ex

                    from openai import RateLimitError, APITimeoutError
                    import httpx

                    is_auth_error = "401" in err_str or "unauthorized" in err_str.lower() or "invalid api key" in err_str.lower()
                    is_rate_limit = "429" in err_str or "rate" in err_str.lower() or "quota" in err_str.lower() or isinstance(ex, RateLimitError)
                    is_timeout = "timeout" in err_str.lower() or isinstance(ex, APITimeoutError) or isinstance(ex, httpx.TimeoutException) or isinstance(ex, asyncio.TimeoutError)

                    if is_auth_error:
                        # 401 = bad API key — don't wait 30 min, short cooldown so system can recover
                        logger.error(f"🔑 Model '{model_name}' returned 401 Unauthorized. Short cooldown 5 min (check API key).")
                        ReceptionistAgent.MODEL_COOLDOWN[model_name] = time.time() + 300
                        ReceptionistAgent.FAILURE_COUNT += 1
                        break
                    elif is_rate_limit:
                        # Detect daily quota exhaustion (limit: 0) vs transient rate limit
                        is_daily_quota = "limit: 0" in err_str or "GenerateRequestsPerDay" in err_str or "free_tier_requests" in err_str
                        if is_daily_quota:
                            cooldown_secs = 21600  # 6 hours for daily quota exhaustion
                            logger.error(f"🚨 Model '{model_name}' daily quota exhausted. Cooldown 6 hours.")
                        else:
                            cooldown_secs = 1200  # 20 minutes for transient rate limits
                            logger.error(f"🚨 Model '{model_name}' rate-limited (429). Cooldown 20 minutes.")
                        ReceptionistAgent.MODEL_COOLDOWN[model_name] = time.time() + cooldown_secs
                        ReceptionistAgent.FAILURE_COUNT += 1
                        if ReceptionistAgent.FAILURE_COUNT >= ReceptionistAgent.MAX_FAILURES:
                            ReceptionistAgent.CIRCUIT_BREAKER_TRIPPED = True
                            ReceptionistAgent.CIRCUIT_BREAKER_TRIPPED_AT = time.time()
                        break
                    elif is_timeout:
                        cooldown_secs = 15 if provider == "huggingface" else 180
                        logger.warning(f"⏱️ Model '{model_name}' timed out. Short cooldown {cooldown_secs} seconds.")
                        ReceptionistAgent.MODEL_COOLDOWN[model_name] = time.time() + cooldown_secs
                        ReceptionistAgent.FAILURE_COUNT += 1
                        break

                    ReceptionistAgent.FAILURE_COUNT += 1
                    if ReceptionistAgent.FAILURE_COUNT >= ReceptionistAgent.MAX_FAILURES:
                        ReceptionistAgent.CIRCUIT_BREAKER_TRIPPED = True
                        ReceptionistAgent.CIRCUIT_BREAKER_TRIPPED_AT = time.time()
                    break

        ReceptionistAgent.FAILURE_COUNT += 1
        if ReceptionistAgent.FAILURE_COUNT >= ReceptionistAgent.MAX_FAILURES:
            ReceptionistAgent.CIRCUIT_BREAKER_TRIPPED = True
            ReceptionistAgent.CIRCUIT_BREAKER_TRIPPED_AT = time.time()

        return self._emergency_mode_response()
