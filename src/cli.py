import json

import requests


def print_tasks(tasks, status_filter=None):
    """Print tasks in a formatted way."""
    if not tasks:
        status_text = f"{status_filter} " if status_filter else ""
        print(f"📋 No {status_text}tasks found.")
        return

    status_text = f"{status_filter} " if status_filter else ""
    print(f"📋 Found {len(tasks)} {status_text}task(s):")
    for i, task in enumerate(tasks, 1):
        status_emoji = {
            "pending": "⏳",
            "in_progress": "🔄",
            "completed": "✅",
            "canceled": "❌",
            "deleted": "🗑️"
        }.get(task.get('task_status', 'pending'), "❓")
        
        print(f"\n{i}. {status_emoji} {task['domain'].replace('_', ' ').title()}")
        print(f"   Goal: {task['goal']}")
        print(f"   Status: {task.get('task_status', 'pending')}")
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

    if command.startswith("/tasks"):
        if not conversation_id:
            print("❌ No active conversation. Start chatting first!")
            return True

        # Parse status filter
        parts = command.split()
        status_filter = parts[1] if len(parts) > 1 else None
        
        # Build URL with status parameter
        url = f"http://127.0.0.1:8001/conversations/{conversation_id}/tasks"
        if status_filter:
            url += f"?status={status_filter}"
        
        response = requests.get(url)
        if response.status_code == 200:
            tasks = response.json().get("tasks", [])
            print_tasks(tasks, status_filter)
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
                print_tasks(result["started_tasks"], "started")
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
  /tasks                View all tasks
  /tasks pending        View pending tasks
  /tasks in_progress    View running tasks
  /tasks completed      View completed tasks
  /tasks canceled       View canceled tasks
  /tasks deleted        View deleted tasks
  /start                Start all pending tasks
  /help                 Show this help message

Example Workflow:
  You: I want a workout plan
  Agent: [Creates ExerciseCoach, gathers info]
  You: /tasks pending
  [Shows pending exercise_planning task]
  You: /start
  [Starts task generation, tasks move to in_progress]
  You: /tasks in_progress
  [Shows running tasks]
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
