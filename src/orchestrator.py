import json
import uuid

from src.agents.dynamic_coach import CoachTemplateManager
from src.agents.exercise_coach import ExerciseCoach
from src.agents.nutrition_coach import NutritionCoach
from src.agents.triage_agent import TriageAgent
from src.logging_config import get_logger
from src.state_manager import (
    create_conversation,
    execute_atomic_updates,
    get_conversation_state,
)

logger = get_logger(__name__)


class Orchestrator:
    def __init__(self):
        logger.info("Initializing Orchestrator")
        self.agents = {
            "triage": TriageAgent(),
            "exercise_coach": ExerciseCoach(),
            "nutrition_coach": NutritionCoach(),
            # Other static agents can be added here
        }
        self.coach_template_manager = CoachTemplateManager()
        logger.info(f"Orchestrator initialized with {len(self.agents)} static agents")

    async def handle_message(self, conversation_id, user_message):
        """
        Handles a new message from the user with atomic state updates.
        """
        logger.info(f"Handling message for conversation {conversation_id}")
        logger.debug(f"User message: {user_message[:100]}...")  # Log first 100 chars

        # Get the current conversation state
        state = get_conversation_state(conversation_id)
        if not state:
            logger.error(f"Conversation {conversation_id} not found")
            return {"error": "Conversation not found."}

        # Get the current agent
        current_agent_name = state["current_agent"]
        logger.info(f"Current agent: {current_agent_name}")

        agent = self.get_agent_for_conversation(current_agent_name)
        if not agent:
            logger.error(f"Agent '{current_agent_name}' not found")
            return {"error": f"Agent '{current_agent_name}' not found."}

        # Let the agent process the request with user message appended
        working_history = state["history"] + [{"role": "user", "content": user_message}]
        logger.debug(f"Processing request with {current_agent_name}")
        action = await agent.process_request(working_history)

        # Process action and build atomic operations
        action_name = action.get("name")
        action_args = json.loads(action.get("arguments", "{}"))
        logger.info(f"Executing action: {action_name}")

        # Start building operations - always add user message first
        operations = [{"type": "add_message", "role": "user", "content": user_message}]
        response_text = ""

        if action_name == "respond_directly":
            # Simple response
            text = action_args.get("text", "")
            operations.append({"type": "add_message", "role": "model", "content": text, "agent": current_agent_name})
            response_text = text

        elif action_name == "hand_off_to_experts":
            # Handle expert handoff
            experts = action_args.get("experts", [])
            if not experts:
                logger.error("No expert specified for handoff")
                return {"error": "No expert specified for handoff."}

            # Create composite agent name
            new_agent_name = "+".join(sorted(experts))
            logger.info(f"Handing off to {new_agent_name}")

            # Update agent
            operations.append({"type": "update_agent", "agent": new_agent_name})

            # Create handoff message
            expert_names = [expert.replace("_", " ").title() for expert in experts]
            if len(expert_names) == 1:
                handoff_message = f"Perfect, connecting you to our {expert_names[0]}..."
            else:
                handoff_message = f"Perfect, connecting you to our {' and '.join(expert_names)} specialists..."

            operations.append(
                {"type": "add_message", "role": "model", "content": handoff_message, "agent": current_agent_name}
            )

            # Get new agent's greeting
            new_agent = self.get_agent_for_conversation(new_agent_name)
            if new_agent:
                # Build history as it will be after handoff
                new_history = working_history + [
                    {"role": "model", "agent": current_agent_name, "content": handoff_message}
                ]

                # Get greeting from new agent
                logger.debug(f"Getting greeting from {new_agent_name}")
                greeting_action = await new_agent.process_request(new_history)

                if greeting_action and greeting_action.get("name") == "respond_directly":
                    greeting_text = json.loads(greeting_action.get("arguments", "{}")).get("text", "")
                    operations.append(
                        {"type": "add_message", "role": "model", "content": greeting_text, "agent": new_agent_name}
                    )
                    response_text = f"{handoff_message}\n--------------------------------\n{greeting_text}"
                else:
                    response_text = handoff_message
            else:
                response_text = handoff_message

        elif action_name == "hand_off_to_triage_agent":
            # Handle triage handoff
            logger.info("Handing off back to triage agent")

            # Update agent
            operations.append({"type": "update_agent", "agent": "triage"})

            # Add handoff message
            handoff_message = "Let me connect you back to our main assistant..."
            operations.append(
                {"type": "add_message", "role": "model", "content": handoff_message, "agent": current_agent_name}
            )

            # Get triage agent's greeting
            triage_agent = self.get_agent_for_conversation("triage")
            if triage_agent:
                # Build history as it will be after handoff
                new_history = working_history + [
                    {"role": "model", "agent": current_agent_name, "content": handoff_message}
                ]

                # Get greeting from triage
                logger.debug("Getting greeting from triage agent")
                greeting_action = await triage_agent.process_request(new_history)

                if greeting_action and greeting_action.get("name") == "respond_directly":
                    greeting_text = json.loads(greeting_action.get("arguments", "{}")).get("text", "")
                    operations.append(
                        {"type": "add_message", "role": "model", "content": greeting_text, "agent": "triage"}
                    )
                    response_text = f"{handoff_message}\n--------------------------------\n{greeting_text}"
                else:
                    response_text = handoff_message
            else:
                response_text = handoff_message

        elif action_name == "create_artifacts":
            # Handle task creation
            domain = action_args.get("domain")
            data = action_args.get("data")

            if not domain or not data:
                logger.error("Missing domain or data for create_artifacts")
                return {"error": "Domain and data are required for create_artifacts"}

            task_id = str(uuid.uuid4())

            # Create task
            operations.append(
                {
                    "type": "create_task",
                    "task": {
                        "task_id": task_id,
                        "conversation_id": conversation_id,
                        "domain": domain,
                        "goal": f"create_{domain}",
                        "context": data,
                        "status": "pending",
                    },
                }
            )

            # Add task creation message
            task_message = f"Your {domain.replace('_', ' ')} task has been prepared! Use /start_tasks when you're ready to begin generation."
            operations.append(
                {"type": "add_message", "role": "model", "content": task_message, "agent": current_agent_name}
            )
            response_text = task_message

        else:
            logger.error(f"Unknown action: {action_name}")
            return {"error": f"Unknown action: {action_name}"}

        # Execute all operations atomically
        try:
            execute_atomic_updates(conversation_id, operations)
            return {"response": response_text}
        except Exception as e:
            logger.error(f"Failed to execute atomic updates: {e}")
            return {"error": "Failed to process message. Please try again."}

    def get_agent_for_conversation(self, agent_name):
        """Get agent for conversation, creating dynamically if needed."""
        # Check if it's a static agent
        if agent_name in self.agents:
            logger.debug(f"Using static agent: {agent_name}")
            return self.agents[agent_name]

        # Check if it's a composite agent
        if "+" in agent_name:
            domains = agent_name.split("+")
            logger.info(f"Creating dynamic multi-domain coach for: {domains}")
            return self.coach_template_manager.create_multi_domain_coach(domains)

        # Agent not found
        logger.warning(f"Agent not found: {agent_name}")
        return None


if __name__ == "__main__":
    import asyncio

    async def main():
        # Example usage
        conv_id = create_conversation()
        orchestrator = Orchestrator()

        # Scenario 1: Complex Task -> Handoff
        print("User: I need a workout and diet plan.")
        response = await orchestrator.handle_message(conv_id, "I need a workout and diet plan.")
        print(f"Agent: {response.get('response')}")

        # Scenario 2: Simple Request -> Direct Execution
        print("\nUser: Delete my 'Summer Shred' plan.")
        response = await orchestrator.handle_message(conv_id, "Delete my 'Summer Shred' plan.")
        print(f"Agent: {response.get('response')}")

    asyncio.run(main())
