"""
Session configuration options and customization examples.
"""

from datetime import timedelta
from enum import Enum
from typing import Dict

from src.core.session_manager import SessionManager


class SessionDuration(Enum):
    """Predefined session duration options."""

    SHORT = timedelta(minutes=15)  # 15 minutes
    STANDARD = timedelta(minutes=30)  # 30 minutes (default)
    LONG = timedelta(hours=2)  # 2 hours
    EXTENDED = timedelta(hours=8)  # 8 hours
    DEV_TEST = timedelta(seconds=30)  # 30 seconds (for testing)


class ConfigurableSessionManager(SessionManager):
    """SessionManager with configurable expiration duration."""

    def __init__(self, session, duration: timedelta = None, duration_preset: SessionDuration = None):
        super().__init__(session)

        if duration_preset:
            self.session_duration = duration_preset.value
        elif duration:
            self.session_duration = duration
        # else use default from parent class


class UserTypeSessionManager(SessionManager):
    """SessionManager that sets duration based on user type."""

    USER_TYPE_DURATIONS: Dict[str, timedelta] = {
        "guest": timedelta(minutes=15),  # Guest users: 15 minutes
        "registered": timedelta(minutes=30),  # Registered users: 30 minutes
        "premium": timedelta(hours=2),  # Premium users: 2 hours
        "admin": timedelta(hours=8),  # Admin users: 8 hours
    }

    def __init__(self, session, user_type: str = "registered"):
        super().__init__(session)
        self.session_duration = self.USER_TYPE_DURATIONS.get(user_type, timedelta(minutes=30))  # Default fallback


class DynamicSessionManager(SessionManager):
    """SessionManager that adjusts duration based on usage patterns."""

    def __init__(self, session):
        super().__init__(session)

    async def create_session_with_dynamic_duration(
        self, ip_address=None, user_agent=None, user_metadata=None, activity_level="normal"
    ):
        """Create session with duration based on expected activity level."""

        # Adjust duration based on activity level
        duration_map = {
            "low": timedelta(minutes=15),  # Casual users
            "normal": timedelta(minutes=30),  # Regular users
            "high": timedelta(hours=1),  # Power users
            "intensive": timedelta(hours=4),  # Heavy usage sessions
        }

        # Temporarily override duration
        original_duration = self.session_duration
        self.session_duration = duration_map.get(activity_level, timedelta(minutes=30))

        # Create session
        session = await self.create_session(ip_address, user_agent, user_metadata)

        # Restore original duration
        self.session_duration = original_duration

        return session


# Configuration examples for different environments
class SessionConfig:
    """Session configuration for different environments."""

    DEVELOPMENT = {
        "duration": timedelta(hours=8),  # Long sessions for development
        "cleanup_interval": timedelta(minutes=1),  # Frequent cleanup for testing
    }

    TESTING = {
        "duration": timedelta(seconds=30),  # Short sessions for fast tests
        "cleanup_interval": timedelta(seconds=10),  # Very frequent cleanup
    }

    STAGING = {
        "duration": timedelta(minutes=15),  # Shorter sessions for staging
        "cleanup_interval": timedelta(minutes=5),
    }

    PRODUCTION = {
        "duration": timedelta(minutes=30),  # Standard 30-minute sessions
        "cleanup_interval": timedelta(minutes=5),
    }

    @classmethod
    def get_config(cls, environment: str = "production"):
        """Get configuration for specific environment."""
        return getattr(cls, environment.upper(), cls.PRODUCTION)


def create_session_manager_for_environment(session, environment="production"):
    """Factory function to create SessionManager for specific environment."""
    config = SessionConfig.get_config(environment)

    class EnvironmentSessionManager(SessionManager):
        def __init__(self, db_session):
            super().__init__(db_session)
            self.session_duration = config["duration"]

    return EnvironmentSessionManager(session)


# Usage examples:


def example_usage():
    """Examples of how to use different session configurations."""

    # Example 1: Basic duration override
    # session_manager = ConfigurableSessionManager(
    #     db_session,
    #     duration=timedelta(hours=1)
    # )

    # Example 2: Using preset durations
    # session_manager = ConfigurableSessionManager(
    #     db_session,
    #     duration_preset=SessionDuration.LONG
    # )

    # Example 3: User-type based sessions
    # session_manager = UserTypeSessionManager(db_session, user_type="premium")

    # Example 4: Environment-based configuration
    # session_manager = create_session_manager_for_environment(db_session, "development")

    # Example 5: Dynamic duration based on activity
    # dynamic_manager = DynamicSessionManager(db_session)
    # session = await dynamic_manager.create_session_with_dynamic_duration(
    #     activity_level="high",
    #     user_metadata={"expected_session_length": "long"}
    # )

    pass
