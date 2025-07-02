# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Triage Agent System - an AI-powered conversational router built with FastAPI and Google Gemini. The system follows a clear architectural pattern where a Triage Agent analyzes user intent and either handles simple requests directly or routes complex tasks to specialist agents.

## Key Architecture Components

1. **Orchestrator** (`src/core/orchestrator.py`): Central routing logic that manages conversation flow and agent handoffs
2. **State Manager** (`src/core/state_manager.py`): Database abstraction layer for conversation state persistence
3. **Triage Agent** (`src/agents/triage_agent.py`): Google Gemini-powered agent that uses function calling for intent classification
4. **Database Models** (`src/db/models.py`): SQLAlchemy models for Conversations and Messages tables

## Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py

# Run tests
pytest

# Run with coverage
pytest --cov=src

# Format code
black src tests

# Lint code
ruff check src tests
```

## Design Principles

- **Stateful Conversations**: All conversation history is persisted in the database
- **Function Calling**: Agents use explicit function calls (handoff_to_coach, execute_direct_request, ask_question) to signal intent
- **Agent Handoffs**: The "memory switch" mechanism allows seamless transitions between agents by updating the current_agent field
- **Async-First**: All database operations and API endpoints are async for better performance

## Adding New Features

When implementing new specialist agents:
1. Create the agent class in `src/agents/` following the TriageAgent pattern
2. Add the agent name to the Triage Agent's system prompt
3. Update the Orchestrator to handle the new agent in the routing logic
4. Ensure the agent uses function calling for any actions it needs to perform

## Important Considerations

- Always use Google Gemini API (not OpenAI) for LLM integration
- Database operations should go through StateManager for consistency
- Function calls from agents must be parsed from the Gemini response structure
- **PostgreSQL with JSONB is required** - The system relies on JSONB for storing complex nested conversation context data
- JSONB enables efficient queries on nested data (e.g., finding conversations by user goals, preferences)
- The context_data field stores rich, queryable state including user profiles, plans, metadata