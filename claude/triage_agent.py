"""
TriageAgent Implementation

This module provides a TriageAgent that uses MessageTagger to classify the intent of the user's message,
and then return routing decisions without handling session management.
"""

import asyncio
from typing import Dict, Any, Optional, TYPE_CHECKING

from message_tagger import MessageTagger
from google.genai import types

if TYPE_CHECKING:
    from claude.session_manager import ChatSession


class TriageAgent:
    """
    Pure logic agent that classifies messages and returns routing decisions.
    Does not handle session management or WebSocket communication.
    """
    
    def __init__(self, high_confidence_threshold: float = 0.8):
        self.message_tagger = MessageTagger()
        self.high_confidence_threshold = high_confidence_threshold
    
    async def classify_and_route(self, session_id: str, session: "ChatSession") -> Dict[str, Any]:
        """
        Classify conversation and return routing decision based on full conversation history
        
        Args:
            session_id: Session identifier
            session: Chat session containing conversation history
            
        Returns:
            Dictionary with routing decision:
            {
                "action": "confirm" | "direct_process" | "reject",
                "confidence": float,
                "intent_domain": str,
                "intent_type": str,
                "tagged_sentences": str,
                "context": str,
                "confirmation_message": str (optional),
                "redirect_message": str (optional)
            }
        """
        # Get conversation history in Gemini format (excluding system messages)
        conversations = session.get_conversation_for_gemini(include_system=False)
        
        # Get the latest user message for response generation
        latest_user_msg = session.get_latest_user_message()
        if not latest_user_msg:
            return self._create_error_response("", "No user message found in conversation")
        
        user_message = latest_user_msg.content
        
        try:
            # Classify the message
            tags = await self.message_tagger.classify_latest_message(conversations)
            
            # Process the primary tag (usually just one)
            if not tags:
                return self._create_default_response(user_message)
            
            tag = tags[0]  # Use the first/primary tag
            
            print(f"Triage classification - Domain: {tag.intent_domain}, Type: {tag.intent_type}, Confidence: {tag.confidence_score}")
            
            # High-confidence create request for exercise planning
            if (tag.confidence_score >= self.high_confidence_threshold and 
                tag.intent_type == "Create Request" and 
                tag.intent_domain == "exercise_planning"):
                
                return {
                    "action": "confirm",
                    "confidence": tag.confidence_score,
                    "intent_domain": tag.intent_domain,
                    "intent_type": tag.intent_type,
                    "tagged_sentences": tag.tagged_sentences,
                    "context": tag.context,
                    "confirmation_message": f"I detected you want to create an exercise plan: '{tag.tagged_sentences}'. Should I proceed with creating your plan?"
                }
            
            # Direct processing for exercise planning (lower confidence or other types)
            elif tag.intent_domain == "exercise_planning":
                return {
                    "action": "direct_process",
                    "confidence": tag.confidence_score,
                    "intent_domain": tag.intent_domain,
                    "intent_type": tag.intent_type,
                    "tagged_sentences": tag.tagged_sentences,
                    "context": tag.context
                }
            
            # Reject and redirect for non-exercise domains
            else:
                return {
                    "action": "reject",
                    "confidence": tag.confidence_score,
                    "intent_domain": tag.intent_domain,
                    "intent_type": tag.intent_type,
                    "tagged_sentences": tag.tagged_sentences,
                    "context": tag.context,
                    "redirect_message": f"I can help with exercise planning. Your message seems to be about '{tag.intent_domain}'. Could you tell me about your exercise goals?"
                }
                
        except Exception as e:
            print(f"Error in message classification: {e}")
            return self._create_error_response(user_message, str(e))
    
    def _create_default_response(self, user_message: str) -> Dict[str, Any]:
        """Create default response when no tags are found"""
        return {
            "action": "direct_process",
            "confidence": 0.0,
            "intent_domain": "other",
            "intent_type": "Query",
            "tagged_sentences": user_message,
            "context": "Unable to classify message, defaulting to direct processing"
        }
    
    def _create_error_response(self, user_message: str, error_msg: str) -> Dict[str, Any]:
        """Create error response when classification fails"""
        return {
            "action": "direct_process",
            "confidence": 0.0,
            "intent_domain": "other", 
            "intent_type": "Query",
            "tagged_sentences": user_message,
            "context": f"Classification error: {error_msg}",
            "error": error_msg
        }
    
    @staticmethod
    def is_confirmation_response(message: str) -> str:
        """
        Check if message is a yes/no confirmation response
        
        Returns:
            "yes" if positive confirmation
            "no" if negative confirmation  
            "unclear" if ambiguous response
        """
        message_lower = message.lower().strip()
        
        # Positive confirmations
        if message_lower in ["yes", "y", "confirm", "proceed", "go ahead", "sure", "ok", "okay", "yep", "yeah"]:
            return "yes"
        
        # Negative confirmations
        elif message_lower in ["no", "n", "cancel", "stop", "abort", "nope", "nah", "don't"]:
            return "no"
        
        # Unclear response
        else:
            return "unclear"


# Testing function
async def test_triage_agent():
    """Test function for the TriageAgent"""
    
    triage = TriageAgent()
    
    test_cases = [
        "Can you help me plan an exercise routine for the week?",
        "Write a short story about a hero",
        "Hello there!",
        "I want to create a workout plan for building muscle",
        "What exercises should I do for chest?",
        "yes",
        "no", 
        "maybe later"
    ]
    
    for message in test_cases:
        print(f"\nTesting: '{message}'")
        result = await triage.classify_and_route(message)
        print(f"Action: {result['action']}")
        print(f"Domain: {result['intent_domain']}, Type: {result['intent_type']}")
        print(f"Confidence: {result['confidence']}")
        
        if result.get('confirmation_message'):
            print(f"Confirmation: {result['confirmation_message']}")
        if result.get('redirect_message'):
            print(f"Redirect: {result['redirect_message']}")


if __name__ == "__main__":
    # Run tests
    asyncio.run(test_triage_agent())
