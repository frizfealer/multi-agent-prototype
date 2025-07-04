import json
import os
from enum import Enum
from typing import List

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

MODEL_CLIENT = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
MODEL_NAME = "gemini-2.5-flash"

TRIAGE_AGENT_SYSTEM_PROMPT = """
As a helpful AI assistant, your primary goal is to fulfill the user's request. You have access to a team of experts for specialized topics. 
You should analyze user messages and chat history to determine their intent, and route them to the appropriate experts. If the intent is unclear or falls outside available expertise, engage with the user or resolve it yourself.
If there is no available expert for the intent, you should use your own knowledge to address the user's request directly. This includes generating detailed plans, writing code, or providing comprehensive explanations if you are capable of doing so. 
For example, if a user asks for a study plan, you should create one for them.

- **Intent Identification**: Identify the user's intent from chat messages and determine if it can be handled by available coaches.
- **Routing to experts**: If the intent matches available expert(s), use the `hand_off` function to route the user to the correct expert(s).
- **Clarification**: If intent is unclear, ask the user for clarification.
- **Handling Non-Routeable Intents**: If no coach is available for the identified intent and you have the capability, attempt to fulfill the user's request yourself.

# Steps

1. **Analyze User Messages**: Read through the user's messages to understand their main intent.
2. **Match with Available Coaches**: Compare the user's intent with the expertise of available coaches.
3. **Route if Match Found**: Use `hand_off(experts = [appropriate_experts])` if a match is found.
4. **Seek Clarification**: If the intent is unclear, formulate a question for further clarification.
5. **Self-Handle**: If no suitable coach is available, first show the user that you don't have an expert for that intent. 
    Then you should address the user's request directly by providing some general information/suggestions/plans/etc.

# Output Format

- **Intent Analysis Outcome**: A brief description of the user's intent.
- **Resulting Action**: A function call `hand_off(experts = [appropriate_experts])`, a clarification question, or a direct response to the user.

# Examples

**Example 1**

- **Input**: "I want to make an exercise plan."
- **Output**: `hand_off(experts = [exercise_expert])`

**Example 2** Assume we have a nutrition expert.

- **Input**: "Can you help me figure out how to lose weight effectively?"
- **Output**: `hand_off(experts = [nutrition_expert])`

**Example 3 The available experts are exercise_expert and nutrition_expert**
- **Input**: "I am thinking of visiting Paris for three days. What should I do there?"
(function call get_available_experts -> returns [exercise_expert, nutrition_expert])
- **Output**: "While I don't have an expert for this, I can suggest some popular attractions in Paris."

**Example 4**

- **Input**: "I need advice on something."
- **Output**: "Could you please provide more details about what you need advice on?"

# Notes

- Only use the `hand_off` function if there is a matching available coach.
- If fulfilling a request directly, ensure accuracy and relevance to the user's context.
- Maintain a user-friendly and engaging tone when asking clarification questions.
"""


class Experts(Enum):
    EXERCISE_EXPERT = "exercise_expert"
    # NUTRITION_EXPERT = "nutrition_expert"


def hand_off_to_experts(experts: List[str]) -> dict:
    """Hand off the conversation to the appropriate expert(s).

    Args:
        experts: The set of the experts to hand off to. Valid values are:
                 - "exercise_expert": For fitness and workout related queries

    Returns:
        None
    """


def get_available_experts() -> List[str]:
    """Get the list of available experts."""
    return [expert.value for expert in Experts]


def convert_to_gemini_message(messages: List[dict]) -> List[types.Content]:
    """Converts a message to a Gemini message.

    Args:
        message: The message to convert.

    Returns:
        A Gemini
    """
    return [types.Content(role=msg["role"], parts=[types.Part(text=msg["content"])]) for msg in messages]


class TriageAgent:
    def __init__(self):
        pass

    async def process_request(self, conversation_history: List[dict]):
        """
        Processes the user request using the LLM and returns the function call.
        """
        try:
            contents = convert_to_gemini_message(conversation_history)
            config = types.GenerateContentConfig(
                tools=[get_available_experts, hand_off_to_experts],
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                system_instruction=TRIAGE_AGENT_SYSTEM_PROMPT,
            )
            response = await MODEL_CLIENT.aio.models.generate_content(
                model=MODEL_NAME,
                contents=contents,
                config=config,
            )
            # Check if there are function calls
            if response.function_calls:
                function_call = response.function_calls[0]
                if function_call.name == "hand_off_to_experts":
                    return {"name": function_call.name, "arguments": function_call.args["experts"]}
                elif function_call.name == "get_available_experts":
                    result = get_available_experts(**function_call.args)
                    function_response_part = types.Part.from_function_response(
                        name=function_call.name,
                        response={"result": result},
                    )
                    # Append function call and result of the function execution to contents
                    contents.append(response.candidates[0].content)  # Append the content from the model's response.
                    contents.append(
                        types.Content(role="user", parts=[function_response_part])
                    )  # Append the function response
                    response = await MODEL_CLIENT.aio.models.generate_content(
                        model=MODEL_NAME,
                        contents=contents,
                        config=config,
                    )
                    return {"name": "respond_directly", "arguments": json.dumps({"text": response.text})}
            else:
                # If no function call, return the text as a direct response
                return {"name": "respond_directly", "arguments": json.dumps({"text": response.text})}

        except Exception as e:
            print(f"Error processing request: {e}")
            return None
