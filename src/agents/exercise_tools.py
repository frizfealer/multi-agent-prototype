"""
Specialist tools for the Exercise Coach.
"""

from typing import Dict, List, Optional, Union


def calculate_training_volume(sets: int, reps: int, weight: Optional[float] = None) -> Dict[str, Union[int, float]]:
    """Calculate training volume for an exercise.
    
    Args:
        sets: Number of sets
        reps: Number of repetitions per set
        weight: Weight used (optional, in kg or lbs)
        
    Returns:
        Dict with volume calculations
    """
    total_reps = sets * reps
    volume = {
        "total_reps": total_reps,
        "sets": sets,
        "reps_per_set": reps
    }
    
    if weight:
        volume["total_volume"] = total_reps * weight
        volume["weight"] = weight
        
    return volume


def suggest_exercise_alternatives(muscle_group: str, equipment: Optional[List[str]] = None) -> Dict[str, Union[str, Dict]]:
    """Suggest alternative exercises for a muscle group.
    
    Args:
        muscle_group: Target muscle group (e.g., "chest", "back", "legs")
        equipment: Available equipment (e.g., ["dumbbells", "barbell", "bands"])
        
    Returns:
        Dict with exercise suggestions
    """
    # Simple example mapping - in reality this would be more comprehensive
    exercises = {
        "chest": {
            "bodyweight": ["push-ups", "diamond push-ups", "wide-grip push-ups"],
            "dumbbells": ["dumbbell bench press", "dumbbell flyes", "dumbbell pullover"],
            "barbell": ["barbell bench press", "incline press", "decline press"],
            "bands": ["band chest press", "band flyes", "band crossover"]
        },
        "back": {
            "bodyweight": ["pull-ups", "chin-ups", "inverted rows"],
            "dumbbells": ["dumbbell rows", "dumbbell pullover", "reverse flyes"],
            "barbell": ["barbell rows", "deadlifts", "t-bar rows"],
            "bands": ["band rows", "band pull-aparts", "band lat pulldown"]
        },
        "legs": {
            "bodyweight": ["squats", "lunges", "bulgarian split squats"],
            "dumbbells": ["goblet squats", "dumbbell lunges", "step-ups"],
            "barbell": ["barbell squats", "front squats", "romanian deadlifts"],
            "bands": ["band squats", "band leg curls", "band hip thrusts"]
        }
    }
    
    muscle_exercises = exercises.get(muscle_group.lower(), {})
    suggestions = {}
    
    if equipment:
        for eq in equipment:
            if eq.lower() in muscle_exercises:
                suggestions[eq] = muscle_exercises[eq.lower()]
    else:
        # Return all equipment options if none specified
        suggestions = muscle_exercises
        
    return {
        "muscle_group": muscle_group,
        "alternatives": suggestions
    }