import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.state_manager import StateManager
from src.db.models import Conversation


@pytest.mark.asyncio
async def test_create_conversation(async_session: AsyncSession):
    """Should create a new conversation with default values."""
    state_manager = StateManager(async_session)
    
    conversation = await state_manager.create_conversation()
    
    assert conversation is not None
    assert isinstance(conversation.conversation_id, uuid.UUID)
    assert conversation.current_agent == "triage"
    assert conversation.context_data == {}


@pytest.mark.asyncio
async def test_get_conversation(async_session: AsyncSession, sample_conversation: Conversation):
    """Should retrieve an existing conversation by ID."""
    state_manager = StateManager(async_session)
    
    retrieved = await state_manager.get_conversation(sample_conversation.conversation_id)
    
    assert retrieved is not None
    assert retrieved.conversation_id == sample_conversation.conversation_id
    assert retrieved.current_agent == sample_conversation.current_agent


@pytest.mark.asyncio
async def test_get_nonexistent_conversation(async_session: AsyncSession):
    """Should return None for non-existent conversation ID."""
    state_manager = StateManager(async_session)
    fake_id = uuid.uuid4()
    
    result = await state_manager.get_conversation(fake_id)
    
    assert result is None


@pytest.mark.asyncio
async def test_update_conversation_context(async_session: AsyncSession, sample_conversation: Conversation):
    """Should update conversation context data."""
    state_manager = StateManager(async_session)
    new_context = {"intent": "fitness", "category": "exercise"}
    
    updated = await state_manager.update_conversation_context(
        sample_conversation.conversation_id, new_context
    )
    
    assert updated is not None
    assert updated.context_data == new_context


@pytest.mark.asyncio
async def test_update_current_agent(async_session: AsyncSession, sample_conversation: Conversation):
    """Should update the current agent handling the conversation."""
    state_manager = StateManager(async_session)
    
    updated = await state_manager.update_current_agent(
        sample_conversation.conversation_id, "exercise_coach"
    )
    
    assert updated is not None
    assert updated.current_agent == "exercise_coach"


@pytest.mark.asyncio
async def test_add_message(async_session: AsyncSession, sample_conversation: Conversation):
    """Should add a new message to the conversation."""
    state_manager = StateManager(async_session)
    
    message = await state_manager.add_message(
        sample_conversation.conversation_id,
        "user",
        "I want to build muscle"
    )
    
    assert message is not None
    assert message.role == "user"
    assert message.content == "I want to build muscle"
    assert message.conversation_id == sample_conversation.conversation_id


@pytest.mark.asyncio
async def test_get_conversation_history(async_session: AsyncSession, conversation_with_messages: Conversation):
    """Should retrieve conversation history in chronological order."""
    state_manager = StateManager(async_session)
    
    history = await state_manager.get_conversation_history(
        conversation_with_messages.conversation_id
    )
    
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "I need help with my fitness routine"
    assert history[1]["role"] == "assistant"


@pytest.mark.asyncio
async def test_get_empty_conversation_history(async_session: AsyncSession, sample_conversation: Conversation):
    """Should return empty list for conversation with no messages."""
    state_manager = StateManager(async_session)
    
    history = await state_manager.get_conversation_history(
        sample_conversation.conversation_id
    )
    
    assert history == []