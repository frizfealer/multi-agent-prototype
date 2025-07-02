# Session Expiration Guide

## How 30-Minute Auto-Expiration Works

### 1. **Database-Driven Expiration**

Sessions are expired using database timestamps, not timers:

```python
# Each session has an expires_at timestamp
session.expires_at = datetime.utcnow() + timedelta(minutes=30)

# Validation query automatically filters expired sessions
stmt = select(Session).where(
    and_(
        Session.session_token == token,
        Session.is_active == True,
        Session.expires_at > datetime.utcnow()  # ← Auto-expiration here
    )
)
```

### 2. **Activity-Based Extension**

Every API request extends the session:

```python
# In SessionManager.get_session_by_token()
if session:
    session.last_accessed = datetime.utcnow()
    session.expires_at = datetime.utcnow() + self.session_duration  # Reset to 30 min from now
    await self.session.commit()
```

### 3. **Timeline Example**

```
10:00 AM - User creates session → expires_at = 10:30 AM
10:15 AM - User sends message → expires_at = 10:45 AM (extended!)
10:20 AM - User sends message → expires_at = 10:50 AM (extended again!)
...no activity for 30 minutes...
11:20 AM - User tries to send message → 401 Unauthorized (expired)
```

### 4. **Background Cleanup**

A background task removes expired sessions every 5 minutes:

```python
async def cleanup_expired_sessions():
    while True:
        session_manager = SessionManager(session)
        count = await session_manager.cleanup_expired_sessions()
        await asyncio.sleep(300)  # 5 minutes
```

## How to Modify Expiration Duration

### Method 1: Change Default Duration

```python
# Modify the SessionManager instance
session_manager = SessionManager(db_session)
session_manager.session_duration = timedelta(hours=1)  # 1-hour sessions
```

### Method 2: Environment-Based Configuration

```python
# src/core/config.py
class Settings(BaseSettings):
    session_duration_minutes: int = 30  # Default 30 minutes
    
# Usage
settings = Settings()
session_manager.session_duration = timedelta(minutes=settings.session_duration_minutes)
```

### Method 3: User-Type Based Sessions

```python
class UserTypeSessionManager(SessionManager):
    USER_DURATIONS = {
        "guest": timedelta(minutes=15),      # 15 minutes
        "registered": timedelta(minutes=30), # 30 minutes  
        "premium": timedelta(hours=2),       # 2 hours
        "admin": timedelta(hours=8),         # 8 hours
    }
    
    def __init__(self, session, user_type="registered"):
        super().__init__(session)
        self.session_duration = self.USER_DURATIONS.get(user_type, timedelta(minutes=30))
```

### Method 4: Custom Session Factory

```python
def create_session_manager(db_session, environment="production"):
    duration_map = {
        "development": timedelta(hours=8),    # Long for development
        "testing": timedelta(seconds=30),     # Short for tests
        "staging": timedelta(minutes=15),     # Medium for staging
        "production": timedelta(minutes=30),  # Standard for production
    }
    
    session_manager = SessionManager(db_session)
    session_manager.session_duration = duration_map.get(environment, timedelta(minutes=30))
    return session_manager
```

### Method 5: Dynamic Duration

```python
async def create_session_with_activity_level(session_manager, activity="normal"):
    duration_map = {
        "low": timedelta(minutes=15),      # Casual users
        "normal": timedelta(minutes=30),   # Regular users  
        "high": timedelta(hours=1),        # Power users
        "intensive": timedelta(hours=4),   # Heavy usage
    }
    
    original_duration = session_manager.session_duration
    session_manager.session_duration = duration_map[activity]
    
    session = await session_manager.create_session()
    
    session_manager.session_duration = original_duration  # Restore
    return session
```

## Key Implementation Details

### 1. **No Timers Required**
- Sessions don't need individual timers
- Database timestamp comparison handles expiration
- Works even if server restarts

### 2. **Sliding Window Expiration**
- Each request resets the 30-minute timer
- "Use it or lose it" approach
- Active users stay logged in indefinitely

### 3. **Immediate Validation**
- Expired sessions rejected instantly on auth check
- No need to wait for cleanup task
- Query-level filtering ensures consistency

### 4. **Efficient Cleanup**
- Background task removes expired sessions from database
- Prevents database bloat
- Configurable cleanup interval

### 5. **Session Extension Logic**

```python
# Every API request triggers this:
def extend_session(session):
    if session.expires_at > datetime.utcnow():  # Still valid
        session.expires_at = datetime.utcnow() + SESSION_DURATION  # Extend
        session.last_accessed = datetime.utcnow()
        return True
    else:  # Already expired
        return False  # Don't extend, session is dead
```

## Testing Session Expiration

### Quick Test with Short Duration

```python
# Create 5-second sessions for testing
session_manager = SessionManager(db_session)
session_manager.session_duration = timedelta(seconds=5)

session = await session_manager.create_session()
print(f"Session expires at: {session.expires_at}")

# Wait 3 seconds, access (should extend)
await asyncio.sleep(3)
valid = await session_manager.validate_session(session.session_token)
print(f"After 3s: Valid = {valid}")

# Wait 6 more seconds (should expire)
await asyncio.sleep(6)  
valid = await session_manager.validate_session(session.session_token)
print(f"After 9s total: Valid = {valid}")  # Should be False
```

### Real-Time Demo

Run the demonstration:
```bash
python demo_session_expiration.py
```

This shows:
- Basic 30-minute expiration
- Activity-based extension
- Custom durations
- User-type based sessions
- Cleanup mechanism
- Realistic API flow

## Production Considerations

### 1. **Security**
- Sessions auto-expire for security
- No way to disable expiration completely
- Tokens are cryptographically secure

### 2. **Performance**
- Database index on `session_token` for fast lookups
- Index on `expires_at` for efficient cleanup
- Background cleanup prevents table bloat

### 3. **Monitoring**
- Log cleanup statistics
- Monitor session duration patterns
- Track expired session attempts

### 4. **Configuration**
- Environment-specific durations
- User-type based policies
- Dynamic adjustment based on load

This mechanism provides automatic, secure session management with no manual intervention required!