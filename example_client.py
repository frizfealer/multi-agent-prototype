"""
Example client demonstrating session-based chat with the Triage Agent API.
"""
import asyncio
import httpx
import json
from datetime import datetime


class TriageAgentClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session_token = None
        self.session_id = None
        self.headers = {"Content-Type": "application/json"}

    async def create_session(self, user_metadata: dict = None):
        """Create a new session."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/session/create",
                json={"user_metadata": user_metadata or {}},
                headers=self.headers
            )
            response.raise_for_status()
            data = response.json()
            
            self.session_token = data["session_token"]
            self.session_id = data["session_id"]
            self.headers["Authorization"] = f"Bearer {self.session_token}"
            
            print(f"✅ Session created: {self.session_id}")
            print(f"   Expires at: {data['expires_at']}")
            return data

    async def chat(self, message: str, conversation_id: str = None):
        """Send a chat message."""
        if not self.session_token:
            raise ValueError("No active session. Call create_session() first.")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/chat",
                json={
                    "message": message,
                    "conversation_id": conversation_id
                },
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()

    async def get_session_info(self):
        """Get information about the current session."""
        if not self.session_token:
            raise ValueError("No active session.")
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/v1/session/info",
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()

    async def logout(self):
        """Expire the current session."""
        if not self.session_token:
            return
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/session/logout",
                headers=self.headers
            )
            response.raise_for_status()
            
            self.session_token = None
            self.session_id = None
            print("✅ Logged out successfully")


async def demo_session_flow():
    """Demonstrate a complete session flow."""
    client = TriageAgentClient()
    
    try:
        # 1. Create a session with user metadata
        print("\n=== Creating Session ===")
        await client.create_session({
            "user_id": "demo_user_123",
            "preferences": {
                "fitness_level": "intermediate",
                "goals": ["muscle_gain", "endurance"]
            }
        })
        
        # 2. Start a conversation
        print("\n=== Starting Conversation ===")
        response = await client.chat("I need help planning my fitness routine")
        print(f"Agent: {response['text']}")
        print(f"Conversation ID: {response['conversation_id']}")
        conversation_id = response['conversation_id']
        
        # 3. Continue the conversation
        print("\n=== Continuing Conversation ===")
        response = await client.chat(
            "I want to build muscle and improve my running",
            conversation_id
        )
        print(f"Agent: {response['text']}")
        if response.get('action'):
            print(f"Action: {json.dumps(response['action'], indent=2)}")
        
        # 4. Get session info
        print("\n=== Session Information ===")
        info = await client.get_session_info()
        print(f"Session ID: {info['session_id']}")
        print(f"Created: {info['created_at']}")
        print(f"Last accessed: {info['last_accessed']}")
        print(f"Expires: {info['expires_at']}")
        print(f"Conversations: {info['conversation_count']}")
        
        # 5. Start another conversation in the same session
        print("\n=== Starting New Conversation ===")
        response = await client.chat("Delete my old workout plan called 'Summer Shred'")
        print(f"Agent: {response['text']}")
        if response.get('action'):
            print(f"Action: {json.dumps(response['action'], indent=2)}")
        
        # 6. Get updated session info
        print("\n=== Updated Session Information ===")
        info = await client.get_session_info()
        print(f"Total conversations: {info['conversation_count']}")
        for conv in info['conversations']:
            print(f"  - {conv['conversation_id']} (Agent: {conv['current_agent']})")
        
        # 7. Logout
        print("\n=== Logging Out ===")
        await client.logout()
        
        # 8. Try to use expired session (should fail)
        print("\n=== Testing Expired Session ===")
        try:
            await client.chat("This should fail")
        except httpx.HTTPStatusError as e:
            print(f"❌ Expected error: {e.response.status_code} - Session expired")
    
    except Exception as e:
        print(f"Error: {e}")


async def demo_session_expiration():
    """Demonstrate session expiration after 30 minutes."""
    client = TriageAgentClient()
    
    print("\n=== Session Expiration Demo ===")
    print("Note: In production, sessions expire after 30 minutes of inactivity")
    print("Each request extends the session by another 30 minutes")
    
    # Create session
    await client.create_session()
    
    # Show initial expiration
    info = await client.get_session_info()
    print(f"Session expires at: {info['expires_at']}")
    
    # Wait and make request
    print("\nWaiting 2 seconds...")
    await asyncio.sleep(2)
    
    # Make a request (this extends the session)
    await client.chat("Hello")
    
    # Show updated expiration
    info = await client.get_session_info()
    print(f"After activity, expires at: {info['expires_at']}")


if __name__ == "__main__":
    print("Triage Agent Client Demo")
    print("========================")
    
    # Run the main demo
    asyncio.run(demo_session_flow())
    
    # Run the expiration demo
    asyncio.run(demo_session_expiration())