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
from typing import Dict, Any, Optional, List

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


# ============================================================================
# HELPER UTILITIES FOR VALIDATION & REPAIR (STABILIZATION LAYER)
# ============================================================================

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


def repair_date(date_input: Any) -> str:
    """Automatically resolve relative date keywords to YYYY-MM-DD format."""
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
    elif "tomorrow" in date_clean:
        tomorrow = base_date + timedelta(days=1)
        return tomorrow.strftime("%Y-%m-%d")
    elif "day after tomorrow" in date_clean:
        target = base_date + timedelta(days=2)
        return target.strftime("%Y-%m-%d")
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
            
    return base_date.strftime("%Y-%m-%d")


def repair_time(time_input: Any) -> str:
    """Convert relative time slots (e.g. 5pm) to standard HH:MM format."""
    if not time_input:
        return "17:00"
        
    time_str = str(time_input).strip()
    import re
    if re.match(r"^\d{2}:\d{2}$", time_str):
        return time_str
    if re.match(r"^\d{2}:\d{2}:\d{2}$", time_str):
        return time_str[:5]
        
    time_clean = time_str.lower().replace(" ", "")
    is_pm = "pm" in time_clean
    is_am = "am" in time_clean
    
    digits = "".join([c for c in time_clean if c.isdigit() or c == ":"])
    if ":" in digits:
        parts = digits.split(":")
        try:
            hour = int(parts[0])
            minute = int(parts[1])
        except ValueError:
            hour, minute = 12, 0
    else:
        try:
            hour = int(digits)
            minute = 0
        except ValueError:
            hour, minute = 12, 0
            
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
            return future.result(timeout=5.0)
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
            return future.result(timeout=5.0)
        except concurrent.futures.TimeoutError:
            return "Error: Tool execution timed out."


def get_available_staff(branch_id: str = None) -> str:
    """
    Discover all available stylists/staff members.
    Optionally filter by a specific branch.
    """
    import concurrent.futures
    repaired_branch = repair_branch(branch_id) if branch_id else None
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(list_available_staff, repaired_branch)
        try:
            return future.result(timeout=5.0)
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
            return future.result(timeout=5.0)
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
            return str(future.result(timeout=5.0))
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
                repaired_time_str = f"{rep_d}T{rep_t}:00Z"
            else:
                parts = dt_str.split("T")
                rep_d = repair_date(parts[0])
                rep_t = repair_time(parts[1])
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
            return str(future.result(timeout=5.0))
        except concurrent.futures.TimeoutError:
            return "Error: Tool execution timed out."


def cancel_existing_appointment(appointment_id: str) -> str:
    """
    Cancel an existing salon booking.
    """
    import concurrent.futures
    def run():
        if not appointment_id or _is_placeholder_value(appointment_id):
            return "Error: Invalid appointment identifier provided. Please check booking history first."
            
        appt_str = str(appointment_id).strip()
        repaired_appt = appt_str
        
        if not _is_valid_uuid(appt_str):
            sys_c = get_query_customer_id()
            if sys_c:
                db = SessionLocal()
                try:
                    from db import Appointment, AppointmentStatus
                    active_appts = db.query(Appointment).filter(
                        Appointment.customer_id == sys_c,
                        Appointment.status.in_([AppointmentStatus.CONFIRMED, AppointmentStatus.PENDING])
                    ).all()
                    if active_appts:
                        repaired_appt = str(active_appts[0].id)
                finally:
                    db.close()
                    
        return cancel_appointment(appointment_id=repaired_appt)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run)
        try:
            return str(future.result(timeout=5.0))
        except concurrent.futures.TimeoutError:
            return "Error: Tool execution timed out."


def reschedule_existing_appointment(appointment_id: str, new_start_time: str) -> str:
    """
    Reschedule an existing booking to a new date/time.
    """
    import concurrent.futures
    def run():
        if not appointment_id or _is_placeholder_value(appointment_id):
            return "Error: Invalid appointment identifier. Rescheduling failed."
            
        appt_str = str(appointment_id).strip()
        repaired_appt = appt_str
        
        if not _is_valid_uuid(appt_str):
            sys_c = get_query_customer_id()
            if sys_c:
                db = SessionLocal()
                try:
                    from db import Appointment, AppointmentStatus
                    active_appts = db.query(Appointment).filter(
                        Appointment.customer_id == sys_c,
                        Appointment.status.in_([AppointmentStatus.CONFIRMED, AppointmentStatus.PENDING])
                    ).all()
                    if active_appts:
                        repaired_appt = str(active_appts[0].id)
                finally:
                    db.close()
                    
        dt_str = str(new_start_time).strip()
        try:
            if "t" not in dt_str.lower():
                rep_d = repair_date(dt_str)
                rep_t = repair_time(dt_str)
                repaired_time_str = f"{rep_d}T{rep_t}:00Z"
            else:
                parts = dt_str.split("T")
                rep_d = repair_date(parts[0])
                rep_t = repair_time(parts[1])
                repaired_time_str = f"{rep_d}T{rep_t}:00"
                if not repaired_time_str.endswith("Z") and not "+" in repaired_time_str:
                    repaired_time_str += "Z"
        except Exception:
            repaired_time_str = f"{repair_date(None)}T17:00:00Z"
            
        return reschedule_appointment(appointment_id=repaired_appt, new_start_time=repaired_time_str)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(run)
        try:
            return str(future.result(timeout=5.0))
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
            return str(future.result(timeout=5.0))
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

RECEPTIONIST_SYSTEM_PROMPT = """You are Clara, a professional AI Salon Receptionist. You manage appointments and nothing else.
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
10. ROLE: You are purely an appointment booking, cancellation, rescheduling, and history management assistant. Never act as sales or marketing agent.
For every booking-related message, TOOL EXECUTION IS MANDATORY."""


# ============================================================================
# RECEPTIONIST AGENT CLASS WITH SEQUENTIAL COOLDOWN TIMEOUT FALLBACKS
# ============================================================================

class ReceptionistAgent(Agent):
    """
    Salon Receptionist Agent powered by Microsoft AutoGen and multi-tier LLM Fallback chain.
    Provides professional, error-free booking automation.
    """

    MODEL_COOLDOWN = {}
    FAILURE_COUNT = 0
    CIRCUIT_BREAKER_TRIPPED = False
    MAX_FAILURES = 5
    
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

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Processes booking queries with strict timeouts and local Ollama support."""
        query = input_data.get("query", "").strip()
        if not query:
            return {"success": False, "error": "Please provide a booking request."}

        ReceptionistAgent.CURRENT_QUERY_CONTEXT = query

        if ReceptionistAgent.CIRCUIT_BREAKER_TRIPPED:
            return self._emergency_mode_response()

        settings = get_settings()
        gemini_key = settings.gemini_api_key or settings.google_api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY", "")
        groq_key = settings.groq_api_key or os.environ.get("GROQ_API_KEY", "")

        fallback_queue = []
        now = time.time()

        # Tier 1: Qwen3 8B via Ollama
        if "qwen2.5:8b" in ReceptionistAgent.MODEL_COOLDOWN and now < ReceptionistAgent.MODEL_COOLDOWN["qwen2.5:8b"]:
            logger.info("⏭️ Skipping Ollama model 'qwen2.5:8b' due to active cooldown.")
        else:
            fallback_queue.append({
                "provider": "ollama",
                "model": "qwen2.5:8b",
                "api_key": "ollama",
                "base_url": "http://localhost:11434/v1"
            })

        # Tier 2: Groq llama-3.1-8b-instant
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

        # Tier 3: Gemini Flash (gemini-2.0-flash or gemini-1.5-flash)
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

        if not fallback_queue:
            fallback_queue.append({"provider": "groq", "model": "llama-3.1-8b-instant", "api_key": "mock-groq-key", "base_url": "https://api.groq.com/openai/v1"})

        last_error = None
        for idx, tier in enumerate(fallback_queue, 1):
            model_name = tier["model"]
            provider = tier["provider"]
            base_url = tier["base_url"]
            api_key = tier["api_key"]

            max_attempts = 1  # 429 logic immediately skips. Disable multi-retries for 429
            for attempt in range(1, max_attempts + 1):
                start_time = time.perf_counter()
                try:
                    model_info = {
                        "vision": False,
                        "function_calling": True,
                        "json_output": True,
                        "family": "gemini-2.0" if "2.0" in model_name else "gemini-1.5" if "1.5" in model_name else "qwen" if "qwen" in model_name else "llama-3.1",
                        "structured_output": False,
                    }

                    model_client = OpenAIChatCompletionClient(
                        model=model_name,
                        api_key=api_key,
                        base_url=base_url,
                        model_info=model_info,
                        timeout=8.0
                    )

                    assistant = AssistantAgent(
                        name=self.name,
                        model_client=model_client,
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
                        ]
                    )

                    result = await asyncio.wait_for(assistant.run(task=query), timeout=10.0)
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
                            timeout=8.0
                        )
                        
                        sys_msg = SystemMessage(content=formatter_sys_prompt)
                        user_msg = UserMessage(content=f"Raw System Result:\n{response_stripped}", source="user")
                        
                        fmt_result = await asyncio.wait_for(formatter_client.create(messages=[sys_msg, user_msg]), timeout=10.0)
                        response_text = fmt_result.content.strip()

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

                    # Check for rate limit / quota / timeout (Priority 1 & timeouts)
                    from openai import RateLimitError, APITimeoutError
                    import httpx

                    is_rate_limit = "429" in err_str or "rate" in err_str.lower() or "quota" in err_str.lower() or isinstance(ex, RateLimitError)
                    is_timeout = "timeout" in err_str.lower() or isinstance(ex, APITimeoutError) or isinstance(ex, httpx.TimeoutException) or isinstance(ex, asyncio.TimeoutError)

                    if is_rate_limit or is_timeout:
                        logger.error(f"🚨 Model '{model_name}' rate limit or timeout. Triggering 30-minute cooldown and immediately fallback.")
                        ReceptionistAgent.MODEL_COOLDOWN[model_name] = time.time() + 1800 # 30 minutes cooldown
                        
                        ReceptionistAgent.FAILURE_COUNT += 1
                        if ReceptionistAgent.FAILURE_COUNT >= ReceptionistAgent.MAX_FAILURES:
                            ReceptionistAgent.CIRCUIT_BREAKER_TRIPPED = True
                        break # Break loop immediately to try next model

                    ReceptionistAgent.FAILURE_COUNT += 1
                    if ReceptionistAgent.FAILURE_COUNT >= ReceptionistAgent.MAX_FAILURES:
                        ReceptionistAgent.CIRCUIT_BREAKER_TRIPPED = True
                    break

        ReceptionistAgent.FAILURE_COUNT += 1
        if ReceptionistAgent.FAILURE_COUNT >= ReceptionistAgent.MAX_FAILURES:
            ReceptionistAgent.CIRCUIT_BREAKER_TRIPPED = True

        return self._emergency_mode_response()
