import json
import uuid

from src.agents.dynamic_coach import CoachTemplateManager
from src.agents.exercise_coach import ExerciseCoach
from src.agents.nutrition_coach import NutritionCoach
from src.agents.triage_agent import TriageAgent
from src.state_manager import (
    add_message,
    create_conversation,
    create_task,
    get_conversation_state,
    update_conversation_state,
)


class Orchestrator:
    def __init__(self):
        self.agents = {
            "triage": TriageAgent(),
            "exercise_coach": ExerciseCoach(),
            "nutrition_coach": NutritionCoach(),
            # Other static agents can be added here
        }
        self.coach_template_manager = CoachTemplateManager()

    async def handle_message(self, conversation_id, user_message):
        """
        Handles a new message from the user.
        """
        # Add user message to history
        add_message(conversation_id, "user", user_message)

        # Get the current conversation state
        state = get_conversation_state(conversation_id)
        if not state:
            return {"error": "Conversation not found."}

        # Get the current agent (create dynamically if needed)
        current_agent_name = state["current_agent"]
        agent = self.get_agent_for_conversation(current_agent_name)
        if not agent:
            return {"error": f"Agent '{current_agent_name}' not found."}

        # Let the agent process the request
        action = await agent.process_request(state["history"])

        # Execute the action
        return await self.execute_action(conversation_id, action, current_agent_name)

    async def execute_action(self, conversation_id, action, current_agent_name):
        """
        Executes the action returned by the agent.
        """
        action_name = action.get("name")
        action_args = json.loads(action.get("arguments", "{}"))

        if action_name == "hand_off_to_experts":
            experts = action_args
            if experts:
                # Create composite agent name
                agent_name = "+".join(sorted(experts))
                update_conversation_state(conversation_id, current_agent=agent_name)

                # Create friendly response message
                expert_names = [expert.replace("_", " ").title() for expert in experts]
                if len(expert_names) == 1:
                    response_message = f"Perfect, connecting you to our {expert_names[0]}..."
                else:
                    response_message = f"Perfect, connecting you to our {' and '.join(expert_names)} specialists..."

                add_message(conversation_id, "model", response_message, agent=current_agent_name)

                # Get the new agent and process an initial greeting
                new_agent = self.get_agent_for_conversation(agent_name)
                if new_agent:
                    # Get updated conversation state with the handoff message
                    updated_state = get_conversation_state(conversation_id)

                    # Let the new agent process the conversation and generate a greeting
                    expert_action = await new_agent.process_request(updated_state["history"])

                    if expert_action:
                        # Execute the expert's action (should be respond_directly with greeting)
                        expert_response = await self.execute_action(conversation_id, expert_action, agent_name)

                        # Combine both messages in the response
                        combined_response = f"{response_message}\n\n{expert_response.get('response', '')}"
                        return {"response": combined_response}

                return {"response": response_message}
            else:
                return {"error": "No expert specified for handoff."}

        elif action_name == "hand_off_to_triage_agent":
            # Escape hatch back to triage
            update_conversation_state(conversation_id, current_agent="triage")
            response_message = "Let me connect you back to our main assistant..."
            add_message(conversation_id, "model", response_message, agent=current_agent_name)

            # Get the triage agent and process the conversation
            triage_agent = self.get_agent_for_conversation("triage")
            if triage_agent:
                # Get updated conversation state with the handoff message
                updated_state = get_conversation_state(conversation_id)

                # Let the triage agent process the conversation and generate a response
                triage_action = await triage_agent.process_request(updated_state["history"])

                if triage_action:
                    # Execute the triage agent's action
                    triage_response = await self.execute_action(conversation_id, triage_action, "triage")

                    # Combine both messages in the response
                    combined_response = f"{response_message}\n\n{triage_response.get('response', '')}"
                    return {"response": combined_response}

            return {"response": response_message}

        elif action_name == "create_artifacts":
            # Create task for background processing
            domain = action_args.get("domain")
            data = action_args.get("data")

            if not domain or not data:
                return {"error": "Domain and data are required for create_artifacts"}

            task_id = str(uuid.uuid4())
            task = {
                "task_id": task_id,
                "conversation_id": conversation_id,
                "domain": domain,
                "goal": f"create_{domain}",
                "context": data,
                "status": "pending",
            }

            create_task(task)
            response_message = f"Your {domain.replace('_', ' ')} task has been prepared! Use /start_tasks when you're ready to begin generation."
            add_message(conversation_id, "model", response_message, agent=current_agent_name)
            return {"response": response_message}

        elif action_name == "respond_directly":
            text = action_args.get("text")
            add_message(conversation_id, "model", text, agent=current_agent_name)
            return {"response": text}

        else:
            return {"error": f"Unknown action: {action_name}"}

    def get_agent_for_conversation(self, agent_name):
        """Get agent for conversation, creating dynamically if needed."""
        # Check if it's a static agent
        if agent_name in self.agents:
            return self.agents[agent_name]

        # Check if it's a composite agent
        if "+" in agent_name:
            domains = agent_name.split("+")
            return self.coach_template_manager.create_multi_domain_coach(domains)

        # Agent not found
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
