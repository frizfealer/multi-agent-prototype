# Dynamic Exercise Planning Multi-Agent System with LangGraph

This implementation creates a sophisticated multi-agent system with **dynamic requirement updates** following your sequence diagram, using LangGraph for orchestration and supporting both HTTP/REST API and WebSocket real-time communication.

## Architecture Overview

The system implements the exact workflow from your sequence diagram with **enhanced dynamic capabilities**:

1. **Requirement Evaluation Agent** - Analyzes requirement updates and determines re-run strategy
2. **Planning Agent** - Orchestrates the entire workflow  
3. **Web Search Agent 1** - Searches for exercise information
4. **Web Search Agent 2** - Searches for training schedules
5. **Summarizer Agent** - Combines results into a final plan
6. **WebSocket Manager** - Handles real-time updates to users

## Key Features

✅ **Dynamic Requirement Updates**: Users can update requirements during processing
✅ **Intelligent Re-evaluation**: LLM analyzes changes and determines what needs re-running
✅ **Selective Re-execution**: Only re-runs necessary agents based on change analysis
✅ **Parallel Processing**: Exercise and schedule searches run concurrently
✅ **Real-time Updates**: WebSocket pushes progress updates to users
✅ **Non-blocking HTTP**: API responds immediately while processing continues asynchronously
✅ **Session Management**: Multiple concurrent users supported with state persistence
✅ **Error Handling**: Robust error handling throughout the pipeline
✅ **Memory**: LangGraph checkpointing for state management
✅ **Requirement History**: Tracks all requirement changes for context

## Requirements

Create a `requirements.txt` file:

```txt
fastapi==0.104.1
uvicorn[standard]==0.24.0
websockets==12.0
aiohttp==3.9.0
langgraph==0.2.16
langchain==0.1.0
langchain-openai==0.0.2
langchain-community==0.0.10
langchain-core==0.1.0
duckduckgo-search==3.9.6
pydantic==2.5.0
python-dotenv==1.0.0
```

## Environment Setup

Create a `.env` file:

```env
OPENAI_API_KEY=your_openai_api_key_here
```

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Set your OpenAI API key
export OPENAI_API_KEY="your_api_key_here"
```

## Running the System

### 1. Start the Server

```bash
python exercise_planning_system.py
```

The server will start on `http://localhost:8000` with:
- HTTP API endpoint: `POST /chat`
- WebSocket endpoint: `ws://localhost:8000/ws/{session_id}`
- Health check: `GET /health`

### 2. Test with the Client

```bash
python client_example.py
```

## API Usage

### Initial HTTP Request
```bash
curl -X POST "http://localhost:8000/chat" \
     -H "Content-Type: application/json" \
     -d '{
       "message": "I want to make an exercise plan to grow wider in six weeks, working out 2-3 times per week.",
       "session_id": "your-session-id",
       "is_update": false
     }'
```

### Requirement Update Request
```bash
curl -X POST "http://localhost:8000/chat" \
     -H "Content-Type: application/json" \
     -d '{
       "message": "Actually, I can only work out 2 times per week and only have dumbbells.",
       "session_id": "your-session-id", 
       "is_update": true
     }'
```

### WebSocket Connection
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/your-session-id');

// Receive updates
ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log(`${data.type}: ${data.content}`);
};

// Send requirement updates via WebSocket
ws.send(JSON.stringify({
    type: "update_requirements",
    message: "I need to change this to home workouts only"
}));
```

### Additional Endpoints
```bash
# Get session status
GET /sessions/{session_id}/status

# Get requirements history  
GET /sessions/{session_id}/requirements

# Health check
GET /health
```

## Dynamic Update Workflow Implementation

### 1. Requirement Evaluation Node
```python
async def requirement_evaluation_node(state: AgentState) -> AgentState:
    if len(state["requirements_history"]) > 1:
        # Analyze what changed using LLM
        analysis = await requirement_analyzer.analyze_update(
            original_request, current_request, history
        )
        
        # Determine what needs re-running
        if analysis["needs_exercise_research"]:
            state["exercise_results"] = None
        if analysis["needs_schedule_research"]:
            state["schedule_results"] = None
        if analysis["needs_new_plan"]:
            state["final_plan"] = None
```

### 2. Intelligent Re-execution Logic
The system uses an LLM to analyze requirement changes and determine:
- **Minor Clarifications**: Update existing plan without re-searching
- **Partial Changes**: Re-run only affected search agents  
- **Major Changes**: Complete workflow restart

### 3. State Management with Updates
```python
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    session_id: str
    user_request: str
    original_request: str  # Preserves initial request
    requirements_history: List[str]  # All updates tracked
    exercise_results: Optional[str]
    schedule_results: Optional[str] 
    final_plan: Optional[str]
    websocket_manager: Optional[object]
    workflow_status: str
    needs_rerun: bool  # Controls re-execution
    last_update_handled: bool  # Tracks processing state
```

## WebSocket Message Flow

### Initial Request Flow
1. **Initial**: "Got it. I'll create a custom exercise plan for you..."
2. **Progress**: "Found exercises for building width. Continuing research..."
3. **Progress**: "Found optimal training schedules. Combining everything..."
4. **Final**: "Here is your plan: [detailed plan]"

### Update Request Flow  
1. **Analysis**: "I've analyzed your updated requirements: [change summary]"
2. **Re-evaluation**: "Your requirements have changed significantly. I'm updating the research..."
3. **Progress**: Various progress updates based on what needs re-running
4. **Final**: "Here is your updated plan: [revised plan]"

### Message Types
- `requirement_analysis`: LLM analysis of requirement changes
- `status_update`: General workflow status updates
- `planning_start`: Beginning of planning phase
- `search_update`: Search progress updates
- `final_plan`: Completed exercise plan
- `error`: Error messages

## Testing the Dynamic System

### Basic Update Test
```python
import asyncio
from client_example import DynamicExercisePlanningClient

async def test_updates():
    client = DynamicExercisePlanningClient()
    
    initial_message = "6-week plan to get wider, 3x weekly"
    updates = [
        "Actually, I can only work out 2 times per week",
        "I only have access to dumbbells, no gym"
    ]
    
    await client.run_with_updates(initial_message, updates, [10, 8])

asyncio.run(test_updates())
```

### Testing Different Update Scenarios

**Minor Clarifications** (no re-search needed):
- "When I say wider, I mean shoulders and back"
- "I'm intermediate level, not beginner"  
- "I prefer compound movements"

**Partial Updates** (selective re-search):
- "Change from 3x to 2x per week" → Schedule re-search only
- "Focus on shoulders instead of back" → Exercise re-search only

**Major Changes** (full re-evaluation):
- "Change from 6 weeks to 10 weeks"
- "Home workouts only instead of gym"
- "Build strength instead of muscle size"

## Error Handling

The system includes comprehensive error handling:
- Web search failures
- LLM API errors
- WebSocket disconnections
- Network timeouts
- Session cleanup

## Monitoring

- **Health Check**: `GET /health` returns system status
- **Session Status**: `GET /sessions/{session_id}/status`
- **Logs**: Detailed logging throughout the workflow

## Customization

### Adding New Agents
```python
async def new_agent_node(state: AgentState) -> AgentState:
    # Your agent logic here
    return state

# Add to workflow
workflow.add_node("new_agent", new_agent_node)
workflow.add_edge("planning", "new_agent")
```

### Custom Search Queries
Modify the search queries in the agent nodes:
```python
search_query = "your custom search terms here"
```

### Different LLM Models
```python
llm = ChatOpenAI(model="gpt-4-turbo", temperature=0.7)
```

## Production Considerations

1. **Scaling**: Use Redis for session management and state persistence
2. **Security**: Add authentication, rate limiting, and input validation
3. **Monitoring**: Integrate with monitoring tools (Prometheus, Grafana)
4. **Persistence**: Use PostgreSQL for long-term storage of sessions and plans
5. **Load Balancing**: Deploy with multiple instances behind a load balancer
6. **Caching**: Cache search results to avoid redundant API calls
7. **Queue Management**: Use Celery or similar for managing long-running tasks
8. **Update Debouncing**: Implement debouncing for rapid successive updates

## Advanced Features

### Requirement Update Analysis
The system uses GPT-4 to intelligently analyze requirement changes:

```python
# Example analysis output
{
    "needs_exercise_research": true,
    "needs_schedule_research": false, 
    "needs_new_plan": true,
    "is_minor_clarification": false,
    "change_summary": "User changed from gym to home workouts",
    "reasoning": "Equipment availability change requires new exercise research"
}
```

### Smart Re-execution
- **Selective Agent Re-runs**: Only affected agents are re-executed
- **State Preservation**: Unaffected results are preserved to save time  
- **Progress Tracking**: Users see exactly what's being updated
- **History Maintenance**: Full requirement change history is maintained

This implementation provides a robust, production-ready foundation for dynamic multi-agent systems with intelligent requirement handling and real-time communication.