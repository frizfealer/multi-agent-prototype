from typing import Optional

from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.auth import get_db_session, get_current_session
from src.core.session_manager import SessionManager
from src.db.models import Session


router = APIRouter(prefix="/session", tags=["session"])


class CreateSessionRequest(BaseModel):
    user_metadata: Optional[dict] = Field(None, description="Optional user metadata to store with session")


class CreateSessionResponse(BaseModel):
    session_token: str
    session_id: str
    expires_at: str


class SessionInfoResponse(BaseModel):
    session_id: str
    created_at: str
    last_accessed: str
    expires_at: str
    is_active: bool
    user_metadata: dict
    conversation_count: int
    conversations: list


@router.post("/create", response_model=CreateSessionResponse)
async def create_session(
    request: Request,
    body: CreateSessionRequest,
    db_session: AsyncSession = Depends(get_db_session)
):
    """Create a new session with 30-minute expiration."""
    session_manager = SessionManager(db_session)
    
    # Get client info
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent")
    
    # Create session
    session = await session_manager.create_session(
        ip_address=ip_address,
        user_agent=user_agent,
        user_metadata=body.user_metadata
    )
    
    return CreateSessionResponse(
        session_token=session.session_token,
        session_id=str(session.session_id),
        expires_at=session.expires_at.isoformat()
    )


@router.get("/info", response_model=SessionInfoResponse)
async def get_session_info(
    current_session: Session = Depends(get_current_session),
    db_session: AsyncSession = Depends(get_db_session)
):
    """Get information about the current session."""
    session_manager = SessionManager(db_session)
    session_info = await session_manager.get_session_info(current_session.session_id)
    
    if not session_info:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return SessionInfoResponse(**session_info)


@router.post("/logout")
async def logout(
    current_session: Session = Depends(get_current_session),
    db_session: AsyncSession = Depends(get_db_session)
):
    """Expire the current session."""
    session_manager = SessionManager(db_session)
    await session_manager.expire_session(current_session.session_id)
    
    return {"message": "Session expired successfully"}