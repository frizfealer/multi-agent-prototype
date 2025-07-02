"""
Integration test demonstrating the full triage agent flow.
Requires Google API key and PostgreSQL.
"""
import os
import pytest
from unittest.mock import Mock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.orchestrator import Orchestrator
from src.db.models import Conversation


@pytest.mark.asyncio
async def test_triage_agent_handoff_flow(async_session: AsyncSession):
    """Should handle a complex request and trigger handoff to specialist coaches."""
    # Mock the Google Gemini API response
    mock_response = Mock()
    mock_response.candidates = [Mock()]
    mock_response.candidates[0].content.parts = [
        Mock(
            function_call=Mock(
                name="handoff_to_coach",
                args={"coach_names": ["exercise_coach", "nutrition_coach"]}
            )
        )
    ]
    
    with patch('google.generativeai.GenerativeModel') as mock_model:
        mock_chat = Mock()
        mock_chat.send_message.return_value = mock_response
        mock_model.return_value.start_chat.return_value = mock_chat
        
        orchestrator = Orchestrator("fake-api-key")
        
        # Process user message
        result = await orchestrator.process_user_message(
            async_session,
            None,
            "I need a complete workout and diet plan to build muscle"
        )
        
        # Verify the response
        assert result["conversation_id"] is not None
        assert result["agent"] == "triage"
        assert result["action"]["type"] == "handoff"
        assert "exercise_coach" in result["action"]["coaches"]
        assert "nutrition_coach" in result["action"]["coaches"]


@pytest.mark.asyncio
async def test_triage_agent_direct_request(async_session: AsyncSession):
    """Should handle a simple direct request without handoff."""
    # Mock the Google Gemini API response
    mock_response = Mock()
    mock_response.candidates = [Mock()]
    mock_response.candidates[0].content.parts = [
        Mock(
            function_call=Mock(
                name="execute_direct_request",
                args={
                    "action": "delete",
                    "context": {"plan_name": "Summer Shred", "type": "workout_plan"}
                }
            )
        )
    ]
    
    with patch('google.generativeai.GenerativeModel') as mock_model:
        mock_chat = Mock()
        mock_chat.send_message.return_value = mock_response
        mock_model.return_value.start_chat.return_value = mock_chat
        
        orchestrator = Orchestrator("fake-api-key")
        
        # Process user message
        result = await orchestrator.process_user_message(
            async_session,
            None,
            "Delete my Summer Shred workout plan"
        )
        
        # Verify the response
        assert result["action"]["type"] == "direct_request"
        assert result["action"]["action"] == "delete"
        assert result["action"]["context"]["plan_name"] == "Summer Shred"


@pytest.mark.asyncio
async def test_conversation_state_persistence(async_session: AsyncSession):
    """Should maintain conversation state across multiple messages."""
    # Mock responses
    mock_responses = [
        Mock(candidates=[Mock(content=Mock(parts=[
            Mock(function_call=Mock(
                name="ask_question",
                args={"question": "What are your specific fitness goals?"}
            ))
        ]))]),
        Mock(candidates=[Mock(content=Mock(parts=[
            Mock(function_call=Mock(
                name="handoff_to_coach",
                args={"coach_names": ["exercise_coach"]}
            ))
        ]))])
    ]
    
    with patch('google.generativeai.GenerativeModel') as mock_model:
        mock_chat = Mock()
        mock_chat.send_message.side_effect = mock_responses
        mock_model.return_value.start_chat.return_value = mock_chat
        
        orchestrator = Orchestrator("fake-api-key")
        
        # First message
        result1 = await orchestrator.process_user_message(
            async_session,
            None,
            "I want to get fit"
        )
        
        conversation_id = result1["conversation_id"]
        assert result1["action"]["type"] == "question"
        
        # Second message in same conversation
        result2 = await orchestrator.process_user_message(
            async_session,
            conversation_id,
            "I want to build muscle and increase strength"
        )
        
        assert result2["conversation_id"] == conversation_id
        assert result2["action"]["type"] == "handoff"
        assert "exercise_coach" in result2["action"]["coaches"]
        
        # Verify conversation state was updated
        from src.core.state_manager import StateManager
        state_manager = StateManager(async_session)
        conversation = await state_manager.get_conversation(conversation_id)
        assert conversation.current_agent == "exercise_coach"
        
        # Verify message history
        history = await state_manager.get_conversation_history(conversation_id)
        assert len(history) == 4  # 2 user messages + 2 assistant responses