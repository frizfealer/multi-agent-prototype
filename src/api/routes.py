import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import get_current_session, get_db_session
from src.core.orchestrator import Orchestrator
from src.core.session_manager import SessionManager
from src.db.models import Session


router = APIRouter()


class ChatMessage(BaseModel):
    message: str
    conversation_id: Optional[str] = Field(None, description="UUID of existing conversation")


class ChatResponse(BaseModel):
    conversation_id: str
    agent: str
    text: Optional[str]
    action: Optional[dict]
    session_id: str


async def get_orchestrator() -> Orchestrator:
    # In production, this would come from config
    import os
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        raise HTTPException(status_code=500, detail="Google API key not configured")
    return Orchestrator(google_api_key)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatMessage,
    current_session: Session = Depends(get_current_session),
    db_session: AsyncSession = Depends(get_db_session),
    orchestrator: Orchestrator = Depends(get_orchestrator)
):
    """Process a chat message through the triage agent system."""
    conversation_id = None
    if request.conversation_id:
        try:
            conversation_id = uuid.UUID(request.conversation_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid conversation ID format")
    
    result = await orchestrator.process_user_message(
        db_session, conversation_id, request.message
    )
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    # Link conversation to session
    if result.get("conversation_id"):
        session_manager = SessionManager(db_session)
        await session_manager.link_conversation_to_session(
            current_session.session_id,
            uuid.UUID(result["conversation_id"])
        )
    
    # Add session_id to response
    result["session_id"] = str(current_session.session_id)
    
    return ChatResponse(**result)