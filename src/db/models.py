"""Database models for the multi-agent prototype application.

This module defines SQLAlchemy ORM models for managing sessions, conversations, and messages.
It includes a custom UUID type that provides database portability across PostgreSQL and other
database systems.

Models:
    - Session: User session management with expiration and metadata
    - SessionConversation: Many-to-many relationship between sessions and conversations
    - Conversation: Individual conversation state and agent tracking
    - Message: Individual messages within conversations
    - CustomUUID: Database-agnostic UUID column type

The CustomUUID type automatically handles the differences between PostgreSQL's native UUID
type and string-based UUID storage in other databases, ensuring seamless portability.
"""

import uuid
from datetime import datetime
from typing import Any, Optional, Union

from sqlalchemy import (
    CHAR,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
    Text,
    TypeDecorator,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import relationship
from sqlalchemy.sql.type_api import UserDefinedType

from .base import Base


class CustomUUID(TypeDecorator[uuid.UUID]):
    """Platform-independent UUID type for SQLAlchemy.

    This custom type provides seamless UUID handling across different database systems:
    - PostgreSQL: Uses native UUID type for optimal 16-byte storage
    - Other databases: Uses CHAR(36) for string-based UUID storage

    The type automatically handles conversion between Python UUID objects and the
    appropriate database representation, ensuring your code works consistently
    regardless of the underlying database.

    Attributes:
        impl: Base SQLAlchemy type (CHAR)
        cache_ok: Enables SQLAlchemy caching for this type
        as_uuid: Whether to return UUID objects (True) or strings (False)

    Example:
        ```python
        # Define a column with database-agnostic UUID support
        user_id = Column(CustomUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
        ```
    """

    impl = CHAR
    cache_ok = True

    def __init__(self, as_uuid: bool = True, **kwargs: Any) -> None:
        """Initialize the CustomUUID type.

        Args:
            as_uuid: If True, return UUID objects; if False, return strings
            **kwargs: Additional arguments passed to parent TypeDecorator
        """
        self.as_uuid = as_uuid
        super().__init__(**kwargs)

    def load_dialect_impl(self, dialect: Dialect) -> UserDefinedType[Any]:
        """Load the appropriate dialect-specific type implementation.

        Selects the optimal UUID representation based on the database dialect:
        - PostgreSQL: Native UUID type
        - Others: CHAR(36) for string storage

        Args:
            dialect: SQLAlchemy dialect instance for the target database

        Returns:
            The appropriate SQLAlchemy type for the given dialect
        """
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=self.as_uuid))
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(
        self, value: Optional[Union[str, uuid.UUID]], dialect: Dialect
    ) -> Optional[Union[str, uuid.UUID]]:
        """Process a value being sent to the database.

        Converts Python values to the appropriate format for database storage:
        - PostgreSQL: Passes UUID objects directly
        - Others: Converts UUID objects to string representation

        Args:
            value: The value to be stored (UUID object, string, or None)
            dialect: SQLAlchemy dialect instance

        Returns:
            The value in the format expected by the database
        """
        if value is None:
            return value
        elif dialect.name == "postgresql":
            return value
        else:
            if isinstance(value, uuid.UUID):
                return str(value)
            else:
                return value

    def process_result_value(self, value: Optional[Union[str, uuid.UUID]], dialect: Dialect) -> Optional[uuid.UUID]:
        """Process a value being returned from the database.

        Converts database values back to Python UUID objects:
        - PostgreSQL: Returns UUID objects directly
        - Others: Converts string representations back to UUID objects

        Args:
            value: The value retrieved from the database
            dialect: SQLAlchemy dialect instance

        Returns:
            A Python UUID object or None
        """
        if value is None:
            return value
        elif dialect.name == "postgresql":
            return value
        else:
            if not isinstance(value, uuid.UUID):
                return uuid.UUID(value)
            else:
                return value


class Session(Base):
    """User session model for managing authentication and session state.

    Tracks user sessions with automatic expiration, metadata storage, and
    relationship tracking to conversations. Supports session token-based
    authentication and stores client information for security.

    Attributes:
        session_id: Unique session identifier (UUID)
        session_token: Unique session token for authentication
        user_metadata: Flexible JSON storage for user-specific data
        created_at: Session creation timestamp
        last_accessed: Last session access timestamp
        expires_at: Session expiration timestamp
        is_active: Whether the session is currently active
        ip_address: Client IP address (supports IPv4 and IPv6)
        user_agent: Client user agent string
        conversations: Related conversations for this session
    """

    __tablename__ = "sessions"

    session_id: Column[uuid.UUID] = Column(CustomUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_token: Column[str] = Column(String(255), unique=True, nullable=False, index=True)
    user_metadata: Column[dict[str, Any]] = Column(JSONB, default={})
    created_at: Column[datetime] = Column(DateTime, default=datetime.utcnow)
    last_accessed: Column[datetime] = Column(DateTime, default=datetime.utcnow)
    expires_at: Column[datetime] = Column(DateTime, nullable=False)
    is_active: Column[bool] = Column(Boolean, default=True)
    ip_address: Column[Optional[str]] = Column(String(45))  # Support IPv6
    user_agent: Column[Optional[str]] = Column(String(500))

    # Relationships
    conversations = relationship("SessionConversation", back_populates="session", cascade="all, delete-orphan")


class SessionConversation(Base):
    """Association table linking sessions to conversations.

    Implements a many-to-many relationship between sessions and conversations,
    allowing multiple sessions to access the same conversation and tracking
    when the association was created.

    Attributes:
        session_id: Foreign key to the session
        conversation_id: Foreign key to the conversation
        created_at: When the session-conversation link was created
        session: Back-reference to the Session object
        conversation: Back-reference to the Conversation object
    """

    __tablename__ = "session_conversations"

    session_id: Column[uuid.UUID] = Column(
        CustomUUID(as_uuid=True), ForeignKey("sessions.session_id"), primary_key=True
    )
    conversation_id: Column[uuid.UUID] = Column(
        CustomUUID(as_uuid=True), ForeignKey("conversations.conversation_id"), primary_key=True
    )
    created_at: Column[datetime] = Column(DateTime, default=datetime.utcnow)

    # Relationships
    session = relationship("Session", back_populates="conversations")
    conversation = relationship("Conversation")


class Conversation(Base):
    """Conversation model for tracking multi-agent interactions.

    Manages the state of individual conversations, including which agent
    is currently handling the conversation and storing conversation-specific
    context data. Automatically tracks creation and update timestamps.

    Attributes:
        conversation_id: Unique conversation identifier (UUID)
        current_agent: Name of the agent currently handling this conversation
        context_data: Flexible JSON storage for conversation context
        created_at: Conversation creation timestamp
        updated_at: Last conversation update timestamp (auto-updated)
        messages: All messages in this conversation
    """

    __tablename__ = "conversations"

    conversation_id: Column[uuid.UUID] = Column(CustomUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    current_agent: Column[str] = Column(String(255), nullable=False, default="triage")
    context_data: Column[dict[str, Any]] = Column(JSONB, default={})
    created_at: Column[datetime] = Column(DateTime, default=datetime.utcnow)
    updated_at: Column[datetime] = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    """Individual message model within conversations.

    Stores individual messages exchanged in conversations, tracking the role
    (user, assistant, system) and content of each message with timestamps.

    Attributes:
        message_id: Unique message identifier (UUID)
        conversation_id: Foreign key to the parent conversation
        role: Message role (user, assistant, system, etc.)
        content: The actual message content
        created_at: Message creation timestamp
        conversation: Back-reference to the Conversation object
    """

    __tablename__ = "messages"

    message_id: Column[uuid.UUID] = Column(CustomUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Column[uuid.UUID] = Column(
        CustomUUID(as_uuid=True), ForeignKey("conversations.conversation_id"), nullable=False
    )
    role: Column[str] = Column(String(255), nullable=False)
    content: Column[str] = Column(Text, nullable=False)
    created_at: Column[datetime] = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")
