import asyncio
import uuid
from typing import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.db.base import Base
from src.db.models import Conversation, Message


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def async_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    # Use SQLite for testing
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session_maker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session_maker() as session:
        yield session
    
    await engine.dispose()


@pytest.fixture
async def sample_conversation(async_session: AsyncSession) -> Conversation:
    """Create a sample conversation for testing."""
    conversation = Conversation(
        conversation_id=uuid.uuid4(),
        current_agent="triage",
        context_data={"intent": "unknown"}
    )
    async_session.add(conversation)
    await async_session.commit()
    await async_session.refresh(conversation)
    return conversation


@pytest.fixture
async def conversation_with_messages(
    async_session: AsyncSession, sample_conversation: Conversation
) -> Conversation:
    """Create a conversation with message history."""
    messages = [
        Message(
            conversation_id=sample_conversation.conversation_id,
            role="user",
            content="I need help with my fitness routine"
        ),
        Message(
            conversation_id=sample_conversation.conversation_id,
            role="assistant",
            content="I'd be happy to help with your fitness routine. What specific aspect would you like to focus on?"
        )
    ]
    
    for msg in messages:
        async_session.add(msg)
    
    await async_session.commit()
    await async_session.refresh(sample_conversation)
    return sample_conversation