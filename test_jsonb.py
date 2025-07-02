"""
Demonstrates JSONB functionality in the Triage Agent system.
Requires PostgreSQL to be running.
"""
import asyncio
import os
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.core.state_manager import StateManager
from src.db.base import Base

load_dotenv()


async def demonstrate_jsonb():
    # Setup database
    database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5432/triage_agent_db")
    engine = create_async_engine(database_url, echo=False)
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session_maker() as session:
        state_manager = StateManager(session)
        
        # Create a conversation
        print("\n=== Creating conversation ===")
        conversation = await state_manager.create_conversation()
        print(f"Created conversation: {conversation.conversation_id}")
        print(f"Initial context: {conversation.context_data}")
        
        # Update with complex nested JSONB data
        print("\n=== Updating context with complex data ===")
        complex_context = {
            "intent": "fitness_planning",
            "user_profile": {
                "age": 30,
                "fitness_level": "intermediate",
                "goals": ["muscle_gain", "fat_loss"],
                "preferences": {
                    "workout_days": ["monday", "wednesday", "friday"],
                    "equipment": ["dumbbells", "barbell", "resistance_bands"],
                    "time_per_session": 60
                }
            },
            "current_plan": {
                "name": "Summer Shred 2024",
                "phase": 2,
                "progress": {
                    "workouts_completed": 15,
                    "strength_gains": {
                        "squat": "+20lbs",
                        "bench": "+15lbs",
                        "deadlift": "+30lbs"
                    }
                }
            },
            "metadata": {
                "last_updated": "2024-01-15",
                "coach_recommendations": ["increase_protein", "add_cardio"],
                "notes": ["User prefers morning workouts", "Has minor knee issue"]
            }
        }
        
        await state_manager.update_conversation_context(
            conversation.conversation_id, complex_context
        )
        
        # Retrieve and display the updated context
        updated_conv = await state_manager.get_conversation(conversation.conversation_id)
        print("Updated context:")
        import json
        print(json.dumps(updated_conv.context_data, indent=2))
        
        # Demonstrate JSONB query capabilities (would be used in production)
        print("\n=== JSONB allows efficient queries ===")
        print("Examples of queries possible with JSONB:")
        print("- Find all conversations with 'muscle_gain' goal")
        print("- Filter by nested data like user_profile->fitness_level = 'intermediate'")
        print("- Search within arrays like 'monday' in preferences->workout_days")
        print("- Update specific nested fields without loading entire document")
        
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(demonstrate_jsonb())