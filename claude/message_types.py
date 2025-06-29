"""
Message Types for Multi-Agent System

This module provides unified message handling that can convert between
Google Gemini format and LangChain format for consistent conversation management.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

from google.genai import types
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage


@dataclass
class Message:
    """
    Universal message format that can convert to both Gemini and LangChain formats.
    
    Attributes:
        role: Message role ("user", "model", "system")
        content: Message content text
        timestamp: When the message was created
        source: Which component created this message ("user", "query_processor", "triage_agent", etc.)
    """
    role: str  # "user", "model", "system"
    content: str
    timestamp: datetime
    source: str  # "user", "query_processor", "triage_agent", etc.
    
    def to_gemini(self) -> types.Content:
        """Convert to Google Gemini format."""
        return types.Content(
            role=self.role,
            parts=[types.Part.from_text(text=self.content)]
        )
    
    def to_langchain(self) -> BaseMessage:
        """Convert to LangChain format."""
        if self.role == "user":
            return HumanMessage(content=self.content)
        elif self.role == "model":
            return AIMessage(content=self.content)
        elif self.role == "system":
            return SystemMessage(content=self.content)
        else:
            # Default to HumanMessage for unknown roles
            return HumanMessage(content=self.content)
    
    @classmethod
    def from_user(cls, content: str) -> "Message":
        """Create a user message."""
        return cls(
            role="user",
            content=content,
            timestamp=datetime.now(),
            source="user"
        )
    
    @classmethod
    def from_ai(cls, content: str, source: str = "ai") -> "Message":
        """Create an AI/model message."""
        return cls(
            role="model",
            content=content,
            timestamp=datetime.now(),
            source=source
        )
    
    @classmethod
    def from_system(cls, content: str, source: str = "system") -> "Message":
        """Create a system message."""
        return cls(
            role="system",
            content=content,
            timestamp=datetime.now(),
            source=source
        )
    
    @classmethod
    def from_gemini(cls, gemini_msg: types.Content, source: str = "unknown") -> "Message":
        """Create from Gemini format."""
        # Extract text from parts (assuming single text part for simplicity)
        content = ""
        if gemini_msg.parts:
            for part in gemini_msg.parts:
                if hasattr(part, 'text'):
                    content += part.text
        
        return cls(
            role=gemini_msg.role,
            content=content,
            timestamp=datetime.now(),
            source=source
        )
    
    @classmethod
    def from_langchain(cls, lc_msg: BaseMessage, source: str = "unknown") -> "Message":
        """Create from LangChain format."""
        if isinstance(lc_msg, HumanMessage):
            role = "user"
        elif isinstance(lc_msg, AIMessage):
            role = "model"
        elif isinstance(lc_msg, SystemMessage):
            role = "system"
        else:
            role = "user"  # Default
        
        return cls(
            role=role,
            content=lc_msg.content,
            timestamp=datetime.now(),
            source=source
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source
        }


class ConversationManager:
    """Helper class for managing conversation history with sliding window."""
    
    def __init__(self, max_messages: int = 50):
        """
        Initialize conversation manager.
        
        Args:
            max_messages: Maximum number of messages to keep in sliding window
        """
        self.max_messages = max_messages
    
    def to_gemini_format(self, messages: List[Message]) -> List[types.Content]:
        """Convert list of Messages to Gemini format."""
        return [msg.to_gemini() for msg in messages]
    
    def to_langchain_format(self, messages: List[Message]) -> List[BaseMessage]:
        """Convert list of Messages to LangChain format."""
        return [msg.to_langchain() for msg in messages]
    
    def apply_sliding_window(self, messages: List[Message]) -> List[Message]:
        """Apply sliding window to keep only recent messages."""
        if len(messages) <= self.max_messages:
            return messages
        
        # Keep the most recent messages
        return messages[-self.max_messages:]
    
    def get_user_messages_only(self, messages: List[Message]) -> List[Message]:
        """Filter to get only user messages."""
        return [msg for msg in messages if msg.role == "user"]
    
    def get_latest_user_message(self, messages: List[Message]) -> Optional[Message]:
        """Get the most recent user message."""
        user_messages = self.get_user_messages_only(messages)
        return user_messages[-1] if user_messages else None
    
    def get_conversation_context(self, messages: List[Message], include_system: bool = True) -> str:
        """Get conversation as formatted string for context."""
        context_lines = []
        
        for msg in messages:
            if not include_system and msg.role == "system":
                continue
            
            role_display = msg.role.title()
            context_lines.append(f"{role_display}: {msg.content}")
        
        return "\n".join(context_lines)