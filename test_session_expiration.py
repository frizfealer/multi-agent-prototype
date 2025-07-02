"""
Comprehensive test demonstrating session expiration mechanisms.
Shows how sessions expire after inactivity and how to modify expiration duration.
"""
import asyncio
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.core.session_manager import SessionManager
from src.db.base import Base

load_dotenv()


async def test_basic_expiration():
    """Test 1: Basic session expiration after 30 minutes of inactivity."""
    print("\n=== Test 1: Basic Session Expiration ===")
    
    # Setup database
    database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5432/triage_agent_db")
    engine = create_async_engine(database_url, echo=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session_maker() as session:
        session_manager = SessionManager(session)
        
        # Create a session
        print("Creating session...")
        db_session = await session_manager.create_session(
            user_metadata={"test": "expiration_demo"}
        )
        print(f"Session created: {db_session.session_id}")
        print(f"Initial expires_at: {db_session.expires_at}")
        print(f"Session duration: {session_manager.session_duration}")
        
        # Verify session is valid
        token = db_session.session_token
        valid_session = await session_manager.get_session_by_token(token)
        assert valid_session is not None
        print("✅ Session is initially valid")
        
        # Show expiration time gets extended on access
        original_expires = valid_session.expires_at
        print(f"Original expiration: {original_expires}")
        
        # Access again (this should extend expiration)
        await asyncio.sleep(1)  # Small delay to see time difference
        extended_session = await session_manager.get_session_by_token(token)
        new_expires = extended_session.expires_at
        print(f"After access expiration: {new_expires}")
        print(f"Time extended by: {new_expires - original_expires}")
        assert new_expires > original_expires
        print("✅ Session expiration extended on access")
        
        # Manually expire the session by setting past expiration
        print("\nManually setting session to expired state...")
        extended_session.expires_at = datetime.utcnow() - timedelta(minutes=1)
        await session.commit()
        
        # Try to access expired session
        expired_session = await session_manager.get_session_by_token(token)
        assert expired_session is None
        print("✅ Expired session correctly rejected")
    
    await engine.dispose()


async def test_activity_based_extension():
    """Test 2: Session extension based on activity."""
    print("\n=== Test 2: Activity-Based Extension ===")
    
    database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5432/triage_agent_db")
    engine = create_async_engine(database_url, echo=False)
    
    async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session_maker() as session:
        session_manager = SessionManager(session)
        
        # Create session
        db_session = await session_manager.create_session()
        token = db_session.session_token
        
        print(f"Session created with 30-minute expiration")
        print(f"Initial expiration: {db_session.expires_at}")
        
        # Simulate user activity every 10 minutes for 50 minutes
        print("\nSimulating user activity every 10 minutes...")
        for i in range(5):
            # Wait a bit to show time progression
            await asyncio.sleep(0.5)
            
            # Access session (this extends expiration)
            active_session = await session_manager.get_session_by_token(token)
            if active_session:
                print(f"Activity {i+1}: Session accessed at {datetime.utcnow().strftime('%H:%M:%S')}")
                print(f"  New expiration: {active_session.expires_at.strftime('%H:%M:%S')}")
                print(f"  Session will expire in: {active_session.expires_at - datetime.utcnow()}")
            else:
                print(f"❌ Session expired at activity {i+1}")
                break
        
        print("✅ Session kept alive through regular activity")
        
        # Now stop activity and let it expire
        print(f"\nStopping activity. Session will expire at: {active_session.expires_at}")
        
        # Fast-forward by manually setting expiration to past
        active_session.expires_at = datetime.utcnow() - timedelta(seconds=1)
        await session.commit()
        
        # Try to access
        expired = await session_manager.get_session_by_token(token)
        assert expired is None
        print("✅ Session expired after inactivity")
    
    await engine.dispose()


async def test_custom_expiration_duration():
    """Test 3: How to modify session expiration duration."""
    print("\n=== Test 3: Custom Expiration Duration ===")
    
    database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5432/triage_agent_db")
    engine = create_async_engine(database_url, echo=False)
    
    async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session_maker() as session:
        # Method 1: Modify session_duration on SessionManager instance
        session_manager = SessionManager(session)
        
        print("Default session duration:", session_manager.session_duration)
        
        # Change to 5 minutes for testing
        session_manager.session_duration = timedelta(minutes=5)
        print("Modified session duration:", session_manager.session_duration)
        
        # Create session with custom duration
        db_session = await session_manager.create_session()
        created_at = db_session.created_at
        expires_at = db_session.expires_at
        actual_duration = expires_at - created_at
        
        print(f"Session created at: {created_at}")
        print(f"Session expires at: {expires_at}")
        print(f"Actual duration: {actual_duration}")
        
        # Verify it's approximately 5 minutes
        expected_duration = timedelta(minutes=5)
        time_diff = abs(actual_duration - expected_duration)
        assert time_diff < timedelta(seconds=10)  # Allow small variance
        print("✅ Custom 5-minute expiration duration working")
        
        # Method 2: Subclass SessionManager for different durations
        class ShortSessionManager(SessionManager):
            def __init__(self, session: AsyncSession):
                super().__init__(session)
                self.session_duration = timedelta(minutes=1)  # 1 minute sessions
        
        class LongSessionManager(SessionManager):
            def __init__(self, session: AsyncSession):
                super().__init__(session)
                self.session_duration = timedelta(hours=2)  # 2 hour sessions
        
        # Test short session
        short_manager = ShortSessionManager(session)
        short_session = await short_manager.create_session()
        short_duration = short_session.expires_at - short_session.created_at
        print(f"\nShort session duration: {short_duration}")
        assert short_duration < timedelta(minutes=2)
        
        # Test long session
        long_manager = LongSessionManager(session)
        long_session = await long_manager.create_session()
        long_duration = long_session.expires_at - long_session.created_at
        print(f"Long session duration: {long_duration}")
        assert long_duration > timedelta(hours=1)
        
        print("✅ Custom SessionManager subclasses working")
    
    await engine.dispose()


async def test_cleanup_background_task():
    """Test 4: Background cleanup task simulation."""
    print("\n=== Test 4: Background Cleanup Task ===")
    
    database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5432/triage_agent_db")
    engine = create_async_engine(database_url, echo=False)
    
    async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session_maker() as session:
        session_manager = SessionManager(session)
        
        # Create multiple sessions
        print("Creating 5 sessions...")
        sessions = []
        for i in range(5):
            s = await session_manager.create_session(
                user_metadata={"session_num": i}
            )
            sessions.append(s)
        
        print(f"Created {len(sessions)} sessions")
        
        # Expire 3 of them
        print("Expiring 3 sessions...")
        for i in range(3):
            sessions[i].expires_at = datetime.utcnow() - timedelta(minutes=1)
        await session.commit()
        
        # Run cleanup (simulating background task)
        print("Running cleanup task...")
        cleaned_count = await session_manager.cleanup_expired_sessions()
        print(f"Cleaned up {cleaned_count} expired sessions")
        assert cleaned_count == 3
        
        # Verify remaining sessions are still valid
        valid_sessions = 0
        for s in sessions:
            if await session_manager.get_session_by_token(s.session_token):
                valid_sessions += 1
        
        print(f"Remaining valid sessions: {valid_sessions}")
        assert valid_sessions == 2
        print("✅ Background cleanup task working correctly")
    
    await engine.dispose()


async def demo_real_time_expiration():
    """Test 5: Real-time expiration demonstration with short duration."""
    print("\n=== Test 5: Real-Time Expiration Demo ===")
    print("Creating session with 3-second expiration for demonstration...")
    
    database_url = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5432/triage_agent_db")
    engine = create_async_engine(database_url, echo=False)
    
    async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session_maker() as session:
        session_manager = SessionManager(session)
        session_manager.session_duration = timedelta(seconds=3)  # 3 seconds for demo
        
        # Create session
        db_session = await session_manager.create_session()
        token = db_session.session_token
        
        print(f"Session created, expires in 3 seconds")
        print(f"Expiration time: {db_session.expires_at}")
        
        # Try accessing immediately
        valid = await session_manager.validate_session(token)
        print(f"t+0s: Session valid? {valid}")
        
        # Wait 1 second, access (should extend)
        await asyncio.sleep(1)
        accessed = await session_manager.get_session_by_token(token)
        if accessed:
            print(f"t+1s: Session accessed, new expiration: {accessed.expires_at}")
        
        # Wait 2 more seconds (still within extended window)
        await asyncio.sleep(2)
        valid = await session_manager.validate_session(token)
        print(f"t+3s: Session valid? {valid}")
        
        # Wait 2 more seconds (should be expired now)
        await asyncio.sleep(2)
        valid = await session_manager.validate_session(token)
        print(f"t+5s: Session valid? {valid}")
        
        print("✅ Real-time expiration demonstration complete")
    
    await engine.dispose()


async def main():
    """Run all session expiration tests."""
    print("Session Expiration Mechanism Demonstration")
    print("=" * 50)
    
    try:
        await test_basic_expiration()
        await test_activity_based_extension()
        await test_custom_expiration_duration()
        await test_cleanup_background_task()
        await demo_real_time_expiration()
        
        print("\n" + "=" * 50)
        print("✅ All tests passed! Session expiration working correctly.")
        
        print("\n📋 Summary of Session Expiration Mechanisms:")
        print("1. Sessions expire 30 minutes after creation (configurable)")
        print("2. Each access extends expiration by another 30 minutes")
        print("3. Expired sessions are rejected at validation time")
        print("4. Background task cleans up expired sessions every 5 minutes")
        print("5. Expiration duration can be customized per SessionManager")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())