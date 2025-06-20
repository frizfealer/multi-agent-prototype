# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a dynamic multi-agent exercise planning system built with LangGraph and FastAPI. The system demonstrates intelligent requirement updates, selective agent re-execution, and real-time communication via WebSockets.

## Development Commands

### Running the System
```bash
# Start the backend server
python backend.py

# Test with the client
python client.py
```

### Environment Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables (create .env file)
export OPENAI_API_KEY="your_api_key_here"
```

### Testing
- No formal test framework is configured
- Use `python client.py` for interactive testing with multiple scenarios
- Use `python test_fix.py` to test requirement context tracking fixes
- Health check endpoint: `GET http://localhost:8000/health`

## Architecture

### Core Components

**Multi-Agent Workflow (backend.py)**:
- **RequirementAnalyzer**: Uses GPT-4 to intelligently analyze requirement changes and determine re-execution strategy
- **WebSearchAgent**: Handles exercise and schedule research via DuckDuckGo
- **SummarizerAgent**: Combines search results into structured exercise plans
- **WebSocketManager**: Manages real-time connections and updates

**LangGraph State Management**:
- Uses `MemorySaver` for workflow checkpointing
- State includes requirement history, search results, and processing status
- Supports selective re-execution of agents based on change analysis

**Dynamic Update System**:
- Analyzes requirement changes using LLM
- Selective re-running: Only affected agents re-execute
- Three update types: minor clarifications, partial changes, major changes

### Communication Patterns

**HTTP + WebSocket Hybrid**:
- HTTP POST `/chat` for initial requests and updates
- WebSocket `/ws/{session_id}` for real-time progress updates
- Non-blocking: HTTP responds immediately, processing continues asynchronously

**Session Management**:
- `active_workflows` dict stores session state
- Each session has unique thread_id for LangGraph checkpointing
- Requirements history tracked for context

## Key Features

### Intelligent Re-evaluation
The system uses GPT-4 to analyze requirement updates and determines:
- `needs_exercise_research`: Whether to re-run exercise search
- `needs_schedule_research`: Whether to re-run schedule search  
- `needs_new_plan`: Whether to regenerate final plan
- `is_minor_clarification`: Whether to update existing plan without re-search

### Parallel Processing
- Exercise and schedule searches run concurrently using LangGraph edges
- Multiple concurrent user sessions supported
- Async/await throughout for non-blocking operations

### Error Handling
- Comprehensive error handling for web search failures, LLM API errors, WebSocket disconnections
- Graceful degradation with fallback responses

## File Structure

- `backend.py`: Main FastAPI server with LangGraph workflow
- `client.py`: Comprehensive test client with multiple scenarios
- `langgraph.ipynb`: Basic LangGraph prototype with Tavily search
- `requirements.txt`: Python dependencies
- `Readme.md`: Detailed documentation and usage examples

## Development Notes

### Requirement Context Tracking
The system now includes sophisticated requirement tracking to solve timing issues:

**Backend Implementation:**
- `WebSocketManager.send_message_with_context()` sends requirement metadata
- `summarization_node` calculates correct requirement numbers and previous requests
- Finds actual requirement position instead of assuming chronological order

**Client Implementation:**
- Parses requirement context from WebSocket messages
- Shows accurate requirement-to-plan correlation
- Enhanced session summaries with plan mapping
- Fallback to old method for backward compatibility

### Adding New Agents
```python
async def new_agent_node(state: AgentState) -> AgentState:
    # Agent logic here
    return state

# Add to workflow
workflow.add_node("new_agent", new_agent_node)
workflow.add_edge("planning", "new_agent")
```

### LangGraph State Schema
The `AgentState` TypedDict includes:
- `messages`: LangChain message history
- `session_id`, `user_request`, `original_request`
- `requirements_history`: List of all requirement updates
- `exercise_results`, `schedule_results`, `final_plan`
- `workflow_status`, `needs_rerun`, `last_update_handled`

### WebSocket Message Types
- `requirement_analysis`: Analysis of requirement changes
- `status_update`: General workflow progress
- `planning_start`: Beginning of planning phase
- `search_update`: Search progress updates
- `final_plan`: Completed exercise plan with requirement context
- `error`: Error messages

### Message Context System
All `final_plan` messages include requirement context for accurate tracking:
```json
{
  "type": "final_plan",
  "content": "Here is your plan...",
  "context": {
    "requirement_number": 3,
    "requirement_text": "Dumbbells only, no gym",
    "previous_request": "Change to 2x weekly only",
    "original_request": "6-week plan to get wider, 3x weekly",
    "is_update": true,
    "total_requirements": 4
  }
}
```

## API Endpoints

- `POST /chat`: Submit requests and updates
- `GET /sessions/{session_id}/status`: Check session status
- `GET /sessions/{session_id}/requirements`: Get requirements history
- `GET /health`: Server health check
- `WebSocket /ws/{session_id}`: Real-time updates

## Environment Variables

- `OPENAI_API_KEY`: Required for GPT-4 access
- Optional: `TAVILY_API_KEY` for notebook example

## Recent Improvements

### Phase 1: Requirement Context Tracking (Implemented)
**Problem Solved:** Client incorrectly correlated final plans with requirements due to async processing timing issues.

**Solution:** Server-side requirement context tracking
- Backend sends requirement metadata with each final plan
- Accurate requirement numbering and previous request tracking
- Client displays correct plan-to-requirement correlation
- Enhanced debugging and session summaries

### Known Issues Fixed
- ✅ **Timing Issue**: Final plans now show correct requirement numbers
- ✅ **"Updated from" Bug**: Shows actual previous requirement, not always original
- ✅ **WebSocket Serialization**: Removed non-serializable WebSocketManager from state
- ✅ **Concurrent Updates**: Eliminated LangGraph concurrent state update errors

## Production Considerations

The current implementation is a prototype. For production:
- Use Redis for session management and requirement context persistence
- Add authentication and rate limiting
- Implement proper logging and monitoring
- Use PostgreSQL for long-term storage of sessions and requirement history
- Add request debouncing for rapid updates
- Consider Phase 2: Enhanced bidirectional state tracking for complex scenarios