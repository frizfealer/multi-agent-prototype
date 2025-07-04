import json

from agents.triage_agent import TriageAgent
from src.state_manager import (
    add_message,
    create_conversation,
    get_conversation_state,
    update_conversation_state,
)


class Orchestrator:
    def __init__(self):
        self.agents = {
            "triage": TriageAgent()
            # Future specialist agents will be added here
        }

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

        # Get the current agent
        current_agent_name = state["current_agent"]
        agent = self.agents.get(current_agent_name)
        if not agent:
            return {"error": f"Agent '{current_agent_name}' not found."}

        # Let the agent process the request
        action = await agent.process_request(state["history"])
        if not action:
            return {"error": "Agent failed to process the request."}

        # Execute the action
        return self.execute_action(conversation_id, action, current_agent_name)

    def execute_action(self, conversation_id, action, current_agent_name):
        """
        Executes the action returned by the agent.
        """
        action_name = action.get("name")
        action_args = json.loads(action.get("arguments", "{}"))

        if action_name == "hand_off_to_experts":
            experts = action_args
            if experts:
                # In a real system, you would have logic to combine prompts
                # For now, we'll just handoff to the first expert
                next_agent = experts[0]
                import pdb

                pdb.set_trace()
                update_conversation_state(conversation_id, current_agent=next_agent)
                response_message = f"Perfect, connecting you to the {next_agent.replace('_', ' ').title()}..."
                add_message(conversation_id, "model", response_message, agent=current_agent_name)
                return {"response": response_message}
            else:
                return {"error": "No expert specified for handoff."}
        elif action_name == "respond_directly":
            text = action_args.get("text")
            add_message(conversation_id, "model", text, agent=current_agent_name)
            return {"response": text}
        else:
            return {"error": f"Unknown action: {action_name}"}


if __name__ == "__main__":
    # Example usage
    conv_id = create_conversation()
    orchestrator = Orchestrator()

    # Scenario 1: Complex Task -> Handoff
    print("User: I need a workout and diet plan.")
    response = orchestrator.handle_message(conv_id, "I need a workout and diet plan.")
    print(f"Agent: {response.get('response')}")

    # Scenario 2: Simple Request -> Direct Execution
    print("\nUser: Delete my 'Summer Shred' plan.")
    response = orchestrator.handle_message(conv_id, "Delete my 'Summer Shred' plan.")
    print(f"Agent: {response.get('response')}")
