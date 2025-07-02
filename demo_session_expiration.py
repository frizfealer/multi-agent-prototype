"""
Session Expiration Mechanism Demonstration
==========================================

This script demonstrates how the 30-minute session expiration works
and how to modify expiration durations.
"""
import asyncio
from datetime import datetime, timedelta


class MockSession:
    """Mock session for demonstration purposes."""
    def __init__(self, duration=timedelta(minutes=30)):
        self.created_at = datetime.now()
        self.last_accessed = datetime.now()
        self.expires_at = datetime.now() + duration
        self.session_duration = duration
        self.is_active = True
    
    def access(self):
        """Simulate accessing the session (extends expiration)."""
        if self.is_expired():
            return False
        
        self.last_accessed = datetime.now()
        # Key: Extend expiration by full duration from now
        self.expires_at = datetime.now() + self.session_duration
        return True
    
    def is_expired(self):
        """Check if session is expired."""
        return datetime.now() > self.expires_at
    
    def time_until_expiry(self):
        """Get time remaining until expiration."""
        if self.is_expired():
            return timedelta(0)
        return self.expires_at - datetime.now()


def demo_basic_expiration():
    """Demonstrate basic 30-minute expiration."""
    print("=== Demo 1: Basic 30-Minute Expiration ===")
    
    # Create session with 30-minute expiration
    session = MockSession(duration=timedelta(minutes=30))
    
    print(f"Session created at: {session.created_at.strftime('%H:%M:%S')}")
    print(f"Initial expiration: {session.expires_at.strftime('%H:%M:%S')}")
    print(f"Time until expiry: {session.time_until_expiry()}")
    print()
    
    # Simulate accessing session after 10 minutes
    print("⏰ 10 minutes pass...")
    session.last_accessed = datetime.now() + timedelta(minutes=10)
    # Manually simulate time passing for demo
    session.expires_at = session.created_at + timedelta(minutes=20)  # 20 minutes left
    
    print("📱 User accesses session...")
    if session.access():
        print(f"✅ Session extended! New expiration: {session.expires_at.strftime('%H:%M:%S')}")
        print(f"Time until expiry: {session.time_until_expiry()}")
    else:
        print("❌ Session was already expired")
    
    print()


def demo_activity_extension():
    """Demonstrate how activity extends sessions."""
    print("=== Demo 2: Activity-Based Extension ===")
    
    session = MockSession(duration=timedelta(seconds=10))  # 10 seconds for demo
    
    print(f"Session created with 10-second expiration")
    print(f"Initial expiration: {session.expires_at.strftime('%H:%M:%S.%f')[:-3]}")
    
    # Simulate regular activity
    for i in range(5):
        print(f"\n⏰ Activity {i+1}:")
        
        # Wait a bit
        import time
        time.sleep(0.5)
        
        if session.access():
            print(f"   ✅ Session accessed at {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
            print(f"   📅 New expiration: {session.expires_at.strftime('%H:%M:%S.%f')[:-3]}")
            print(f"   ⏳ Time remaining: {session.time_until_expiry()}")
        else:
            print(f"   ❌ Session expired!")
            break
    
    # Stop activity and let it expire
    print(f"\n🛑 Stopping activity...")
    time.sleep(1)
    
    if session.is_expired():
        print(f"❌ Session expired at {datetime.now().strftime('%H:%M:%S.%f')[:-3]}")
    
    print()


def demo_custom_durations():
    """Demonstrate different session durations."""
    print("=== Demo 3: Custom Session Durations ===")
    
    durations = [
        ("Short (15 min)", timedelta(minutes=15)),
        ("Standard (30 min)", timedelta(minutes=30)),
        ("Long (2 hours)", timedelta(hours=2)),
        ("Extended (8 hours)", timedelta(hours=8)),
        ("Dev Test (30 sec)", timedelta(seconds=30)),
    ]
    
    for name, duration in durations:
        session = MockSession(duration)
        print(f"{name:20} | Expires: {session.expires_at.strftime('%H:%M:%S')} | Duration: {duration}")
    
    print()


def demo_user_type_sessions():
    """Demonstrate different durations based on user type."""
    print("=== Demo 4: User-Type Based Durations ===")
    
    user_types = {
        "guest": timedelta(minutes=15),
        "registered": timedelta(minutes=30),
        "premium": timedelta(hours=2),
        "admin": timedelta(hours=8),
    }
    
    for user_type, duration in user_types.items():
        session = MockSession(duration)
        print(f"{user_type.capitalize():12} | Duration: {str(duration):8} | Expires: {session.expires_at.strftime('%H:%M:%S')}")
    
    print()


def demo_cleanup_mechanism():
    """Demonstrate how expired sessions are cleaned up."""
    print("=== Demo 5: Cleanup Mechanism ===")
    
    # Simulate multiple sessions
    sessions = []
    
    # Create 5 sessions with different states
    for i in range(5):
        duration = timedelta(seconds=5) if i < 3 else timedelta(minutes=30)
        session = MockSession(duration)
        session.session_id = f"session_{i+1}"
        sessions.append(session)
    
    print("Created 5 sessions:")
    for session in sessions:
        status = "Active" if not session.is_expired() else "Expired"
        print(f"  {session.session_id}: {status} (expires: {session.expires_at.strftime('%H:%M:%S')})")
    
    # Simulate time passing
    import time
    print("\n⏰ Waiting 6 seconds for some sessions to expire...")
    time.sleep(6)
    
    # Check which sessions are expired
    expired_sessions = [s for s in sessions if s.is_expired()]
    active_sessions = [s for s in sessions if not s.is_expired()]
    
    print(f"\n🧹 Cleanup: Found {len(expired_sessions)} expired sessions")
    for session in expired_sessions:
        print(f"  ❌ Removing {session.session_id}")
    
    print(f"\n✅ Remaining active sessions: {len(active_sessions)}")
    for session in active_sessions:
        print(f"  ✅ {session.session_id} (expires in {session.time_until_expiry()})")
    
    print()


async def demo_real_api_flow():
    """Demonstrate realistic API flow with session management."""
    print("=== Demo 6: Realistic API Flow ===")
    
    # Simulate session creation
    session = MockSession(duration=timedelta(seconds=5))  # 5 seconds for demo
    session_token = "abc123xyz789"
    
    print(f"1. 🔐 Session created with token: {session_token}")
    print(f"   Expires at: {session.expires_at.strftime('%H:%M:%S')}")
    
    # Simulate API requests
    api_calls = [
        "POST /api/v1/chat",
        "GET /api/v1/session/info", 
        "POST /api/v1/chat",
        "POST /api/v1/chat"
    ]
    
    for i, api_call in enumerate(api_calls):
        await asyncio.sleep(1)  # 1 second between calls
        
        print(f"\n{i+2}. 📡 API Request: {api_call}")
        
        # Check session validity (this happens in auth middleware)
        if session.is_expired():
            print(f"   ❌ 401 Unauthorized - Session expired")
            break
        else:
            # Session is valid, extend it
            session.access()
            print(f"   ✅ 200 OK - Session extended")
            print(f"   📅 New expiration: {session.expires_at.strftime('%H:%M:%S')}")
    
    # Try one more call after letting session expire
    await asyncio.sleep(6)
    print(f"\n6. 📡 API Request: POST /api/v1/chat (after long delay)")
    if session.is_expired():
        print(f"   ❌ 401 Unauthorized - Session expired")
        print(f"   💡 Client needs to create new session")
    
    print()


def show_configuration_examples():
    """Show how to configure different session durations."""
    print("=== Configuration Examples ===")
    
    print("""
# 1. Basic Duration Override
session_manager = SessionManager(db_session)
session_manager.session_duration = timedelta(hours=1)  # 1-hour sessions

# 2. Environment-Based Configuration
if environment == "development":
    session_duration = timedelta(hours=8)  # Long sessions for dev
elif environment == "production":
    session_duration = timedelta(minutes=30)  # Standard for prod

# 3. User-Type Based Sessions
class UserTypeSessionManager(SessionManager):
    def __init__(self, db_session, user_type="registered"):
        super().__init__(db_session)
        durations = {
            "guest": timedelta(minutes=15),
            "registered": timedelta(minutes=30),
            "premium": timedelta(hours=2),
            "admin": timedelta(hours=8),
        }
        self.session_duration = durations.get(user_type, timedelta(minutes=30))

# 4. Dynamic Duration Based on Activity
async def create_session_with_activity_level(activity="normal"):
    durations = {
        "low": timedelta(minutes=15),
        "normal": timedelta(minutes=30),
        "high": timedelta(hours=1),
        "intensive": timedelta(hours=4),
    }
    session_manager.session_duration = durations[activity]
    return await session_manager.create_session()
""")


async def main():
    """Run all demonstration scenarios."""
    print("🔐 Session Expiration Mechanism Demonstration")
    print("=" * 50)
    
    demo_basic_expiration()
    demo_activity_extension()
    demo_custom_durations()
    demo_user_type_sessions()
    demo_cleanup_mechanism()
    await demo_real_api_flow()
    show_configuration_examples()
    
    print("=" * 50)
    print("✅ Key Takeaways:")
    print("1. Sessions expire 30 minutes after creation (configurable)")
    print("2. Each API request extends the session by another 30 minutes")
    print("3. Expired sessions are rejected immediately during auth")
    print("4. Background cleanup removes expired sessions from database")
    print("5. Duration can be customized per user type or environment")
    print("6. No timers needed - database timestamps handle everything")


if __name__ == "__main__":
    asyncio.run(main())