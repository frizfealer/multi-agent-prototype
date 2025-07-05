"""
Unit tests for Orchestrator class
"""
import pytest
import os
import json
from unittest.mock import Mock, patch, AsyncMock
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.orchestrator import Orchestrator


class TestOrchestrator:
    """Should test Orchestrator functionality"""
    
    def setup_method(self):
        """Should set up test environment for each test"""
        with patch.dict(os.environ, {'GEMINI_API_KEY': 'fake-key'}), \
             patch('google.generativeai.configure'), \
             patch('google.generativeai.GenerativeModel'):
            self.orchestrator = Orchestrator()
    
    def test_initialization(self):
        """Should initialize with agent registry and template manager"""
        assert "triage" in self.orchestrator.agents
        assert "exercise_coach" in self.orchestrator.agents
        assert "nutrition_coach" in self.orchestrator.agents
        assert hasattr(self.orchestrator, 'coach_template_manager')
    
    @patch.dict(os.environ, {'GEMINI_API_KEY': 'fake-key'})
    @patch('google.generativeai.configure')
    @patch('google.generativeai.GenerativeModel')
    def test_get_static_agent(self, mock_model, mock_configure):
        """Should retrieve static agents from registry"""
        triage_agent = self.orchestrator.get_agent_for_conversation("triage")
        assert triage_agent is not None
        
        exercise_agent = self.orchestrator.get_agent_for_conversation("exercise_coach")
        assert exercise_agent is not None
    
    def test_get_dynamic_agent(self):
        """Should create dynamic agents for composite names"""
        multi_agent = self.orchestrator.get_agent_for_conversation("exercise_coach+nutrition_coach")
        assert multi_agent is not None
        assert multi_agent.domain == "exercise_coach+nutrition_coach"
    
    def test_get_unknown_agent(self):
        """Should return None for unknown agent names"""
        unknown_agent = self.orchestrator.get_agent_for_conversation("unknown_agent")
        assert unknown_agent is None
    
    @patch('src.state_manager.add_message')
    @patch('src.state_manager.get_conversation_state')
    def test_handle_message_with_static_agent(self, mock_get_state, mock_add_message):
        """Should handle messages with static agents"""
        # Mock conversation state
        mock_get_state.return_value = {
            "current_agent": "triage",
            "context_data": {},
            "history": [{"role": "user", "content": "Hello"}]
        }
        
        # Mock agent response
        mock_agent = Mock()
        mock_agent.process_request = AsyncMock(return_value={
            "name": "respond_directly",
            "arguments": '{"text": "Hello there!"}'
        })
        self.orchestrator.agents["triage"] = mock_agent
        
        import asyncio
        result = asyncio.run(self.orchestrator.handle_message("test-conv-id", "Hello"))
        
        assert "response" in result
        assert result["response"] == "Hello there!"
        mock_add_message.assert_called()
    
    @patch('src.state_manager.add_message')
    @patch('src.state_manager.update_conversation_state')
    def test_execute_hand_off_to_experts(self, mock_update_state, mock_add_message):
        """Should handle hand_off_to_experts action"""
        action = {
            "name": "hand_off_to_experts",
            "arguments": '["exercise_coach", "nutrition_coach"]'
        }
        
        result = self.orchestrator.execute_action("test-conv-id", action, "triage")
        
        assert "response" in result
        assert "Exercise" in result["response"]
        assert "Nutrition" in result["response"]
        mock_update_state.assert_called_with("test-conv-id", current_agent="exercise_coach+nutrition_coach")
    
    @patch('src.state_manager.add_message')
    @patch('src.state_manager.update_conversation_state')
    def test_execute_hand_off_to_triage_agent(self, mock_update_state, mock_add_message):
        """Should handle hand_off_to_triage_agent action"""
        action = {
            "name": "hand_off_to_triage_agent",
            "arguments": '{}'
        }
        
        result = self.orchestrator.execute_action("test-conv-id", action, "exercise_coach")
        
        assert "response" in result
        assert "main assistant" in result["response"]
        mock_update_state.assert_called_with("test-conv-id", current_agent="triage")
    
    @patch('src.state_manager.add_message')
    @patch('src.state_manager.create_task')
    def test_execute_create_artifacts(self, mock_create_task, mock_add_message):
        """Should handle create_artifacts action"""
        action = {
            "name": "create_artifacts",
            "arguments": json.dumps({
                "domain": "exercise_planning",
                "data": {"goal": "muscle building", "duration": "12 weeks"}
            })
        }
        
        result = self.orchestrator.execute_action("test-conv-id", action, "exercise_coach")
        
        assert "response" in result
        assert "exercise planning" in result["response"]
        assert "start_tasks" in result["response"]
        mock_create_task.assert_called_once()
        
        # Check task creation arguments
        task_arg = mock_create_task.call_args[0][0]
        assert task_arg["domain"] == "exercise_planning"
        assert task_arg["conversation_id"] == "test-conv-id"
        assert task_arg["status"] == "pending"
    
    @patch('src.state_manager.add_message')
    def test_execute_search_internet(self, mock_add_message):
        """Should handle search_internet action"""
        action = {
            "name": "search_internet",
            "arguments": '{"query": "best exercises for beginners"}'
        }
        
        result = self.orchestrator.execute_action("test-conv-id", action, "exercise_coach")
        
        assert "response" in result
        assert "search" in result["response"].lower()
        assert "best exercises for beginners" in result["response"]
    
    @patch('src.state_manager.add_message')
    def test_execute_respond_directly(self, mock_add_message):
        """Should handle respond_directly action"""
        action = {
            "name": "respond_directly",
            "arguments": '{"text": "Here is my direct response"}'
        }
        
        result = self.orchestrator.execute_action("test-conv-id", action, "exercise_coach")
        
        assert "response" in result
        assert result["response"] == "Here is my direct response"
        mock_add_message.assert_called_with("test-conv-id", "model", "Here is my direct response", agent="exercise_coach")
    
    def test_execute_unknown_action(self):
        """Should handle unknown actions gracefully"""
        action = {
            "name": "unknown_action",
            "arguments": '{}'
        }
        
        result = self.orchestrator.execute_action("test-conv-id", action, "exercise_coach")
        
        assert "error" in result
        assert "Unknown action" in result["error"]
    
    def test_execute_create_artifacts_missing_data(self):
        """Should handle create_artifacts with missing required data"""
        action = {
            "name": "create_artifacts",
            "arguments": '{"domain": "exercise_planning"}'  # Missing data
        }
        
        result = self.orchestrator.execute_action("test-conv-id", action, "exercise_coach")
        
        assert "error" in result
        assert "Domain and data are required" in result["error"]
    
    def test_execute_search_internet_missing_query(self):
        """Should handle search_internet with missing query"""
        action = {
            "name": "search_internet",
            "arguments": '{}'  # Missing query
        }
        
        result = self.orchestrator.execute_action("test-conv-id", action, "exercise_coach")
        
        assert "error" in result
        assert "Query is required" in result["error"]
    
    def test_hand_off_to_experts_single_coach(self):
        """Should handle handoff to single coach correctly"""
        action = {
            "name": "hand_off_to_experts",
            "arguments": '["exercise_coach"]'
        }
        
        with patch('src.state_manager.add_message'), patch('src.state_manager.update_conversation_state') as mock_update:
            result = self.orchestrator.execute_action("test-conv-id", action, "triage")
            
            assert "Exercise" in result["response"]
            assert "and" not in result["response"]  # Should not use "and" for single coach
            mock_update.assert_called_with("test-conv-id", current_agent="exercise_coach")
    
    def test_hand_off_to_experts_empty_list(self):
        """Should handle handoff with empty expert list"""
        action = {
            "name": "hand_off_to_experts",
            "arguments": '[]'
        }
        
        result = self.orchestrator.execute_action("test-conv-id", action, "triage")
        
        assert "error" in result
        assert "No expert specified" in result["error"]