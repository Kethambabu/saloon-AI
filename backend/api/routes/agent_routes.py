"""
FastAPI router for AI Agent endpoints.
Defines the /agent/chat endpoint which connects directly to the ReceptionistAgent (Clara).
"""

import logging
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, ConfigDict

# Project imports
from agents.receptionist_agent import ReceptionistAgent

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
async def chat_with_agent(payload: ChatRequest):
    """
    Endpoint to send queries to Clara, the AI Salon Receptionist.
    Maintains context through history prepending and executes booking operations on the database automatically.
    """
    logger.info(f"POST /api/agent/chat received (Session ID: {payload.session_id})")
    
    # 1. Format conversational history as LLM context prepended to the query
    full_query = ""
    if payload.chat_history:
        full_query += "Here is the conversation history so far for context:\n"
        for idx, msg in enumerate(payload.chat_history):
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

    # 3. Process query through AutoGen asynchronously
    try:
        agent_response = await agent.process({"query": full_query})
        
        if not agent_response.get("success"):
            error_msg = agent_response.get("error", "Unknown agent processing error.")
            logger.error(f"Agent failed to process query: {error_msg}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Agent failed to process query: {error_msg}"
            )

        # 4. Construct structured response mapping back aliases
        return ChatResponse(
            success=True,
            session_id=payload.session_id,
            response=agent_response.get("response", ""),
            agent_name=agent_response.get("agent_name", "Clara")
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Unexpected error in /chat endpoint: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during agent execution: {str(e)}"
        )
