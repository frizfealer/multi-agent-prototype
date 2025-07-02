"""
Database abstraction layer providing async SQLAlchemy support.

This module establishes the foundation for database operations in an async application.
It provides connection management, session handling, and schema initialization while
maintaining proper resource cleanup and async compatibility.

Key architectural decisions:
- Uses async SQLAlchemy for non-blocking database operations
- Implements session factory pattern for proper resource management
- Separates connection-level operations (schema) from session-level operations (ORM)
"""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Base class for all database models using SQLAlchemy's declarative pattern
# WHY: This allows us to define database tables as Python classes that inherit from Base
# All model classes (User, Session, etc.) will extend this to get SQLAlchemy functionality
Base = declarative_base()


class DatabaseManager:
    """
    Central database management class that handles connections, sessions, and schema operations.

    This class encapsulates all database infrastructure concerns and provides a clean
    interface for the rest of the application to interact with the database.

    WHY this design:
    - Separation of concerns: Database logic is isolated from business logic
    - Resource management: Proper connection pooling and session cleanup
    - Testability: Easy to mock or replace for testing
    - Configuration: Database URL can be changed based on environment
    """

    def __init__(self, database_url: str):
        """
        Initialize the database manager with connection configuration.

        Args:
            database_url: Database connection string (e.g., postgresql+asyncpg://...)

        WHY async engine:
        - Handles concurrent requests efficiently without blocking
        - Integrates well with async frameworks like FastAPI

        WHY echo=False:
        - Prevents SQL query logging in production (set to True for debugging)

        WHY expire_on_commit=False:
        - Keeps model objects accessible after commit operations
        - Prevents lazy-loading issues in async contexts
        """
        self.engine = create_async_engine(database_url, echo=False)
        self.async_session_maker = sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Create and yield a database session as an async generator.

        This method provides sessions for ORM operations (CRUD with model objects).

        WHY async generator pattern:
        - Context management: Automatically handles opening/closing sessions
        - Resource cleanup: Ensures connections are properly released back to pool
        - Dependency injection: Works seamlessly with FastAPI's dependency system
        - Exception safety: Session cleanup happens even if operations fail

        Usage:
            async for session in db_manager.get_session():
                user = await session.get(User, user_id)
                # Session automatically closed when exiting context
        """
        async with self.async_session_maker() as session:
            yield session

    async def init_db(self):
        """
        Create all database tables defined by model classes.

        This method uses CONNECTION-level operations (not session-level) because:
        - Schema creation is a one-time administrative task
        - Doesn't require object tracking or ORM features
        - More efficient for DDL (Data Definition Language) operations

        WHY run_sync:
        - Base.metadata.create_all is a synchronous SQLAlchemy operation
        - run_sync safely executes sync operations within async context
        - Maintains async compatibility while using existing SQLAlchemy APIs

        Usage:
            await db_manager.init_db()  # Creates all tables defined in models
        """
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
