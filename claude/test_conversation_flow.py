"""
Test conversation flow with QueryProcessor

Tests the new conversation-based approach where QueryProcessor
understands references and context from previous messages.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock

from claude.domain_models import RunningWorkflow
from claude.query_processor import QueryProcessor
from claude.session_manager import ChatSession


def test_conversation_context_understanding():
    """Should understand references to previous conversation"""

    # Create session with a workflow
    session = ChatSession("conversation_test")

    finance_workflow = RunningWorkflow(
        id="wf_finance_1", domain="finance", description="portfolio_analysis", created_at=datetime.now()
    )
    finance_workflow.context["entities"] = {"symbol": "AAPL"}
    finance_workflow.context["state"] = {"status": "running", "progress": 85}
    session.add_workflow("finance", finance_workflow)

    # Mock LLM responses
    mock_llm = AsyncMock()

    # First response about portfolio
    first_response = Mock()
    first_response.content = "Your AAPL portfolio analysis is 85% complete and showing strong performance."

    # Second response understanding "it" refers to the portfolio
    second_response = Mock()
    second_response.content = "The portfolio analysis should be finished within the next hour. The final report will include recommendations based on the current market trends."

    mock_llm.ainvoke.side_effect = [first_response, second_response]

    processor = QueryProcessor(llm=mock_llm)

    async def run_conversation_test():
        # First user message
        session.add_user_message("What's the status of my portfolio analysis?")

        result1 = await processor.process_query(session=session, intent_domain="finance")

        assert result1["status"] == "completed"
        assert "AAPL" in result1["response"]
        assert "85%" in result1["response"]

        # Second user message with reference to previous context
        session.add_user_message("When will it be finished?")

        result2 = await processor.process_query(session=session, intent_domain="finance")

        assert result2["status"] == "completed"
        assert "portfolio" in result2["response"]

        # Verify conversation history was passed to LLM for second call
        second_call_args = mock_llm.ainvoke.call_args_list[1][0][0]
        # Should have system message + 3 conversation messages (user1, ai1, user2)
        assert len(second_call_args) >= 4

        # Verify the conversation history includes previous messages
        conversation_text = str(second_call_args)
        assert "portfolio analysis" in conversation_text.lower()
        assert "when will it be finished" in conversation_text.lower()

        # Verify session has full conversation
        assert len(session.message_history) == 4  # user1, ai1, user2, ai2
        assert session.message_history[0].content == "What's the status of my portfolio analysis?"
        assert session.message_history[1].source == "query_processor"
        assert session.message_history[2].content == "When will it be finished?"
        assert session.message_history[3].source == "query_processor"

    # Run the async test
    asyncio.run(run_conversation_test())


def test_sliding_window_behavior():
    """Should apply sliding window to limit conversation history"""
    from claude.session_manager import ChatSession

    # Create session with small sliding window
    session = ChatSession("sliding_test")
    session.conversation_manager.max_messages = 5  # Very small for testing

    # Add many messages to trigger sliding window
    for i in range(10):
        session.add_user_message(f"Message {i}")
        session.add_ai_message(f"Response {i}", source="test")

    # Should only keep the last 5 messages
    assert len(session.message_history) == 5

    # Should keep the most recent messages
    # With 10 pairs (20 messages total), keeping last 5 means messages 15-19 (0-indexed)
    # Which correspond to pairs 7,8,9: "Message 7", "Response 7", "Message 8", "Response 8", "Message 9"
    message_contents = [msg.content for msg in session.message_history]
    assert "Message 7" in message_contents or "Response 7" in message_contents
    assert "Message 9" in message_contents


def test_message_format_conversion():
    """Should convert between message formats correctly"""
    from claude.session_manager import ChatSession

    session = ChatSession("format_test")

    # Add various message types
    session.add_user_message("Hello")
    session.add_ai_message("Hi there", source="query_processor")
    session.add_system_message("System notification", source="system")

    # Test Gemini format conversion
    gemini_messages = session.get_conversation_for_gemini(include_system=True)
    assert len(gemini_messages) == 3
    assert gemini_messages[0].role == "user"
    assert gemini_messages[1].role == "model"
    assert gemini_messages[2].role == "system"

    # Test LangChain format conversion
    langchain_messages = session.get_conversation_for_langchain(include_system=True)
    assert len(langchain_messages) == 3

    # Test filtering system messages
    no_system_messages = session.get_conversation_for_gemini(include_system=False)
    assert len(no_system_messages) == 2
    assert all(msg.role != "system" for msg in no_system_messages)


def test_empty_conversation_handling():
    """Should handle empty conversation gracefully"""
    from claude.query_processor import QueryProcessor
    from claude.session_manager import ChatSession

    session = ChatSession("empty_test")
    processor = QueryProcessor()

    async def run_test():
        # No messages in session
        result = await processor.process_query(session=session)

        assert result["status"] == "error"
        assert result["error_type"] == "no_user_message"
        assert "No user message found" in result["response"]

    asyncio.run(run_test())


def test_latest_message_extraction():
    """Should correctly identify the latest user message"""
    from claude.session_manager import ChatSession

    session = ChatSession("latest_test")

    # Add mixed message types
    session.add_user_message("First user message")
    session.add_ai_message("AI response", source="query_processor")
    session.add_system_message("System message", source="system")
    session.add_user_message("Latest user message")

    latest = session.get_latest_user_message()
    assert latest is not None
    assert latest.content == "Latest user message"
    assert latest.role == "user"
