import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.session_manager import SessionManager
from src.db.models import Session, Conversation


@pytest.mark.asyncio
async def test_create_session(async_session: AsyncSession):
    """Should create a new session with proper expiration."""
    session_manager = SessionManager(async_session)
    
    session = await session_manager.create_session(
        ip_address="127.0.0.1",
        user_agent="Test Browser",
        user_metadata={"user_id": "test123"}
    )
    
    assert session is not None
    assert session.session_token is not None
    assert len(session.session_token) > 20  # Secure token
    assert session.ip_address == "127.0.0.1"
    assert session.user_agent == "Test Browser"
    assert session.user_metadata == {"user_id": "test123"}
    assert session.is_active is True
    assert session.expires_at > datetime.utcnow()


@pytest.mark.asyncio
async def test_get_session_by_token(async_session: AsyncSession):
    """Should retrieve session by token and update last_accessed."""
    session_manager = SessionManager(async_session)
    
    # Create session
    session = await session_manager.create_session()
    original_last_accessed = session.last_accessed
    original_expires_at = session.expires_at
    
    # Wait a moment
    await asyncio.sleep(0.1)
    
    # Retrieve session
    retrieved = await session_manager.get_session_by_token(session.session_token)
    
    assert retrieved is not None
    assert retrieved.session_id == session.session_id
    assert retrieved.last_accessed > original_last_accessed
    assert retrieved.expires_at > original_expires_at


@pytest.mark.asyncio
async def test_expired_session_not_retrieved(async_session: AsyncSession):
    """Should not retrieve expired sessions."""
    session_manager = SessionManager(async_session)
    
    # Create session with past expiration
    session = await session_manager.create_session()
    session.expires_at = datetime.utcnow() - timedelta(minutes=1)
    await async_session.commit()
    
    # Try to retrieve
    retrieved = await session_manager.get_session_by_token(session.session_token)
    
    assert retrieved is None


@pytest.mark.asyncio
async def test_validate_session(async_session: AsyncSession):
    """Should validate active sessions correctly."""
    session_manager = SessionManager(async_session)
    
    # Create session
    session = await session_manager.create_session()
    
    # Validate existing session
    is_valid = await session_manager.validate_session(session.session_token)
    assert is_valid is True
    
    # Validate non-existing session
    is_valid = await session_manager.validate_session("fake-token")
    assert is_valid is False


@pytest.mark.asyncio
async def test_expire_session(async_session: AsyncSession):
    """Should manually expire a session."""
    session_manager = SessionManager(async_session)
    
    # Create session
    session = await session_manager.create_session()
    
    # Expire it
    success = await session_manager.expire_session(session.session_id)
    assert success is True
    
    # Verify it's expired
    retrieved = await session_manager.get_session_by_token(session.session_token)
    assert retrieved is None


@pytest.mark.asyncio
async def test_link_conversation_to_session(
    async_session: AsyncSession,
    sample_conversation: Conversation
):
    """Should link conversations to sessions."""
    session_manager = SessionManager(async_session)
    
    # Create session
    session = await session_manager.create_session()
    
    # Link conversation
    link = await session_manager.link_conversation_to_session(
        session.session_id,
        sample_conversation.conversation_id
    )
    
    assert link is not None
    assert link.session_id == session.session_id
    assert link.conversation_id == sample_conversation.conversation_id


@pytest.mark.asyncio
async def test_get_session_conversations(
    async_session: AsyncSession,
    sample_conversation: Conversation
):
    """Should retrieve all conversations for a session."""
    session_manager = SessionManager(async_session)
    
    # Create session and link conversation
    session = await session_manager.create_session()
    await session_manager.link_conversation_to_session(
        session.session_id,
        sample_conversation.conversation_id
    )
    
    # Get conversations
    conversations = await session_manager.get_session_conversations(session.session_id)
    
    assert len(conversations) == 1
    assert conversations[0].conversation_id == sample_conversation.conversation_id


@pytest.mark.asyncio
async def test_cleanup_expired_sessions(async_session: AsyncSession):
    """Should clean up expired sessions."""
    session_manager = SessionManager(async_session)
    
    # Create active session
    active_session = await session_manager.create_session()
    
    # Create expired sessions
    for _ in range(3):
        expired = await session_manager.create_session()
        expired.expires_at = datetime.utcnow() - timedelta(minutes=1)
        await async_session.commit()
    
    # Clean up
    count = await session_manager.cleanup_expired_sessions()
    
    assert count == 3
    
    # Verify active session still exists
    retrieved = await session_manager.get_session_by_token(active_session.session_token)
    assert retrieved is not None


@pytest.mark.asyncio
async def test_session_info(
    async_session: AsyncSession,
    sample_conversation: Conversation
):
    """Should return detailed session information."""
    session_manager = SessionManager(async_session)
    
    # Create session with metadata
    session = await session_manager.create_session(
        user_metadata={"preferences": {"theme": "dark"}}
    )
    
    # Link conversation
    await session_manager.link_conversation_to_session(
        session.session_id,
        sample_conversation.conversation_id
    )
    
    # Get info
    info = await session_manager.get_session_info(session.session_id)
    
    assert info is not None
    assert info["session_id"] == str(session.session_id)
    assert info["is_active"] is True
    assert info["user_metadata"] == {"preferences": {"theme": "dark"}}
    assert info["conversation_count"] == 1
    assert len(info["conversations"]) == 1
    assert info["conversations"][0]["conversation_id"] == str(sample_conversation.conversation_id)


# Add missing import
import asyncio