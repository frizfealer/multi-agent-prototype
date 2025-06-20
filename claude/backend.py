import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Annotated, Dict, List, Optional, TypedDict

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel


# Pydantic models for API
class ChatRequest(BaseModel):
    message: str
    session_id: str
    is_update: bool = False  # Flag to indicate if this is an update to existing requirements


class ChatResponse(BaseModel):
    message: str
    session_id: str
    status: str  # "processing", "completed", "updated", "re_evaluating"


# Workflow status enum
class WorkflowStatus(Enum):
    INITIAL = "initial"
    PLANNING = "planning"
    SEARCHING = "searching"
    SUMMARIZING = "summarizing"
    COMPLETED = "completed"
    UPDATED = "updated"
    RE_EVALUATING = "re_evaluating"


# State definitions
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    session_id: str
    user_request: str
    original_request: str  # Keep track of original request
    requirements_history: List[str]  # Track all requirement updates
    exercise_results: Optional[str]
    final_plan: Optional[str]
    workflow_status: str
    needs_rerun: bool  # Flag to indicate if workflow needs to restart
    last_update_handled: bool  # Track if the last update was processed


@dataclass
class WebSocketManager:
    """Manages WebSocket connections for real-time updates"""

    connections: Dict[str, WebSocket] = None

    def __post_init__(self):
        if self.connections is None:
            self.connections = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.connections[session_id] = websocket
        print(f"WebSocket connected for session: {session_id}")

    def disconnect(self, session_id: str):
        if session_id in self.connections:
            del self.connections[session_id]
            print(f"WebSocket disconnected for session: {session_id}")

    async def send_message(self, session_id: str, message: str, message_type: str = "update"):
        if session_id in self.connections:
            try:
                response = {"type": message_type, "content": message, "timestamp": datetime.now().isoformat()}
                await self.connections[session_id].send_text(json.dumps(response))
                print(f"Sent WebSocket message to {session_id}: {message[:100]}...")
            except Exception as e:
                print(f"Error sending WebSocket message: {e}")
                self.disconnect(session_id)


# Initialize components
websocket_manager = WebSocketManager()
llm = ChatOpenAI(model="gpt-4", temperature=0.7)
search_tool = DuckDuckGoSearchRun()

# Store active workflows for updates
active_workflows: Dict[str, dict] = {}


# Agent implementations
class RequirementAnalyzer:
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4", temperature=0.3)

    async def analyze_update(self, original_request: str, new_request: str, requirements_history: List[str]) -> dict:
        """Analyze if the new request requires re-running the workflow"""

        history_text = "\n".join([f"- {req}" for req in requirements_history])

        prompt = f"""
        Analyze the following requirement update for an exercise planning system:
        
        Original Request: "{original_request}"
        New/Updated Request: "{new_request}"
        
        Previous Requirements History:
        {history_text}
        
        Determine:
        1. Is this a significant change that requires re-running the exercise search?
        2. Is this a significant change that requires re-running the schedule search?
        3. Does this require creating a completely new plan?
        4. Or is this just a clarification that can be incorporated into the existing plan?
        
        Consider changes in:
        - Training frequency (times per week)
        - Duration (weeks)
        - Goals (muscle groups, objectives)
        - Equipment availability
        - Experience level
        - Specific constraints
        
        Respond in JSON format:
        {{
            "needs_exercise_research": boolean,
            "needs_schedule_research": boolean,
            "needs_new_plan": boolean,
            "is_minor_clarification": boolean,
            "change_summary": "brief description of what changed",
            "reasoning": "explanation of the decision"
        }}
        """

        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            # Parse JSON response
            result = json.loads(response.content)
            return result
        except Exception as e:
            print(f"Error analyzing requirements: {e}")
            # Default to re-running everything on error
            return {
                "needs_exercise_research": True,
                "needs_schedule_research": True,
                "needs_new_plan": True,
                "is_minor_clarification": False,
                "change_summary": "Unable to analyze changes",
                "reasoning": f"Analysis failed: {str(e)}",
            }


class WebSearchAgent:
    def __init__(self, agent_type: str):
        self.agent_type = agent_type
        self.search_tool = DuckDuckGoSearchRun()

    async def search(self, query: str) -> str:
        """Perform web search and return results"""
        try:
            print(f"{self.agent_type} searching for: {query}")
            results = self.search_tool.run(query)
            return results
        except Exception as e:
            print(f"Search error in {self.agent_type}: {e}")
            return f"Search failed: {str(e)}"


class SummarizerAgent:
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4", temperature=0.3)

    async def summarize(
        self, exercise_data: str, schedule_data: str, user_request: str, is_update: bool = False
    ) -> str:
        """Combine search results into a structured exercise plan"""

        update_context = ""
        if is_update:
            update_context = "\n\nNote: This is an updated plan based on revised requirements."

        prompt = f"""
        Based on the user's request: "{user_request}"
        
        Exercise Research Data:
        {exercise_data}
        
        Schedule Research Data:
        {schedule_data}
        
        Create a comprehensive, structured exercise plan that addresses the user's requirements.
        Include:
        1. Weekly schedule breakdown
        2. Specific exercises with sets/reps
        3. Progressive overload strategy
        4. Key focus areas for building width
        5. Tips for success
        6. Any modifications based on the specific requirements
        
        Format it as a clear, actionable plan.{update_context}
        """

        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            return response.content
        except Exception as e:
            print(f"Summarization error: {e}")
            return f"Failed to create plan: {str(e)}"


# Initialize agents
requirement_analyzer = RequirementAnalyzer()
exercise_search_agent = WebSearchAgent("Exercise Search Agent")
schedule_search_agent = WebSearchAgent("Schedule Search Agent")
summarizer_agent = SummarizerAgent()


# Graph node functions
async def requirement_evaluation_node(state: AgentState) -> AgentState:
    """Evaluate requirements and determine if re-running is needed"""
    session_id = state["session_id"]

    # Check if this is an update
    if len(state["requirements_history"]) > 1:
        print(f"Evaluating requirement update for session {session_id}")

        original_request = state["original_request"]
        current_request = state["user_request"]
        history = state["requirements_history"]

        # Analyze the update
        analysis = await requirement_analyzer.analyze_update(original_request, current_request, history)

        # Send analysis to user
        await websocket_manager.send_message(
            session_id,
            f"I've analyzed your updated requirements: {analysis['change_summary']}. {analysis['reasoning']}",
            "requirement_analysis",
        )

        # Determine what needs to be re-run
        if analysis["is_minor_clarification"]:
            state["workflow_status"] = WorkflowStatus.COMPLETED.value
            # Just update the final plan with clarification
            await websocket_manager.send_message(
                session_id,
                "This is a minor clarification. I'll update your existing plan accordingly.",
                "status_update",
            )
        else:
            # Reset results that need to be regenerated
            if analysis["needs_exercise_research"] or analysis["needs_schedule_research"]:
                state["exercise_results"] = None
                print("Resetting exercise results for re-search")

            if analysis["needs_new_plan"]:
                state["final_plan"] = None
                print("Resetting final plan for regeneration")

            state["workflow_status"] = WorkflowStatus.RE_EVALUATING.value
            state["needs_rerun"] = True

            await websocket_manager.send_message(
                session_id,
                "Your requirements have changed significantly. I'm updating the research and plan accordingly...",
                "status_update",
            )

    state["last_update_handled"] = True
    return state


async def planning_node(state: AgentState) -> AgentState:
    """Planning Agent - orchestrates the workflow"""
    session_id = state["session_id"]
    user_request = state["user_request"]
    status = state.get("workflow_status", WorkflowStatus.INITIAL.value)

    # Send initial acknowledgment via WebSocket
    if status == WorkflowStatus.RE_EVALUATING.value:
        message = "Re-evaluating your updated requirements and adjusting the plan..."
    else:
        message = "Got it. I'll create a custom exercise plan for you. This might take a moment..."

    await websocket_manager.send_message(session_id, message, "planning_start")

    print(f"Planning Agent processing request: {user_request} (Status: {status})")

    # Add planning message to state
    planning_message = AIMessage(content=f"Planning your exercise routine... (Status: {status})")
    state["messages"].append(planning_message)
    state["workflow_status"] = WorkflowStatus.PLANNING.value

    return state


async def exercise_search_node(state: AgentState) -> AgentState:
    """Web Search Agent - searches for exercises and training schedules"""
    # Skip if we already have results and don't need to re-run
    if state.get("exercise_results") and not state.get("needs_rerun"):
        print("Skipping exercise search - already have results")
        return state

    user_request = state["user_request"]

    # Combined search query for exercises and scheduling
    search_query = f"exercises training schedule workout plan for building wider back lats deltoids upper body width muscle hypertrophy {user_request}"

    print("Starting exercise and schedule search...")
    state["workflow_status"] = WorkflowStatus.SEARCHING.value

    exercise_results = await exercise_search_agent.search(search_query)
    state["exercise_results"] = exercise_results

    # Notify via WebSocket
    await websocket_manager.send_message(
        state["session_id"], "Found exercises and training schedules. Creating your personalized plan...", "search_update"
    )

    return state


async def summarization_node(state: AgentState) -> AgentState:
    """Summarizer Agent - creates final plan"""
    exercise_data = state.get("exercise_results", "")
    user_request = state["user_request"]
    is_update = len(state["requirements_history"]) > 1

    print("Starting plan summarization...")
    state["workflow_status"] = WorkflowStatus.SUMMARIZING.value

    # Use exercise_data for both exercises and scheduling since we combined the search
    final_plan = await summarizer_agent.summarize(exercise_data, exercise_data, user_request, is_update)

    state["final_plan"] = final_plan
    state["workflow_status"] = WorkflowStatus.COMPLETED.value
    state["needs_rerun"] = False

    # Send final plan via WebSocket
    plan_type = "updated plan" if is_update else "plan"
    final_message = f"Here is your {plan_type}:\n\n{final_plan}"
    await websocket_manager.send_message(state["session_id"], final_message, "final_plan")

    # Add final message to state
    final_message_obj = AIMessage(content=final_plan)
    state["messages"].append(final_message_obj)

    return state


def should_continue(state: AgentState) -> str:
    """Determine next step in the workflow"""
    # If we have unprocessed updates, evaluate requirements first
    if not state.get("last_update_handled", True):
        return "evaluate_requirements"

    # If we need results and don't have them, go to search
    if not state.get("exercise_results") and state.get("needs_rerun", True):
        return "search"

    # If we have results but no final plan, or need to regenerate plan
    if not state.get("final_plan") or state.get("needs_rerun"):
        return "summarize"

    # Everything is complete
    return "end"


# Build the graph
def create_workflow():
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("evaluate_requirements", requirement_evaluation_node)
    workflow.add_node("planning", planning_node)
    workflow.add_node("exercise_search", exercise_search_node)
    workflow.add_node("summarization", summarization_node)

    # Define the flow
    workflow.add_edge(START, "evaluate_requirements")

    # After requirement evaluation, go to planning
    workflow.add_edge("evaluate_requirements", "planning")

    # After planning, go to exercise search
    workflow.add_edge("planning", "exercise_search")

    # After exercise search, go to summarization
    workflow.add_edge("exercise_search", "summarization")

    # Add conditional logic to handle updates
    workflow.add_conditional_edges(
        "summarization",
        should_continue,
        {
            "evaluate_requirements": "evaluate_requirements",
            "search": "exercise_search",
            "summarize": "summarization",
            "end": END,
        },
    )

    # Compile with memory
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)

    return app


# Initialize the workflow
workflow_app = create_workflow()

# FastAPI application
app = FastAPI(title="Dynamic Exercise Planning Multi-Agent System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """Handle chat requests and start async processing"""

    session_id = request.session_id
    user_message = request.message
    is_update = request.is_update

    print(f"Received {'update' if is_update else 'new'} request for session {session_id}: {user_message}")

    # Get or create workflow state
    config = {"configurable": {"thread_id": session_id}}

    if session_id in active_workflows:
        # This is an update to existing workflow
        workflow_data = active_workflows[session_id]

        # Get current state
        current_state = workflow_data.get("last_state", {})

        # Update the state with new requirements
        current_state["user_request"] = user_message
        current_state["requirements_history"] = current_state.get("requirements_history", [])
        current_state["requirements_history"].append(user_message)
        current_state["last_update_handled"] = False

        # Add new user message
        if "messages" not in current_state:
            current_state["messages"] = []
        current_state["messages"].append(HumanMessage(content=user_message))

        # Start async processing for the update
        task = asyncio.create_task(process_update_async(session_id, current_state, config))

        workflow_data["task"] = task
        workflow_data["last_state"] = current_state

        return ChatResponse(
            message="I've received your updated requirements. Let me analyze what needs to be changed...",
            session_id=session_id,
            status="updated",
        )

    else:
        # This is a new workflow
        initial_state = {
            "messages": [HumanMessage(content=user_message)],
            "session_id": session_id,
            "user_request": user_message,
            "original_request": user_message,
            "requirements_history": [user_message],
            "exercise_results": None,
            "final_plan": None,
            "workflow_status": WorkflowStatus.INITIAL.value,
            "needs_rerun": True,
            "last_update_handled": True,
        }

        # Start async processing
        task = asyncio.create_task(process_request_async(session_id, initial_state, config))

        active_workflows[session_id] = {"task": task, "last_state": initial_state, "created_at": datetime.now()}

        return ChatResponse(
            message="I'm working on your exercise plan. You'll receive updates via WebSocket.",
            session_id=session_id,
            status="processing",
        )


async def process_request_async(session_id: str, initial_state: AgentState, config: dict):
    """Process the request asynchronously using the workflow"""
    try:
        print(f"Starting async processing for session {session_id}")

        # Run the workflow
        async for event in workflow_app.astream(initial_state, config=config):
            print(f"Workflow event: {list(event.keys())}")

            # Update stored state
            if session_id in active_workflows:
                for node_name, node_state in event.items():
                    active_workflows[session_id]["last_state"] = node_state

        print(f"Workflow completed for session {session_id}")

    except Exception as e:
        print(f"Error in async processing for session {session_id}: {e}")
        if websocket_manager:
            await websocket_manager.send_message(
                session_id, f"Sorry, there was an error creating your plan: {str(e)}", "error"
            )


async def process_update_async(session_id: str, updated_state: AgentState, config: dict):
    """Process requirement updates asynchronously"""
    try:
        print(f"Processing requirement update for session {session_id}")

        # Continue the workflow from where it left off
        async for event in workflow_app.astream(updated_state, config=config):
            print(f"Update workflow event: {list(event.keys())}")

            # Update stored state
            if session_id in active_workflows:
                for node_name, node_state in event.items():
                    active_workflows[session_id]["last_state"] = node_state

        print(f"Update workflow completed for session {session_id}")

    except Exception as e:
        print(f"Error processing update for session {session_id}: {e}")
        if websocket_manager:
            await websocket_manager.send_message(
                session_id, f"Sorry, there was an error processing your update: {str(e)}", "error"
            )


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """Handle WebSocket connections for real-time updates"""
    await websocket_manager.connect(websocket, session_id)

    try:
        while True:
            # Keep connection alive and handle any incoming messages
            data = await websocket.receive_text()
            print(f"Received WebSocket message from {session_id}: {data}")

            # You could handle WebSocket-based updates here too
            try:
                message_data = json.loads(data)
                if message_data.get("type") == "update_requirements":
                    # Handle requirement updates via WebSocket
                    new_requirements = message_data.get("message")
                    if new_requirements:
                        # Trigger update via the same mechanism as HTTP
                        await handle_websocket_update(session_id, new_requirements)
            except json.JSONDecodeError:
                # Not JSON, ignore or handle as plain text
                pass

    except WebSocketDisconnect:
        websocket_manager.disconnect(session_id)
        print(f"WebSocket disconnected: {session_id}")


async def handle_websocket_update(session_id: str, new_requirements: str):
    """Handle requirement updates received via WebSocket"""
    if session_id in active_workflows:
        workflow_data = active_workflows[session_id]
        current_state = workflow_data.get("last_state", {})

        # Update requirements
        current_state["user_request"] = new_requirements
        current_state["requirements_history"].append(new_requirements)
        current_state["last_update_handled"] = False
        current_state["messages"].append(HumanMessage(content=new_requirements))

        # Process the update
        config = {"configurable": {"thread_id": session_id}}
        task = asyncio.create_task(process_update_async(session_id, current_state, config))
        workflow_data["task"] = task


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "active_sessions": len(active_workflows), "sessions": list(active_workflows.keys())}


@app.get("/sessions/{session_id}/status")
async def get_session_status(session_id: str):
    """Get the status of a specific session"""
    if session_id in active_workflows:
        workflow_data = active_workflows[session_id]
        task = workflow_data["task"]
        last_state = workflow_data.get("last_state", {})

        return {
            "session_id": session_id,
            "status": last_state.get("workflow_status", "unknown"),
            "processing": not task.done(),
            "requirements_count": len(last_state.get("requirements_history", [])),
            "has_final_plan": bool(last_state.get("final_plan")),
            "created_at": workflow_data.get("created_at", "").isoformat() if workflow_data.get("created_at") else None,
        }
    else:
        return {"session_id": session_id, "status": "not_found", "processing": False}


@app.get("/sessions/{session_id}/requirements")
async def get_session_requirements(session_id: str):
    """Get the requirements history for a session"""
    if session_id in active_workflows:
        last_state = active_workflows[session_id].get("last_state", {})
        return {
            "session_id": session_id,
            "original_request": last_state.get("original_request", ""),
            "current_request": last_state.get("user_request", ""),
            "requirements_history": last_state.get("requirements_history", []),
        }
    else:
        raise HTTPException(status_code=404, detail="Session not found")


if __name__ == "__main__":
    import uvicorn

    print("Starting Dynamic Exercise Planning Multi-Agent System...")
    print("HTTP API available at: http://localhost:8000")
    print("WebSocket endpoint: ws://localhost:8000/ws/{session_id}")
    print("Health check: http://localhost:8000/health")
    print("Features: Dynamic requirement updates, re-evaluation, selective re-running")

    uvicorn.run(app, host="0.0.0.0", port=8000)
