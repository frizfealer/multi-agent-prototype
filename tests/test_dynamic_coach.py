"""
Unit tests for Dynamic Coach Creation System
"""
import pytest
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.dynamic_coach import DynamicCoach, CoachTemplateManager


@pytest.fixture
def sample_domains():
    """Should provide sample domains for testing"""
    return ["exercise_planning", "nutrition_planning"]


@pytest.fixture
def sample_tools():
    """Should provide sample tools for testing"""
    return [{"name": "test_tool", "description": "Test tool description"}]


@pytest.fixture
def coach_template_manager():
    """Should create a CoachTemplateManager instance for testing"""
    return CoachTemplateManager()


def test_initialization(sample_domains, sample_tools):
    """Should initialize DynamicCoach with domains and prompt"""
    system_prompt = "Test prompt"
    
    coach = DynamicCoach(sample_domains, system_prompt, sample_tools)
    
    assert coach.domains == sample_domains
    assert coach.domain == "exercise_planning+nutrition_planning"
    assert coach.get_system_prompt() == system_prompt
    assert coach.get_specialist_tools() == sample_tools


def test_single_domain():
    """Should handle single domain correctly"""
    domains = ["exercise_planning"]
    system_prompt = "Test prompt"
    tools = []
    
    coach = DynamicCoach(domains, system_prompt, tools)
    
    assert coach.domain == "exercise_planning"


def test_multiple_domains_sorted():
    """Should sort domains for consistent naming"""
    domains = ["nutrition_planning", "exercise_planning"]
    system_prompt = "Test prompt"
    tools = []
    
    coach = DynamicCoach(domains, system_prompt, tools)
    
    # Domain should be sorted alphabetically
    assert coach.domain == "nutrition_planning+exercise_planning"


def test_initialization_coach_template_manager(coach_template_manager):
    """Should initialize with predefined specialty blocks"""
    assert "exercise_planning" in coach_template_manager.SPECIALTY_BLOCKS
    assert "nutrition_planning" in coach_template_manager.SPECIALTY_BLOCKS
    assert "sleep_optimization" in coach_template_manager.SPECIALTY_BLOCKS


def test_get_available_specialties(coach_template_manager):
    """Should return list of available specialties"""
    specialties = coach_template_manager.get_available_specialties()
    
    assert "exercise_planning" in specialties
    assert "nutrition_planning" in specialties
    assert "sleep_optimization" in specialties
    assert len(specialties) >= 3


def test_create_single_domain_coach(coach_template_manager):
    """Should create coach for single domain"""
    coach = coach_template_manager.create_multi_domain_coach(["exercise_planning"])
    
    assert isinstance(coach, DynamicCoach)
    assert coach.domain == "exercise_planning"
    
    prompt = coach.get_system_prompt()
    assert "Exercise Planning Specialty" in prompt
    # Single domain should not contain nutrition content
    assert "Nutrition Planning Specialty" not in prompt


def test_create_multi_domain_coach(coach_template_manager):
    """Should create coach for multiple domains"""
    coach = coach_template_manager.create_multi_domain_coach(["exercise_planning", "nutrition_planning"])
    
    assert isinstance(coach, DynamicCoach)
    assert coach.domain == "exercise_planning+nutrition_planning"
    
    prompt = coach.get_system_prompt()
    assert "Exercise Planning Specialty" in prompt
    assert "Nutrition Planning Specialty" in prompt


def test_combined_prompt_structure(coach_template_manager):
    """Should create well-structured combined prompt"""
    coach = coach_template_manager.create_multi_domain_coach(["exercise_planning", "nutrition_planning"])
    prompt = coach.get_system_prompt()
    
    # Check for base template content
    assert "specialist" in prompt.lower()
    assert "GENERAL GUIDELINES" in prompt
    assert "CONFLICT PREVENTION" in prompt
    
    # Check for domain-specific content
    assert "Exercise Planning" in prompt
    assert "Nutrition Planning" in prompt
    
    # Check for tool information
    assert "Available tools" in prompt


def test_combined_tools(coach_template_manager):
    """Should combine tools from all domains"""
    coach = coach_template_manager.create_multi_domain_coach(["exercise_planning", "nutrition_planning"])
    specialist_tools = coach.get_specialist_tools()
    
    tool_names = [tool["name"] for tool in specialist_tools]
    
    # Should include exercise tools
    assert "calculate_training_volume" in tool_names
    assert "suggest_exercise_alternatives" in tool_names
    
    # Should include nutrition tools
    assert "calculate_calories" in tool_names
    assert "suggest_meal_alternatives" in tool_names


def test_unknown_domain_handling(coach_template_manager):
    """Should handle unknown domains gracefully"""
    coach = coach_template_manager.create_multi_domain_coach(["unknown_domain"])
    prompt = coach.get_system_prompt()
    
    # Should include placeholder for unknown domain
    assert "Unknown Domain" in prompt or "Instructions not yet defined" in prompt


def test_add_specialty(coach_template_manager):
    """Should allow adding new specialties"""
    new_specialty = "test_specialty"
    new_instructions = "## Test Specialty\nTest instructions"
    new_tools = [{"name": "test_tool", "description": "Test tool"}]
    
    coach_template_manager.add_specialty(new_specialty, new_instructions, new_tools)
    
    assert new_specialty in coach_template_manager.SPECIALTY_BLOCKS
    assert coach_template_manager.SPECIALTY_BLOCKS[new_specialty] == new_instructions
    assert coach_template_manager.SPECIALIST_TOOLS[new_specialty] == new_tools
    
    # Test creating coach with new specialty
    coach = coach_template_manager.create_multi_domain_coach([new_specialty])
    prompt = coach.get_system_prompt()
    assert "Test Specialty" in prompt


def test_domain_sorting_consistency(coach_template_manager):
    """Should create consistent domain names regardless of input order"""
    coach1 = coach_template_manager.create_multi_domain_coach(["exercise_planning", "nutrition_planning"])
    coach2 = coach_template_manager.create_multi_domain_coach(["nutrition_planning", "exercise_planning"])
    
    # Both should contain both domains, but order might differ
    assert "exercise_planning" in coach1.domain and "nutrition_planning" in coach1.domain
    assert "exercise_planning" in coach2.domain and "nutrition_planning" in coach2.domain


def test_tool_deduplication(coach_template_manager):
    """Should not duplicate tools when multiple domains share them"""
    # Add a specialty that shares tools with existing ones
    coach_template_manager.add_specialty(
        "test_specialty",
        "Test instructions",
        [{"name": "calculate_calories", "description": "Duplicate tool"}]  # Same as nutrition
    )
    
    coach = coach_template_manager.create_multi_domain_coach(["nutrition_planning", "test_specialty"])
    specialist_tools = coach.get_specialist_tools()
    
    tool_names = [tool["name"] for tool in specialist_tools]
    
    # Should not have duplicate calculate_calories
    assert tool_names.count("calculate_calories") == 2  # One from each domain as designed


@pytest.mark.parametrize("domains,expected_domain", [
    (["exercise_planning"], "exercise_planning"),
    (["nutrition_planning", "exercise_planning"], "nutrition_planning+exercise_planning"),
    (["sleep_optimization"], "sleep_optimization"),
])
def test_domain_naming_patterns(domains, expected_domain):
    """Should create correct domain names for various domain combinations"""
    coach = DynamicCoach(domains, "Test prompt", [])
    assert coach.domain == expected_domain


@pytest.mark.parametrize("specialty,expected_in_prompt", [
    ("exercise_planning", "Exercise Planning Specialty"),
    ("nutrition_planning", "Nutrition Planning Specialty"),
    ("sleep_optimization", "Sleep Optimization"),
])
def test_specialty_content_inclusion(coach_template_manager, specialty, expected_in_prompt):
    """Should include correct specialty content in prompts"""
    coach = coach_template_manager.create_multi_domain_coach([specialty])
    prompt = coach.get_system_prompt()
    assert expected_in_prompt in prompt