import asyncio
import json
import uuid
from datetime import datetime
from typing import Optional

import aiohttp
import websockets


class DynamicExercisePlanningClient:
    def __init__(self, base_url="http://localhost:8000", ws_url="ws://localhost:8000"):
        self.base_url = base_url
        self.ws_url = ws_url
        self.session_id = str(uuid.uuid4())
        self.websocket = None
        self.received_messages = []
        self.final_plan_count = 0
        self.requirements_sent = 0
        self.requirements_history = []

    async def send_chat_request(self, message: str, is_update: bool = False):
        """Send a chat request to the HTTP endpoint"""
        async with aiohttp.ClientSession() as session:
            data = {"message": message, "session_id": self.session_id, "is_update": is_update}

            async with session.post(f"{self.base_url}/chat", json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    if not is_update:
                        self.requirements_sent = 1
                    else:
                        self.requirements_sent += 1
                    
                    # Track requirement text
                    self.requirements_history.append(message)
                    
                    update_type = "update" if is_update else "initial request"
                    print(f"✅ {update_type.title()} sent successfully (Requirement #{self.requirements_sent})")
                    print(f"Response: {result['message']}")
                    print(f"Status: {result['status']}")
                    return result
                else:
                    print(f"❌ Error: {response.status}")
                    error_text = await response.text()
                    print(f"Error details: {error_text}")
                    return None

    async def connect_websocket(self):
        """Connect to WebSocket and keep connection open"""
        ws_endpoint = f"{self.ws_url}/ws/{self.session_id}"
        print(f"🔗 Connecting to WebSocket: {ws_endpoint}")

        try:
            self.websocket = await websockets.connect(ws_endpoint)
            print("✅ WebSocket connected, ready for updates...")
            return True
        except Exception as e:
            print(f"❌ WebSocket connection failed: {e}")
            return False

    async def listen_to_websocket(self, timeout: Optional[float] = None):
        """Listen to WebSocket for real-time updates"""
        if not self.websocket:
            print("❌ WebSocket not connected")
            return

        try:
            start_time = asyncio.get_event_loop().time()

            async for message in self.websocket:
                try:
                    # Parse JSON message
                    data = json.loads(message)
                    message_type = data.get("type", "unknown")
                    content = data.get("content", message)
                    timestamp = data.get("timestamp", datetime.now().isoformat())

                    self.received_messages.append(data)

                    # Format timestamp
                    try:
                        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                        time_str = dt.strftime("%H:%M:%S")
                    except:
                        time_str = datetime.now().strftime("%H:%M:%S")

                    # Display message with type
                    print(f"\n📨 [{time_str}] {message_type.upper()}:")
                    print("-" * 60)
                    print(content)
                    print("-" * 60)

                    # Check if this is a final plan
                    if message_type == "final_plan":
                        self.final_plan_count += 1
                        current_requirement = self.requirements_history[-1] if self.requirements_history else "Unknown"
                        print(f"🎉 Final plan #{self.final_plan_count} received!")
                        print(f"📋 This plan addresses requirement #{self.requirements_sent}:")
                        print(f"   '{current_requirement}'")
                        print("=" * 80)
                        # Don't break immediately - wait for potential additional updates
                        continue

                except json.JSONDecodeError:
                    # Handle non-JSON messages
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    print(f"\n📨 [{timestamp}] MESSAGE:")
                    print("-" * 50)
                    print(message)
                    print("-" * 50)

                    if "Here is your" in message and "plan" in message:
                        print("🎉 Final plan received! Closing connection.")
                        break

                # Check timeout
                if timeout and (asyncio.get_event_loop().time() - start_time) > timeout:
                    print(f"⏰ Timeout reached ({timeout}s)")
                    break

        except websockets.exceptions.ConnectionClosed:
            print("🔌 WebSocket connection closed")
        except Exception as e:
            print(f"❌ WebSocket error: {e}")

    async def send_update_via_websocket(self, update_message: str):
        """Send an update via WebSocket"""
        if not self.websocket:
            print("❌ WebSocket not connected")
            return False

        try:
            update_data = {"type": "update_requirements", "message": update_message}
            await self.websocket.send(json.dumps(update_data))
            print(f"📤 Update sent via WebSocket: {update_message[:100]}...")
            return True
        except Exception as e:
            print(f"❌ Error sending WebSocket update: {e}")
            return False

    async def get_session_status(self):
        """Check the status of the current session"""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.base_url}/sessions/{self.session_id}/status") as response:
                if response.status == 200:
                    result = await response.json()
                    return result
                else:
                    return None

    async def get_requirements_history(self):
        """Get the requirements history for the session"""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.base_url}/sessions/{self.session_id}/requirements") as response:
                if response.status == 200:
                    result = await response.json()
                    return result
                else:
                    return None

    async def close_websocket(self):
        """Close the WebSocket connection"""
        if self.websocket:
            await self.websocket.close()
            print("🔌 WebSocket connection closed")

    async def run_with_updates(self, initial_message: str, updates: list, update_delays: list = None):
        """Run a complete flow with multiple updates"""
        print("🚀 Starting dynamic exercise planning session")
        print(f"Session ID: {self.session_id}")
        print(f"Initial Request: {initial_message}")
        print(f"Planned Updates: {len(updates)}")
        print("=" * 80)

        # Connect to WebSocket
        if not await self.connect_websocket():
            return

        # Start listening to WebSocket in background (longer timeout for multiple updates)
        listen_task = asyncio.create_task(self.listen_to_websocket(timeout=180))

        # Give WebSocket a moment to connect
        await asyncio.sleep(1)

        # Send initial request
        initial_response = await self.send_chat_request(initial_message, is_update=False)
        if not initial_response:
            print("Failed to send initial request")
            await self.close_websocket()
            return

        # Send updates with delays
        if not update_delays:
            update_delays = [10] * len(updates)  # Default 10 second delays

        for i, (update, delay) in enumerate(zip(updates, update_delays)):
            print(f"\n⏳ Waiting {delay} seconds before sending update {i+1}...")
            await asyncio.sleep(delay)

            print(f"\n🔄 Sending update {i+1}: {update}")
            update_response = await self.send_chat_request(update, is_update=True)

            if not update_response:
                print(f"Failed to send update {i+1}")
                continue

        # Wait for all updates to be processed
        try:
            await listen_task
        except asyncio.CancelledError:
            print("Listening task was cancelled")

        # Get final status and requirements history
        print("\n" + "=" * 80)
        status = await self.get_session_status()
        if status:
            print("📊 Final session status:")
            print(f"  Status: {status.get('status', 'unknown')}")
            print(f"  Processing: {status.get('processing', False)}")
            print(f"  Requirements count: {status.get('requirements_count', 0)}")
            print(f"  Has final plan: {status.get('has_final_plan', False)}")

        requirements = await self.get_requirements_history()
        if requirements:
            print("\n📝 Requirements History:")
            print(f"  Original: {requirements.get('original_request', '')}")
            print(f"  Current: {requirements.get('current_request', '')}")
            print("  All updates:")
            for i, req in enumerate(requirements.get("requirements_history", [])):
                print(f"    {i+1}. {req}")
            
            print(f"\n📊 Session Summary:")
            print(f"  Total requirements sent: {self.requirements_sent}")
            print(f"  Total final plans received: {self.final_plan_count}")
            if self.final_plan_count < self.requirements_sent:
                print(f"  ⚠️  Missing {self.requirements_sent - self.final_plan_count} final plan(s) - may still be processing")

        await self.close_websocket()


# Example usage functions
async def example_basic_with_updates():
    """Basic example with requirement updates"""
    client = DynamicExercisePlanningClient()

    initial_message = "I want to make an exercise plan to grow wider in six weeks, working out 2-3 times per week."

    updates = [
        "Actually, I can only work out 2 times per week, not 3.",
        "I forgot to mention - I only have access to dumbbells, no gym equipment.",
        "Can you focus more on shoulders and less on back muscles?",
    ]

    update_delays = [8, 12, 8]  # Wait these many seconds between updates

    await client.run_with_updates(initial_message, updates, update_delays)


async def example_major_requirement_changes():
    """Example with major requirement changes that should trigger re-evaluation"""
    client = DynamicExercisePlanningClient()

    initial_message = "Create a 6-week plan to build wider shoulders, 3 times per week with gym access."

    updates = [
        "Change of plans - I want to focus on building a wider back instead of shoulders.",
        "I need to change this to an 8-week program instead of 6 weeks.",
        "Actually, I can only work out at home with resistance bands now.",
    ]

    update_delays = [10, 15, 10]

    await client.run_with_updates(initial_message, updates, update_delays)


async def example_minor_clarifications():
    """Example with minor clarifications that shouldn't trigger full re-evaluation"""
    client = DynamicExercisePlanningClient()

    initial_message = "I want a 6-week plan to get wider, working out 3 times per week."

    updates = [
        "Just to clarify - when I say 'wider', I mean broader shoulders and lats.",
        "I should mention I'm an intermediate lifter, not a beginner.",
        "Oh, and I prefer compound movements over isolation exercises.",
    ]

    update_delays = [8, 10, 8]

    await client.run_with_updates(initial_message, updates, update_delays)


async def example_websocket_updates():
    """Example using WebSocket for updates instead of HTTP"""
    client = DynamicExercisePlanningClient()

    print("🚀 Testing WebSocket-based updates")
    print(f"Session ID: {client.session_id}")
    print("=" * 60)

    # Connect WebSocket first
    if not await client.connect_websocket():
        return

    # Start listening
    listen_task = asyncio.create_task(client.listen_to_websocket(timeout=60))
    await asyncio.sleep(1)

    # Send initial HTTP request
    initial_message = "Create a plan to build wider lats, 3 times weekly for 6 weeks."
    await client.send_chat_request(initial_message, is_update=False)

    # Send updates via WebSocket
    updates = ["Update: I can only do 2 workouts per week", "Another update: Focus on home workouts only"]

    for i, update in enumerate(updates):
        await asyncio.sleep(10)  # Wait 10 seconds
        print(f"\n🔄 Sending WebSocket update {i+1}")
        await client.send_update_via_websocket(update)

    # Wait for processing to complete
    try:
        await listen_task
    except asyncio.CancelledError:
        pass

    await client.close_websocket()


# Health check function
async def check_server_health():
    """Check if the server is running and healthy"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("http://localhost:8000/health") as response:
                if response.status == 200:
                    health_data = await response.json()
                    print("✅ Server is healthy!")
                    print(f"Status: {health_data['status']}")
                    print(f"Active sessions: {health_data['active_sessions']}")
                    if health_data.get("sessions"):
                        print(f"Session IDs: {health_data['sessions']}")
                    return True
                else:
                    print(f"❌ Server health check failed: {response.status}")
                    return False
    except Exception as e:
        print(f"❌ Cannot connect to server: {e}")
        print("Make sure the server is running on http://localhost:8000")
        return False


# Advanced testing functions
async def test_concurrent_sessions_with_updates():
    """Test multiple concurrent sessions each with their own updates"""
    print("🔄 Testing concurrent sessions with dynamic updates...")

    tasks = []

    # Session 1: Basic updates
    client1 = DynamicExercisePlanningClient()
    task1 = asyncio.create_task(
        client1.run_with_updates(
            "6-week wider back plan, 3x/week", ["Change to 2x/week", "Focus on home workouts"], [8, 8]
        )
    )
    tasks.append(("Session 1", task1))

    # Session 2: Major changes
    client2 = DynamicExercisePlanningClient()
    task2 = asyncio.create_task(
        client2.run_with_updates(
            "Build wider shoulders in 4 weeks", ["Actually make it 8 weeks", "Change focus to back instead"], [10, 12]
        )
    )
    tasks.append(("Session 2", task2))

    # Stagger the start times
    await asyncio.sleep(3)

    # Session 3: Minor clarifications
    client3 = DynamicExercisePlanningClient()
    task3 = asyncio.create_task(
        client3.run_with_updates(
            "Get wider muscles, any suggestions?", ["I mean back and shoulders", "I'm intermediate level"], [6, 6]
        )
    )
    tasks.append(("Session 3", task3))

    # Wait for all to complete
    print("⏳ Waiting for all sessions to complete...")
    for name, task in tasks:
        try:
            await task
            print(f"✅ {name} completed")
        except Exception as e:
            print(f"❌ {name} failed: {e}")

    print("\n🎉 All concurrent sessions completed!")


# Main execution
async def main():
    """Main function to run examples"""
    print("🏋️ Dynamic Exercise Planning System Client")
    print("=" * 50)

    # Check server health first
    if not await check_server_health():
        print("\n❌ Server is not available. Please start the server first:")
        print("python exercise_planning_system.py")
        return

    print("\n" + "=" * 50)
    print("Choose an example to run:")
    print("1. Basic request with updates")
    print("2. Major requirement changes")
    print("3. Minor clarifications")
    print("4. WebSocket-based updates")
    print("5. Concurrent sessions with updates")
    print("=" * 50)

    choice = input("Enter your choice (1-5): ").strip()

    if choice == "1":
        await example_basic_with_updates()
    elif choice == "2":
        await example_major_requirement_changes()
    elif choice == "3":
        await example_minor_clarifications()
    elif choice == "4":
        await example_websocket_updates()
    elif choice == "5":
        await test_concurrent_sessions_with_updates()
    else:
        print("Invalid choice, running basic example...")
        await example_basic_with_updates()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Client stopped by user")
    except Exception as e:
        print(f"❌ Error: {e}")


# Quick test functions
async def quick_test_updates():
    """Quick test of update functionality"""
    client = DynamicExercisePlanningClient()
    await client.run_with_updates(
        "6-week wider plan, 3x weekly", ["Change to 2x weekly", "Home workouts only"], [8, 8]
    )


# Uncomment to run quick test
# asyncio.run(quick_test_updates())
