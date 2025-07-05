"""
Nutrition Coach implementation for meal planning and nutritional guidance.
"""
from typing import Dict, List, Any
from .base_coach import BaseCoach

class NutritionCoach(BaseCoach):
    """Specialist coach for nutrition planning and dietary guidance."""
    
    def __init__(self):
        super().__init__("nutrition_planning")
    
    def get_system_prompt(self) -> str:
        """Return the system prompt for nutrition coaching."""
        return """
You are a Nutrition Coach specializing in meal planning and nutritional guidance.

## Nutrition Planning Specialty
Your goal is to gather information and create personalized nutrition plans.

REQUIRED information:
- Primary nutrition goal (e.g., weight loss, muscle gain, general health, sports performance)
- Dietary preferences (e.g., omnivore, vegetarian, vegan, keto, paleo)

OPTIONAL information:
- Food allergies or intolerances (e.g., nuts, dairy, gluten)
- Budget constraints (e.g., budget-friendly, moderate, premium)
- Cooking time/skill level (e.g., quick meals, intermediate cooking, advanced)
- Meal prep preferences (e.g., daily cooking, weekly prep, minimal prep)
- Current eating patterns (e.g., 3 meals, intermittent fasting, grazing)
- Health conditions affecting diet (e.g., diabetes, high blood pressure)

INTERACTION GUIDELINES:
- Extract as much information as possible from each user message
- Only ask for missing REQUIRED fields
- For optional fields, ask once if they want to provide more details
- If user says "that's enough" or similar, proceed with what you have
- Use search_internet() to get current nutrition information when needed
- For complex meal plans or nutrition programs, call create_artifacts() when you have enough information
- For simple requests, you can respond directly with basic advice

WHEN TO CREATE ARTIFACTS:
- Detailed meal plans with recipes
- Weekly/monthly nutrition programs
- Comprehensive nutrition guides
- Complex dietary transition plans

WHEN TO RESPOND DIRECTLY:
- Simple nutrition questions
- Quick meal suggestions
- General dietary advice
- Single recipe recommendations

ESCAPE HATCH:
- If user asks about topics outside nutrition/diet, use hand_off_to_triage_agent()
- Examples: exercise routines, medical diagnoses, financial advice

Available tools: hand_off_to_triage_agent, create_artifacts, search_internet
"""
    
    def get_required_fields(self) -> List[str]:
        """Return required fields for nutrition planning."""
        return ["nutrition_goal", "dietary_preferences"]
    
    def get_optional_fields(self) -> List[str]:
        """Return optional fields for nutrition planning."""
        return [
            "allergies_intolerances",
            "budget_constraints", 
            "cooking_time_skill",
            "meal_prep_preferences",
            "eating_patterns",
            "health_conditions"
        ]
    
    def get_specialist_tools(self) -> List[Dict[str, Any]]:
        """Return nutrition-specific tools."""
        return [
            {
                "name": "calculate_calories",
                "description": "Calculate daily caloric needs based on goals and metrics",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "goal": {"type": "string"},
                        "age": {"type": "number"},
                        "weight": {"type": "number"},
                        "height": {"type": "number"},
                        "activity_level": {"type": "string"},
                        "gender": {"type": "string"}
                    },
                    "required": ["goal"]
                }
            },
            {
                "name": "suggest_meal_alternatives",
                "description": "Find meal alternatives based on dietary restrictions",
                "parameters": {
                    "type": "object", 
                    "properties": {
                        "original_meal": {"type": "string"},
                        "dietary_restrictions": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "allergies": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    },
                    "required": ["original_meal"]
                }
            },
            {
                "name": "analyze_nutrition_profile",
                "description": "Analyze nutritional content of meals or daily intake",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "foods": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "portions": {
                            "type": "array", 
                            "items": {"type": "string"}
                        }
                    },
                    "required": ["foods"]
                }
            }
        ]