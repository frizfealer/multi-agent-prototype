import json

import requests


def print_tasks(tasks):
    """Print tasks in a formatted way."""
    if not tasks:
        print("📋 No pending tasks found.")
        return

    print(f"📋 Found {len(tasks)} pending task(s):")
    for i, task in enumerate(tasks, 1):
        print(f"\n{i}. {task['domain'].replace('_', ' ').title()}")
        print(f"   Goal: {task['goal']}")
        print(f"   Task ID: {task['task_id'][:8]}...")
        if task.get("context"):
            context = task["context"]
            if isinstance(context, str):
                try:
                    context = json.loads(context)
                except:
                    pass
            if isinstance(context, dict):
                for key, value in context.items():
                    if key != "domain":  # Don't duplicate domain info
                        print(f"   {key.replace('_', ' ').title()}: {value}")


def handle_command(command, conversation_id):
    """Handle special CLI commands."""
    command = command.lower().strip()

    if command == "/tasks":
        if not conversation_id:
            print("❌ No active conversation. Start chatting first!")
            return True

        response = requests.get(f"http://127.0.0.1:8000/conversations/{conversation_id}/tasks")
        if response.status_code == 200:
            tasks = response.json().get("pending_tasks", [])
            print_tasks(tasks)
        else:
            print(f"❌ Error getting tasks: {response.text}")
        return True

    elif command == "/start":
        if not conversation_id:
            print("❌ No active conversation. Start chatting first!")
            return True

        response = requests.post(f"http://127.0.0.1:8001/conversations/{conversation_id}/start_tasks", json={})
        if response.status_code == 200:
            result = response.json()
            print(f"🚀 {result['message']}")
            if result.get("started_tasks"):
                print("\nStarted tasks:")
                print_tasks(result["started_tasks"])
        else:
            print(f"❌ Error starting tasks: {response.text}")
        return True

    elif command == "/help":
        print(
            """
🤖 Specialist Coach CLI Commands:

Chat Commands:
  <message>     Send a message to the agent
  exit          Exit the CLI

Task Commands:
  /tasks        View pending tasks for this conversation
  /start        Start all pending tasks
  /help         Show this help message

Example Workflow:
  You: I want a workout plan
  Agent: [Creates ExerciseCoach, gathers info]
  You: /tasks
  [Shows pending exercise_planning task]
  You: /start
  [Starts task generation]
        """
        )
        return True

    return False


def main():
    print("🤖 Specialist Coach CLI")
    print("Type '/help' for commands or start chatting!")
    print("=" * 50)

    conversation_id = None
    while True:
        message = input("\nYou: ").strip()

        if message.lower() == "exit":
            print("👋 Goodbye!")
            break

        # Handle special commands
        if handle_command(message, conversation_id):
            continue

        if not message:
            continue

        # Send chat message
        response = requests.post(
            "http://127.0.0.1:8001/chat", json={"message": message, "conversation_id": conversation_id}
        )

        if response.status_code == 200:
            result = response.json()
            print(f"\nAgent: {result['response']}")
            conversation_id = result["conversation_id"]

            # Auto-show tasks if agent mentions task creation
            if result["response"] and "task has been prepared" in result["response"].lower():
                print("\n💡 Tip: Type '/tasks' to see pending tasks, '/start' to begin generation")
        else:
            print(f"\n❌ Error: {response.text}")


if __name__ == "__main__":
    main()
