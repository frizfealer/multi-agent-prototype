"""
Sentence Tagger Implementation

This module provides a sentence tagger that uses Google Gemini API with structured output
to classify user input according to intent domain and intent type with confidence scores.
"""

import asyncio
from typing import List

from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# Load environment variables from .env file (look in parent directory)
load_dotenv(dotenv_path="../.env")


class Tag(BaseModel):
    """Individual tag for a sentence or phrase"""

    intent_domain: str
    intent_type: str
    confidence_score: float
    tagged_sentences: str
    context: str = Field(description="Context for the user's intent")


MODEL = "gemini-2.5-flash-lite-preview-06-17"

SYSTEM_PROMPT = """
Analyze the user and agent's chat history, classify the LATEST MESSAGE's intent domain and intent type, determine the input type, and capture the context for the user's intent. The input can have one or multiple intents.

**Intent domain:**
- "exercise_planning": Requests related to exercise planning.
- "social_interaction": Casual conversation or greetings.
- "creative_generation": Requests for creative content.
- "other": Unclassified intent domains.

**Intent type:**
- "Query": User searches or asks about something that already exists or information already available.
- "Create Request": User explicitly requests the creation of something new.
- "Update Request": User requests changes or modifications to something previously created.
- "Delete Request": User explicitly requests deleting the previous requests.

Steps:
1. Analyze User Input: Examine the user's text to understand the context and gather information about their request.
2. Classify Intent Domain: Determine which of the specified domains the user's request falls into.
3. Classify Intent Type: Categorize the user's request into one or more of the specified intent types.
4. Determine Confidence: Decide on a confidence score between 0.0 and 1.0 based on the clarity of the classification.
5. Extract User's Words: Identify and include the specific words or phrases from the user's input that contribute to the classification.
6. Capture Context: Identify and record any contextual information surrounding the user's intent.

# Output Format

Each intent should be represented as an entry with the determined fields:
- intent_domain
- intent_type
- confidence_score
- tagged_sentences
- context

# Examples

Input: "Can you help me plan an exercise routine for the week?"
- intent_domain: "exercise_planning"
- intent_type: "Create Request" 
- confidence_score: 0.95
- tagged_sentences: "plan an exercise routine"
- context: "User is preparing a weekly exercise plan."

Input: "Write a short story about a hero."
- intent_domain: "creative_generation"
- intent_type: "Create Request"
- confidence_score: 0.85
- tagged_sentences: "write a short story"
- context: "User is interested in storytelling about heroic figures."

Input: "I'm not sure what I want."
- intent_domain: "other"
- intent_type: "Query"
- confidence_score: 0.30
- tagged_sentences: "not sure what I want"
- context: "User is uncertain and exploratory."

Input: "I would like to update my exercise routine and write a poem."
Should produce two tags:
1. intent_domain: "exercise_planning", intent_type: "Update Request", confidence_score: 0.80, tagged_sentences: "update my exercise routine", context: "User is modifying existing exercise plans."
2. intent_domain: "creative_generation", intent_type: "Create Request", confidence_score: 0.75, tagged_sentences: "write a poem", context: "User expresses an interest in poetry writing."

# Notes

- Make sure to match the intent types and domains closely to the user input based on context clues within the text.
- If any part of the input does not clearly fit into the categories, classify it as "other".
- Consider any specific vocabulary or context in the input that might suggest its intent type.
- Confidence scores should reflect how certain you are about the classification (0.0 = very uncertain, 1.0 = very certain).
"""


class MessageTagger:
    """
    Message tagger that uses Google Gemini API with structured output to analyze
    and classify user input into intent domains and types with confidence scores.
    """

    def __init__(self):
        """
        Initialize the MessageTagger with Google Gen AI SDK
        """
        self.client = genai.Client()
        self.generation_config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            thinking_config=types.ThinkingConfig(thinking_budget=512),
            temperature=0,
            response_mime_type="application/json",
            response_schema=list[Tag],
        )

    async def classify_latest_message(self, conversations: List[types.Content]) -> List[Tag]:
        """
        Analyze the latest message in conversation and return intent classification

        Args:
            conversations: List of conversation contents with full context

        Returns:
            List of Tag objects containing classified intent information for the latest message
        """

        try:
            if not conversations:
                raise ValueError("Conversations list cannot be empty")

            # Get the latest user message for fallback
            latest_message = conversations[-1]
            latest_text = latest_message.parts[0].text if latest_message.parts else ""

            # Generate response using Gemini 2.5 Flash with structured output (async)
            response = await self.client.aio.models.generate_content(
                model=MODEL, contents=conversations, config=self.generation_config
            )

            # Use the parsed response directly
            tags = response.parsed

            # Validate that we have at least one tag
            if not tags:
                # Create a default tag if none found
                tags = [
                    Tag(intent_domain="other", intent_type="Query", confidence_score=0.0, tagged_sentences=latest_text)
                ]

            return tags

        except Exception as e:
            print(f"Error in message classification: {e}")
            # Get latest message text for fallback
            fallback_text = ""
            if conversations and conversations[-1].parts:
                fallback_text = conversations[-1].parts[0].text

            # Return fallback tag
            return [
                Tag(intent_domain="other", intent_type="Query", confidence_score=0.0, tagged_sentences=fallback_text)
            ]

    def classify_latest_message_sync(self, conversations: List[types.Content]) -> List[Tag]:
        """
        Synchronous wrapper for classify_latest_message method

        Args:
            conversations: List of conversation contents with full context

        Returns:
            List of Tag objects containing classified intent information for the latest message
        """
        return asyncio.run(self.classify_latest_message(conversations))


# Testing and example usage
async def test_MessageTagger():
    """Test function for the MessageTagger"""

    tagger = MessageTagger()

    # Test cases with conversation context
    test_cases = [
        [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text="Can you help me plan an exercise routine for the week?")],
            )
        ],
        [
            types.Content(role="user", parts=[types.Part.from_text(text="Hello there!")]),
            types.Content(role="user", parts=[types.Part.from_text(text="What exercises should I do for chest?")]),
        ],
        [
            types.Content(role="user", parts=[types.Part.from_text(text="I want to create it.")]),
            types.Content(
                role="model",
                parts=[types.Part.from_text(text="What do you want to create? Could you be more specific?")],
            ),
            types.Content(role="user", parts=[types.Part.from_text(text="my trip plan")]),
        ],
        [types.Content(role="user", parts=[types.Part.from_text(text="Write a short story about a hero.")])],
        [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text="I would like to update my exercise routine and write a poem.")],
            )
        ],
    ]

    for i, conversations in enumerate(test_cases, 1):
        latest_message = conversations[-1].parts[0].text
        print(f"\nTest {i}: '{latest_message}'")
        print(f"Context: {len(conversations)} message(s) in conversation")
        try:
            result = await tagger.classify_latest_message(conversations)
            print(f"Result: {[tag.model_dump() for tag in result]}")
        except Exception as e:
            print(f"Error: {e}")


# Example of how to integrate with existing system
def integrate_with_interaction_agent(tagger: MessageTagger, conversations: List[types.Content]) -> dict:
    """
    Example of how to integrate sentence tagger with existing interaction agent

    Args:
        tagger: SentenceTagger instance
        conversations: List of conversation contents

    Returns:
        Dictionary with routing information
    """
    tags = tagger.classify_latest_message_sync(conversations)

    # Find the highest confidence exercise planning tag
    exercise_tags = [tag for tag in tags if tag.intent_domain == "exercise_planning"]

    if exercise_tags:
        # Sort by confidence and get the highest
        best_tag = max(exercise_tags, key=lambda x: x.confidence_score)

        # Determine routing based on intent type
        if best_tag.intent_type in ["Create Request", "Update Request", "Delete Request"]:
            return {
                "route": "workflow",
                "intent_domain": best_tag.intent_domain,
                "intent_type": best_tag.intent_type,
                "confidence": best_tag.confidence_score,
                "tagged_text": best_tag.tagged_sentences,
                "update_request": best_tag.tagged_sentences,
            }
        else:  # Query
            return {
                "route": "direct_response",
                "intent_domain": best_tag.intent_domain,
                "intent_type": best_tag.intent_type,
                "confidence": best_tag.confidence_score,
                "tagged_text": best_tag.tagged_sentences,
                "query": best_tag.tagged_sentences,
            }
    else:
        # No exercise planning intents found
        highest_confidence_tag = max(tags, key=lambda x: x.confidence_score)
        return {
            "route": "not_supported",
            "intent_domain": highest_confidence_tag.intent_domain,
            "intent_type": highest_confidence_tag.intent_type,
            "confidence": highest_confidence_tag.confidence_score,
            "message": f"Sorry we are not supporting this {highest_confidence_tag.intent_domain}",
        }


if __name__ == "__main__":
    # Run tests
    asyncio.run(test_MessageTagger())
