from dataclasses import dataclass

SYSTEM_PROMPT = """
Exercise-Specific Instruction Block (Appended to Base Prompt):

"Your specialty is Exercise Planning. Your goal is to fill in all the fields under the exercise_planning key in the context object by calling the ask_question function. The fields you need are: goal, duration, fitness_level, workout_frequency, workout_duration_minutes, equipment, injuries_or_limitations, and preferences. Once all fields are filled, call the create_plan function with the complete context."
"""


def hand_off_to_triage_agent() -> dict:
    


@dataclass
class ExerciseCoachPersona:
    SYSTEM_PROMPT = SYSTEM_PROMPT
    TOOLS = [hand_off_to_]
