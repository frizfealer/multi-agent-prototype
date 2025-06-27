"""
InteractionAgent Implementation

This module provides an InteractionAgent that directly uses LLM to classify user intents
and generate appropriate responses in JSON format with query and update_request fields.
"""

import asyncio
import json
import os
from typing import Any, Dict, Optional

from google import genai
from google.genai import types


class InteractionAgent:
    """
    Direct LLM-based interaction agent that classifies intents and generates responses.
    Returns structured JSON responses with intent classification and routing fields.
    """

    def __init__(self, project_id: str, location: str = "us-central1"):
        """
        Initialize the InteractionAgent with Google Gen AI SDK

        Args:
            project_id: Google Cloud project ID
            location: Google Cloud location (default: us-central1)
        """
        # Set up environment variables for Vertex AI
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "true"
        os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
        os.environ["GOOGLE_CLOUD_LOCATION"] = location

        # Initialize the client with Vertex AI
        self.client = genai.Client(vertexai=True, project=project_id, location=location)

        self.model = "gemini-2.5-flash"

    async def process_user_input(
        self, user_input: str, session_id: str, current_state: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process user input and return structured JSON response with intent classification and routing

        Args:
            user_input: The user's message
            session_id: Session identifier
            current_state: Current workflow state (optional, used only for query responses)

        Returns:
            Dict containing response, intent, query, and update_request fields
        """

        # Create the prompt for intent classification and response generation
        prompt = f"""
You are an InteractionAgent, like a senior assistant for a user. Analyze the user input and provide a structured response.

User Input: "{user_input}"

intent classification Rules:
1. "exercise_planning" - make/modify/discuss exercise plans based on user requirements.
2. "social_interaction" - Greetings, thanks, casual conversation  
3. "information_request" - General questions that required definitive answers.
4. "creative_generation" - Requests for creative content, stories, etc. 
5. "other" - Other intents that are not covered by the above categories.

Response Rules:
- If intent is NOT "exercise_planning", respond with: "Sorry we are not supporting this [intent]"
- If intent is "exercise_planning", determine if it's a QUERY or UPDATE_REQUEST:
  
  QUERY examples (answer directly using current state):
  - "What's my current plan?"
  - "Show me my exercise plan"
  - "What's the status?"
  - "How many days per week?"
  - "What exercises are included?"
  
  UPDATE_REQUEST examples (needs workflow processing):
  - "Change to 4 days per week"
  - "Add chest exercises"
  - "Make it shorter"
  - "Use only dumbbells"
  - "I want to focus on arms instead"
  - "Create a workout plan for me"

Field Instructions:
- "query": Set to the user's question if they want information about current state (can be null)
- "update_request": Set to the user's change request if they want to modify requirements (can be null)
- "response": Your direct response to the user
- "intent": The classified intent

If query is not null: Set response to "Query will be answered using current state"
If update_request is not null: Set response to "Update request will be processed through workflow"

Respond in this EXACT JSON format:
{{
    "response": "Your response message here",
    "intent": "planning|social_interaction|information_request|creative_generation",
    "query": "user's question or null",
    "update_request": "user's change request or null"
}}
"""

        try:
            # Generate response using Gemini 2.5 Flash
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.3, max_output_tokens=800, top_p=0.95),
            )

            # Parse the JSON response
            response_text = response.text.strip()

            # Handle potential markdown code blocks
            if response_text.startswith("```json"):
                response_text = response_text.replace("```json", "").replace("```", "").strip()
            elif response_text.startswith("```"):
                response_text = response_text.replace("```", "").strip()

            result = json.loads(response_text)

            # Validate required fields
            required_fields = ["response", "intent", "query", "update_request"]
            for field in required_fields:
                if field not in result:
                    result[field] = None

            # Validate intent enum
            valid_intents = ["planning", "social_interaction", "information_request", "creative_generation"]
            if result["intent"] not in valid_intents:
                raise ValueError(f"Invalid intent: {result['intent']}")

            # Post-process the response if it's a planning query and we have state
            if result["intent"] == "planning" and result["query"] and current_state:
                # Generate a detailed response for planning queries using state
                detailed_response = await self.generate_detailed_query_response(result["query"], current_state)
                result["response"] = detailed_response

            # For non-planning intents, format the response correctly
            if result["intent"] != "planning":
                result["response"] = f"Sorry we are not supporting this {result['intent']}"

            # Add metadata
            result["session_id"] = session_id
            result["model"] = self.model
            result["processing_type"] = "llm_direct"

            return result

        except json.JSONDecodeError as e:
            print(f"Error parsing JSON response: {e}")
            print(f"Raw response: {response_text}")
            return {
                "response": "I'm having trouble understanding your request. Could you please rephrase?",
                "intent": "social_interaction",
                "query": None,
                "update_request": None,
                "session_id": session_id,
                "model": self.model,
                "processing_type": "error_fallback",
                "error": str(e),
            }

        except Exception as e:
            print(f"Error in InteractionAgent processing: {e}")
            return {
                "response": "I encountered an error processing your request. Please try again.",
                "intent": "social_interaction",
                "query": None,
                "update_request": None,
                "session_id": session_id,
                "model": self.model,
                "processing_type": "error_fallback",
                "error": str(e),
            }

    async def generate_detailed_query_response(self, query: str, current_state: Dict[str, Any]) -> str:
        """
        Generate detailed response for planning queries using current state

        Args:
            query: User's query
            current_state: Current workflow state

        Returns:
            Detailed response based on current state
        """
        workflow_status = current_state.get("workflow_status", "unknown")
        final_plan = current_state.get("final_plan")
        requirements_count = len(current_state.get("requirements_history", []))
        current_request = current_state.get("user_request", "")

        # Handle different workflow states
        if not final_plan:
            if workflow_status == "not_started":
                return "I haven't started working on your exercise plan yet. Please provide your requirements first."
            elif workflow_status == "planning":
                return "I'm currently planning your exercise routine. This should take just a moment..."
            elif workflow_status == "searching":
                return "I'm searching for the best exercises and schedules for your needs..."
            elif workflow_status == "summarizing":
                return "I'm putting together your personalized exercise plan..."
            elif workflow_status == "re_evaluating":
                return "I'm analyzing your updated requirements and adjusting the plan..."
            else:
                return f"I'm working on your exercise plan. Current status: {workflow_status}. Please wait a moment..."

        # Plan is ready - use LLM to answer specific questions
        prompt = f"""
        Based on this exercise plan and user requirements, answer the specific question:
        
        Exercise Plan:
        {final_plan}
        
        User Requirements:
        {current_request}
        
        Requirements History Count: {requirements_count}
        
        User Question: {query}
        
        Provide a direct, helpful answer based on the plan content. If asking for the full plan, include it.
        If asking for status, mention it's complete and ready.
        If the question can't be answered from the plan, say so politely.
        """

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(temperature=0.3, max_output_tokens=1000, top_p=0.95),
            )
            return response.text.strip()
        except Exception:
            return "I have your exercise plan ready, but I'm having trouble answering that specific question right now. Your plan is complete and ready to view."


# State accessor for getting current workflow state
class StateAccessor:
    """Provides atomic access to workflow state"""

    def __init__(self, workflow_app, active_workflows: Dict[str, dict]):
        self.workflow_app = workflow_app
        self.active_workflows = active_workflows

    def get_current_state(self, session_id: str) -> Dict[str, Any]:
        """Get current state atomically using LangGraph's built-in thread safety"""
        config = {"configurable": {"thread_id": session_id}}

        try:
            # Use LangGraph's atomic state access
            state_snapshot = self.workflow_app.get_state(config)

            if state_snapshot and state_snapshot.values:
                return state_snapshot.values
            else:
                # No state exists yet or check active workflows
                if session_id in self.active_workflows:
                    return self.active_workflows[session_id].get(
                        "last_state",
                        {
                            "session_id": session_id,
                            "workflow_status": "not_started",
                            "final_plan": None,
                            "exercise_results": None,
                            "requirements_history": [],
                            "user_request": None,
                        },
                    )
                else:
                    return {
                        "session_id": session_id,
                        "workflow_status": "not_started",
                        "final_plan": None,
                        "exercise_results": None,
                        "requirements_history": [],
                        "user_request": None,
                    }

        except Exception as e:
            print(f"Error accessing state for session {session_id}: {e}")
            return {"session_id": session_id, "workflow_status": "error", "error": str(e)}


# Example usage and testing functions
async def test_interaction_agent():
    """Test function for the InteractionAgent"""

    # You would need to set your actual project ID
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "your-project-id")

    agent = InteractionAgent(project_id)

    # Test cases with different intents
    test_cases = [
        ("Hello there!", None),
        (
            "What's my current exercise plan?",
            {
                "workflow_status": "completed",
                "final_plan": "Day 1: Chest and Triceps\n- Bench Press: 3x8-10\n- Incline Dumbbell Press: 3x10-12",
                "requirements_history": ["I want to build muscle"],
                "user_request": "I want to build muscle",
            },
        ),
        ("Change my workout to 4 days per week", None),
        ("Tell me a joke", None),
        ("What's the weather like?", None),
        ("Create a workout plan for me", None),
    ]

    for test_input, state in test_cases:
        print(f"\nTesting: '{test_input}'")
        result = await agent.process_user_input(test_input, "test_session", state)
        print(f"Response: {json.dumps(result, indent=2)}")


if __name__ == "__main__":
    # Run tests
    asyncio.run(test_interaction_agent())
