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
from src.agents.utils import convert_to_gemini_message, is_function_terminal
from src.logging_config import get_logger

load_dotenv()
logger = get_logger(__name__)
MODEL_CLIENT = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL_NAME = "gemini-2.5-flash"


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
            while response.function_calls:
                function_response_parts = []
                try:
                    for function_call in response.function_calls:
                        target_func = [
                            tool_func for tool_func in self.get_all_tools() if tool_func.__name__ == function_call.name
                        ][0]
                        if is_function_terminal(target_func):
                            logger.info(f"Model called terminal function: {function_call.name}")
                            if function_call.name == "search_internet":
                                result = search_internet(query_prompt=function_call.args["query_prompt"])
                                return {"name": "respond_directly", "arguments": json.dumps({"text": result})}
                            else:  # hand_off_to_triage_agent and create_artifacts are terminal functions
                                return {"name": function_call.name, "arguments": json.dumps(function_call.args)}
                        result = target_func(**function_call.args)
                        logger.debug(
                            f"Calling function {function_call.name} with args {function_call.args} and result {result}"
                        )
                        function_response_parts.append(
                            types.Part.from_function_response(
                                name=function_call.name,
                                response={"result": result},
                            )
                        )
                        # Append function call and result of the function execution to contents
                        contents.append(
                            response.candidates[0].content
                        )  # Append the content from the model's response.
                        contents.append(
                            types.Content(role="user", parts=function_response_parts)
                        )  # Append the function response
                        logger.info("Sending follow-up request after get_available_experts")
                        response = await MODEL_CLIENT.aio.models.generate_content(
                            model=MODEL_NAME,
                            contents=contents,
                            config=config,
                        )
                except Exception as e:
                    logger.error(f"Error processing request: {e}", exc_info=True)
                    return {
                        "name": "respond_directly",
                        "arguments": json.dumps(
                            {"text": f"I encountered an error: {str(e)}. Could you please rephrase your request?"}
                        ),
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
