"""
Dynamic Coach Creation System for Multi-Domain Coaching
"""
from typing import Dict, List, Any
from .base_coach import BaseCoach
import json

class DynamicCoach(BaseCoach):
    """Dynamically created coach that combines multiple specialties."""
    
    def __init__(self, domains: List[str], system_prompt: str, tools: List[Dict[str, Any]]):
        super().__init__("+".join(domains))
        self.domains = domains
        self._system_prompt = system_prompt
        self._tools = tools
    
    def get_system_prompt(self) -> str:
        """Return the dynamically created system prompt."""
        return self._system_prompt
    
    def get_required_fields(self) -> List[str]:
        """Return all required fields across domains."""
        # This is aggregated from all domains
        return []
    
    def get_optional_fields(self) -> List[str]:
        """Return all optional fields across domains."""
        # This is aggregated from all domains
        return []
    
    def get_specialist_tools(self) -> List[Dict[str, Any]]:
        """Return all specialist tools for this composite coach."""
        return self._tools


class CoachTemplateManager:
    """Manages coach templates and creates dynamic coaches."""
    
    BASE_COACH_TEMPLATE = """
You are a {coach_types} specialist. Your role is to have detailed conversations to gather information and create plans for your active specialties.

{specialty_instructions}

GENERAL GUIDELINES:
- Extract as much information as possible from each user message
- Only ask for missing REQUIRED fields
- Handle one specialty at a time if user provides mixed information
- For complex multi-step processes, call create_artifacts() when you have enough information
- For simple requests, you can respond directly with advice
- Use search_internet() to get current information when needed
- If user asks about topics outside your specialties, use hand_off_to_triage_agent()

CONFLICT PREVENTION:
If advice between specialties might conflict:
1. Acknowledge the potential conflict
2. Explain how to balance both goals
3. Prioritize based on user's primary objective
4. Use search_internet() to find current best practices

Example: "I notice you want to build muscle (exercise) and lose weight (nutrition). 
These can work together - let me search for the latest research on body recomposition..."

Available tools: {available_tools}
"""
    
    SPECIALTY_BLOCKS = {
        "exercise_planning": """
## Exercise Planning Specialty
Your goal is to gather information for workout plans.

REQUIRED: Primary fitness goal, program duration, current fitness level
OPTIONAL: Available equipment, time constraints, workout frequency, injuries/limitations, preferences

When ready, call: create_artifacts("exercise_planning", {data})
        """,
        
        "nutrition_planning": """
## Nutrition Planning Specialty  
Your goal is to gather information for meal plans and nutrition guidance.

REQUIRED: Primary nutrition goal, dietary preferences
OPTIONAL: Allergies, budget constraints, cooking time, meal prep preferences

When ready, call: create_artifacts("nutrition_planning", {data})
        """,
        
        "sleep_optimization": """
## Sleep Optimization Specialty
Your goal is to gather information for sleep improvement plans.

REQUIRED: Current sleep issues, desired sleep schedule
OPTIONAL: Sleep environment, current habits, work schedule, stress factors

When ready, call: create_artifacts("sleep_optimization", {data})
        """
    }
    
    SPECIALIST_TOOLS = {
        "exercise_planning": [
            {
                "name": "calculate_training_volume",
                "description": "Calculate appropriate sets/reps based on goals and experience",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "goal": {"type": "string"},
                        "experience_level": {"type": "string"},
                        "available_time": {"type": "number"}
                    },
                    "required": ["goal", "experience_level"]
                }
            },
            {
                "name": "suggest_exercise_alternatives",
                "description": "Find alternative exercises based on equipment or limitations",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "original_exercise": {"type": "string"},
                        "available_equipment": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "limitations": {
                            "type": "array", 
                            "items": {"type": "string"}
                        }
                    },
                    "required": ["original_exercise"]
                }
            }
        ],
        "nutrition_planning": [
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
                        "activity_level": {"type": "string"}
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
            }
        ],
        "sleep_optimization": [
            {
                "name": "analyze_sleep_schedule",
                "description": "Analyze current sleep patterns and suggest improvements",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "current_bedtime": {"type": "string"},
                        "current_wake_time": {"type": "string"},
                        "sleep_quality": {"type": "number"},
                        "work_schedule": {"type": "string"}
                    },
                    "required": ["current_bedtime", "current_wake_time"]
                }
            }
        ]
    }
    
    def create_multi_domain_coach(self, domains: List[str]) -> DynamicCoach:
        """Create a coach that handles multiple domains."""
        # Combine specialty instructions
        specialty_instructions = "\n".join([
            self.SPECIALTY_BLOCKS.get(domain, f"## {domain.replace('_', ' ').title()} Specialty\n(Instructions not yet defined)")
            for domain in domains
        ])
        
        # Create coach type names for display
        coach_names = " + ".join([domain.replace("_", " ").title() for domain in domains])
        
        # Combine specialist tools
        specialist_tools = []
        for domain in domains:
            specialist_tools.extend(self.SPECIALIST_TOOLS.get(domain, []))
        
        # Format available tools for prompt
        all_tools = ["hand_off_to_triage_agent", "create_artifacts", "search_internet"] + [tool["name"] for tool in specialist_tools]
        
        # Create system prompt
        system_prompt = self.BASE_COACH_TEMPLATE.format(
            coach_types=coach_names,
            specialty_instructions=specialty_instructions,
            available_tools=", ".join(all_tools)
        )
        
        return DynamicCoach(
            domains=domains,
            system_prompt=system_prompt,
            tools=specialist_tools
        )
    
    def get_available_specialties(self) -> List[str]:
        """Return list of available specialties."""
        return list(self.SPECIALTY_BLOCKS.keys())
    
    def add_specialty(self, name: str, instructions: str, tools: List[Dict[str, Any]] = None):
        """Add a new specialty to the system."""
        self.SPECIALTY_BLOCKS[name] = instructions
        if tools:
            self.SPECIALIST_TOOLS[name] = tools