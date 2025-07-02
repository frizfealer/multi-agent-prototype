from typing import Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.session_manager import SessionManager
from src.core.config import settings
from src.db.models import Session


security = HTTPBearer()


async def get_db_session() -> AsyncSession:
    from main import db_manager
    async for session in db_manager.get_session():
        yield session


async def get_current_session(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db_session: AsyncSession = Depends(get_db_session)
) -> Session:
    """Validate session token and return current session."""
    token = credentials.credentials
    session_manager = SessionManager(db_session)
    
    session = await session_manager.get_session_by_token(token)
    if not session:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired session",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return session


async def get_optional_session(
    request: Request,
    db_session: AsyncSession = Depends(get_db_session)
) -> Optional[Session]:
    """Get session if authorization header is present, otherwise return None."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None
    
    token = auth_header.split(" ")[1]
    session_manager = SessionManager(db_session)
    return await session_manager.get_session_by_token(token)