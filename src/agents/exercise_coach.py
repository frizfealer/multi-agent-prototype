"""
Exercise Coach implementation for workout planning and fitness guidance.
"""

from typing import Any, List

from src.agents.base_coach import BaseCoach
from src.agents.exercise_tools import (
    calculate_training_volume,
    suggest_exercise_alternatives,
)


class ExerciseCoach(BaseCoach):
    """Specialist coach for exercise planning and fitness guidance."""

    def __init__(self):
        super().__init__("exercise_planning")

    def get_system_prompt(self) -> str:
        """Return the system prompt for exercise coaching."""
        return """
You are an Exercise Coach specializing in workout planning and fitness guidance.

## Exercise Planning Specialty
Your goal is to gather information and create personalized workout plans.

REQUIRED information:
- Primary fitness goal (e.g., build muscle, lose weight, improve endurance, general fitness)
- Program duration (e.g., 4 weeks, 8 weeks, 12 weeks, ongoing)
- Current fitness level (beginner, intermediate, advanced)

OPTIONAL information:
- Available equipment (e.g., gym access, home equipment, bodyweight only)
- Time constraints (e.g., 30 minutes, 45 minutes, 1 hour per session)
- Workout frequency (e.g., 3 times per week, daily)
- Injuries or limitations (e.g., bad knee, shoulder issues)
- Specific preferences (e.g., prefer strength training, hate cardio)

INTERACTION GUIDELINES:
- Extract as much information as possible from each user message
- Only ask for missing REQUIRED fields
- For optional fields, ask once if they want to provide more details
- If user says "that's enough" or similar, proceed with what you have
- Use search_internet() to get current fitness information when needed
- For complex multi-step workout plans, call create_artifacts() when you have enough information
- For simple requests, you can respond directly with basic advice

WHEN TO CREATE ARTIFACTS:
- Multi-week structured programs
- Detailed workout schedules with progression
- Comprehensive exercise libraries
- Complex nutrition integration

WHEN TO RESPOND DIRECTLY:
- Simple exercise form questions
- Quick workout suggestions
- General fitness advice
- Single exercise recommendations

ESCAPE HATCH:
- If user asks about topics outside fitness/exercise, use hand_off_to_triage_agent()
- Examples: career advice, relationship issues, non-fitness health concerns

Available tools: hand_off_to_triage_agent, create_artifacts, search_internet, calculate_training_volume, suggest_exercise_alternatives
"""

    def get_required_fields(self) -> List[str]:
        """Return required fields for exercise planning."""
        return ["goal", "duration", "fitness_level"]

    def get_optional_fields(self) -> List[str]:
        """Return optional fields for exercise planning."""
        return ["equipment", "time_constraints", "workout_frequency", "injuries_limitations", "preferences"]

    def get_specialist_tools(self) -> List[Any]:
        """Return exercise-specific tool functions."""
        return [
            calculate_training_volume,
            suggest_exercise_alternatives,
        ]


async def test_exercise_coach_prompts():
    """Test ExerciseCoach with various prompts using real Gemini API."""
    import os

    from dotenv import load_dotenv

    load_dotenv()

    # Check if API key is available
    if not os.getenv("GEMINI_API_KEY"):
        print("❌ GEMINI_API_KEY not found. Please set it in your .env file.")
        return

    coach = ExerciseCoach()

    test_cases = [
        # {
        #     "name": "Simple workout request",
        #     "conversation": [
        #         {"role": "user", "content": "I want to start working out. I'm a beginner and want to build muscle."}
        #     ],
        # },
        # {
        #     "name": "Detailed fitness plan request",
        #     "conversation": [
        #         {
        #             "role": "user",
        #             "content": "I want a 8-week muscle building program. I'm intermediate level with gym access, can workout 4 times per week for 1 hour each session.",
        #         }
        #     ],
        # },
        # {
        #     "name": "Exercise alternative request",
        #     "conversation": [
        #         {
        #             "role": "user",
        #             "content": "I can't do regular push-ups due to wrist pain. What are some alternatives for chest training?",
        #         }
        #     ],
        # },
        # {
        #     "name": "Off-topic request (should hand off)",
        #     "conversation": [
        #         {
        #             "role": "user",
        #             "content": "Can you help me with relationship advice? I'm having trouble with my partner.",
        #         }
        #     ],
        # },
        # {
        #     "name": "Volume calculation request",
        #     "conversation": [
        #         {
        #             "role": "user",
        #             "content": "How much total volume should I aim for when doing 4 sets of 8 reps with 50kg on bench press?",
        #         }
        #     ],
        # },
        {
            "name": "Internet search request",
            "conversation": [
                {
                    "role": "user",
                    "content": "What are the latest research findings on optimal protein intake for muscle building in 2024?",
                }
            ],
        },
        {
            "name": "Create artifacts request",
            "conversation": [
                {
                    "role": "user",
                    "content": "Create a complete 12-week progressive strength training program for me. I'm intermediate level, have full gym access, want to focus on powerlifting movements, and can train 4 days per week. Include detailed progression, deload weeks, and accessory work.",
                },
                {
                    "role": "model",
                    "content": "Okay, this sounds like a great goal. Just to confirm, your primary fitness goal is to build strength with a focus on powerlifting movements? Also, to confirm, you have an intermediate fitness level and can train 4 days per week, with full gym access, for a duration of 12 weeks. Before I create this program, are there any injuries or limitations I should be aware of?",
                },
                {
                    "role": "user",
                    "content": "No, I don't have any injuries or limitations.",
                },
            ],
        },
    ]

    print("🏋️ Testing ExerciseCoach with Real Gemini API")
    print("=" * 60)

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{i}. {test_case['name']}")
        print("-" * 40)
        print(f"User: {test_case['conversation'][0]['content']}")

        try:
            response = await coach.process_request(test_case["conversation"])
            print(f"Action: {response['name']}, Arguments: {response['arguments']}")
        except Exception as e:
            print(f"❌ Error: {e}")

        print()


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_exercise_coach_prompts())
