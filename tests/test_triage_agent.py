"""
Unit tests for TriageAgent class
"""
import pytest
import os
import json
from unittest.mock import Mock, patch, MagicMock
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def mock_genai():
    """Should mock Google Generative AI dependencies"""
    mock_genai = MagicMock()
    mock_types = MagicMock()
    mock_client = MagicMock()
    mock_aio = MagicMock()
    mock_models = MagicMock()
    
    # Set up the client structure
    mock_genai.Client.return_value = mock_client
    mock_client.aio = mock_aio
    mock_aio.models = mock_models
    
    # Mock types module
    mock_genai.types = mock_types
    mock_types.Content = MagicMock
    mock_types.Part = MagicMock
    mock_types.GenerateContentConfig = MagicMock
    mock_types.AutomaticFunctionCallingConfig = MagicMock
    
    with patch.dict(os.environ, {'GEMINI_API_KEY': 'fake-key'}), \
         patch.dict('sys.modules', {'google.genai': mock_genai, 'google.genai.types': mock_types}):
        yield mock_genai, mock_models


@pytest.fixture
def conversation_history():
    """Should provide sample conversation history"""
    return [
        {"role": "user", "content": "I want to create an exercise plan"}
    ]


@pytest.fixture
def mock_response():
    """Should provide mock response object"""
    response = MagicMock()
    response.function_calls = []
    response.text = "Test response"
    response.candidates = [MagicMock()]
    response.candidates[0].content = MagicMock()
    return response


@pytest.fixture
def mock_function_call():
    """Should provide mock function call object"""
    function_call = MagicMock()
    function_call.name = "hand_off_to_experts"
    function_call.args = {"experts": ["exercise_coach"]}
    return function_call


def test_initialization(mock_genai):
    """Should initialize TriageAgent with correct tools"""
    mock_genai_module, mock_models = mock_genai
    
    from src.agents.triage_agent import TriageAgent
    
    agent = TriageAgent()
    assert hasattr(agent, 'available_tools')
    assert len(agent.available_tools) == 2
    
    tool_names = [tool.__name__ for tool in agent.available_tools]
    assert "get_available_experts" in tool_names
    assert "hand_off_to_experts" in tool_names


def test_get_available_experts():
    """Should return list of available experts"""
    with patch.dict(os.environ, {'GEMINI_API_KEY': 'fake-key'}):
        from src.agents.triage_agent import get_available_experts
        
        experts = get_available_experts()
        assert isinstance(experts, list)
        assert "exercise_coach" in experts
        assert "nutrition_coach" in experts


def test_hand_off_to_experts_function():
    """Should be marked as terminal function"""
    with patch.dict(os.environ, {'GEMINI_API_KEY': 'fake-key'}):
        from src.agents.triage_agent import hand_off_to_experts
        from src.agents.utils import is_function_terminal
        
        assert is_function_terminal(hand_off_to_experts) == True


def test_get_available_experts_function():
    """Should be marked as non-terminal function"""
    with patch.dict(os.environ, {'GEMINI_API_KEY': 'fake-key'}):
        from src.agents.triage_agent import get_available_experts
        from src.agents.utils import is_function_terminal
        
        assert is_function_terminal(get_available_experts) == False


@pytest.mark.asyncio
async def test_process_request_direct_response(mock_genai, conversation_history, mock_response):
    """Should handle direct response when no function calls"""
    mock_genai_module, mock_models = mock_genai
    
    # Set up mock response with no function calls
    mock_response.function_calls = None
    mock_models.generate_content.return_value = mock_response
    
    from src.agents.triage_agent import TriageAgent
    
    agent = TriageAgent()
    result = await agent.process_request(conversation_history)
    
    assert result["name"] == "respond_directly"
    assert "text" in json.loads(result["arguments"])
    assert json.loads(result["arguments"])["text"] == "Test response"


@pytest.mark.asyncio
async def test_process_request_hand_off_to_experts(mock_genai, conversation_history, mock_response, mock_function_call):
    """Should handle handoff to experts"""
    mock_genai_module, mock_models = mock_genai
    
    # Set up mock response with hand_off_to_experts function call
    mock_response.function_calls = [mock_function_call]
    mock_models.generate_content.return_value = mock_response
    
    from src.agents.triage_agent import TriageAgent
    
    agent = TriageAgent()
    result = await agent.process_request(conversation_history)
    
    assert result["name"] == "hand_off_to_experts"
    experts = json.loads(result["arguments"])
    assert experts == ["exercise_coach"]


@pytest.mark.asyncio
async def test_process_request_get_available_experts_then_handoff(mock_genai, conversation_history):
    """Should handle get_available_experts followed by handoff"""
    mock_genai_module, mock_models = mock_genai
    
    # First response: get_available_experts
    first_response = MagicMock()
    first_function_call = MagicMock()
    first_function_call.name = "get_available_experts"
    first_function_call.args = {}
    first_response.function_calls = [first_function_call]
    first_response.candidates = [MagicMock()]
    first_response.candidates[0].content = MagicMock()
    
    # Second response: hand_off_to_experts
    second_response = MagicMock()
    second_function_call = MagicMock()
    second_function_call.name = "hand_off_to_experts"
    second_function_call.args = {"experts": ["exercise_coach"]}
    second_response.function_calls = [second_function_call]
    
    # Mock generate_content to return different responses
    mock_models.generate_content.side_effect = [first_response, second_response]
    
    from src.agents.triage_agent import TriageAgent
    
    agent = TriageAgent()
    result = await agent.process_request(conversation_history)
    
    assert result["name"] == "hand_off_to_experts"
    experts = json.loads(result["arguments"])
    assert experts == ["exercise_coach"]
    
    # Should have called generate_content twice
    assert mock_models.generate_content.call_count == 2


@pytest.mark.asyncio
async def test_process_request_error_handling(mock_genai, conversation_history):
    """Should handle errors gracefully in process_request"""
    mock_genai_module, mock_models = mock_genai
    
    # Make generate_content raise an exception
    mock_models.generate_content.side_effect = Exception("Test error")
    
    from src.agents.triage_agent import TriageAgent
    
    agent = TriageAgent()
    result = await agent.process_request(conversation_history)
    
    assert result["name"] == "respond_directly"
    args = json.loads(result["arguments"])
    assert "error" in args["text"].lower()
    assert "apologize" in args["text"].lower()


@pytest.mark.asyncio
async def test_process_request_with_logging(mock_genai, conversation_history, mock_response):
    """Should log appropriate messages during processing"""
    mock_genai_module, mock_models = mock_genai
    
    mock_response.function_calls = None
    mock_models.generate_content.return_value = mock_response
    
    with patch('src.agents.triage_agent.logger') as mock_logger:
        from src.agents.triage_agent import TriageAgent
        
        agent = TriageAgent()
        await agent.process_request(conversation_history)
        
        # Check that debug and info logs were called
        mock_logger.debug.assert_called()
        mock_logger.info.assert_called()


@pytest.mark.parametrize("expert_list,expected", [
    (["exercise_coach"], ["exercise_coach"]),
    (["nutrition_coach"], ["nutrition_coach"]),
    (["exercise_coach", "nutrition_coach"], ["exercise_coach", "nutrition_coach"]),
])
def test_hand_off_to_experts_with_different_experts(expert_list, expected):
    """Should handle different expert combinations"""
    with patch.dict(os.environ, {'GEMINI_API_KEY': 'fake-key'}):
        from src.agents.triage_agent import hand_off_to_experts
        
        # The function doesn't actually return anything, it's just for LLM tooling
        # So we just test that it can be called without error
        hand_off_to_experts(expert_list)


def test_experts_enum():
    """Should have correct expert enum values"""
    with patch.dict(os.environ, {'GEMINI_API_KEY': 'fake-key'}):
        from src.agents.triage_agent import Experts
        
        assert Experts.EXERCISE_COACH.value == "exercise_coach"
        assert Experts.NUTRITION_COACH.value == "nutrition_coach"


@pytest.mark.asyncio
async def test_process_request_message_conversion(mock_genai, conversation_history, mock_response):
    """Should convert messages to Gemini format"""
    mock_genai_module, mock_models = mock_genai
    
    mock_response.function_calls = None
    mock_models.generate_content.return_value = mock_response
    
    with patch('src.agents.triage_agent.convert_to_gemini_message') as mock_convert:
        mock_convert.return_value = [MagicMock()]
        
        from src.agents.triage_agent import TriageAgent
        
        agent = TriageAgent()
        await agent.process_request(conversation_history)
        
        mock_convert.assert_called_once_with(conversation_history)


@pytest.mark.asyncio
async def test_process_request_config_creation(mock_genai, conversation_history, mock_response):
    """Should create proper generation config"""
    mock_genai_module, mock_models = mock_genai
    
    mock_response.function_calls = None
    mock_models.generate_content.return_value = mock_response
    
    from src.agents.triage_agent import TriageAgent
    
    agent = TriageAgent()
    await agent.process_request(conversation_history)
    
    # Check that generate_content was called with proper config
    call_args = mock_models.generate_content.call_args
    assert 'config' in call_args.kwargs
    
    # Check model name
    assert call_args.kwargs['model'] == "gemini-2.5-flash"


@pytest.mark.parametrize("message_count", [1, 3, 5])
@pytest.mark.asyncio
async def test_process_request_with_different_history_lengths(mock_genai, mock_response, message_count):
    """Should handle different conversation history lengths"""
    mock_genai_module, mock_models = mock_genai
    
    mock_response.function_calls = None
    mock_models.generate_content.return_value = mock_response
    
    # Create conversation history with different lengths
    conversation_history = [
        {"role": "user", "content": f"Message {i+1}"}
        for i in range(message_count)
    ]
    
    from src.agents.triage_agent import TriageAgent
    
    agent = TriageAgent()
    result = await agent.process_request(conversation_history)
    
    assert result["name"] == "respond_directly"
    assert "text" in json.loads(result["arguments"])