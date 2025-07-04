"""
Base Coach class providing shared functionality for all specialist coaches.
"""

import json
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from dotenv import load_dotenv
from google import genai
from google.genai import types

from src.agents.shared_tools import (
    create_artifacts,
    hand_off_to_triage_agent,
    search_internet,
)

load_dotenv()

MODEL_CLIENT = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL_NAME = "gemini-2.0-flash-exp"


def convert_to_gemini_message(messages: List[Dict[str, str]]) -> List[types.Content]:
    """Convert messages to Gemini format.

    Args:
        messages: List of message dictionaries with 'role' and 'content'

    Returns:
        List of Gemini Content objects
    """
    gemini_messages = []
    for msg in messages:
        # Skip system messages as they're handled in the config
        if msg["role"] == "system":
            continue
        # Map roles appropriately
        role = "user" if msg["role"] == "user" else "model"
        gemini_messages.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))
    return gemini_messages


class BaseCoach(ABC):
    """Abstract base class for all specialist coaches."""

    def __init__(self, domain: str):
        self.domain = domain

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Return the system prompt for this coach."""
        pass

    @abstractmethod
    def get_required_fields(self) -> List[str]:
        """Return the required fields this coach needs to gather."""
        pass

    @abstractmethod
    def get_optional_fields(self) -> List[str]:
        """Return the optional fields this coach can gather."""
        pass

    def get_shared_tools(self) -> List[Any]:
        """Return shared tool functions available to all coaches."""
        return [
            hand_off_to_triage_agent,
            create_artifacts,
            search_internet,
        ]

    def get_specialist_tools(self) -> List[Any]:
        """Return specialist tool functions specific to this coach. Override in subclasses."""
        return []

    def get_all_tools(self) -> List[Any]:
        """Return all tool functions available to this coach."""
        return self.get_shared_tools() + self.get_specialist_tools()

    async def process_request(self, conversation_history: List[Dict[str, str]]) -> Dict[str, Any]:
        """Process a request and return an action.

        Args:
            conversation_history: List of conversation messages

        Returns:
            Action dictionary with 'name' and 'arguments' keys
        """
        try:
            # Convert messages to Gemini format
            contents = convert_to_gemini_message(conversation_history)

            # Create config with tools and system instruction
            config = types.GenerateContentConfig(
                tools=self.get_all_tools(),
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                system_instruction=self.get_system_prompt(),
            )

            # Generate response
            response = await MODEL_CLIENT.aio.models.generate_content(
                model=MODEL_NAME,
                contents=contents,
                config=config,
            )
            # Check if there are function calls
            if response.function_calls:
                function_call = response.function_calls[0]

                if function_call.name == "hand_off_to_triage_agent" or function_call.name == "create_artifacts":
                    return {
                        "name": function_call.name,
                        "arguments": function_call.args,
                    }
                elif function_call.name == "search_internet":
                    result = search_internet(query_prompt=function_call.args["query_prompt"])
                    return {"name": "respond_directly", "arguments": json.dumps({"text": result})}
                else:
                    # For other functions (like calculate_training_volume, suggest_exercise_alternatives, search_internet)
                    # Execute them and pass the result back to the LLM for a final response
                    function_name = function_call.name
                    function_args = function_call.args

                    # Find and execute the function
                    all_tools = self.get_all_tools()
                    for tool_func in all_tools:
                        if tool_func.__name__ == function_name:
                            try:
                                # Execute the function with the provided arguments
                                result = tool_func(**function_args)

                                # Create function response part
                                function_response_part = types.Part.from_function_response(
                                    name=function_call.name,
                                    response={"result": result},
                                )

                                # Append function call and result to contents
                                contents.append(response.candidates[0].content)  # Append the model's function call
                                contents.append(
                                    types.Content(role="user", parts=[function_response_part])
                                )  # Append the function response

                                # Generate final response with the function result
                                response = await MODEL_CLIENT.aio.models.generate_content(
                                    model=MODEL_NAME,
                                    contents=contents,
                                    config=config,
                                )

                                import pdb

                                pdb.set_trace()

                                return {"name": "respond_directly", "arguments": json.dumps({"text": response.text})}

                            except Exception as func_error:
                                return {
                                    "name": "respond_directly",
                                    "arguments": json.dumps(
                                        {
                                            "text": f"I encountered an error executing {function_name}: {str(func_error)}"
                                        }
                                    ),
                                }

                    # If function not found, return error
                    return {
                        "name": "respond_directly",
                        "arguments": json.dumps({"text": f"Unknown function: {function_name}"}),
                    }
            else:
                # If no function call, return the text as a direct response
                return {"name": "respond_directly", "arguments": json.dumps({"text": response.text})}

        except Exception as e:
            # Fallback to direct response
            return {
                "name": "respond_directly",
                "arguments": json.dumps(
                    {"text": f"I encountered an error: {str(e)}. Could you please rephrase your request?"}
                ),
            }
