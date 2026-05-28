"""
AI Receptionist Agent for SalonAI Workforce Platform.
Built using Microsoft AutoGen (agentchat v0.4+ / v0.10+).
Wraps the booking business tools and exposes an AssistantAgent driven by settings configuration.
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

logger = logging.getLogger(__name__)
settings = get_settings()


# Define clean wrapper tools to decouple DB session handling from LLM function schemas
def check_stylist_availability(
    branch_id: str,
    date: str,
    staff_id: Optional[str] = None,
    service_id: Optional[str] = None
) -> str:
    """
    Checks and suggests available salon time slots for a branch location on a given date.
    
    Args:
        branch_id: The UUID string of the physical branch location.
        date: The target date in ISO format YYYY-MM-DD (e.g., '2026-05-28').
        staff_id: Optional UUID string of a specific stylist to filter availability.
        service_id: Optional UUID string of a service to check slot duration fit.
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
    Creates, validates, and confirms a new salon booking appointment.
    
    Args:
        customer_id: The UUID string of the customer booking the appointment.
        branch_id: The UUID string of the physical salon branch.
        service_id: The UUID string of the service catalog item.
        start_time: The ISO format start date-time (e.g., '2026-05-28T14:30:00Z').
        staff_id: Optional UUID string of the preferred stylist. If omitted, a free stylist will be auto-assigned.
        notes: Optional customer requests or stylist comments.
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
    Cancels an existing salon booking.
    
    Args:
        appointment_id: The UUID string of the appointment to cancel.
    """
    result = cancel_appointment(appointment_id=appointment_id)
    return str(result)


def reschedule_existing_appointment(appointment_id: str, new_start_time: str) -> str:
    """
    Moves an existing booking slot to a new start date-time.
    
    Args:
        appointment_id: The UUID string of the appointment to reschedule.
        new_start_time: The new ISO format start date-time (e.g., '2026-05-28T16:00:00Z').
    """
    result = reschedule_appointment(appointment_id=appointment_id, new_start_time=new_start_time)
    return str(result)


def check_customer_booking_history(customer_id: str) -> str:
    """
    Gets full booking history for a specific customer, including past appointments, branches, and ratings.
    
    Args:
        customer_id: The UUID string of the customer.
    """
    result = get_customer_history(customer_id=customer_id)
    return str(result)


# Elegant and conversational salon receptionist system prompt
RECEPTIONIST_SYSTEM_PROMPT = """
You are Clara, the elegant, professional, and warm AI Receptionist at SalonAI Workforce Platform.
Your goal is to assist clients with their booking and schedule management requests smoothly, including:
1. Booking new appointments
2. Rescheduling existing appointments
3. Canceling appointments
4. Checking stylists' availability or suggesting free slots
5. Reviewing customer history

Business Rules & Standards:
1. Salon business hours are from 9:00 AM to 8:00 PM UTC daily.
2. We offer 4 signature high-value services:
   - Signature Precision Haircut ($85.00, 60 mins)
   - Balayage & Creative Color ($220.00, 150 mins)
   - Hydrating Deep-Cleansing Facial ($120.00, 75 mins)
   - Himalayan Hot Stone Massage ($150.00, 90 mins)
3. You MUST use the provided booking tools whenever a user requests an operation (availability check, booking, cancellation, rescheduling, history lookup). Do not make up confirmations, slot listings, or history entries.
4. When suggesting available slots, present them clearly, grouped logically.
5. If a booking tool returns a validation or conflict error (e.g., overlap conflicts, out of business hours), explain the reason politely and offer appropriate alternatives.
6. Keep your responses concise, warm, helpful, and highly professional. Avoid unnecessarily long preambles.
"""


class ReceptionistAgent(Agent):
    """
    Salon Receptionist Agent powered by Microsoft AutoGen v0.4+ and Groq LLM.
    Provides complete booking business automation.
    """

    def __init__(self, name: str = "Clara", role: str = "AI Salon Receptionist"):
        super().__init__(name=name, role=role)
        logger.info(f"Initializing AI Receptionist Agent '{name}'...")

        # 1. Get centralized LLM configuration
        llm_config = get_llm_config()
        config = llm_config.get_config()
        
        logger.info(f"Using model: {config['model']}")

        # 2. Instantiate AutoGen AssistantAgent with system prompt and tools
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
                check_stylist_availability,
                book_new_appointment,
                cancel_existing_appointment,
                reschedule_existing_appointment,
                check_customer_booking_history
            ]
        )
        logger.info("AI Receptionist Agent initialized successfully.")

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Standardized entrypoint to process booking queries.
        
        Args:
            input_data: Dictionary containing:
                - "query": The user conversational message (e.g. "I want to book a haircut tomorrow at 10 AM")
                
        Returns:
            Dictionary containing:
                - "success": True/False
                - "response": Conversational response text from the agent
        """
        query = input_data.get("query")
        if not query:
            return {"success": False, "error": "Input data must contain a 'query' key."}

        logger.info(f"Receptionist agent processing query: '{query}'")
        try:
            # Execute agent run task asynchronously
            result = await self.assistant.run(task=query)
            
            # Extract final message from assistant
            response_text = result.messages[-1].content
            
            return {
                "success": True,
                "agent_name": self.name,
                "response": response_text
            }
        except Exception as e:
            logger.error(f"Error executing ReceptionistAgent task: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": f"Agent processing failed: {str(e)}"
            }
