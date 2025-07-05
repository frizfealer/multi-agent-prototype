"""
Unit tests for BaseCoach class
"""
import pytest
import os
from unittest.mock import Mock, patch, MagicMock
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def concrete_coach_class():
    """Should create a concrete implementation of BaseCoach for testing"""
    with patch.dict(os.environ, {'GEMINI_API_KEY': 'fake-key'}):
        # Mock the entire genai module before importing BaseCoach
        mock_genai = MagicMock()
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        
        with patch.dict('sys.modules', {'google.genai': mock_genai}):
            from src.agents.base_coach import BaseCoach
            
            class ConcreteCoach(BaseCoach):
                def get_system_prompt(self):
                    return "Test system prompt"
                
                def get_required_fields(self):
                    return ["test_field"]
                
                def get_optional_fields(self):
                    return ["optional_field"]
            
            return ConcreteCoach


@pytest.fixture
def coach_with_specialist_tools(concrete_coach_class):
    """Should create a coach with specialist tools for testing"""
    class CoachWithSpecialistTools(concrete_coach_class):
        def get_specialist_tools(self):
            return [{"name": "specialist_tool", "description": "Test tool"}]
    
    return CoachWithSpecialistTools


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
        {"role": "user", "content": "Test message"}
    ]


def test_initialization(mock_genai):
    """Should initialize BaseCoach with domain"""
    mock_genai_module, mock_models = mock_genai
    
    # Import after mocking
    from src.agents.base_coach import BaseCoach
    
    class TestCoach(BaseCoach):
        def get_system_prompt(self):
            return "Test system prompt"
        def get_required_fields(self):
            return ["test_field"]
        def get_optional_fields(self):
            return ["optional_field"]
    
    coach = TestCoach("test_domain")
    assert coach.domain == "test_domain"
    # Client should be created once
    mock_genai_module.Client.assert_called_once()


def test_shared_tools(mock_genai):
    """Should return correct shared tools"""
    from src.agents.base_coach import BaseCoach
    
    class TestCoach(BaseCoach):
        def get_system_prompt(self):
            return "Test system prompt"
        def get_required_fields(self):
            return ["test_field"]
        def get_optional_fields(self):
            return ["optional_field"]
    
    coach = TestCoach("test_domain")
    tools = coach.get_shared_tools()
    
    assert len(tools) == 3
    tool_names = [tool["name"] for tool in tools]
    
    assert "hand_off_to_triage_agent" in tool_names
    assert "create_artifacts" in tool_names
    assert "search_internet" in tool_names


def test_specialist_tools_default(mock_genai):
    """Should return empty specialist tools by default"""
    from src.agents.base_coach import BaseCoach
    
    class TestCoach(BaseCoach):
        def get_system_prompt(self):
            return "Test system prompt"
        def get_required_fields(self):
            return ["test_field"]
        def get_optional_fields(self):
            return ["optional_field"]
    
    coach = TestCoach("test_domain")
    specialist_tools = coach.get_specialist_tools()
    
    assert specialist_tools == []


def test_all_tools_combination(mock_genai):
    """Should combine shared and specialist tools"""
    from src.agents.base_coach import BaseCoach
    
    class TestCoach(BaseCoach):
        def get_system_prompt(self):
            return "Test system prompt"
        def get_required_fields(self):
            return ["test_field"]
        def get_optional_fields(self):
            return ["optional_field"]
        def get_specialist_tools(self):
            return [{"name": "specialist_tool", "description": "Test tool"}]
    
    coach = TestCoach("test_domain")
    all_tools = coach.get_all_tools()
    
    assert len(all_tools) == 4  # 3 shared + 1 specialist
    tool_names = [tool["name"] for tool in all_tools]
    assert "specialist_tool" in tool_names


def test_abstract_methods_implemented(mock_genai):
    """Should implement required abstract methods"""
    from src.agents.base_coach import BaseCoach
    
    class TestCoach(BaseCoach):
        def get_system_prompt(self):
            return "Test system prompt"
        def get_required_fields(self):
            return ["test_field"]
        def get_optional_fields(self):
            return ["optional_field"]
    
    coach = TestCoach("test_domain")
    
    assert coach.get_system_prompt() == "Test system prompt"
    assert coach.get_required_fields() == ["test_field"]
    assert coach.get_optional_fields() == ["optional_field"]


def test_abstract_class_cannot_instantiate():
    """Should not allow direct instantiation of BaseCoach"""
    with patch.dict(os.environ, {'GEMINI_API_KEY': 'fake-key'}):
        mock_genai = MagicMock()
        with patch.dict('sys.modules', {'google.genai': mock_genai}):
            from src.agents.base_coach import BaseCoach
            
            with pytest.raises(TypeError):
                BaseCoach("test_domain")


@pytest.mark.asyncio
async def test_process_request_error_handling(mock_genai, conversation_history):
    """Should handle errors gracefully in process_request"""
    mock_genai_module, mock_models = mock_genai
    
    # Make generate_content raise an exception
    mock_models.generate_content.side_effect = Exception("Test error")
    
    from src.agents.base_coach import BaseCoach
    
    class TestCoach(BaseCoach):
        def get_system_prompt(self):
            return "Test system prompt"
        def get_required_fields(self):
            return ["test_field"]
        def get_optional_fields(self):
            return ["optional_field"]
    
    coach = TestCoach("test_domain")
    result = await coach.process_request(conversation_history)
    
    assert result["name"] == "respond_directly"
    assert "error" in result["arguments"]


@pytest.mark.parametrize("domain,expected", [
    ("exercise", "exercise"),
    ("nutrition", "nutrition"),
    ("test_domain", "test_domain"),
])
def test_domain_assignment(mock_genai, domain, expected):
    """Should correctly assign domain during initialization"""
    from src.agents.base_coach import BaseCoach
    
    class TestCoach(BaseCoach):
        def get_system_prompt(self):
            return "Test system prompt"
        def get_required_fields(self):
            return ["test_field"]
        def get_optional_fields(self):
            return ["optional_field"]
    
    coach = TestCoach(domain)
    assert coach.domain == expected


@pytest.mark.parametrize("tool_count,specialist_tools", [
    (3, []),
    (4, [{"name": "tool1", "description": "desc1"}]),
    (5, [{"name": "tool1", "description": "desc1"}, {"name": "tool2", "description": "desc2"}]),
])
def test_dynamic_tool_count(mock_genai, tool_count, specialist_tools):
    """Should handle different numbers of specialist tools"""
    from src.agents.base_coach import BaseCoach
    
    class DynamicCoach(BaseCoach):
        def get_system_prompt(self):
            return "Test system prompt"
        def get_required_fields(self):
            return ["test_field"]
        def get_optional_fields(self):
            return ["optional_field"]
        def get_specialist_tools(self):
            return specialist_tools
    
    coach = DynamicCoach("test_domain")
    all_tools = coach.get_all_tools()
    
    assert len(all_tools) == tool_count