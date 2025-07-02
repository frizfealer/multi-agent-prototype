import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import Conversation, Session, SessionConversation


class SessionManager:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.session_duration = timedelta(minutes=30)

    async def create_session(
        self, ip_address: Optional[str] = None, user_agent: Optional[str] = None, user_metadata: Optional[Dict] = None
    ) -> Session:
        """Create a new session with expiration."""
        session_token = self._generate_session_token()
        expires_at = datetime.now(timezone.utc) + self.session_duration

        db_session = Session(
            session_token=session_token,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
            user_metadata=user_metadata or {},
        )

        self.session.add(db_session)
        await self.session.commit()
        await self.session.refresh(db_session)
        return db_session

    async def get_session_by_token(self, token: str) -> Optional[Session]:
        """Get active session by token and update last_accessed."""
        stmt = (
            select(Session)
            .where(
                and_(
                    Session.session_token == token,
                    Session.is_active == True,
                    Session.expires_at > datetime.now(timezone.utc),
                )
            )
            .options(selectinload(Session.conversations))
        )

        result = await self.session.execute(stmt)
        session = result.scalar_one_or_none()

        if session:
            # Update last_accessed and extend expiration
            session.last_accessed = datetime.now(timezone.utc)
            session.expires_at = datetime.now(timezone.utc) + self.session_duration
            await self.session.commit()
            await self.session.refresh(session)

        return session

    async def validate_session(self, token: str) -> bool:
        """Check if session is valid and active."""
        session = await self.get_session_by_token(token)
        return session is not None

    async def expire_session(self, session_id: uuid.UUID) -> bool:
        """Manually expire a session."""
        stmt = select(Session).where(Session.session_id == session_id)
        result = await self.session.execute(stmt)
        session = result.scalar_one_or_none()

        if session:
            session.is_active = False
            session.expires_at = datetime.now(timezone.utc)
            await self.session.commit()
            return True
        return False

    async def link_conversation_to_session(
        self, session_id: uuid.UUID, conversation_id: uuid.UUID
    ) -> SessionConversation:
        """Link a conversation to a session."""
        link = SessionConversation(session_id=session_id, conversation_id=conversation_id)
        self.session.add(link)
        await self.session.commit()
        await self.session.refresh(link)
        return link

    async def get_session_conversations(self, session_id: uuid.UUID) -> List[Conversation]:
        """Get all conversations for a session."""
        stmt = (
            select(Conversation)
            .join(SessionConversation)
            .where(SessionConversation.session_id == session_id)
            .order_by(SessionConversation.created_at.desc())
        )

        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def cleanup_expired_sessions(self) -> int:
        """Remove expired sessions. Returns count of deleted sessions."""
        stmt = delete(Session).where(and_(Session.expires_at < datetime.now(timezone.utc), Session.is_active == True))
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount

    async def get_session_info(self, session_id: uuid.UUID) -> Optional[Dict]:
        """Get detailed session information."""
        stmt = select(Session).where(Session.session_id == session_id)
        result = await self.session.execute(stmt)
        session = result.scalar_one_or_none()

        if not session:
            return None

        conversations = await self.get_session_conversations(session_id)

        return {
            "session_id": str(session.session_id),
            "created_at": session.created_at.isoformat(),
            "last_accessed": session.last_accessed.isoformat(),
            "expires_at": session.expires_at.isoformat(),
            "is_active": session.is_active,
            "user_metadata": session.user_metadata,
            "conversation_count": len(conversations),
            "conversations": [
                {
                    "conversation_id": str(conv.conversation_id),
                    "created_at": conv.created_at.isoformat(),
                    "current_agent": conv.current_agent,
                }
                for conv in conversations
            ],
        }

    def _generate_session_token(self) -> str:
        """Generate a secure session token."""
        return secrets.token_urlsafe(32)
