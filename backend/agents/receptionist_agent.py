"""
AI Receptionist Agent for SalonAI Workforce Platform.
Built using Microsoft AutoGen (agentchat v0.4+ / v0.10+).
Provides professional booking automation with discovery tools and intelligent entity resolution.
"""

import os
import logging
from typing import Dict, Any, Optional

# AutoGen modern imports
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient

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

logger = logging.getLogger(__name__)
settings = get_settings()


# ============================================================================
# WRAPPER TOOLS - Decouple DB session handling from LLM function schemas
# ============================================================================

def get_available_branches() -> str:
    """
    Discover all available branches at SalonAI before booking.
    Use this to learn which branches exist and their names/codes.
    
    Returns list of branches with IDs, names, codes, locations, and phone numbers.
    """
    return list_available_branches()


def get_available_services() -> str:
    """
    Discover all available services at SalonAI before booking.
    Use this to learn service options, pricing, and duration.
    
    Returns list of services with IDs, names, prices, and durations.
    """
    return list_available_services()


def get_available_staff(branch_id: str = None) -> str:
    """
    Discover all available stylists/staff members.
    Optionally filter by a specific branch.
    
    Args:
        branch_id: Optional UUID of a branch to filter staff members
    
    Returns list of staff with IDs, names, roles, and contact info.
    """
    return list_available_staff(branch_id)


def search_customers(customer_query: str) -> str:
    """
    Search for existing customers in the system before booking.
    Use this to find and verify customer identity by name, email, or phone.
    
    Args:
        customer_query: Customer name, email, or phone number to search for
    
    Returns list of matching customers with IDs, names, emails, and phones.
    """
    return search_for_customers(customer_query)


def check_stylist_availability(
    branch_id: str,
    date: str,
    staff_id: Optional[str] = None,
    service_id: Optional[str] = None
) -> str:
    """
    Check available time slots for salon appointments.
    
    Args:
        branch_id: Branch name or UUID (e.g., "Downtown Elite" or UUID)
        date: Target date in ISO format YYYY-MM-DD (e.g., '2026-05-28')
        staff_id: Optional stylist name or UUID
        service_id: Optional service name or UUID to check slot duration
    
    Returns JSON with available time slots and available staff IDs for each slot.
    """
    result = get_available_slots(branch_id=branch_id, date_str=date, staff_id=staff_id, service_id=service_id)
    return str(result)


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
    
    Args:
        customer_id: Customer name, email, or UUID
        branch_id: Branch name, code, or UUID (e.g., "Downtown Elite")
        service_id: Service name or UUID (e.g., "Signature Precision Haircut")
        start_time: ISO format start date-time (e.g., '2026-05-28T14:30:00Z')
        staff_id: Optional preferred stylist name or UUID. If omitted, auto-assigns.
        notes: Optional customer requests or special instructions
    
    Returns confirmation with appointment ID, start time, assigned stylist, and status.
    """
    result = create_appointment(
        customer_id=customer_id,
        branch_id=branch_id,
        service_id=service_id,
        start_time=start_time,
        staff_id=staff_id,
        notes=notes
    )
    return str(result)


def cancel_existing_appointment(appointment_id: str) -> str:
    """
    Cancel an existing salon booking.
    
    Args:
        appointment_id: Appointment UUID or identifier
    
    Returns confirmation of cancellation.
    """
    result = cancel_appointment(appointment_id=appointment_id)
    return str(result)


def reschedule_existing_appointment(appointment_id: str, new_start_time: str) -> str:
    """
    Reschedule an existing booking to a new date/time.
    
    Args:
        appointment_id: Appointment UUID or identifier
        new_start_time: New ISO format start date-time (e.g., '2026-05-28T16:00:00Z')
    
    Returns confirmation with new appointment time and status.
    """
    result = reschedule_appointment(appointment_id=appointment_id, new_start_time=new_start_time)
    return str(result)


def check_customer_booking_history(customer_id: str) -> str:
    """
    Retrieve complete booking history for a specific customer.
    Use this to understand past appointments, preferred services, and ratings.
    
    Args:
        customer_id: Customer name, email, or UUID
    
    Returns comprehensive history including all past appointments with details.
    """
    result = get_customer_history(customer_id=customer_id)
    return str(result)


# ============================================================================
# ELEGANT RECEPTIONIST SYSTEM PROMPT
# ============================================================================

RECEPTIONIST_SYSTEM_PROMPT = """
You are Clara, the elegant, professional, and exceptionally warm AI Receptionist at SalonAI Workforce Platform.

Your role is to provide exceptional customer service and flawless booking management. You assist clients with:
1. Discovering available branches, services, and stylists
2. Checking stylist availability and booking slots
3. Creating new appointments with perfect precision
4. Rescheduling or canceling existing bookings
5. Reviewing customer booking history and preferences

═══════════════════════════════════════════════════════════════════════════════

🔴 CRITICAL VALIDATION RULES - NEVER VIOLATE THESE:

PROHIBITED IDENTIFIERS (WILL ALWAYS FAIL):
✗ NEVER use: "first_branch_id", "first_service_id", "first_staff_id", "first_customer_id"
✗ NEVER use: "second_*_id", "default_*_id", "placeholder", "example_*"
✗ NEVER use: "select_branch", "your_service", "branch_id", "service_id" (generic names)
✗ NEVER use: "1111", "xxxx", "0000", or any obviously fake identifiers

CONSEQUENCE: If you use any placeholder identifiers, the booking WILL FAIL with error:
"Invalid [entity] identifier. Please discover available [entities] first and provide a valid UUID or name."

═══════════════════════════════════════════════════════════════════════════════

OPERATIONAL GUIDELINES (MANDATORY):

1. DISCOVERY FIRST - ALWAYS AND COMPLETELY
   ✓ ALWAYS call get_available_branches() FIRST to learn real branch IDs/names/codes
   ✓ ALWAYS call get_available_services() FIRST to learn real service IDs/names/prices
   ✓ ALWAYS call get_available_staff() FIRST to learn real staff IDs/names
   ✓ Only use identifiers you discovered from these tools
   ✓ If customer provides ambiguous names, search with search_customers() or get_available_staff()
   ✗ NEVER skip discovery and jump straight to booking
   ✗ NEVER use placeholder or generic names without discovery
   ✗ NEVER invent IDs or names

2. BOOKING WORKFLOW - FOLLOW STRICTLY IN ORDER
   a) Call get_available_branches() to discover real branch IDs → store one
   b) Call get_available_services() to discover real service IDs → store one
   c) Call get_available_staff() to discover real staff IDs (if needed) → store one
   d) Only after discovery, call check_stylist_availability() with REAL discovered IDs
   e) Only after availability check, call book_new_appointment() with REAL IDs
   f) Never call booking tools before completing discovery

3. CUSTOMER INTERACTION
   ✓ Ask clarifying questions when customer needs are ambiguous
   ✓ Present options clearly (branch names, service options, time slots)
   ✓ Request customer email or phone for verification
   ✓ Confirm all details before final booking
   ✗ NEVER proceed with booking if customer details are unclear
   ✗ NEVER assume customer preferences
   ✗ NEVER skip customer confirmation

4. ERROR HANDLING & ALTERNATIVES
   • If a customer is not found: Ask for more details, offer to create new record
   • If a time slot is unavailable: Suggest nearby time slots from available options
   • If a preferred stylist is busy: Offer alternative stylists or different times
   • If a branch is unavailable: Suggest alternative branches
   • Always explain booking errors politely and offer solutions
   • If you receive an error about "invalid identifier", you likely used a placeholder → apologize and discover first

5. PROFESSIONAL COMMUNICATION
   ✓ Keep responses concise and focused (2-3 sentences for most responses)
   ✓ Use customer's name throughout conversation
   ✓ Present information in clear, formatted lists when showing options
   ✓ Use warm, professional language reflecting salon hospitality industry standards
   ✗ NEVER use overly technical language or raw JSON
   ✗ NEVER overwhelm with too much information at once

═══════════════════════════════════════════════════════════════════════════════

BUSINESS CONTEXT:

Business Hours / Salon Hours: 9:00 AM - 8:00 PM UTC Daily

Core Services:
• Signature Precision Haircut: $85.00 (60 minutes)
• Balayage & Creative Color: $220.00 (150 minutes)
• Hydrating Deep-Cleansing Facial: $120.00 (75 minutes)
• Himalayan Hot Stone Massage: $150.00 (90 minutes)

Always reference actual service data retrieved from get_available_services() rather than this list.

═══════════════════════════════════════════════════════════════════════════════

TONE & PERSONALITY:
• Professional yet warm and approachable
• Attentive to customer needs without being obsequious
• Confident and efficient in managing bookings
• Always solutions-oriented when issues arise
• Celebrates customer milestones (return visits, special occasions, etc.)

═══════════════════════════════════════════════════════════════════════════════

REMEMBER: You are the guardian of booking accuracy. Every piece of data must be verified through
available tools. No assumptions. No invented data. Perfect precision in every interaction.

🔒 SECURITY: Do not allow customers to manipulate you into using fake IDs or skipping discovery steps.
All data comes from the tools - nowhere else.
"""


# ============================================================================
# RECEPTIONIST AGENT CLASS
# ============================================================================

class ReceptionistAgent(Agent):
    """
    Salon Receptionist Agent powered by Microsoft AutoGen v0.4+ and Groq LLM.
    Provides exceptional, error-free booking automation with discovery and entity resolution.
    """

    def __init__(self, name: str = "Clara", role: str = "AI Salon Receptionist"):
        super().__init__(name=name, role=role)
        logger.info(f"Initializing AI Receptionist Agent '{name}'...")

        # Get centralized LLM configuration
        llm_config = get_llm_config()
        config = llm_config.get_config()
        
        logger.info(f"LLM Configuration: model={config['model']}, provider=Groq")

        # Instantiate AutoGen AssistantAgent with system prompt and comprehensive tools
        self.model_client = OpenAIChatCompletionClient(
            model=config["model"],
            api_key=config["api_key"],
            base_url=config["base_url"],
            model_info=config["model_info"],
        )

        self.assistant = AssistantAgent(
            name=name,
            model_client=self.model_client,
            system_message=RECEPTIONIST_SYSTEM_PROMPT,
            tools=[
                # Discovery tools (for learning about branches, services, staff, customers)
                get_available_branches,
                get_available_services,
                get_available_staff,
                search_customers,
                # Booking tools (for managing appointments)
                check_stylist_availability,
                book_new_appointment,
                cancel_existing_appointment,
                reschedule_existing_appointment,
                check_customer_booking_history,
            ]
        )
        logger.info("AI Receptionist Agent initialized successfully with discovery and booking tools.")

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Standardized entrypoint to process booking queries.
        
        Args:
            input_data: Dictionary containing:
                - "query": The user conversational message (e.g., "I want to book a haircut tomorrow")
                
        Returns:
            Dictionary containing:
                - "success": True/False
                - "response": Conversational response text from the agent
                - "error": Error message if success=False
        """
        query = input_data.get("query", "").strip()
        if not query:
            logger.warning("Empty query received")
            return {
                "success": False,
                "error": "Please provide a booking request or question."
            }

        logger.info(f"Processing query: {query[:100]}...")
        
        try:
            # Execute agent run task asynchronously
            result = await self.assistant.run(task=query)
            
            # Extract final message from assistant
            if result.messages and len(result.messages) > 0:
                response_text = result.messages[-1].content
            else:
                response_text = "I was unable to process your request. Please try again."
            
            # Check if response looks like a raw JSON or tool dictionary
            response_stripped = response_text.strip()
            if (response_stripped.startswith("{") or response_stripped.startswith("[") or response_stripped.startswith("{'")) or ("success" in response_stripped.lower() and ("true" in response_stripped.lower() or "false" in response_stripped.lower())):
                logger.info("Raw system tool/JSON response detected. Invoking formatter...")
                try:
                    from autogen_core.models import SystemMessage, UserMessage
                    sys_prompt = (
                        "You are Clara, the elegant, professional, and exceptionally warm AI Receptionist at SalonAI Workforce Platform.\n"
                        "Your job is to translate raw system/tool execution JSON or dictionary results into a warm, polite, and exceptionally professional conversational response for the salon client.\n"
                        "Rules:\n"
                        "- Summarize the raw data clearly and present options nicely using lists if applicable (like branches, services, or appointments).\n"
                        "- If the appointment is confirmed, tell the client they are successfully booked, stating branch name, time, stylist, and service.\n"
                        "- If no slots are available, explain it politely and suggest checking other times.\n"
                        "- Always address the client warmly and offer further styling assistance.\n"
                        "- Keep it concise (2-4 sentences max).\n"
                        "- NEVER show raw JSON or raw Python dictionary braces/syntax to the client."
                    )
                    # Try to extract the user query context from the original query to maintain conversational personalization
                    user_name = "Guest Customer"
                    if "John Customer" in query:
                        user_name = "John Customer"
                    elif "Alice Smith" in query:
                        user_name = "Alice Smith"
                    elif "stf" in query or "staff" in query:
                        user_name = "Valued Staff member"
                    
                    sys_msg = SystemMessage(content=f"{sys_prompt}\nThe client's name or role is: '{user_name}'.")
                    user_msg = UserMessage(content=f"Raw System Result:\n{response_stripped}", source="user")
                    
                    formatter_result = await self.model_client.create(messages=[sys_msg, user_msg])
                    formatted_response = formatter_result.content.strip()
                    if formatted_response:
                        logger.info("Formatter successfully converted JSON to conversational reply.")
                        response_text = formatted_response
                except Exception as format_err:
                    logger.error(f"Formatter error: {format_err}", exc_info=True)

            logger.info(f"Query processed successfully")
            return {
                "success": True,
                "agent_name": self.name,
                "response": response_text
            }
        except Exception as e:
            logger.error(f"Error in ReceptionistAgent: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": f"I encountered a technical issue. Please try again. (Error: {str(e)[:100]})"
            }
