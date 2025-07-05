from typing import Any, Callable, Dict, List

from google.genai import types


def convert_to_gemini_message(messages: List[Dict[str, Any]]) -> List[types.Content]:
    """Converts a message to a Gemini message.

    Args:
        message: The message to convert.

    Returns:
        A list of Gemini Content objects.
    """
    return [types.Content(role=msg["role"], parts=[types.Part(text=msg["content"])]) for msg in messages]


def terminal_function(func: Callable) -> Callable:
    """Decorator to mark a function as terminal (should end agent processing)."""
    func.is_terminal = True
    return func


def non_terminal_function(func: Callable) -> Callable:
    """Decorator to mark a function as non-terminal (agent should continue processing)."""
    func.is_terminal = False
    return func


def is_function_terminal(func: Callable) -> bool:
    """Check if a function is marked as terminal."""
    return getattr(func, "is_terminal", False)


def get_non_terminal_functions(function_list: List[Callable]) -> List[Callable]:
    """Get all non-terminal functions from a list of functions."""
    return [func for func in function_list if not is_function_terminal(func)]


def get_terminal_functions(function_list: List[Callable]) -> List[Callable]:
    """Get all terminal functions from a list of functions."""
    return [func for func in function_list if is_function_terminal(func)]


def get_function_names_by_terminal_status(function_list: List[Callable]) -> Dict[str, List[str]]:
    """Get function names organized by terminal status."""
    return {
        "terminal": [func.__name__ for func in function_list if is_function_terminal(func)],
        "non_terminal": [func.__name__ for func in function_list if not is_function_terminal(func)],
    }
