"""
FastAPI router for AI Agent endpoints.
Defines the /agent/chat endpoint which connects directly to the ReceptionistAgent (Clara).
"""

import logging
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, HTTPException, status, Depends, BackgroundTasks
from pydantic import BaseModel, Field, ConfigDict

# Project imports
from ai.agents.receptionist_agent import ReceptionistAgent
from api.deps import get_current_user


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])

# Maximum wall-clock time allotted to a single agent run before the request
# is aborted and a timeout response is returned to the client.
AGENT_TIMEOUT_SECONDS = 90.0

# Thread-safe global singleton for the Orchestrator/Agent to optimize load times
_agent_orchestrator: Any = None
_receptionist_agent: Any = None


def get_receptionist_agent() -> Any:
    """Helper to lazily load and cache the OrchestratorV3 singleton."""
    global _agent_orchestrator, _receptionist_agent
    if _agent_orchestrator is None:
        logger.info("Initializing lazy OrchestratorV3 singleton...")
        from ai.orchestrator import get_phase2_orchestrator
        _agent_orchestrator = get_phase2_orchestrator(tenant_id="default")
        _receptionist_agent = _agent_orchestrator
    return _agent_orchestrator


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
    response_type: str = Field(default="general_chat", description="Classification of the response payload")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Optional structured data accompanying the response")


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
    
    from datetime import datetime, timezone
    import asyncio

    # Enforce Customer Role profile requirement
    if current_user.role.value == "CUSTOMER" and not current_user.customer_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customer users must have an associated customer profile"
        )

    context_prefix = ""
    # Inject current date and time context.
    # NOTE: Must be UTC — the orchestrator's own enriched-query builder also injects
    # a "[SYSTEM TIME CONTEXT: ... (UTC)]" block using UTC, and all backend datetime
    # validation (past-date/past-time rejection, business hours) is UTC-based. Using
    # naive local server time here previously created a second, conflicting "current
    # time" inside the same prompt and could mislead the LLM's relative-date reasoning.
    now_dt = datetime.now(timezone.utc)
    context_prefix += f"[SYSTEM TIME CONTEXT: Current system time is {now_dt.strftime('%Y-%m-%d %H:%M:%S')} (UTC) (Today is {now_dt.strftime('%A, %B %d, %Y')}). Use this to calculate exact dates like 'tomorrow', 'next Tuesday', etc.]\n"
    
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

    # Populate conversation state service history from payload.chat_history when it is a new/empty session
    try:
        from application.services.conversation_state_service import get_state_service
        state_svc = get_state_service()
        session = state_svc.get_session(payload.session_id)
        if not session or not session.history:
            session = state_svc.get_or_create(
                session_id=payload.session_id,
                user_id=current_user.id,
                user_role=current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role)
            )
            if payload.chat_history:
                logger.info(f"Populating session {payload.session_id} history from payload chat_history ({len(payload.chat_history)} turns)")
                for msg in payload.chat_history:
                    role = msg.get("role", "user").lower()
                    content = msg.get("content", "")
                    # Don't add if empty
                    if content.strip():
                        # AutoGen format has sender/source, map to user or assistant
                        role_clean = "assistant" if role in ("assistant", "agent", "clara") else "user"
                        session.add_turn(role_clean, content)
    except Exception as e:
        logger.warning(f"Failed to populate conversation state from payload: {e}")

    # Remove repeated history context from the queries, since the orchestrator already manages the session history in state_service
    full_query = context_prefix + f"\nLatest User Message: {payload.message}"
    
    # 2. Lazy load the agent (returns the Multi-Agent Orchestrator in production)
    try:
        agent = get_receptionist_agent()
    except Exception as e:
        logger.error(f"Failed to load agent: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Agent service is currently initializing or unavailable: {str(e)}"
        )

    # 3. Store chat log with customer isolation
    from infrastructure.db import get_db, ChatLog, SessionLocal
    
    # Store user message first
    db_sess = SessionLocal()
    try:
        chat_log = ChatLog(
            session_id=payload.session_id,
            user_id=current_user.id,
            customer_id=current_user.customer_id if current_user.customer_id else None,
            staff_id=current_user.staff_id if current_user.staff_id else None,
            agent_type="RECEPTIONIST",
            sender="user",
            message=payload.message
        )
        db_sess.add(chat_log)
        
        # Reset existing lead to NEW because they are active in the chat again!
        from infrastructure.db import Lead, LeadStatus
        from datetime import datetime
        existing_lead = db_sess.query(Lead).filter(
            (Lead.notes.like(f"%Session ID: {payload.session_id}%")) |
            (Lead.customer_id == current_user.customer_id if current_user.customer_id else False)
        ).filter(Lead.status != LeadStatus.CONVERTED).first()
        
        if existing_lead:
            existing_lead.status = LeadStatus.NEW
            existing_lead.notes = (existing_lead.notes or "") + f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Customer resumed chat session."
            logger.info(f"Reset existing lead status to NEW for session {payload.session_id}")
            
        db_sess.commit()
        logger.info(f"Stored user chat log for user {current_user.id}, customer_id: {current_user.customer_id}")
    except Exception as e:
        logger.error(f"Failed to store user chat log: {e}")
        db_sess.rollback()
    finally:
        db_sess.close()

    # 4. Process query through AutoGen asynchronously
    try:
        logger.debug(f"Sending query to agent: {full_query[:100]}...")
        
        # Try to wait for the agent response for a maximum of AGENT_TIMEOUT_SECONDS
        agent_response = await asyncio.wait_for(
            agent.process({
                "query": payload.message,
                "full_query": full_query,
                "intent_override": payload.intent_override,
                "user_role": current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role),
                "session_id": payload.session_id,
                "customer_id": current_user.customer_id,
                "staff_id": getattr(current_user, "staff_id", None),
                "user_id": current_user.id,
            }),
            timeout=AGENT_TIMEOUT_SECONDS
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

        # Store agent response
        db_sess_sync = SessionLocal()
        try:
            chat_log = ChatLog(
                session_id=payload.session_id,
                user_id=current_user.id,
                customer_id=current_user.customer_id if current_user.customer_id else None,
                staff_id=current_user.staff_id if current_user.staff_id else None,
                agent_type="RECEPTIONIST",
                sender="assistant",
                message=agent_response.get("response", "").strip()
            )
            db_sess_sync.add(chat_log)
            db_sess_sync.commit()
            logger.info(f"Stored sync agent chat log for user {current_user.id}")
        except Exception as e:
            logger.error(f"Failed to store sync agent chat log: {e}")
            db_sess_sync.rollback()
        finally:
            db_sess_sync.close()

        logger.info(f"Agent successfully processed query within {AGENT_TIMEOUT_SECONDS:.0f}s for session {payload.session_id}")
        return ChatResponse(
            success=True,
            session_id=payload.session_id,
            response=agent_response.get("response", "").strip(),
            agent_name=agent_response.get("agent_name", "Clara"),
            response_type=agent_response.get("response_type", "general_chat"),
            data=agent_response.get("data")
        )

    except asyncio.TimeoutError:
        logger.warning(f"⏰ Agent execution exceeded {AGENT_TIMEOUT_SECONDS:.0f}s. Returning timeout error.")
        return ChatResponse(
            success=False,
            session_id=payload.session_id,
            response="I apologize, but processing your request timed out. Please try again.",
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

