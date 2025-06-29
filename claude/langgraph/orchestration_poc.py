"""
Proof of Concept: Async LangGraph Orchestration Architecture with HTTP-First Communication

This POC demonstrates:
1. Main orchestrator with async domain workflow dispatch
2. Atomic state reading from running domain workflows  
3. Context aggregation from running workflows
4. Non-blocking responsiveness with HTTP communication patterns
5. Production-ready workflow status polling

All components are mocked to focus on orchestration patterns.
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional, TypedDict, Any
from dataclasses import dataclass
from enum import Enum

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver


# ================== STATE DEFINITIONS ==================

class IntentState(TypedDict):
    """Main orchestrator state"""
    messages: List[BaseMessage]
    session_id: str
    user_message: str
    triage_result: Dict[str, Any]
    approval_status: Optional[str]
    domain_results: Dict[str, Any]


class ExerciseState(TypedDict):
    """Exercise domain workflow state"""
    messages: List[BaseMessage]
    session_id: str
    user_request: str
    requirements_history: List[str]
    exercise_results: Optional[str]
    final_plan: Optional[str]
    workflow_status: str
    progress: float
    current_step: str


class FinanceState(TypedDict):
    """Finance domain workflow state"""
    messages: List[BaseMessage]
    session_id: str
    user_request: str
    transaction_details: Dict[str, Any]
    risk_analysis: Optional[str]
    compliance_check: Optional[str]
    execution_result: Optional[str]
    workflow_status: str
    progress: float
    current_step: str


# ================== MOCK COMPONENTS ==================

@dataclass
class MockHTTPResponseManager:
    """Mock HTTP response manager for testing"""
    responses: List[Dict[str, Any]] = None
    workflow_updates: Dict[str, List[Dict[str, Any]]] = None
    
    def __post_init__(self):
        if self.responses is None:
            self.responses = []
        if self.workflow_updates is None:
            self.workflow_updates = {}
    
    def log_immediate_response(self, session_id: str, response: dict):
        """Log immediate HTTP response"""
        response_data = {
            "session_id": session_id,
            "response_type": "immediate",
            "data": response,
            "timestamp": datetime.now().isoformat()
        }
        self.responses.append(response_data)
        print(f"📤 HTTP Response to {session_id}: {response.get('status', 'unknown')}")
        if response.get('workflow_id'):
            print(f"   Workflow ID: {response['workflow_id']}")
        if response.get('immediate_response'):
            print(f"   Message: {response['immediate_response']}")
    
    def log_workflow_update(self, workflow_id: str, update: dict):
        """Log workflow status update (for polling endpoints)"""
        if workflow_id not in self.workflow_updates:
            self.workflow_updates[workflow_id] = []
        
        update_data = {
            "type": "status_update",
            "data": update,
            "timestamp": datetime.now().isoformat()
        }
        self.workflow_updates[workflow_id].append(update_data)
        print(f"📊 Workflow Update [{workflow_id}]: {update.get('status', 'unknown')} ({update.get('progress', 0):.0%})")
        if update.get('current_step'):
            print(f"   Step: {update['current_step']}")
    
    def get_workflow_status(self, workflow_id: str) -> dict:
        """Get latest workflow status (simulates GET /workflow/{id}/status)"""
        updates = self.workflow_updates.get(workflow_id, [])
        if updates:
            latest = updates[-1]["data"]
            print(f"🔍 HTTP GET /workflow/{workflow_id}/status -> {latest.get('status', 'unknown')}")
            return latest
        else:
            return {"status": "not_found", "workflow_id": workflow_id}


class MockTriageAgent:
    """Mock triage agent for POC"""
    
    async def classify_and_route(self, message: str) -> Dict[str, Any]:
        """Mock intent classification"""
        await asyncio.sleep(0.1)  # Simulate processing time
        
        message_lower = message.lower()
        
        if "workout" in message_lower or "exercise" in message_lower:
            return {
                "action": "direct_process",
                "intent_type": "Create Request",
                "domain": "exercise_planning",
                "confidence": 0.9,
                "reasoning": "High confidence exercise planning request"
            }
        elif "transfer" in message_lower or "payment" in message_lower:
            return {
                "action": "confirm", 
                "intent_type": "Create Request",
                "domain": "finance",
                "confidence": 0.85,
                "confirmation_message": "You want to make a financial transaction. Should I proceed?",
                "reasoning": "High confidence financial transaction requiring approval"
            }
        elif any(word in message_lower for word in ["question", "what", "how", "good", "should", "can", "?"]):
            return {
                "action": "direct_process",
                "intent_type": "Query", 
                "domain": "general",
                "confidence": 0.8,
                "reasoning": "General query request"
            }
        else:
            return {
                "action": "reject",
                "intent_type": "Unknown",
                "domain": "other",
                "confidence": 0.3,
                "redirect_message": "I specialize in exercise planning and finance. How can I help with those?",
                "reasoning": "Low confidence, unclear intent"
            }
    
    def is_confirmation_response(self, message: str) -> str:
        """Mock confirmation parsing"""
        message_lower = message.lower().strip()
        if message_lower in ["yes", "y", "sure", "ok", "proceed"]:
            return "yes"
        elif message_lower in ["no", "n", "cancel", "stop"]:
            return "no"
        else:
            return "unclear"


class MockQueryProcessor:
    """Mock query processor for POC"""
    
    async def process_query(self, query: str, context: Dict[str, Any], 
                          conversation_history: List[BaseMessage]) -> str:
        """Mock query processing with context"""
        await asyncio.sleep(0.2)  # Simulate processing time
        
        running_workflows = context.get("running_workflows", {})
        completed_workflows = context.get("completed_workflows", {})
        
        response_parts = [f"Based on your question: '{query}'"]
        
        if running_workflows:
            response_parts.append(f"\nI can see you have {len(running_workflows)} workflows currently running:")
            for domain, ctx in running_workflows.items():
                response_parts.append(f"- {domain}: {ctx['status']} ({ctx['progress']:.0%} complete)")
        
        if completed_workflows:
            response_parts.append(f"\nYou also have {len(completed_workflows)} completed workflows I can reference.")
        
        response_parts.append("\nThis is a mock response demonstrating real-time context access!")
        
        return "\n".join(response_parts)


# ================== WORKFLOW STATE READER ==================

class WorkflowStateReader:
    """Atomic state reading from running domain workflows"""
    
    def __init__(self, domain_workflows: Dict[str, StateGraph], running_workflows: Dict[str, asyncio.Task]):
        self.domain_workflows = domain_workflows
        self.running_workflows = running_workflows
    
    async def read_domain_workflow_state(self, thread_id: str, domain: str) -> Optional[dict]:
        """Read current state of running domain workflow atomically"""
        try:
            domain_workflow = self.domain_workflows[domain]
            config = {"configurable": {"thread_id": thread_id}}
            
            # LangGraph atomic state read - doesn't interfere with execution!
            current_state = await domain_workflow.aget_state(config)
            
            if current_state and current_state.values:
                return current_state.values
            return None
            
        except Exception as e:
            print(f"❌ Error reading workflow state {thread_id}: {e}")
            return None
    
    async def get_all_domain_contexts(self, session_id: str) -> Dict[str, dict]:
        """Get context from all running domain workflows for this session"""
        contexts = {}
        
        # Find all running workflows for this session
        for thread_id, task in self.running_workflows.items():
            if thread_id.startswith(session_id) and not task.done():
                # Extract domain from thread_id format: "session_id_domain"
                try:
                    domain = thread_id.split(f"{session_id}_", 1)[1]
                    
                    # Read current state atomically
                    state = await self.read_domain_workflow_state(thread_id, domain)
                    if state:
                        contexts[domain] = {
                            "thread_id": thread_id,
                            "status": state.get("workflow_status", "unknown"),
                            "progress": state.get("progress", 0.0),
                            "current_step": state.get("current_step", "unknown"),
                            "partial_results": {
                                k: v for k, v in state.items() 
                                if k.endswith("_results") or k.endswith("_analysis")
                            }
                        }
                except Exception as e:
                    print(f"❌ Error processing thread_id {thread_id}: {e}")
                    continue
        
        return contexts


# ================== MAIN ORCHESTRATOR ==================

class AsyncOrchestrationSystem:
    """Main async orchestration system with HTTP-first communication"""
    
    def __init__(self):
        self.http_manager = MockHTTPResponseManager()
        self.triage_agent = MockTriageAgent()
        self.query_processor = MockQueryProcessor()
        
        # Domain workflows will be created separately
        self.domain_workflows: Dict[str, StateGraph] = {}
        self.running_workflows: Dict[str, asyncio.Task] = {}
        self.workflow_results: Dict[str, dict] = {}  # Store completed results
        
        # State reader for atomic access
        self.state_reader = WorkflowStateReader(self.domain_workflows, self.running_workflows)
        
        # Pending approvals (for human-in-the-loop)
        self.pending_approvals: Dict[str, Dict[str, Any]] = {}
        
        # Create main orchestrator
        self.main_orchestrator = self._create_main_orchestrator()
    
    def _create_main_orchestrator(self) -> StateGraph:
        """Create main intent routing workflow"""
        workflow = StateGraph(IntentState)
        
        workflow.add_node("triage_agent", self._triage_node)
        workflow.add_node("approval_handler", self._approval_node)
        workflow.add_node("query_processor", self._query_node)
        workflow.add_node("domain_launcher", self._domain_launcher_node)
        
        workflow.add_edge(START, "triage_agent")
        
        workflow.add_conditional_edges(
            "triage_agent",
            self._route_after_triage,
            {
                "needs_approval": "approval_handler",
                "direct_query": "query_processor",
                "direct_action": "domain_launcher",
                "low_confidence": END
            }
        )
        
        workflow.add_conditional_edges(
            "approval_handler",
            self._route_after_approval,
            {
                "approved": "domain_launcher",
                "rejected": END,
                "wait": "approval_handler"  # Human-in-the-loop interrupt
            }
        )
        
        workflow.add_edge("query_processor", END)
        workflow.add_edge("domain_launcher", END)
        
        return workflow.compile(
            checkpointer=MemorySaver(),
            interrupt_before=["approval_handler"]
        )
    
    async def _triage_node(self, state: IntentState) -> IntentState:
        """Triage agent node - classify user intent"""
        print(f"🔍 Triage: Analyzing message '{state['user_message']}'")
        
        triage_result = await self.triage_agent.classify_and_route(state["user_message"])
        state["triage_result"] = triage_result
        
        print(f"🎯 Triage Result: {triage_result['action']} -> {triage_result['intent_type']} ({triage_result['confidence']:.2f})")
        
        # No immediate HTTP response needed - triage is internal processing
        # Results will be returned in the final HTTP response
        
        return state
    
    def _route_after_triage(self, state: IntentState) -> str:
        """Route based on triage result"""
        action = state["triage_result"]["action"]
        intent_type = state["triage_result"]["intent_type"]
        
        if action == "confirm":
            return "needs_approval"
        elif action == "direct_process" and intent_type == "Query":
            return "direct_query"
        elif action == "direct_process":
            return "direct_action"
        else:
            return "low_confidence"
    
    async def _approval_node(self, state: IntentState) -> IntentState:
        """Handle approval workflow (human-in-the-loop)"""
        session_id = state["session_id"]
        triage_result = state["triage_result"]
        
        if session_id in self.pending_approvals:
            # Handle approval response
            approval_data = self.pending_approvals[session_id]
            user_response = state["user_message"]
            
            confirmation_result = self.triage_agent.is_confirmation_response(user_response)
            state["approval_status"] = confirmation_result
            
            if confirmation_result in ["yes", "no"]:
                del self.pending_approvals[session_id]
                
                if confirmation_result == "yes":
                    await self.websocket_manager.send_message(
                        session_id, "Great! I'll proceed with your request.", "approval_confirmed"
                    )
                else:
                    await self.websocket_manager.send_message(
                        session_id, "Request cancelled. How else can I help?", "approval_rejected"
                    )
            else:
                await self.websocket_manager.send_message(
                    session_id, "Please respond with 'yes' to proceed or 'no' to cancel.", "approval_clarification"
                )
        else:
            # Send approval request
            await self.websocket_manager.send_message(
                session_id,
                triage_result.get("confirmation_message", "Do you want me to proceed?"),
                "approval_request"
            )
            
            self.pending_approvals[session_id] = {
                "triage_result": triage_result,
                "timestamp": datetime.now()
            }
            state["approval_status"] = "waiting"
        
        return state
    
    def _route_after_approval(self, state: IntentState) -> str:
        """Route based on approval status"""
        approval_status = state.get("approval_status")
        
        if approval_status == "yes":
            return "approved"
        elif approval_status == "no":
            return "rejected"
        else:
            return "wait"  # Interrupt for human input
    
    async def _query_node(self, state: IntentState) -> IntentState:
        """Query processing with real-time domain workflow context"""
        print(f"🔍 Query: Processing '{state['user_message']}'")
        
        session_id = state["session_id"]
        
        # Get context from ALL currently running domain workflows
        domain_contexts = await self.state_reader.get_all_domain_contexts(session_id)
        
        # Mock completed workflows context
        completed_contexts = {}  # Would come from SessionManager in real implementation
        
        # Merge running + completed contexts
        full_context = {
            "running_workflows": domain_contexts,
            "completed_workflows": completed_contexts,
            "total_active_workflows": len(domain_contexts)
        }
        
        print(f"📊 Query Context: {len(domain_contexts)} running, {len(completed_contexts)} completed workflows")
        
        # Process query with full multi-domain context
        response = await self.query_processor.process_query(
            state["user_message"], full_context, state["messages"]
        )
        
        # Update state
        state["domain_results"]["query_response"] = {
            "answer": response,
            "context_used": domain_contexts,
            "timestamp": datetime.now().isoformat()
        }
        
        # No immediate notification needed - query response returned in HTTP response
        
        return state
    
    async def _domain_launcher_node(self, state: IntentState) -> IntentState:
        """Launch domain workflow asynchronously and return immediately"""
        triage_result = state["triage_result"]
        domain = triage_result["domain"]
        session_id = state["session_id"]
        thread_id = f"{session_id}_{domain}"
        
        print(f"🚀 Domain Launcher: Starting {domain} workflow for {session_id}")
        
        # Create domain state
        domain_state = self._create_domain_state(state, domain)
        
        # Launch domain workflow asynchronously (fire-and-forget)
        task = asyncio.create_task(
            self._run_domain_workflow_async(domain, domain_state, thread_id)
        )
        
        # Track running workflow
        self.running_workflows[thread_id] = task
        
        # Update main state immediately - no waiting!
        state["domain_results"][domain] = {
            "status": "launched",
            "thread_id": thread_id,
            "launched_at": datetime.now().isoformat()
        }
        
        # No immediate notification needed - HTTP response will include workflow_id
        # Client can poll GET /workflow/{thread_id}/status for updates
        
        print(f"✅ Domain workflow {domain} launched async. Main orchestrator continues!")
        
        return state
    
    def _create_domain_state(self, main_state: IntentState, domain: str) -> dict:
        """Create domain-specific state from main orchestrator state"""
        base_state = {
            "session_id": main_state["session_id"],
            "messages": main_state["messages"],
            "user_request": main_state["user_message"],
            "workflow_status": "initializing",
            "progress": 0.0,
            "current_step": "starting"
        }
        
        # Add domain-specific fields
        if domain == "exercise_planning":
            base_state.update({
                "requirements_history": [main_state["user_message"]],
                "exercise_results": None,
                "final_plan": None
            })
        elif domain == "finance":
            base_state.update({
                "transaction_details": {},
                "risk_analysis": None,
                "compliance_check": None,
                "execution_result": None
            })
        
        return base_state
    
    async def _run_domain_workflow_async(self, domain: str, domain_state: dict, thread_id: str):
        """Run domain workflow asynchronously with lifecycle tracking"""
        session_id = thread_id.split(f"_{domain}")[0]
        
        try:
            print(f"🔄 Starting {domain} workflow execution for {thread_id}")
            
            config = {"configurable": {"thread_id": thread_id}}
            domain_workflow = self.domain_workflows[domain]
            
            # Stream workflow execution
            async for event in domain_workflow.astream(domain_state, config=config):
                node_name, node_state = next(iter(event.items()))
                
                # Log progress updates (available via polling)
                await self._log_workflow_progress(thread_id, domain, node_name, node_state)
            
            # Workflow completed successfully
            final_state = await domain_workflow.aget_state(config)
            await self._handle_workflow_completion(thread_id, domain, final_state.values)
            
        except Exception as e:
            # Workflow failed
            print(f"❌ {domain} workflow failed for {thread_id}: {e}")
            await self._handle_workflow_failure(thread_id, domain, str(e))
        
        finally:
            # Clean up from tracking
            if thread_id in self.running_workflows:
                del self.running_workflows[thread_id]
                print(f"🧹 Cleaned up {thread_id} from running workflows")
    
    async def _log_workflow_progress(self, thread_id: str, domain: str, node_name: str, node_state: dict):
        """Log workflow progress updates (available via status polling)"""
        
        progress_update = {
            "status": "running",
            "domain": domain,
            "current_node": node_name,
            "workflow_status": node_state.get("workflow_status", "unknown"),
            "progress": node_state.get("progress", 0.0),
            "current_step": node_state.get("current_step", node_name),
            "workflow_id": thread_id
        }
        
        # Log update for HTTP status polling
        self.http_manager.log_workflow_update(thread_id, progress_update)
    
    async def _handle_workflow_completion(self, thread_id: str, domain: str, final_state: dict):
        """Handle successful workflow completion"""
        
        print(f"✅ {domain} workflow completed for {thread_id}")
        
        # Store completion result (available via status polling)
        completion_result = {
            "status": "completed",
            "progress": 1.0,
            "workflow_id": thread_id,
            "domain": domain,
            "final_result": final_state.get("final_plan") or final_state.get("execution_result", "Workflow completed"),
            "completed_at": datetime.now().isoformat()
        }
        
        # Store for immediate retrieval
        self.workflow_results[thread_id] = completion_result
        
        # Log final update
        self.http_manager.log_workflow_update(thread_id, completion_result)
    
    async def _handle_workflow_failure(self, thread_id: str, domain: str, error: str):
        """Handle workflow failure"""
        
        print(f"❌ {domain} workflow failed for {thread_id}: {error}")
        
        # Store failure result (available via status polling)
        failure_result = {
            "status": "failed",
            "workflow_id": thread_id,
            "domain": domain,
            "error": error,
            "failed_at": datetime.now().isoformat()
        }
        
        # Store for immediate retrieval
        self.workflow_results[thread_id] = failure_result
        
        # Log failure update
        self.http_manager.log_workflow_update(thread_id, failure_result)
    
    async def process_message(self, session_id: str, message: str) -> dict:
        """Main entry point - process user message through orchestration"""
        print(f"\n{'='*50}")
        print(f"📥 Processing message from {session_id}: '{message}'")
        print(f"{'='*50}")
        
        # Create initial state
        initial_state: IntentState = {
            "messages": [HumanMessage(content=message)],
            "session_id": session_id,
            "user_message": message,
            "triage_result": {},
            "approval_status": None,
            "domain_results": {}
        }
        
        # Run main orchestrator
        config = {"configurable": {"thread_id": f"main_{session_id}"}}
        
        final_state = initial_state  # Default fallback
        async for event in self.main_orchestrator.astream(initial_state, config=config):
            # Get the last state from the event
            if isinstance(event, dict):
                for node_name, node_state in event.items():
                    if isinstance(node_state, dict):
                        final_state = node_state
            else:
                print(f"Debug: Unexpected event type: {type(event)}, value: {event}")
        
        # Create HTTP-style response
        triage_result = final_state.get("triage_result", {})
        domain_results = final_state.get("domain_results", {})
        
        # Extract workflow ID if launched
        workflow_id = None
        for domain, result_data in domain_results.items():
            if result_data.get("status") == "launched":
                workflow_id = result_data["thread_id"]
                break
        
        # Determine response based on workflow type
        if triage_result.get("intent_type") == "Query":
            # Query was answered immediately
            response = {
                "status": "completed",
                "session_id": session_id,
                "immediate_response": domain_results.get("query_response", {}).get("answer", "Query processed"),
                "workflow_id": None,
                "estimated_duration": None
            }
        elif triage_result.get("action") == "reject":
            # Request rejected
            response = {
                "status": "rejected", 
                "session_id": session_id,
                "immediate_response": triage_result.get("redirect_message", "Request not supported"),
                "workflow_id": None,
                "estimated_duration": None
            }
        elif workflow_id:
            # Workflow launched
            domain = triage_result.get("domain", "unknown")
            response = {
                "status": "processing",
                "session_id": session_id,
                "workflow_id": workflow_id,
                "immediate_response": f"Started {domain} workflow. Check status for progress.",
                "estimated_duration": "30-60 seconds"
            }
        else:
            # Fallback
            response = {
                "status": "completed",
                "session_id": session_id,
                "immediate_response": "Request processed",
                "workflow_id": None,
                "estimated_duration": None
            }
        
        # Log HTTP response
        self.http_manager.log_immediate_response(session_id, response)
        
        print(f"📤 Main orchestrator completed for {session_id}")
        return response
    
    async def get_workflow_status(self, workflow_id: str) -> dict:
        """Get current workflow status (simulates GET /workflow/{id}/status)"""
        
        # Check if workflow is complete
        if workflow_id in self.workflow_results:
            return self.workflow_results[workflow_id]
        
        # Check if workflow is still running
        if workflow_id in self.running_workflows:
            task = self.running_workflows[workflow_id]
            
            if task.done():
                # Task completed, get result
                try:
                    result = await task
                    completed_result = {
                        "status": "completed",
                        "progress": 1.0,
                        "workflow_id": workflow_id,
                        "final_result": result.get("final_plan") or result.get("execution_result", "Workflow completed"),
                        "completed_at": datetime.now().isoformat()
                    }
                    self.workflow_results[workflow_id] = completed_result
                    del self.running_workflows[workflow_id]
                    return completed_result
                except Exception as e:
                    error_result = {
                        "status": "failed",
                        "error": str(e),
                        "workflow_id": workflow_id
                    }
                    self.workflow_results[workflow_id] = error_result
                    return error_result
            else:
                # Still running - get current state via atomic read
                try:
                    domain = workflow_id.split("_")[-1]  # Extract domain from thread_id
                    current_state = await self.state_reader.read_domain_workflow_state(workflow_id, domain)
                    
                    if current_state:
                        status_result = {
                            "status": "running",
                            "progress": current_state.get("progress", 0.0),
                            "current_step": current_state.get("current_step", "Processing"),
                            "workflow_status": current_state.get("workflow_status", "unknown"),
                            "workflow_id": workflow_id,
                            "partial_results": {
                                k: v for k, v in current_state.items() 
                                if k.endswith("_results") or k.endswith("_analysis")
                            }
                        }
                        
                        # Log workflow update for HTTP polling simulation
                        self.http_manager.log_workflow_update(workflow_id, status_result)
                        
                        return status_result
                    else:
                        return {
                            "status": "running",
                            "progress": 0.0,
                            "current_step": "Initializing",
                            "workflow_id": workflow_id
                        }
                except Exception as e:
                    return {
                        "status": "error",
                        "error": f"Failed to read workflow state: {str(e)}",
                        "workflow_id": workflow_id
                    }
        
        # Workflow not found
        return {
            "status": "not_found", 
            "workflow_id": workflow_id
        }


# ================== DOMAIN WORKFLOWS ==================

def create_exercise_workflow() -> StateGraph:
    """Create mock exercise planning workflow"""
    
    async def requirement_analysis_node(state: ExerciseState) -> ExerciseState:
        """Mock requirement analysis"""
        print(f"🏃 Exercise: Analyzing requirements for {state['session_id']}")
        await asyncio.sleep(1)  # Simulate processing time
        
        state["workflow_status"] = "analyzing_requirements"
        state["progress"] = 0.2
        state["current_step"] = "Analyzing your fitness goals and requirements"
        return state
    
    async def exercise_search_node(state: ExerciseState) -> ExerciseState:
        """Mock exercise research"""
        print(f"🔍 Exercise: Searching for exercises for {state['session_id']}")
        await asyncio.sleep(2)  # Simulate longer processing
        
        state["exercise_results"] = "Mock exercise research: Push-ups, Pull-ups, Squats, Deadlifts"
        state["workflow_status"] = "researching_exercises"
        state["progress"] = 0.6
        state["current_step"] = "Researching best exercises for your goals"
        return state
    
    async def plan_generation_node(state: ExerciseState) -> ExerciseState:
        """Mock plan generation"""
        print(f"📋 Exercise: Generating plan for {state['session_id']}")
        await asyncio.sleep(1.5)
        
        state["final_plan"] = f"""
        Mock 4-Week Workout Plan:
        Week 1-2: Foundation Building
        - Day 1: Push-ups (3x8), Squats (3x10)
        - Day 2: Pull-ups (3x5), Deadlifts (3x8)
        - Day 3: Rest
        
        Week 3-4: Progression
        - Day 1: Push-ups (3x12), Squats (3x15)
        - Day 2: Pull-ups (3x8), Deadlifts (3x10)
        - Day 3: Rest
        
        Generated for: {state['user_request']}
        """
        state["workflow_status"] = "completed"
        state["progress"] = 1.0
        state["current_step"] = "Plan generation complete"
        return state
    
    workflow = StateGraph(ExerciseState)
    
    workflow.add_node("requirement_analysis", requirement_analysis_node)
    workflow.add_node("exercise_search", exercise_search_node)
    workflow.add_node("plan_generation", plan_generation_node)
    
    workflow.add_edge(START, "requirement_analysis")
    workflow.add_edge("requirement_analysis", "exercise_search")
    workflow.add_edge("exercise_search", "plan_generation")
    workflow.add_edge("plan_generation", END)
    
    return workflow.compile(checkpointer=MemorySaver())


def create_finance_workflow() -> StateGraph:
    """Create mock finance workflow"""
    
    async def risk_analysis_node(state: FinanceState) -> FinanceState:
        """Mock risk analysis"""
        print(f"💰 Finance: Risk analysis for {state['session_id']}")
        await asyncio.sleep(1.2)
        
        state["risk_analysis"] = "Mock risk analysis: Medium risk transaction detected"
        state["workflow_status"] = "analyzing_risk"
        state["progress"] = 0.3
        state["current_step"] = "Analyzing transaction risk factors"
        return state
    
    async def compliance_check_node(state: FinanceState) -> FinanceState:
        """Mock compliance check"""
        print(f"📋 Finance: Compliance check for {state['session_id']}")
        await asyncio.sleep(0.8)
        
        state["compliance_check"] = "Mock compliance: All regulatory requirements met"
        state["workflow_status"] = "checking_compliance"
        state["progress"] = 0.7
        state["current_step"] = "Verifying regulatory compliance"
        return state
    
    async def execution_node(state: FinanceState) -> FinanceState:
        """Mock transaction execution"""
        print(f"✅ Finance: Executing transaction for {state['session_id']}")
        await asyncio.sleep(1.0)
        
        state["execution_result"] = "Mock execution: Transaction completed successfully. Reference: TXN123456"
        state["workflow_status"] = "completed"
        state["progress"] = 1.0
        state["current_step"] = "Transaction execution complete"
        return state
    
    workflow = StateGraph(FinanceState)
    
    workflow.add_node("risk_analysis", risk_analysis_node)
    workflow.add_node("compliance_check", compliance_check_node)
    workflow.add_node("execution", execution_node)
    
    workflow.add_edge(START, "risk_analysis")
    workflow.add_edge("risk_analysis", "compliance_check")
    workflow.add_edge("compliance_check", "execution")
    workflow.add_edge("execution", END)
    
    return workflow.compile(checkpointer=MemorySaver())


# ================== POC SETUP ==================

def setup_poc_system() -> AsyncOrchestrationSystem:
    """Setup the complete POC system"""
    system = AsyncOrchestrationSystem()
    
    # Add domain workflows
    system.domain_workflows["exercise_planning"] = create_exercise_workflow()
    system.domain_workflows["finance"] = create_finance_workflow()
    
    # Update state reader with workflows
    system.state_reader = WorkflowStateReader(system.domain_workflows, system.running_workflows)
    
    return system


# ================== MAIN POC DEMO ==================

async def run_poc_demo():
    """Run POC demonstration scenarios with HTTP patterns"""
    print("🚀 Starting Async LangGraph Orchestration POC Demo (HTTP-First)")
    print("=" * 70)
    
    system = setup_poc_system()
    
    # Scenario 1: Exercise planning request
    print("\n📋 SCENARIO 1: Exercise Planning Request (HTTP POST /chat)")
    result1 = await system.process_message("user_123", "Create a 4-week workout plan for me")
    print(f"HTTP Response: {result1}")
    
    # Scenario 2: Check workflow status via polling
    if result1.get("workflow_id"):
        print("\n📊 SCENARIO 2: Workflow Status Polling (HTTP GET /workflow/{id}/status)")
        workflow_id = result1["workflow_id"]
        
        # Simulate polling every 2 seconds
        for i in range(3):
            await asyncio.sleep(2)
            status = await system.get_workflow_status(workflow_id)
            print(f"Poll {i+1}: {status}")
            if status["status"] in ["completed", "failed"]:
                break
    
    # Scenario 3: Query while exercise workflow is running
    print("\n❓ SCENARIO 3: Query During Running Workflow")
    result3 = await system.process_message("user_123", "What exercises are good for building strength?")
    print(f"HTTP Response: {result3}")
    
    # Scenario 4: Finance transaction (requires approval)
    print("\n💰 SCENARIO 4: Finance Transaction (Approval Required)")
    result4 = await system.process_message("user_456", "Transfer $5000 to my savings account")
    print(f"HTTP Response: {result4}")
    
    # Scenario 5: Start another workflow for different user
    print("\n🏋️ SCENARIO 5: Different User Workflow")
    result5 = await system.process_message("user_789", "Create an exercise routine")
    print(f"HTTP Response: {result5}")
    
    # Scenario 6: Poll multiple workflows
    print("\n📊 SCENARIO 6: Multi-Workflow Status Check")
    active_workflows = [wf_id for wf_id in system.running_workflows.keys()]
    for workflow_id in active_workflows[:2]:  # Check first 2
        status = await system.get_workflow_status(workflow_id)
        print(f"Workflow {workflow_id}: {status['status']} ({status.get('progress', 0):.0%})")
    
    # Wait for workflows to complete
    print("\n⏳ Waiting for domain workflows to complete...")
    await asyncio.sleep(6)
    
    # Final status check
    print(f"\n📊 FINAL STATUS:")
    print(f"Running workflows: {len(system.running_workflows)}")
    print(f"Completed workflows: {len(system.workflow_results)}")
    print(f"HTTP responses logged: {len(system.http_manager.responses)}")
    
    # Show final workflow results
    print(f"\n✅ Final Workflow Results:")
    for workflow_id, result in system.workflow_results.items():
        print(f"- {workflow_id}: {result['status']}")
    
    # Show HTTP communication summary  
    print(f"\n📡 HTTP Communication Summary:")
    immediate_responses = len(system.http_manager.responses)
    total_status_updates = sum(len(updates) for updates in system.http_manager.workflow_updates.values())
    print(f"- Immediate responses (POST /chat): {immediate_responses}")
    print(f"- Status updates (GET /workflow/*/status): {total_status_updates}")
    print(f"- Total HTTP interactions: {immediate_responses + total_status_updates}")


if __name__ == "__main__":
    # Run the POC demo
    asyncio.run(run_poc_demo())