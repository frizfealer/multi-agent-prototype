import json
from typing import Dict, List, Optional

import google.generativeai as genai
from google.generativeai.types import FunctionDeclaration, Tool

from src.core.state_manager import StateManager


class TriageAgent:
    def __init__(self, api_key: str, state_manager: StateManager):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            model_name="gemini-1.5-pro",
            tools=[self._create_tools()],
            system_instruction=self._get_system_prompt()
        )
        self.state_manager = state_manager

    def _get_system_prompt(self) -> str:
        return """You are an expert Intent Classification and Routing Agent. Your primary role is to analyze a user's chat history to determine their intent and gather just enough information to either fulfill the request directly or determine that the request requires handoff to one or more specialist agents.

Intent & Action Flow:
1. Analyze History: Review the conversation to understand the user's goal.
2. Classify Intent: Determine if the request is a Direct Request (e.g., delete an item, ask a simple question) or a Complex Task (e.g., create a new plan).
3. Decide Next Action:
   - For Direct Requests: Gather any necessary details and then call the execute_direct_request function with the required arguments.
   - For Complex Tasks: Gather only the most critical, high-level information (e.g., "what kind of plan?") and then call the handoff_to_coach function, specifying which specialist(s) are needed in the coach_names list.
   - If more info is needed for any request: Call the ask_question function with the clarifying question for the user.

Available specialists:
- exercise_coach: For workout plans, fitness goals, exercise routines
- nutrition_coach: For diet plans, meal planning, nutritional advice
- wellness_coach: For general health, sleep, stress management
- recovery_coach: For injury recovery, rest days, rehabilitation"""

    def _create_tools(self) -> Tool:
        handoff_to_coach = FunctionDeclaration(
            name="handoff_to_coach",
            description="Hand off the conversation to one or more specialist coaches",
            parameters={
                "type": "object",
                "properties": {
                    "coach_names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of coach names to hand off to (e.g., ['exercise_coach', 'nutrition_coach'])"
                    }
                },
                "required": ["coach_names"]
            }
        )

        execute_direct_request = FunctionDeclaration(
            name="execute_direct_request",
            description="Execute a simple, direct request that doesn't require specialist knowledge",
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "description": "The action to perform (e.g., 'delete', 'list', 'update')"
                    },
                    "context": {
                        "type": "object",
                        "description": "Additional context needed to execute the action"
                    }
                },
                "required": ["action", "context"]
            }
        )

        ask_question = FunctionDeclaration(
            name="ask_question",
            description="Ask the user a clarifying question to gather more information",
            parameters={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The question to ask the user"
                    }
                },
                "required": ["question"]
            }
        )

        return Tool(function_declarations=[handoff_to_coach, execute_direct_request, ask_question])

    async def process_message(
        self, conversation_history: List[Dict[str, str]], user_message: str
    ) -> Dict:
        """Process a user message and return the agent's decision."""
        
        # Build chat history for Gemini
        chat = self.model.start_chat(history=[])
        
        # Add conversation history
        for msg in conversation_history:
            if msg["role"] == "user":
                chat.send_message(msg["content"])
            elif msg["role"] == "assistant":
                # For assistant messages, we need to reconstruct them
                # This is a simplified approach - in production you'd store function calls
                chat.send_message(msg["content"])
        
        # Send new user message
        response = chat.send_message(user_message)
        
        # Parse response
        result = {
            "text_response": None,
            "function_call": None
        }
        
        # Check for function calls
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'function_call'):
                    function_call = part.function_call
                    result["function_call"] = {
                        "name": function_call.name,
                        "args": dict(function_call.args)
                    }
                elif hasattr(part, 'text'):
                    result["text_response"] = part.text
        
        return result