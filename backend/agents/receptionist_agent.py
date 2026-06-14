
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
)
from tools.discovery_tools import (
    list_available_branches,
    list_available_services,
    list_available_staff,
    search_for_customers,
)
from tools.mcp_tool import mcp_execute
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

    history = data.get("history") or data.get("records")
    if not history and isinstance(data.get("data"), dict):
        history = data["data"].get("records") or data["data"].get("history")
    if not history and isinstance(data.get("data"), list):
        history = data["data"]
    if not history:
        history = []

    if not history:
        return "No past styling appointments on record."

    total_count = len(history)
    completed_count = sum(1 for a in history if str(a.get("status")).upper() == "COMPLETED")
    cancelled_count = sum(1 for a in history if str(a.get("status")).upper() == "CANCELLED")
    confirmed_count = sum(1 for a in history if str(a.get("status")).upper() == "CONFIRMED")

    total_spent = sum(float(a.get("service_price") or 0.0) for a in history if str(a.get("status")).upper() == "COMPLETED")

    active_statuses = {"CONFIRMED", "PENDING", "confirmed", "pending"}
    active_appts = [a for a in history if str(a.get("status")) in active_statuses]
    past_appts = [a for a in history if str(a.get("status")) not in active_statuses]
    
    selected_appts = active_appts[:15] + past_appts[:8]

    compressed_records = []
    for appt in selected_appts:
        start_time = appt.get("start_time", "")
        date_part = start_time.split("T")[0] if "T" in start_time else start_time
        time_part = ""
        if "T" in start_time:
            time_part = start_time.split("T")[1][:5]

        compressed_records.append({
            "id": appt.get("appointment_id") or appt.get("id"),
            "date": date_part,
            "time": time_part,
            "service": appt.get("service_name"),
            "price": appt.get("service_price") or appt.get("price"),
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
            # Also check nested data (TypedAgentResponse format)
            inner = data.get("data") or {}
            if inner.get("success"):
                return "Your appointment has been successfully cancelled. The database has been updated accordingly."
            err = data.get("error") or inner.get("error") or "Cancellation failed."
            return f"I apologize, but we encountered an issue cancelling your appointment: {err}"
            
    elif intent == "reschedule":
        if data.get("success"):
            # start_time may be at top level or nested under data (TypedAgentResponse format)
            inner = data.get("data") or {}
            start_str = data.get("start_time") or inner.get("start_time") or inner.get("new_start_time") or ""
            try:
                dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                nice_dt = dt.strftime("%A, %B %d, %Y at %I:%M %p")
            except Exception:
                nice_dt = start_str or "your requested time"
            return f"Your appointment has been successfully rescheduled to {nice_dt}."
        else:
            inner = data.get("data") or {}
            err = data.get("error") or inner.get("error") or "Rescheduling failed."
            if "cancelled" in str(err).lower():
                return "I apologize, but we cannot reschedule a cancelled appointment. Please book a new styling session instead."
            return f"I apologize, but we encountered an issue rescheduling your appointment: {err}"
            
    elif intent == "history":
        history = data.get("history") or data.get("records")
        if not history and isinstance(data.get("data"), dict):
            history = data["data"].get("records") or data["data"].get("history")
        if not history and isinstance(data.get("data"), list):
            history = data["data"]
        if not history:
            history = []

        if not history:
            return "You do not have any past styling appointments on record with us."
        
        lines = []
        for appt in history:
            if not isinstance(appt, dict):
                continue
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


def get_available_staff(
    date: Optional[str] = None,
    time: Optional[str] = None,
    branch_id: Optional[str] = None
) -> str:
    """
    Discover all stylists/staff members who are active and available for a specific date and time slot.
    Checks staff leaves and overlapping appointments.
    """
    import concurrent.futures
    def run():
        from datetime import datetime, time as dt_time, timedelta, timezone
        from db.models import Staff, Appointment, AppointmentStatus
        from db.database import SessionLocal
        from tools.booking_tools import is_staff_on_leave
        
        repaired_branch = repair_branch(branch_id)
        repaired_date = repair_date(date)
        repaired_time = repair_time(time)
        
        session = SessionLocal()
        try:
            # Resolve target date and time
            target_date = datetime.strptime(repaired_date, "%Y-%m-%d").date()
            slot_start = datetime.combine(target_date, datetime.strptime(repaired_time, "%H:%M").time(), tzinfo=timezone.utc)
            # Default duration of 30 minutes for slot check
            slot_end = slot_start + timedelta(minutes=30)
            
            # Fetch all active staff at the branch
            staff_list = session.query(Staff).filter(Staff.branch_id == repaired_branch, Staff.is_active == True).all()
            
            # Fetch all non-cancelled appointments for this branch on the target date
            day_start = datetime.combine(target_date, dt_time(0, 0), tzinfo=timezone.utc)
            day_end = datetime.combine(target_date, dt_time(23, 59, 59), tzinfo=timezone.utc)
            appointments = session.query(Appointment).filter(
                Appointment.branch_id == repaired_branch,
                Appointment.status != AppointmentStatus.CANCELLED,
                Appointment.start_time >= day_start,
                Appointment.start_time <= day_end
            ).all()
            
            available_staff = []
            for member in staff_list:
                # Check leave
                on_leave, _ = is_staff_on_leave(member.id, repaired_date, session)
                if on_leave:
                    continue
                    
                # Check overlap
                has_overlap = False
                for appt in appointments:
                    if appt.staff_id == member.id:
                        appt_start = appt.start_time.replace(tzinfo=timezone.utc) if appt.start_time.tzinfo is None else appt.start_time.astimezone(timezone.utc)
                        appt_end = appt.end_time.replace(tzinfo=timezone.utc) if appt.end_time.tzinfo is None else appt.end_time.astimezone(timezone.utc)
                        if slot_start < appt_end and slot_end > appt_start:
                            has_overlap = True
                            break
                
                if not has_overlap:
                    available_staff.append(member)
            
            if not available_staff:
                return f"No stylists are available at {repaired_time} on {repaired_date}."
                
            formatted = f"Available Staff at {repaired_time} on {repaired_date}:\n\n"
            for staff in available_staff:
                formatted += f"• {staff.full_name} ({staff.role})\n"
                formatted += f"  Email: {staff.email}\n"
                formatted += f"  ID: {staff.id}\n\n"
            return formatted
            
        except Exception as e:
            logger.error(f"Error in get_available_staff: {str(e)}", exc_info=True)
            return f"Error checking available staff: {str(e)}"
        finally:
            session.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run)
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
        from workflows.booking_workflow import check_availability_workflow
        return check_availability_workflow(
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
            import re
            is_iso = False
            if "T" in dt_str:
                parts = dt_str.split("T")
                if len(parts) == 2 and re.match(r"^\d{4}-\d{2}-\d{2}$", parts[0]):
                    is_iso = True
            
            if is_iso:
                parts = dt_str.split("T")
                rep_d = repair_date(parts[0])
                rep_t = repair_time(parts[1])
                rep_d = adjust_past_date_today(rep_d, rep_t)
                repaired_time_str = f"{rep_d}T{rep_t}:00"
                if not repaired_time_str.endswith("Z") and not "+" in repaired_time_str:
                    repaired_time_str += "Z"
            else:
                rep_d = repair_date(dt_str)
                rep_t = repair_time(dt_str)
                rep_d = adjust_past_date_today(rep_d, rep_t)
                repaired_time_str = f"{rep_d}T{rep_t}:00Z"
        except Exception:
            repaired_time_str = f"{repair_date(None)}T17:00:00Z"
            
        from workflows.booking_workflow import book_appointment_workflow
        return book_appointment_workflow(
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
        from workflows.booking_workflow import cancel_appointment_workflow
        return cancel_appointment_workflow(appointment_id=repaired_appt, customer_id=sys_c)
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
            import re
            is_iso = False
            if "T" in dt_str:
                parts = dt_str.split("T")
                if len(parts) == 2 and re.match(r"^\d{4}-\d{2}-\d{2}$", parts[0]):
                    is_iso = True
            
            if is_iso:
                parts = dt_str.split("T")
                rep_d = repair_date(parts[0])
                rep_t = repair_time(parts[1])
                rep_d = adjust_past_date_today(rep_d, rep_t)
                repaired_time_str = f"{rep_d}T{rep_t}:00"
                if not repaired_time_str.endswith("Z") and not "+" in repaired_time_str:
                    repaired_time_str += "Z"
            else:
                rep_d = repair_date(dt_str)
                rep_t = repair_time(dt_str)
                rep_d = adjust_past_date_today(rep_d, rep_t)
                repaired_time_str = f"{rep_d}T{rep_t}:00Z"
        except Exception:
            repaired_time_str = f"{repair_date(None)}T17:00:00Z"
            
        sys_c = get_query_customer_id()
        from workflows.booking_workflow import reschedule_appointment_workflow
        return reschedule_appointment_workflow(appointment_id=repaired_appt, new_start_time=repaired_time_str, customer_id=sys_c)
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
        from tools.mcp_tool import mcp_execute
        sys_c = get_query_customer_id()
        user_ctx = {"user_id": sys_c or "system", "role": "CUSTOMER", "customer_id": repaired_cust}
        res = mcp_execute(
            resource="appointments",
            operation="select",
            filters={"customer_id": repaired_cust},
            agent_name="Clara",
            user_context=user_ctx,
            limit=50
        )
        from utils.typed_responses import TypedAgentResponse
        if res.get("success"):
            records = res.get("data", [])
            return str(TypedAgentResponse.appointment_history(records).to_agent_dict())
        else:
            return str(TypedAgentResponse.general_error(res.get("error", "Failed to retrieve booking history")).to_agent_dict())
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run)
        try:
            return str(future.result(timeout=25.0))
        except concurrent.futures.TimeoutError:
            return "Error: Tool execution timed out."


# ============================================================================
# RESPONSE NORMALIZATION LAYER
# ============================================================================

def append_upsells_if_booking_confirmed(text: str) -> str:
    """
    Checks if the response is a successful booking confirmation.
    If it is, and the '🎁 Recommended Add-on Treatments' block is missing,
    detects the Service and appends the appropriate Zenoti smart upsells.
    """
    if not text:
        return text
        
    # Check if this is a confirmed booking
    import re
    # Match "status: confirmed" or "status:\nconfirmed" or "status:\n\nconfirmed" or "status: CONFIRMED"
    status_match = re.search(r"status:\s*(\n\s*)*confirmed", text, re.IGNORECASE)
    if not status_match:
        return text
        
    # Check if upsells are already present
    if "Zenoti smart upsell" in text or "Recommended Add-on" in text or "🎁" in text:
        return text
        
    # Extract Service Name to determine the correct upsell recommendations
    service_match = re.search(r"service:\s*([^\n\r]+)", text, re.IGNORECASE)
    service_name = "Styling Session"
    if service_match:
        service_name = service_match.group(1).strip()
        # Clean any markdown/asterisks/underscores
        service_name = re.sub(r"[\*\_]", "", service_name)
        
    # Determine correct upsell recommendations based on Service Name
    upsells = []
    if "haircut" in service_name.lower():
        upsells = ["Hair Spa ($55)", "Special Head Massage ($25)", "Professional Beard Styling ($35)"]
    elif "massage" in service_name.lower():
        upsells = ["Luxury Facial Treatment ($120)", "Himalayan Sea Salt foot wash ($30)"]
    else:
        upsells = ["Signature Precision Haircut ($85)", "Special Head Massage ($25)"]
        
    # Replace the Status: Confirmed line with the full Status and Recommended Add-on block
    status_line_regex = r"status:\s*(\n\s*)*confirmed"
    
    upsell_block = (
        "Status:\n\nConfirmed\n\n"
        "🎁 Recommended Add-on Treatments (Zenoti smart upsell):\n\n" +
        "\n".join(upsells)
    )
    
    # We perform case-insensitive substitution of the status line with the new block
    # Only replace the first occurrence
    text_with_upsells = re.sub(status_line_regex, upsell_block, text, count=1, flags=re.IGNORECASE)
    return text_with_upsells


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
                if data.get("success") and "appointment_id" in data and data.get("operation") != "select":
                    service_name = data.get("service_name") or "Styling Session"
                    upsells = []
                    if "haircut" in service_name.lower():
                        upsells = ["Hair Spa ($55)", "Special Head Massage ($25)", "Professional Beard Styling ($35)"]
                    elif "massage" in service_name.lower():
                        upsells = ["Luxury Facial Treatment ($120)", "Himalayan Sea Salt foot wash ($30)"]
                    else:
                        upsells = ["Signature Precision Haircut ($85)", "Special Head Massage ($25)"]
                    return (
                        f"I have successfully secured your styling appointment! "
                        f"Your booking has been confirmed.\n\n"
                        f"Status:\n\nConfirmed\n\n"
                        f"🎁 Recommended Add-on Treatments (Zenoti smart upsell):\n\n" +
                        "\n".join(upsells)
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
            
    text_clean = append_upsells_if_booking_confirmed(text_clean)
    return text_clean



# ============================================================================
# HYPER-FOCUSED 10-RULE SYSTEM PROMPT (REDUCED BY >50%)
# ============================================================================

RECEPTIONIST_SYSTEM_PROMPT = """You are Clara, a professional AI Salon Receptionist. You manage appointments and salon inquiries.

Absolute Rules:
1. NEVER INVENT DATA: If user provides service, branch, stylist, date, time, price, use those EXACT values. Never alter, replace, or suggest alternatives.
2. BOOKING REQUESTS ARE TOOL TASKS: Immediately execute the appropriate tool. DO NOT CHAT, explain, list services/branches, or greet again.
3. REQUIRED BOOKING FLOW: Extract service, branch, stylist, date, time -> Call mcp_read(resource="appointments", operation="check_availability", filters={"branch_id": ..., "date": ..., "staff_id": ..., "service_id": ...}). If available, return booking confirmation. If not, offer alternatives.
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
   Status:

   Confirmed

   🎁 Recommended Add-on Treatments (Zenoti smart upsell):

   [Upsell Items]

   Where [Upsell Items] are determined as:
   - If Service contains "haircut" (case-insensitive):
     Hair Spa ($55)
     Special Head Massage ($25)
     Professional Beard Styling ($35)
   - If Service contains "massage" (case-insensitive):
     Luxury Facial Treatment ($120)
     Himalayan Sea Salt foot wash ($30)
   - Otherwise:
     Signature Precision Haircut ($85)
     Special Head Massage ($25)
8. AVAILABILITY QUESTIONS: For "Is this slot available?", immediately call availability check via mcp_read. Do not explain services or suggest options.
9. TOOL FAILURE: If tool fails, output exactly "I could not verify availability right now." Never fake availability.
10. ROLE: You are purely an appointment booking, cancellation, rescheduling, history management, and salon information/policies assistant. Never act as sales or marketing agent.
11. RECEPTIONIST KNOWLEDGE BASE: For any questions about salon policies, business hours/timings, active offers/promotions, refunds, cancellations, FAQs, or general salon information, ALWAYS execute `search_knowledge_base(domain="policies", query=...)` first. Never invent timings, policies, or offers. If no information is found in the knowledge base, state exactly: 'I couldn't find that information in the salon knowledge base.'
12. TRANSACTIONAL WORKFLOWS: All modifications/mutations to appointments (booking, canceling, rescheduling) are processed securely through execute_transaction().

For every booking-related message, TOOL EXECUTION IS MANDATORY."""


# ============================================================================
# RECEPTIONIST AGENT CLASS WITH SEQUENTIAL COOLDOWN TIMEOUT FALLBACKS
# ============================================================================

# ============================================================================
# RECEPTIONIST PLANNER — Structured Task Decomposition
# ============================================================================
# Replaces the old fragile keyword-only intent shortcut.
#
# The planner asks a tiny LLM call to return a structured JSON plan with:
#   - confidence  : float 0-1 (< 0.70 triggers a clarifying question)
#   - tasks       : list of task dicts, each with 'action' and optional args
#
# Example plan for "Cancel my haircut and rebook for next Friday at 3pm":
#   {
#     "confidence": 0.97,
#     "tasks": [
#       {"action": "cancel",   "appointment_reference": "current"},
#       {"action": "book",     "date": "next friday", "time": "3pm",
#        "service": "haircut", "stylist": null, "branch": null}
#     ]
#   }
# ============================================================================

_PLANNER_SYSTEM_PROMPT = """\
You are a task planning assistant for a salon receptionist AI.
Given the user's message, return a JSON plan (no extra text, raw JSON only).

Schema:
{
  "confidence": <float 0.0-1.0>,
  "tasks": [
    {
      "action": "<one of: book|cancel|reschedule|availability|history|policy_faq|general_chat>",
      "service": "<service name or null>",
      "branch": "<branch name or null>",
      "stylist": "<stylist name or null>",
      "date": "<date string or null>",
      "time": "<time string or null>",
      "appointment_reference": "<'current'|'last'|appointment_id or null>"
    }
  ]
}

Rules:
- Set confidence < 0.70 if the user's intent is truly ambiguous.
- Include ALL actions from the message (e.g. cancel + rebook = two tasks).
- Extract date/time/service/stylist EXACTLY as stated — do not paraphrase.
- Output ONLY valid JSON. No explanation.
- Distinguish 'history' vs 'availability':
  * Use 'history' when the user asks about their own booked/existing appointments (e.g., "do I have any appointments", "is I have any appointments", "when is my booking", "give me my appointments", "check my schedule").
  * Use 'availability' ONLY when the user asks if the salon or a stylist has open/free slots for booking a new appointment (e.g., "is there any slot open", "are you free", "check openings")."""

_PLANNER_CONFIDENCE_THRESHOLD = 0.70  # Below this -> ask a clarifying question


async def _run_planner(
    latest_message: str,
    fallback_queue: List[Dict],
) -> Dict:
    """
    Run the ReceptionistPlanner against the given message using the fastest
    available LLM in the fallback queue.

    Returns the parsed plan dict, or a safe default plan on failure.
    """
    import json as _json

    default_plan = {
        "confidence": 0.50,
        "tasks": [{"action": "unknown", "service": None, "branch": None,
                   "stylist": None, "date": None, "time": None,
                   "appointment_reference": None}],
    }

    for tier in fallback_queue:
        model_name = tier["model"]
        if model_name in ReceptionistAgent.MODEL_COOLDOWN and \
                time.time() < ReceptionistAgent.MODEL_COOLDOWN[model_name]:
            continue
        try:
            timeout_val = 10.0 if tier["provider"] == "huggingface" else 12.0
            client = OpenAIChatCompletionClient(
                model=model_name,
                api_key=tier["api_key"],
                base_url=tier["base_url"],
                timeout=timeout_val,
            )
            from autogen_core.models import SystemMessage, UserMessage
            import asyncio as _asyncio
            res = await _asyncio.wait_for(
                client.create(
                    messages=[
                        SystemMessage(content=_PLANNER_SYSTEM_PROMPT),
                        UserMessage(content=f"User message: {latest_message[:500]}", source="user"),
                    ],
                    max_tokens=300,
                ),
                timeout=timeout_val,
            )
            raw = (res.content or "").strip()
            # Strip markdown fences if present
            if "```" in raw:
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            plan = _json.loads(raw.strip())
            # Convert legacy intent JSON structure if present (e.g. from tests or old models)
            if "intent" in plan and "tasks" not in plan:
                action = plan.get("intent")
                task = {
                    "action": action,
                    "service": plan.get("service"),
                    "branch": plan.get("branch"),
                    "stylist": plan.get("stylist"),
                    "date": plan.get("date"),
                    "time": plan.get("time"),
                    "appointment_reference": plan.get("appointment_id")
                }
                plan = {
                    "confidence": 0.95,
                    "tasks": [task]
                }
            # Validate minimal schema
            if "tasks" in plan and isinstance(plan["tasks"], list):
                plan.setdefault("confidence", 0.90)
                return plan
        except Exception as exc:
            logger.warning("[Planner] Failed on model '%s': %s", model_name, str(exc)[:100])
            err_str = str(exc)
            if "401" in err_str or "unauthorized" in err_str.lower():
                ReceptionistAgent.MODEL_COOLDOWN[model_name] = time.time() + 300
            else:
                cooldown_secs = 15 if tier["provider"] == "huggingface" else 1800
                ReceptionistAgent.MODEL_COOLDOWN[model_name] = time.time() + cooldown_secs

    return default_plan


def _select_agent_tools(planned_tasks: List[Dict]) -> List[Any]:
    """
    Dynamically select only the tools required by the planned tasks from the consolidated tool suite.
    """
    from tools.mcp_tool import mcp_read
    from tools.rag_unified import search_knowledge_base
    from tools.transaction_unified import execute_transaction

    actions = {t.get("action", "") for t in planned_tasks}
    tools: List[Any] = []

    # Map actions to consolidated tools
    # 1. Reads
    if any(act in actions for act in ("book", "cancel", "reschedule", "availability", "history")):
        tools.append(mcp_read)
    
    # 2. Writes / Transactions
    if any(act in actions for act in ("book", "cancel", "reschedule")):
        tools.append(execute_transaction)
        
    # 3. RAG/Knowledge
    if "policy_faq" in actions or "general_chat" in actions:
        tools.append(search_knowledge_base)

    if not tools:
        tools = [mcp_read, search_knowledge_base]

    # Ensure search_knowledge_base is always available as a fallback
    if search_knowledge_base not in tools:
        tools.append(search_knowledge_base)

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
            timeout=30.0
        )

        from tools.mcp_tool import mcp_read
        from tools.rag_unified import search_knowledge_base
        from tools.transaction_unified import execute_transaction

        self.assistant = AssistantAgent(
            name=name,
            model_client=self.model_client,
            system_message=RECEPTIONIST_SYSTEM_PROMPT,
            tools=[
                mcp_read,
                search_knowledge_base,
                execute_transaction,
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
        query = (input_data.get("full_query") or input_data.get("query", "")).strip()
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

        # ── NOTE: Greeting / thanks / farewell fast-path is handled at the ────────
        # ── Orchestrator level (zero LLM tokens). Only real intent queries ────────
        # ── reach this point inside ReceptionistAgent.process()            ────────

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

        # ── STEP 1: PLANNER — Structured task decomposition (replaces dual extraction) ─
        plan = await _run_planner(latest_message, fallback_queue)
        plan_confidence = float(plan.get("confidence", 0.50))
        plan_tasks: List[Dict] = plan.get("tasks", [{}])

        logger.info(
            "[Planner] confidence=%.2f  tasks=%s",
            plan_confidence,
            [{t.get('action'): {k: v for k, v in t.items() if k != 'action' and v}} for t in plan_tasks]
        )

        # ── STEP 2: Confidence gating — ask clarifying question if ambiguous ──────
        if plan_confidence < _PLANNER_CONFIDENCE_THRESHOLD:
            clarify_msg = (
                f"I want to make sure I understand you correctly. Could you clarify — "
                f"are you looking to **book**, **cancel**, **reschedule**, or **check "
                f"availability** for an appointment, or did you have a different question?"
            )
            logger.info("[Planner] Low confidence (%.2f) — returning clarification request.", plan_confidence)
            return {
                "success": True,
                "agent_name": self.name,
                "response": clarify_msg,
                "provider": "planner_clarification",
                "response_type": "clarification_needed",
            }

        # ── STEP 3: Map plan to backward-compatible intent_json ───────────────────
        # Use the FIRST task as the primary intent; all tasks drive tool selection.
        primary_task = plan_tasks[0] if plan_tasks else {}
        intent_json = {
            "intent":   primary_task.get("action", "chat"),
            "service":  primary_task.get("service"),
            "branch":   primary_task.get("branch"),
            "stylist":  primary_task.get("stylist"),
            "date":     primary_task.get("date"),
            "time":     primary_task.get("time"),
            "appointment_id": primary_task.get("appointment_reference"),
        }

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
            import json as _json
            slots_dict = {}
            try:
                slots_dict = ast.literal_eval(slots_data)
            except Exception:
                try:
                    slots_dict = _json.loads(slots_data)
                except Exception:
                    pass

            # Handle TypedAgentResponse wrapper: slots may be nested under data.slots
            def _extract_slots(d):
                """Extract slots list from dict, handling both flat and nested TypedAgentResponse formats."""
                if not isinstance(d, dict):
                    return []
                # Direct top-level slots key
                if d.get("slots") is not None:
                    return d.get("slots", [])
                # TypedAgentResponse format: data.slots
                data_field = d.get("data")
                if isinstance(data_field, dict) and data_field.get("slots") is not None:
                    return data_field.get("slots", [])
                return []

            # Handle staff_on_leave: check both top-level and nested under data
            def _get_field(d, key, default=None):
                """Get field from dict, checking top-level and data nested key."""
                if not isinstance(d, dict):
                    return default
                val = d.get(key)
                if val is not None:
                    return val
                data_field = d.get("data")
                if isinstance(data_field, dict):
                    return data_field.get(key, default)
                return default

            staff_on_leave = _get_field(slots_dict, "staff_on_leave", False)
            if staff_on_leave:
                staff_name = _get_field(slots_dict, "staff_name") or "The stylist"
                slots = _extract_slots(slots_dict)
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

            has_error = False
            if not slots_data:
                has_error = True
            elif slots_dict:
                # Check success from top-level or TypedAgentResponse wrapper
                is_success = slots_dict.get("success", True)
                if not is_success and not staff_on_leave:
                    # Also check if there's an error field
                    err_val = slots_dict.get("error")
                    if err_val:
                        has_error = True
            else:
                if "error" in str(slots_data).lower():
                    has_error = True

            if has_error:
                return {
                    "success": True,
                    "agent_name": self.name,
                    "response": f"{pref_str}\n\nI could not verify availability right now.",
                    "provider": "booking_engine"
                }

            # Smart Slot Suggestions (Rule 12)
            # Parse available slots to check if the requested time is free
            # Handle TypedAgentResponse format: slots may be nested under data.slots
            slots = _extract_slots(slots_dict)
                
            is_requested_slot_available = False
            for s in slots:
                start_iso = s.get("start_time", "")
                if f"{repaired_date}T{repaired_time}" in start_iso:
                    is_requested_slot_available = True
                    break
            
            # If no slots returned at all but availability check succeeded, allow booking
            # (the slot validation inside create_appointment will handle conflicts)
            if not slots and slots_dict.get("success", True):
                is_requested_slot_available = True
                    
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
                try:
                    import json as _bjson
                    booking_res = _bjson.loads(booking_res_str)
                except Exception:
                    booking_res = {"success": False, "error": booking_res_str}
            
            # Handle TypedAgentResponse wrapper: unwrap if needed
            if isinstance(booking_res, dict) and "response_type" in booking_res and "data" in booking_res:
                inner_data = booking_res.get("data") or {}
                booking_res = {
                    "success": booking_res.get("success", False),
                    "appointment_id": inner_data.get("appointment_id"),
                    "error": booking_res.get("error"),
                }
                if inner_data.get("appointment_id"):
                    booking_res["success"] = True
                
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
                f"Status:\n\nConfirmed\n\n"
                f"🎁 Recommended Add-on Treatments (Zenoti smart upsell):\n\n" + 
                "\n".join(upsells)
            )
            
            # Parse upsells to get name and price
            smart_upsells = []
            for u in upsells:
                try:
                    name_part, price_part = u.split("($")
                    name = name_part.strip()
                    price = float(price_part.replace(")", "").strip())
                    smart_upsells.append({"name": name, "price": price})
                except Exception:
                    smart_upsells.append({"name": u, "price": 0.0})

            data_payload = {
                "transaction_type": "booking_confirmation",
                "appointment": {
                    "id": booking_res.get("appointment_id") if isinstance(booking_res, dict) else None,
                    "service": service_name,
                    "price": float(price_val) if price_val else 0.0,
                    "stylist": stylist_name,
                    "date": repaired_date,
                    "time": repaired_time,
                    "status": "Confirmed"
                },
                "smart_upsells": smart_upsells
            }

            return {
                "success": True,
                "agent_name": self.name,
                "response": confirm_msg,
                "provider": "booking_engine",
                "data": data_payload
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
            slots_dict = {}
            is_staff_leave_err = False
            try:
                slots_dict = ast.literal_eval(slots_data)
                if slots_dict.get("staff_on_leave"):
                    is_staff_leave_err = True
            except Exception:
                pass

            has_error = False
            if not slots_data:
                has_error = True
            elif slots_dict:
                if not slots_dict.get("success") and not is_staff_leave_err:
                    has_error = True
            else:
                if "error" in slots_data.lower() and not is_staff_leave_err:
                    has_error = True

            if has_error:
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
            
            # Check if this is a specific natural language query about history (contains dates, question words, or specific keywords)
            specific_keywords = [
                "spend", "cost", "pay", "charge", "last", "recent", "how many", "count", 
                "this month", "this year", "year", "month", "total", "sum", "price", "value",
                "jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec",
                "mon", "tue", "wed", "thu", "fri", "sat", "sun", "today", "tomorrow", "yesterday",
                "week", "slot", "when", "which", "do i", "is i", "have i", "any", "are there", "is there"
            ]
            is_specific_query = any(k in query.lower() for k in specific_keywords) or any(char.isdigit() for char in query)
            
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
        _agent_tools = _select_agent_tools(plan_tasks)

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

                    client_timeout = 10.0 if provider == "huggingface" else 30.0
                    run_timeout = 15.0 if provider == "huggingface" else 30.0

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
                        
                        # Parse the JSON response to see if it is a SELECT/history/list operation vs an INSERT/new booking confirmation
                        formatter_sys_prompt = None
                        try:
                            import json
                            data = json.loads(response_stripped)
                        except Exception:
                            try:
                                import ast
                                data = ast.literal_eval(response_stripped)
                            except Exception:
                                data = None
                                
                        if isinstance(data, dict):
                            response_type = str(data.get("response_type", "")).lower()
                            resource = str(data.get("resource", "")).lower()
                            operation = str(data.get("operation", "")).lower()
                            
                            # Check if the raw result failed
                            if not data.get("success", True) or response_type == "general_error" or (data.get("error") is not None and data.get("error") != ""):
                                formatter_sys_prompt = (
                                    "You are Clara, a professional AI Salon Receptionist.\n"
                                    "Translate this raw system/tool error into a warm, polite customer-facing explanation.\n"
                                    "Rules:\n"
                                    "- Explain the error politely without technical terms (do not say 'database', 'UUID', 'SQL', etc.).\n"
                                    "- Ask the user if they would like to try a different time, date, or stylist."
                                )
                            elif (resource == "appointments" and operation == "select") or response_type == "appointment_history":
                                formatter_sys_prompt = (
                                    "You are Clara, a professional AI Salon Receptionist.\n"
                                    "Translate this booking history list into a warm, professional styling history summary.\n"
                                    "Rules:\n"
                                    "- List each appointment clearly: Service, Stylist, Branch, Date, Time, and Status.\n"
                                    "- Format it nicely using markdown lists.\n"
                                    "- Address the client politely."
                                )
                            elif (resource == "reviews" and operation == "select") or response_type in ("review_submitted", "review_escalated"):
                                formatter_sys_prompt = (
                                    "You are Clara, a professional AI Salon Receptionist.\n"
                                    "Translate this customer reviews list into a clean, warm, and professional summary of the customer's reviews.\n"
                                    "Rules:\n"
                                    "- List each review: Rating (stars), Service, Stylist, Comment, and Date.\n"
                                    "- Address the client politely."
                                )
                            elif resource == "services" and operation == "select":
                                formatter_sys_prompt = (
                                    "You are Clara, a professional AI Salon Receptionist.\n"
                                    "Translate this services list into a clean, professional catalog listing of available services and prices.\n"
                                    "Rules:\n"
                                    "- Present each service with its name, description, duration, and price.\n"
                                    "- Format it nicely using markdown lists or tables."
                                )
                                
                        if not formatter_sys_prompt:
                            formatter_sys_prompt = (
                                "You are Clara, a professional AI Salon Receptionist.\n"
                                "Translate this raw system/tool result into a warm, professional booking confirmation.\n"
                                "Rules:\n"
                                "- Confirm precisely using the exact values from the tool results.\n"
                                "- Follow the confirmation format: Service, Branch, Stylist, Date, Time, Price, and Status.\n"
                                "- Under the Status line, you MUST append the following recommended add-on treatments based on the Service:\n"
                                "  - If Service contains 'haircut' (case-insensitive):\n"
                                "    🎁 Recommended Add-on Treatments (Zenoti smart upsell):\n\n"
                                "    Hair Spa ($55)\n"
                                "    Special Head Massage ($25)\n"
                                "    Professional Beard Styling ($35)\n"
                                "  - If Service contains 'massage' (case-insensitive):\n"
                                "    🎁 Recommended Add-on Treatments (Zenoti smart upsell):\n\n"
                                "    Luxury Facial Treatment ($120)\n"
                                "    Himalayan Sea Salt foot wash ($30)\n"
                                "  - Otherwise:\n"
                                "    🎁 Recommended Add-on Treatments (Zenoti smart upsell):\n\n"
                                "    Signature Precision Haircut ($85)\n"
                                "    Special Head Massage ($25)\n"
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

                    # Use the Response Renderer instead of the old normalize_response()
                    # This prevents type mis-detection (e.g. review -> booking_confirmation).
                    from utils.renderer import render_response as _render_response
                    _response_type = input_data.get("response_type", "general_chat")
                    rendered_text = _render_response({
                        "response_type": _response_type,
                        "text": response_text,
                        "data": input_data.get("response_data"),
                    })

                    return {
                        "success": True,
                        "agent_name": self.name,
                        "response": rendered_text,
                        "response_type": _response_type,
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
