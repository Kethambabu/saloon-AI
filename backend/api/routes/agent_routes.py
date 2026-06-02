"""
FastAPI router for AI Agent endpoints.
Defines the /agent/chat endpoint which connects directly to the ReceptionistAgent (Clara).
"""

import logging
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, HTTPException, status, Depends, BackgroundTasks
from pydantic import BaseModel, Field, ConfigDict

# Project imports
from agents.receptionist_agent import ReceptionistAgent
from api.deps import get_current_user


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])

# Thread-safe global singleton for ReceptionistAgent to optimize load times
_receptionist_agent: Optional[ReceptionistAgent] = None


def get_receptionist_agent() -> ReceptionistAgent:
    """Helper to lazily load and cache the ReceptionistAgent singleton."""
    global _receptionist_agent
    if _receptionist_agent is None:
        logger.info("Initializing lazy ReceptionistAgent singleton...")
        _receptionist_agent = ReceptionistAgent()
    return _receptionist_agent


# Pydantic models for structured requests & responses
class ChatRequest(BaseModel):
    """Structured Chat Request model supporting both space-based aliases and standard snake_case keys."""
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "message": "I want to check availability for tomorrow.",
                "session id": "session-12345",
                "chat history": []
            }
        }
    )

    message: str = Field(..., description="The conversational message or query from the user")
    session_id: str = Field(
        ...,
        validation_alias="session id",
        serialization_alias="session id",
        description="Dynamic session or conversation identifier"
    )
    chat_history: Optional[List[Dict[str, Any]]] = Field(
        default=[],
        validation_alias="chat history",
        serialization_alias="chat history",
        description="Historical messages context: [{'role': 'user', 'content': '...'}, {'role': 'assistant', 'content': '...'}]"
    )
    intent_override: Optional[str] = Field(
        default=None,
        validation_alias="intent override",
        serialization_alias="intent override",
        description="Optional intent override (e.g. 'business_intelligence')"
    )


class ChatResponse(BaseModel):
    """Structured Standard JSON response from Clara the AI Receptionist."""
    model_config = ConfigDict(populate_by_name=True)

    success: bool = Field(..., description="Indicates if the query was processed successfully")
    session_id: str = Field(
        ...,
        alias="session id",
        validation_alias="session id",
        serialization_alias="session id",
        description="The ongoing session identifier"
    )
    response: str = Field(..., description="Conversational reply text from the AI Agent")
    agent_name: str = Field(..., description="Name of the agent replying")


@router.post(
    "/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Chat with Clara the AI Receptionist Agent"
)
async def chat_with_agent(
    payload: ChatRequest,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user)
):
    """
    Endpoint to send queries to Clara, the AI Salon Receptionist.
    Maintains context through history prepending and executes booking operations on the database automatically.
    Role-based: Customers use customer-specific agent, Staff use staff agent.
    """
    logger.info(f"POST /api/agent/chat received (Session ID: {payload.session_id}, User Role: {current_user.role})")
    
    from datetime import datetime
    import asyncio

    # Route to Orchestrator if intent_override is specified
    if payload.intent_override:
        logger.info(f"Routing to Multi-Agent Orchestrator with intent override: {payload.intent_override}")
        try:
            from agents.orchestrator import MultiAgentOrchestrator
            global _orchestrator
            if "_orchestrator" not in globals() or globals()["_orchestrator"] is None:
                globals()["_orchestrator"] = MultiAgentOrchestrator()
            
            orch = globals()["_orchestrator"]
            agent_response = await orch.process({
                "query": payload.message,
                "intent_override": payload.intent_override,
                "session_id": payload.session_id,
                "chat_history": payload.chat_history
            })
            
            if not agent_response.get("success"):
                logger.error(f"Orchestration failed: {agent_response.get('error')}")
                return ChatResponse(
                    success=False,
                    session_id=payload.session_id,
                    response="I encountered an issue processing your request through the analytics supervisor.",
                    agent_name="Atlas_BI"
                )
                
            return ChatResponse(
                success=True,
                session_id=payload.session_id,
                response=agent_response.get("response", ""),
                agent_name=agent_response.get("agent_name", "Atlas_BI")
            )
        except Exception as ex:
            logger.error(f"Orchestrator processing crashed: {ex}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Orchestrator processing failed: {str(ex)}"
            )
    
    # Role-based agent enforcement
    if current_user.role.value == "CUSTOMER" and not current_user.customer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customer users must have an associated customer profile"
        )
    
    context_prefix = ""
    # Inject current date and time context
    now_dt = datetime.now()
    context_prefix += f"[SYSTEM TIME CONTEXT: Current system time is {now_dt.strftime('%Y-%m-%d %H:%M:%S')} (Today is {now_dt.strftime('%A, %B %d, %Y')}). Use this to calculate exact dates like 'tomorrow', 'next Tuesday', etc.]\n"
    
    # Inject logged-in user context WITH ROLE ISOLATION
    if current_user:
        if current_user.customer:
            cust = current_user.customer
            context_prefix += f"[SYSTEM CUSTOMER CONTEXT: The user chatting with you is logged in as Customer '{cust.full_name}' (ID: {cust.id}, Email: {cust.email}, Phone: {cust.phone or 'N/A'}, Loyalty Points: {cust.loyalty_points}). Always use this Customer ID directly for bookings and customer history lookups. Do NOT ask them to search or provide their details.]\n"
        elif current_user.staff:
            stf = current_user.staff
            context_prefix += f"[SYSTEM STAFF CONTEXT: The user chatting with you is logged in as Staff '{stf.full_name}' (ID: {stf.id}, Role: {stf.role}, Branch ID: {stf.branch_id}). You have access to internal staff tools and analytics.]\n"
        else:
            context_prefix += f"[SYSTEM USER CONTEXT: The user chatting with you is logged in with email: '{current_user.email}' (Role: {current_user.role.value if hasattr(current_user.role, 'value') else current_user.role}).]\n"
            
    full_query = context_prefix + "\n"
    if payload.chat_history:
        full_query += "Here is the conversation history so far for context:\n"
        for idx, msg in enumerate(payload.chat_history[-5:]):
            role = msg.get("role", "user").capitalize()
            content = msg.get("content", "")
            full_query += f"- {role}: {content}\n"
        full_query += "\n"
        
    full_query += f"Latest User Message: {payload.message}"
    
    # 2. Lazy load the agent
    try:
        agent = get_receptionist_agent()
    except Exception as e:
        logger.error(f"Failed to load ReceptionistAgent: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Agent service is currently initializing or unavailable: {str(e)}"
        )

    # 3. Store chat log with customer isolation
    from db import get_db, ChatLog
    from sqlalchemy.orm import Session as SQLAlchemySession
    
    async def store_chat_log(db_session: SQLAlchemySession, sender: str, message: str):
        """Store chat interaction with proper customer isolation."""
        try:
            chat_log = ChatLog(
                session_id=payload.session_id,
                user_id=current_user.id,
                customer_id=current_user.customer_id if current_user.customer_id else None,
                staff_id=current_user.staff_id if current_user.staff_id else None,
                agent_type="RECEPTIONIST",
                sender=sender,
                message=message
            )
            db_session.add(chat_log)
            db_session.commit()
            logger.info(f"Stored chat log for user {current_user.id}, customer_id: {current_user.customer_id}")
        except Exception as e:
            logger.error(f"Failed to store chat log: {e}")
            db_session.rollback()

    # Helper function to run agent processing in a background task
    async def run_agent_in_background(query_data: Dict[str, Any]):
        try:
            logger.info("Executing agent process in background task...")
            await agent.process(query_data)
            logger.info("Agent process completed in background task successfully.")
        except Exception as bg_ex:
            logger.error(f"Error in background agent process execution: {bg_ex}")

    # 4. Process query through AutoGen asynchronously with hybrid background forking
    try:
        logger.debug(f"Sending query to agent: {full_query[:100]}...")
        
        # Try to wait for the agent response for a maximum of 3.0 seconds
        agent_response = await asyncio.wait_for(
            agent.process({"query": full_query}),
            timeout=3.0
        )
        
        if not agent_response.get("success"):
            error_msg = agent_response.get("error", "Unknown agent processing error.")
            logger.error(f"Agent returned failure response: {error_msg}")
            
            return ChatResponse(
                success=False,
                session_id=payload.session_id,
                response=f"I encountered an issue processing your request: {error_msg}. Please try again.",
                agent_name=agent_response.get("agent_name", "Clara")
            )

        logger.info(f"Agent successfully processed query within 3 seconds for session {payload.session_id}")
        return ChatResponse(
            success=True,
            session_id=payload.session_id,
            response=agent_response.get("response", ""),
            agent_name=agent_response.get("agent_name", "Clara")
        )

    except asyncio.TimeoutError:
        logger.warning(f"⏰ Agent execution exceeded 3.0 seconds. Forking task to FastAPI background worker.")
        background_tasks.add_task(run_agent_in_background, {"query": full_query})
        
        return ChatResponse(
            success=True,
            session_id=payload.session_id,
            response="Processing your request...",
            agent_name="Clara"
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(
            f"Unexpected error in /chat endpoint: {str(e)}",
            exc_info=True,
            extra={
                "session_id": payload.session_id,
                "message_preview": payload.message[:50],
                "error_type": type(e).__name__,
            }
        )
        
        return ChatResponse(
            success=False,
            session_id=payload.session_id,
            response="An unexpected error occurred. Our team has been notified. Please try again later.",
            agent_name="Clara"
        )
