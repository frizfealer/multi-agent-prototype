#!/usr/bin/env python3
"""
Simple CLI Chat Interface for Dynamic Exercise Planning System
Provides an interactive command-line interface to chat with the multi-agent system.
"""

import asyncio
import json
import uuid
import sys
from datetime import datetime
from typing import Optional

import aiohttp
import websockets


class ChatCLI:
    def __init__(self, base_url="http://localhost:8000", ws_url="ws://localhost:8000"):
        self.base_url = base_url
        self.ws_url = ws_url
        self.session_id = str(uuid.uuid4())
        self.websocket = None
        self.is_first_message = True
        self.processing = False
        self.shutdown_event = asyncio.Event()
        
    async def check_server_health(self):
        """Check if the server is running"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/health") as response:
                    if response.status == 200:
                        return True
                    return False
        except:
            return False
    
    async def connect_websocket(self):
        """Connect to WebSocket for real-time updates"""
        try:
            ws_endpoint = f"{self.ws_url}/ws/{self.session_id}"
            self.websocket = await websockets.connect(ws_endpoint)
            return True
        except Exception as e:
            print(f"❌ Failed to connect to WebSocket: {e}")
            return False
    
    async def send_message(self, message: str):
        """Send message to the backend"""
        try:
            async with aiohttp.ClientSession() as session:
                data = {
                    "message": message,
                    "session_id": self.session_id,
                    "is_update": not self.is_first_message
                }
                
                async with session.post(f"{self.base_url}/chat", json=data) as response:
                    if response.status == 200:
                        self.is_first_message = False
                        self.processing = True
                        return await response.json()
                    else:
                        print(f"❌ Server error: {response.status}")
                        return None
        except Exception as e:
            print(f"❌ Failed to send message: {e}")
            return None
    
    async def listen_websocket(self):
        """Listen for WebSocket updates"""
        if not self.websocket:
            return
            
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    await self.handle_websocket_message(data)
                except json.JSONDecodeError:
                    print(f"📨 {message}")
                except Exception as e:
                    print(f"❌ Error handling message: {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            print("🔌 Connection closed")
        except Exception as e:
            print(f"❌ WebSocket error: {e}")
    
    async def handle_websocket_message(self, data: dict):
        """Handle different types of WebSocket messages"""
        message_type = data.get("type", "unknown")
        content = data.get("content", "")
        context = data.get("context", {})
        timestamp = data.get("timestamp", "")
        
        # Format timestamp for display
        time_str = ""
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                time_str = f"[{dt.strftime('%H:%M:%S')}] "
            except:
                time_str = f"[{datetime.now().strftime('%H:%M:%S')}] "
        else:
            time_str = f"[{datetime.now().strftime('%H:%M:%S')}] "
        
        # Map message types to user-friendly displays
        if message_type == "planning_start":
            print(f"{time_str}🔄 {content}")
            
        elif message_type == "requirement_analysis":
            print(f"{time_str}🔍 {content}")
            
        elif message_type == "status_update":
            print(f"{time_str}📊 {content}")
            
        elif message_type == "search_update":
            print(f"{time_str}🔍 {content}")
            
        elif message_type == "final_plan":
            print(f"\n{time_str}✅ {content}")
            
            # Show requirement context if available
            if context:
                req_num = context.get("requirement_number", 1)
                is_update = context.get("is_update", False)
                if is_update:
                    prev_req = context.get("previous_request", "")
                    if prev_req:
                        print(f"📝 (Updated from: '{prev_req[:50]}...')")
                    else:
                        print(f"📝 (This is an update to your request)")
            
            print("-" * 60)
            self.processing = False
            
        elif message_type == "error":
            print(f"{time_str}❌ {content}")
            self.processing = False
            
        else:
            # Fallback for unknown message types
            print(f"{time_str}📨 {content}")
    
    async def get_session_status(self):
        """Get current session status"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/sessions/{self.session_id}/status") as response:
                    if response.status == 200:
                        return await response.json()
                    return None
        except:
            return None
    
    async def get_requirements_history(self):
        """Get requirements history"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/sessions/{self.session_id}/requirements") as response:
                    if response.status == 200:
                        return await response.json()
                    return None
        except:
            return None
    
    def print_welcome(self):
        """Print welcome message"""
        print("🏋️  Exercise Planning Chat")
        print("=" * 40)
        print("💬 Type your exercise planning requests")
        print("📝 Follow-up messages will update your plan")
        print("⚡ Available commands:")
        print("   /new     - Start new session")
        print("   /status  - Check session status")
        print("   /history - View requirements history")
        print("   /quit    - Exit")
        print("=" * 40)
        print(f"🆔 Session: {self.session_id[:8]}...")
        print()
    
    def print_prompt(self):
        """Print input prompt"""
        status = "⏳ Processing..." if self.processing else "💬 Ready"
        print(f"\n{status}")
        print("You: ", end="", flush=True)
    
    async def handle_command(self, command: str):
        """Handle special commands"""
        if command == "/new":
            # Start new session
            self.session_id = str(uuid.uuid4())
            self.is_first_message = True
            self.processing = False
            
            # Reconnect WebSocket
            if self.websocket:
                await self.websocket.close()
            
            if await self.connect_websocket():
                print(f"🆕 New session started: {self.session_id[:8]}...")
                # Restart WebSocket listener if needed
                pass  # Will be handled by main loop
            else:
                print("❌ Failed to start new session")
                
        elif command == "/status":
            if self.is_first_message:
                print("📊 Session Status: No active session")
                print("   💡 Send a message first to create a session")
            else:
                status = await self.get_session_status()
                if status and status.get('status') != 'not_found':
                    print(f"📊 Session Status:")
                    print(f"   Status: {status.get('status', 'unknown')}")
                    print(f"   Processing: {status.get('processing', False)}")
                    print(f"   Requirements: {status.get('requirements_count', 0)}")
                    print(f"   Has Plan: {status.get('has_final_plan', False)}")
                else:
                    print("📊 Session Status: Session not found or expired")
                    print("   💡 Send a message to create a new session")
                
        elif command == "/history":
            if self.is_first_message:
                print("📝 Requirements History: No active session")
                print("   💡 Send a message first to create a session")
            else:
                history = await self.get_requirements_history()
                if history:
                    print(f"📝 Requirements History:")
                    print(f"   Original: {history.get('original_request', 'None')}")
                    print(f"   Current: {history.get('current_request', 'None')}")
                    reqs = history.get('requirements_history', [])
                    if reqs:
                        print(f"   All updates:")
                        for i, req in enumerate(reqs, 1):
                            print(f"     {i}. {req}")
                    else:
                        print("   No requirements yet")
                else:
                    print("📝 Requirements History: Session not found or expired")
                    print("   💡 Send a message to create a new session")
                
        elif command == "/quit":
            return True
            
        else:
            print(f"❌ Unknown command: {command}")
            print("Available: /new, /status, /history, /quit")
            
        return False
    
    async def get_user_input(self):
        """Get user input using asyncio to_thread for non-blocking input"""
        while not self.shutdown_event.is_set():
            try:
                # Use asyncio.to_thread for input (Python 3.9+)
                user_input = await asyncio.to_thread(input)
                user_input = user_input.strip()
                
                if not user_input:
                    self.print_prompt()
                    continue
                
                # Handle commands
                if user_input.startswith("/"):
                    should_quit = await self.handle_command(user_input)
                    if should_quit:
                        self.shutdown_event.set()
                        print("\n👋 Goodbye!")
                        break
                    # Show prompt again after command
                    self.print_prompt()
                    continue
                
                # Send regular message
                response = await self.send_message(user_input)
                if response:
                    print(f"📤 {response.get('message', 'Message sent')}")
                else:
                    print("❌ Failed to send message")
                
                # Show prompt again for next input
                self.print_prompt()
                
            except (EOFError, KeyboardInterrupt):
                self.shutdown_event.set()
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error getting input: {e}")
                break
    
    async def run(self):
        """Main chat loop with concurrent input and WebSocket handling"""
        # Check server health
        if not await self.check_server_health():
            print("❌ Server is not running!")
            print("Please start the server first:")
            print("   python backend.py")
            return
        
        # Connect WebSocket
        if not await self.connect_websocket():
            print("❌ Failed to connect. Exiting.")
            return
        
        # Print welcome
        self.print_welcome()
        self.print_prompt()
        
        try:
            # Start concurrent tasks
            listen_task = asyncio.create_task(self.listen_websocket())
            input_task = asyncio.create_task(self.get_user_input())
            
            # Wait for either task to complete
            done, pending = await asyncio.wait(
                [listen_task, input_task], 
                return_when=asyncio.FIRST_COMPLETED
            )
            
            # Cancel remaining tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
        
        finally:
            # Cleanup
            self.shutdown_event.set()
            if self.websocket:
                await self.websocket.close()


async def main():
    """Main entry point"""
    cli = ChatCLI()
    await cli.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Error: {e}")