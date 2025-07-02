import uuid
from typing import Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.triage_agent import TriageAgent
from src.core.state_manager import StateManager


class Orchestrator:
    def __init__(self, google_api_key: str):
        self.google_api_key = google_api_key
        self.specialist_agents = {}  # Future: Map of agent_name -> agent instance

    async def process_user_message(
        self, session: AsyncSession, conversation_id: Optional[uuid.UUID], message: str
    ) -> Dict:
        """Process a user message through the appropriate agent."""
        state_manager = StateManager(session)
        
        # Create or retrieve conversation
        if conversation_id:
            conversation = await state_manager.get_conversation(conversation_id)
            if not conversation:
                return {"error": "Conversation not found"}
        else:
            conversation = await state_manager.create_conversation()
            conversation_id = conversation.conversation_id
        
        # Add user message to history
        await state_manager.add_message(conversation_id, "user", message)
        
        # Get conversation history
        history = await state_manager.get_conversation_history(conversation_id)
        
        # Route to appropriate agent based on current_agent
        current_agent = conversation.current_agent
        
        if current_agent == "triage":
            response = await self._handle_triage_agent(
                state_manager, conversation_id, history, message
            )
        else:
            # Future: Handle specialist agents
            response = {
                "error": f"Agent '{current_agent}' not implemented yet",
                "conversation_id": str(conversation_id)
            }
        
        return response

    async def _handle_triage_agent(
        self, state_manager: StateManager, conversation_id: uuid.UUID, 
        history: list, message: str
    ) -> Dict:
        """Handle message processing with the triage agent."""
        triage_agent = TriageAgent(self.google_api_key, state_manager)
        
        # Process message with triage agent
        result = await triage_agent.process_message(history[:-1], message)  # Exclude the just-added message
        
        response = {
            "conversation_id": str(conversation_id),
            "agent": "triage",
            "text": result.get("text_response"),
            "action": None
        }
        
        # Handle function calls
        if result.get("function_call"):
            function_call = result["function_call"]
            function_name = function_call["name"]
            
            if function_name == "handoff_to_coach":
                # Update current agent
                coach_names = function_call["args"]["coach_names"]
                # For now, use the first coach if multiple are specified
                new_agent = coach_names[0] if coach_names else "triage"
                await state_manager.update_current_agent(conversation_id, new_agent)
                
                response["action"] = {
                    "type": "handoff",
                    "coaches": coach_names
                }
                response["text"] = response["text"] or f"Connecting you to {', '.join(coach_names)}..."
                
            elif function_name == "execute_direct_request":
                # Handle direct request
                action = function_call["args"]["action"]
                context = function_call["args"]["context"]
                
                response["action"] = {
                    "type": "direct_request",
                    "action": action,
                    "context": context
                }
                
                # Future: Actually execute the action
                response["text"] = response["text"] or f"Executing {action} action..."
                
            elif function_name == "ask_question":
                # Return clarifying question
                question = function_call["args"]["question"]
                response["action"] = {
                    "type": "question",
                    "question": question
                }
                response["text"] = question
        
        # Save assistant response
        if response["text"]:
            await state_manager.add_message(conversation_id, "assistant", response["text"])
        
        return response