# Triage Agent System

A sophisticated AI assistant system built with FastAPI and Google Gemini, featuring a smart conversational router (Triage Agent) that handles user requests and routes complex tasks to specialist agents.

## Architecture Overview

The system follows the design outlined in `design_doc_triage_agent.md` with three core components:

1. **Orchestrator (Agent Router)**: Central backend logic that manages conversation flow
2. **State Manager**: Database layer for storing conversation state and history
3. **Triage Agent**: LLM-powered agent that classifies intent and routes requests

## Setup

### Option 1: Local Development

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Set up environment variables:

```bash
cp .env.example .env
# Edit .env with your Google API key and database URL
```

3. Set up PostgreSQL (required for JSONB support):

```bash
# Using Docker
docker run -d --name postgres-triage \
  -e POSTGRES_USER=user \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=triage_agent_db \
  -p 5432:5432 \
  postgres:15-alpine
```

4. Run the application:

```bash
python main.py
```

### Option 2: Docker Compose

1. Set up environment variables:

```bash
cp .env.example .env
# Edit .env with your Google API key
```

2. Run with Docker Compose:

```bash
docker-compose up -d
```

## API Usage

### Session Management

All API requests require an active session. Sessions expire after 30 minutes of inactivity.

#### Create Session

```bash
POST /api/v1/session/create
{
  "user_metadata": {  # Optional
    "user_id": "123",
    "preferences": {}
  }
}
```

Response:

```json
{
  "session_token": "secure-token-here",
  "session_id": "uuid-here",
  "expires_at": "2024-01-15T10:30:00Z"
}
```

#### Get Session Info

```bash
GET /api/v1/session/info
Headers: {
  "Authorization": "Bearer {session_token}"
}
```

#### Logout

```bash
POST /api/v1/session/logout
Headers: {
  "Authorization": "Bearer {session_token}"
}
```

### Chat Endpoint

Send a message to the triage agent (requires active session):

```bash
POST /api/v1/chat
Headers: {
  "Authorization": "Bearer {session_token}"
}
Body: {
  "message": "I need help creating a workout plan",
  "conversation_id": null  # Optional, for continuing conversations
}
```

Response:

```json
{
  "conversation_id": "uuid-here",
  "agent": "triage",
  "text": "I'd be happy to help you create a workout plan. What are your fitness goals?",
  "action": {
    "type": "handoff",
    "coaches": ["exercise_coach"]
  },
  "session_id": "session-uuid-here"
}
```

### Example Client Usage

```python
# See example_client.py for a complete example
client = TriageAgentClient()
await client.create_session({"user_id": "123"})
response = await client.chat("I need help with fitness")
```

## Testing

Tests require PostgreSQL for JSONB support:

```bash
# Start test database
docker-compose -f docker-compose.test.yml up -d

# Run tests
DATABASE_URL=postgresql+asyncpg://test:test@localhost:5433/test_triage_agent_db pytest

# Stop test database
docker-compose -f docker-compose.test.yml down
```

## Future Enhancements

- Implement specialist coach agents (exercise, nutrition, wellness, recovery)
- Add authentication and user management
- Implement actual action execution for direct requests
- Add comprehensive logging and monitoring
