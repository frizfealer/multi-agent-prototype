"""
Unit tests for StateManager functions
"""
import pytest
import json
import uuid
from unittest.mock import Mock, patch
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.state_manager import (
    create_task,
    get_pending_tasks_by_conversation,
    start_tasks
)


class TestStateManager:
    """Should test StateManager database functions"""
    
    def test_create_task_structure(self):
        """Should create task with correct structure"""
        with patch('src.state_manager.get_db_connection') as mock_conn:
            mock_cursor = Mock()
            mock_conn.return_value.cursor.return_value = mock_cursor
            
            task_dict = {
                "task_id": "test-task-id",
                "conversation_id": "test-conv-id",
                "domain": "exercise_planning",
                "goal": "create_exercise_plan",
                "context": {"goal": "muscle building"},
                "status": "pending"
            }
            
            result = create_task(task_dict)
            
            # Should return the task_id
            assert result == "test-task-id"
            
            # Should call execute with correct parameters
            mock_cursor.execute.assert_called_once()
            execute_args = mock_cursor.execute.call_args[0]
            
            # Check SQL structure
            assert "INSERT INTO Task" in execute_args[0]
            assert "task_id" in execute_args[0]
            assert "conversation_id" in execute_args[0]
            assert "goal" in execute_args[0]
            assert "domain" in execute_args[0]
            assert "task_status" in execute_args[0]
            assert "context" in execute_args[0]
    
    def test_create_task_with_defaults(self):
        """Should use defaults for missing optional fields"""
        with patch('src.state_manager.get_db_connection') as mock_conn, \
             patch('uuid.uuid4') as mock_uuid:
            
            mock_cursor = Mock()
            mock_conn.return_value.cursor.return_value = mock_cursor
            mock_uuid.return_value = "generated-uuid"
            
            # Minimal task dict
            task_dict = {
                "conversation_id": "test-conv-id",
                "domain": "exercise_planning",
                "goal": "create_exercise_plan"
            }
            
            result = create_task(task_dict)
            
            # Should generate UUID and use default status
            assert result == "generated-uuid"
            
            execute_args = mock_cursor.execute.call_args[0][1]
            assert execute_args[0] == "generated-uuid"  # task_id
            assert execute_args[4] == "pending"  # status
            assert execute_args[5] == "{}"  # context as JSON
    
    def test_start_tasks_all_pending(self):
        """Should start all pending tasks when no task_ids specified"""
        with patch('src.state_manager.get_db_connection') as mock_conn:
            mock_cursor = Mock()
            mock_cursor.rowcount = 3  # 3 tasks affected
            mock_conn.return_value.cursor.return_value = mock_cursor
            
            result = start_tasks("test-conv-id")
            
            assert result == 3
            
            # Should update all pending tasks
            mock_cursor.execute.assert_called_once()
            execute_args = mock_cursor.execute.call_args[0]
            
            assert "UPDATE Task SET task_status = 'in_progress'" in execute_args[0]
            assert "task_status = 'pending'" in execute_args[0]
            assert execute_args[1] == ("test-conv-id",)
    
    def test_start_tasks_specific_ids(self):
        """Should start only specified task_ids"""
        with patch('src.state_manager.get_db_connection') as mock_conn:
            mock_cursor = Mock()
            mock_cursor.rowcount = 2  # 2 tasks affected
            mock_conn.return_value.cursor.return_value = mock_cursor
            
            task_ids = ["task-1", "task-2"]
            result = start_tasks("test-conv-id", task_ids)
            
            assert result == 2
            
            # Should update specific tasks
            mock_cursor.execute.assert_called_once()
            execute_args = mock_cursor.execute.call_args[0]
            
            assert "task_id IN" in execute_args[0]
            assert "%s,%s" in execute_args[0]
            assert execute_args[1] == ["test-conv-id", "task-1", "task-2"]
    
    def test_get_pending_tasks_structure(self):
        """Should retrieve and structure pending tasks correctly"""
        with patch('src.state_manager.get_db_connection') as mock_conn:
            mock_cursor = Mock()
            mock_conn.return_value.cursor.return_value = mock_cursor
            
            # Mock database response
            mock_cursor.fetchall.return_value = [
                (
                    "task-1",  # task_id
                    "create_exercise_plan",  # goal
                    "exercise_planning",  # domain
                    "pending",  # task_status
                    '{"goal": "muscle building"}',  # context (JSON string)
                    None,  # result
                    "2024-01-01 10:00:00",  # created_at
                    "2024-01-01 10:00:00"   # updated_at
                ),
                (
                    "task-2",
                    "create_nutrition_plan",
                    "nutrition_planning", 
                    "pending",
                    '{"goal": "weight loss"}',
                    None,
                    "2024-01-01 10:05:00",
                    "2024-01-01 10:05:00"
                )
            ]
            
            result = get_pending_tasks_by_conversation("test-conv-id")
            
            assert len(result) == 2
            
            # Check first task structure
            task1 = result[0]
            assert task1["task_id"] == "task-1"
            assert task1["goal"] == "create_exercise_plan"
            assert task1["domain"] == "exercise_planning"
            assert task1["task_status"] == "pending"
            assert task1["context"] == {"goal": "muscle building"}  # Should be parsed JSON
            
            # Check second task
            task2 = result[1]
            assert task2["task_id"] == "task-2"
            assert task2["context"] == {"goal": "weight loss"}
    
    def test_get_pending_tasks_empty_context(self):
        """Should handle empty or null context gracefully"""
        with patch('src.state_manager.get_db_connection') as mock_conn:
            mock_cursor = Mock()
            mock_conn.return_value.cursor.return_value = mock_cursor
            
            # Mock task with null context
            mock_cursor.fetchall.return_value = [
                (
                    "task-1",
                    "create_exercise_plan",
                    "exercise_planning",
                    "pending",
                    None,  # null context
                    None,
                    "2024-01-01 10:00:00",
                    "2024-01-01 10:00:00"
                )
            ]
            
            result = get_pending_tasks_by_conversation("test-conv-id")
            
            assert len(result) == 1
            assert result[0]["context"] == {}  # Should default to empty dict
    
    def test_get_pending_tasks_query_structure(self):
        """Should query only pending tasks for specific conversation"""
        with patch('src.state_manager.get_db_connection') as mock_conn:
            mock_cursor = Mock()
            mock_cursor.fetchall.return_value = []
            mock_conn.return_value.cursor.return_value = mock_cursor
            
            get_pending_tasks_by_conversation("test-conv-id")
            
            # Check SQL query structure
            mock_cursor.execute.assert_called_once()
            execute_args = mock_cursor.execute.call_args[0]
            
            assert "SELECT" in execute_args[0]
            assert "FROM Task" in execute_args[0]
            assert "WHERE conversation_id = %s" in execute_args[0]
            assert "task_status = 'pending'" in execute_args[0]
            assert "ORDER BY created_at ASC" in execute_args[0]
            assert execute_args[1] == ("test-conv-id",)