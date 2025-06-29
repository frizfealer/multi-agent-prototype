"""
Tests for QueryProcessor following TDD approach

The QueryProcessor is responsible for routing query intents to multi-domain
context, integrating with LLM for response generation with domain awareness.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

from claude.domain_models import PendingApproval, RunningWorkflow
from claude.message_types import Message


# Fixtures
@pytest.fixture
def sample_session():
    """Fixture to create a fresh ChatSession for each test"""
    from claude.session_manager import ChatSession

    return ChatSession("test_session_123")


@pytest.fixture
def context_aggregator():
    """Fixture to create a ContextAggregator"""
    from claude.context_aggregator import ContextAggregator

    return ContextAggregator()


@pytest.fixture
def mock_llm():
    """Fixture for mocked LLM"""
    mock = AsyncMock()
    mock.ainvoke = AsyncMock()
    return mock


@pytest.fixture
def sample_workflows(sample_session):
    """Fixture to create sample workflows across multiple domains"""
    # Finance workflow
    finance_workflow = RunningWorkflow(
        id="wf_finance_1",
        domain="finance",
        description="analyze_portfolio",
        created_at=datetime.now()
    )
    finance_workflow.context["intent"] = "analyze_portfolio"
    finance_workflow.context["entities"] = {"portfolio_id": "P123", "symbol": "AAPL"}
    finance_workflow.context["state"] = {"status": "running", "progress": 75, "analysis": "Strong buy recommendation"}
    
    # HR workflow
    hr_workflow = RunningWorkflow(
        id="wf_hr_1",
        domain="hr",
        description="onboard_employee",
        created_at=datetime.now()
    )
    hr_workflow.context["intent"] = "onboard_employee"
    hr_workflow.context["entities"] = {"employee_id": "E456"}
    hr_workflow.context["state"] = {"status": "collecting_documents", "next_step": "Schedule orientation"}
    
    sample_session.add_workflow("finance", finance_workflow)
    sample_session.add_workflow("hr", hr_workflow)
    
    return sample_session


# Test functions for QueryProcessor
def test_create_query_processor():
    """Should create query processor with LLM integration"""
    from claude.query_processor import QueryProcessor

    processor = QueryProcessor()
    assert processor is not None
    assert hasattr(processor, "context_aggregator")


def test_create_query_processor_with_custom_llm():
    """Should create query processor with custom LLM"""
    from claude.query_processor import QueryProcessor

    mock_llm = Mock()
    processor = QueryProcessor(llm=mock_llm)
    
    assert processor.llm == mock_llm


def test_process_simple_query():
    """Should process simple queries without domain context"""
    from claude.query_processor import QueryProcessor
    from claude.session_manager import ChatSession

    # Mock LLM response
    mock_llm = AsyncMock()
    mock_response = Mock()
    mock_response.content = "Hello! I'm here to help with your questions."
    mock_llm.ainvoke.return_value = mock_response

    processor = QueryProcessor(llm=mock_llm)
    session = ChatSession("test_session")
    
    # Add user message to conversation history
    session.add_user_message("Hello, how are you?")
    
    async def run_test():
        result = await processor.process_query(session=session)
        
        assert result["status"] == "completed"
        assert result["response"] == "Hello! I'm here to help with your questions."
        assert result["domains_referenced"] == []
        
        # Verify LLM was called
        mock_llm.ainvoke.assert_called_once()
        
        # Verify AI response was added to session
        assert len(session.message_history) == 2  # User + AI
        assert session.message_history[-1].role == "model"
        assert session.message_history[-1].source == "query_processor"
    
    # Run the async test
    asyncio.run(run_test())


def test_process_domain_specific_query():
    """Should process domain-specific queries with context"""
    from claude.query_processor import QueryProcessor

    # Create session with workflows
    from claude.session_manager import ChatSession
    session = ChatSession("test_session")
    
    finance_workflow = RunningWorkflow(
        id="wf_finance_1",
        domain="finance",
        description="analyze_portfolio",
        created_at=datetime.now()
    )
    finance_workflow.context["intent"] = "analyze_portfolio"
    finance_workflow.context["entities"] = {"portfolio_id": "P123", "symbol": "AAPL"}
    finance_workflow.context["state"] = {"status": "running", "progress": 75}
    session.add_workflow("finance", finance_workflow)

    # Add user message to conversation history
    session.add_user_message("What's the status of my portfolio analysis?")

    # Mock LLM response
    mock_llm = AsyncMock()
    mock_response = Mock()
    mock_response.content = "Based on your portfolio analysis, AAPL shows strong performance with 75% completion."
    mock_llm.ainvoke.return_value = mock_response

    processor = QueryProcessor(llm=mock_llm)
    
    async def run_test():
        result = await processor.process_query(
            session=session,
            intent_domain="finance"
        )
        
        assert result["status"] == "completed"
        assert result["response"] == "Based on your portfolio analysis, AAPL shows strong performance with 75% completion."
        assert result["domains_referenced"] == ["finance"]
        
        # Verify LLM was called with conversation history
        call_args = mock_llm.ainvoke.call_args[0][0]
        assert len(call_args) >= 2  # Should have system message + conversation history
        assert "portfolio" in call_args[0].content.lower()
        
        # Verify AI response was added to session
        assert len(session.message_history) == 2  # User + AI
        assert session.message_history[-1].source == "query_processor"
    
    # Run the async test
    asyncio.run(run_test())


def test_query_with_empty_session():
    """Should handle queries on empty sessions gracefully"""
    from claude.query_processor import QueryProcessor
    from claude.session_manager import ChatSession

    empty_session = ChatSession("empty_session")
    
    # Add user message to conversation
    empty_session.add_user_message("What workflows are running?")
    
    # Mock LLM response
    mock_llm = AsyncMock()
    mock_response = Mock()
    mock_response.content = "I don't see any active workflows in your session."
    mock_llm.ainvoke.return_value = mock_response

    processor = QueryProcessor(llm=mock_llm)
    
    async def run_test():
        result = await processor.process_query(session=empty_session)
        
        assert result["status"] == "completed"
        assert result["domains_referenced"] == []
        assert "active workflows" in result["response"].lower()
    
    # Run the async test
    asyncio.run(run_test())


def test_query_confidence_scoring():
    """Should include confidence scoring for query responses"""
    from claude.query_processor import QueryProcessor
    from claude.session_manager import ChatSession

    session = ChatSession("test_session")
    finance_workflow = RunningWorkflow(
        id="wf_finance_1",
        domain="finance",
        description="analyze_portfolio",
        created_at=datetime.now()
    )
    finance_workflow.context["intent"] = "analyze_portfolio"
    finance_workflow.context["entities"] = {"symbol": "AAPL"}
    finance_workflow.context["state"] = {"status": "running", "progress": 75}
    session.add_workflow("finance", finance_workflow)

    # Add user message to conversation
    session.add_user_message("How is my portfolio doing?")

    # Mock LLM response with confidence
    mock_llm = AsyncMock()
    mock_response = Mock()
    mock_response.content = "Based on available data, your portfolio analysis is progressing well."
    mock_llm.ainvoke.return_value = mock_response

    processor = QueryProcessor(llm=mock_llm)
    
    async def run_test():
        result = await processor.process_query(
            session=session,
            intent_domain="finance"
        )
        
        assert "confidence" in result
        assert isinstance(result["confidence"], float)
        assert 0.0 <= result["confidence"] <= 1.0
    
    # Run the async test
    asyncio.run(run_test())


def test_query_error_handling():
    """Should handle LLM errors gracefully"""
    from claude.query_processor import QueryProcessor
    from claude.session_manager import ChatSession

    session = ChatSession("test_session")

    # Add user message to conversation
    session.add_user_message("What's my status?")

    # Mock LLM to raise an exception
    mock_llm = AsyncMock()
    mock_llm.ainvoke.side_effect = Exception("LLM API error")

    processor = QueryProcessor(llm=mock_llm)
    
    async def run_test():
        result = await processor.process_query(session=session)
        
        assert result["status"] == "error"
        assert "error" in result["response"].lower()
        assert result["error_type"] == "llm_error"
    
    # Run the async test
    asyncio.run(run_test())


def test_query_response_formatting():
    """Should format query responses consistently"""
    from claude.query_processor import QueryProcessor
    from claude.session_manager import ChatSession

    session = ChatSession("test_session")
    finance_workflow = RunningWorkflow(
        id="wf_finance_1",
        domain="finance",
        description="analyze_portfolio",
        created_at=datetime.now()
    )
    finance_workflow.context["intent"] = "analyze_portfolio"
    session.add_workflow("finance", finance_workflow)

    # Add user message to conversation
    session.add_user_message("Portfolio status?")

    # Mock LLM response
    mock_llm = AsyncMock()
    mock_response = Mock()
    mock_response.content = "Your portfolio analysis shows strong performance."
    mock_llm.ainvoke.return_value = mock_response

    processor = QueryProcessor(llm=mock_llm)
    
    async def run_test():
        result = await processor.process_query(session=session)
        
        # Verify response structure
        required_fields = ["status", "response", "domains_referenced", "confidence", "timestamp"]
        for field in required_fields:
            assert field in result
        
        assert isinstance(result["timestamp"], str)
        assert isinstance(result["domains_referenced"], list)
    
    # Run the async test
    asyncio.run(run_test())




def test_domain_relevance_scoring():
    """Should score domain relevance for queries"""
    from claude.query_processor import QueryProcessor
    from claude.session_manager import ChatSession

    session = ChatSession("test_session")
    
    # Add finance workflow
    finance_workflow = RunningWorkflow(
        id="wf_finance_1",
        domain="finance",
        description="analyze_portfolio",
        created_at=datetime.now()
    )
    finance_workflow.context["entities"] = {"symbol": "AAPL"}
    session.add_workflow("finance", finance_workflow)
    
    # Add HR workflow  
    hr_workflow = RunningWorkflow(
        id="wf_hr_1",
        domain="hr", 
        description="onboard_employee",
        created_at=datetime.now()
    )
    session.add_workflow("hr", hr_workflow)

    processor = QueryProcessor()
    
    # Test domain relevance
    finance_score = processor.calculate_domain_relevance(
        query="What's my portfolio performance?",
        domain="finance",
        session=session
    )
    
    hr_score = processor.calculate_domain_relevance(
        query="What's my portfolio performance?",
        domain="hr",
        session=session
    )
    
    assert isinstance(finance_score, float)
    assert isinstance(hr_score, float)
    assert finance_score > hr_score  # Finance should be more relevant


def test_context_size_limit():
    """Should respect context size limits"""
    from claude.query_processor import QueryProcessor
    from claude.session_manager import ChatSession

    session = ChatSession("test_session")

    # Add workflow with large context
    large_workflow = RunningWorkflow(
        id="wf_large",
        domain="analytics",
        description="process_data",
        created_at=datetime.now()
    )
    large_workflow.context["large_data"] = "x" * 2000  # Large context
    large_workflow.context["state"] = {"summary": "Processing large dataset"}
    session.add_workflow("analytics", large_workflow)
    
    # Add user message to conversation
    session.add_user_message("What's happening with analytics?")
    
    # Mock LLM response
    mock_llm = AsyncMock()
    mock_response = Mock()
    mock_response.content = "Your analytics workflow is processing a large dataset."
    mock_llm.ainvoke.return_value = mock_response

    processor = QueryProcessor(llm=mock_llm, max_context_size=5000)
    
    async def run_test():
        result = await processor.process_query(
            session=session,
            intent_domain="analytics"
        )
        
        assert result["status"] == "completed"
        # Context should be summarized
        call_args = mock_llm.ainvoke.call_args[0][0]
        context_content = call_args[0].content
        assert len(context_content) < 6000  # Should be truncated
    
    # Run the async test
    asyncio.run(run_test())




def test_empty_context_handling():
    """Should handle workflows with empty context gracefully"""
    from claude.query_processor import QueryProcessor
    from claude.session_manager import ChatSession

    session = ChatSession("test_session")
    
    workflow = RunningWorkflow(
        id="wf_empty",
        domain="test",
        description="empty_workflow",
        created_at=datetime.now()
    )
    # Don't add anything to context - it should be empty dict
    session.add_workflow("test", workflow)

    # Add user message to conversation
    session.add_user_message("What's my status?")

    # Mock LLM response
    mock_llm = AsyncMock()
    mock_response = Mock()
    mock_response.content = "I see you have a workflow but no context available."
    mock_llm.ainvoke.return_value = mock_response

    processor = QueryProcessor(llm=mock_llm)
    
    async def run_test():
        result = await processor.process_query(session=session)
        
        assert result["status"] == "completed"
        assert result["domains_referenced"] == ["test"]
        
        # Verify empty context was handled
        call_args = mock_llm.ainvoke.call_args[0][0]
        context_content = call_args[0].content
        # The system prompt should mention the workflow context even if minimal
        assert "workflow" in context_content.lower()
    
    # Run the async test
    asyncio.run(run_test())