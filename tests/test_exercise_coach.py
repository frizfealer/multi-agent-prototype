"""
Unit tests for ExerciseCoach class
"""
import pytest
import os
from unittest.mock import Mock, patch
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.exercise_coach import ExerciseCoach


class TestExerciseCoach:
    """Should test ExerciseCoach specialist functionality"""
    
    @patch.dict(os.environ, {'GEMINI_API_KEY': 'fake-key'})
    @patch('google.generativeai.configure')
    @patch('google.generativeai.GenerativeModel')
    def test_initialization(self, mock_model, mock_configure):
        """Should initialize ExerciseCoach with correct domain"""
        coach = ExerciseCoach()
        
        assert coach.domain == "exercise_planning"
        mock_configure.assert_called_once()
    
    @patch.dict(os.environ, {'GEMINI_API_KEY': 'fake-key'})
    @patch('google.generativeai.configure')
    @patch('google.generativeai.GenerativeModel')
    def test_system_prompt_content(self, mock_model, mock_configure):
        """Should contain exercise-specific content in system prompt"""
        coach = ExerciseCoach()
        prompt = coach.get_system_prompt()
        
        assert "Exercise Coach" in prompt
        assert "workout planning" in prompt
        assert "fitness" in prompt
        assert "create_artifacts" in prompt
        assert "Exercise Planning" in prompt  # Check for capitalized version
    
    @patch.dict(os.environ, {'GEMINI_API_KEY': 'fake-key'})
    @patch('google.generativeai.configure')
    @patch('google.generativeai.GenerativeModel')
    def test_required_fields(self, mock_model, mock_configure):
        """Should return correct required fields"""
        coach = ExerciseCoach()
        required_fields = coach.get_required_fields()
        
        assert "goal" in required_fields
        assert "duration" in required_fields
        assert "fitness_level" in required_fields
        assert len(required_fields) == 3
    
    @patch.dict(os.environ, {'GEMINI_API_KEY': 'fake-key'})
    @patch('google.generativeai.configure')
    @patch('google.generativeai.GenerativeModel')
    def test_optional_fields(self, mock_model, mock_configure):
        """Should return correct optional fields"""
        coach = ExerciseCoach()
        optional_fields = coach.get_optional_fields()
        
        assert "equipment" in optional_fields
        assert "time_constraints" in optional_fields
        assert "workout_frequency" in optional_fields
        assert "injuries_limitations" in optional_fields
        assert "preferences" in optional_fields
        assert len(optional_fields) == 5
    
    @patch.dict(os.environ, {'GEMINI_API_KEY': 'fake-key'})
    @patch('google.generativeai.configure')
    @patch('google.generativeai.GenerativeModel')
    def test_specialist_tools(self, mock_model, mock_configure):
        """Should return exercise-specific tools"""
        coach = ExerciseCoach()
        specialist_tools = coach.get_specialist_tools()
        
        assert len(specialist_tools) == 2
        tool_names = [tool["name"] for tool in specialist_tools]
        
        assert "calculate_training_volume" in tool_names
        assert "suggest_exercise_alternatives" in tool_names
    
    @patch.dict(os.environ, {'GEMINI_API_KEY': 'fake-key'})
    @patch('google.generativeai.configure')
    @patch('google.generativeai.GenerativeModel')
    def test_tool_parameters(self, mock_model, mock_configure):
        """Should have correct parameters for specialist tools"""
        coach = ExerciseCoach()
        specialist_tools = coach.get_specialist_tools()
        
        # Test calculate_training_volume tool
        calc_tool = next(tool for tool in specialist_tools if tool["name"] == "calculate_training_volume")
        assert "goal" in calc_tool["parameters"]["properties"]
        assert "experience_level" in calc_tool["parameters"]["properties"]
        assert "available_time" in calc_tool["parameters"]["properties"]
        
        # Test suggest_exercise_alternatives tool
        suggest_tool = next(tool for tool in specialist_tools if tool["name"] == "suggest_exercise_alternatives")
        assert "original_exercise" in suggest_tool["parameters"]["properties"]
        assert "available_equipment" in suggest_tool["parameters"]["properties"]
        assert "limitations" in suggest_tool["parameters"]["properties"]
    
    @patch.dict(os.environ, {'GEMINI_API_KEY': 'fake-key'})
    @patch('google.generativeai.configure')
    @patch('google.generativeai.GenerativeModel')
    def test_all_tools_includes_shared_and_specialist(self, mock_model, mock_configure):
        """Should combine shared tools with exercise-specific tools"""
        coach = ExerciseCoach()
        all_tools = coach.get_all_tools()
        
        # Should have 3 shared + 2 specialist = 5 total tools
        assert len(all_tools) == 5
        
        tool_names = [tool["name"] for tool in all_tools]
        
        # Check shared tools
        assert "hand_off_to_triage_agent" in tool_names
        assert "create_artifacts" in tool_names
        assert "search_internet" in tool_names
        
        # Check specialist tools
        assert "calculate_training_volume" in tool_names
        assert "suggest_exercise_alternatives" in tool_names