import asyncio
import os
from dotenv import load_dotenv

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.core.orchestrator import Orchestrator
from src.db.base import Base

load_dotenv()


async def main():
    # Setup database - use PostgreSQL for JSONB support
    database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5432/triage_agent_db")
    engine = create_async_engine(database_url, echo=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    # Create orchestrator
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        print("Please set GOOGLE_API_KEY in your .env file")
        return
    
    orchestrator = Orchestrator(google_api_key)
    
    # Example conversation
    async with async_session_maker() as session:
        print("\n=== Starting new conversation ===\n")
        
        # First message
        response1 = await orchestrator.process_user_message(
            session, None, "I need help with my fitness routine"
        )
        print(f"User: I need help with my fitness routine")
        print(f"Agent: {response1['text']}")
        print(f"Action: {response1.get('action')}\n")
        
        conversation_id = response1['conversation_id']
        
        # Follow-up message
        response2 = await orchestrator.process_user_message(
            session, conversation_id, "I want to build muscle and lose fat"
        )
        print(f"User: I want to build muscle and lose fat")
        print(f"Agent: {response2['text']}")
        print(f"Action: {response2.get('action')}\n")
        
        # Simple request
        response3 = await orchestrator.process_user_message(
            session, conversation_id, "Delete my old workout plan called 'Summer Shred'"
        )
        print(f"User: Delete my old workout plan called 'Summer Shred'")
        print(f"Agent: {response3['text']}")
        print(f"Action: {response3.get('action')}\n")


if __name__ == "__main__":
    asyncio.run(main())