# System Patterns

## 1. Architecture

The system follows a component-based architecture composed of an Orchestrator, a State Manager, and Agent Definitions.

- **Orchestrator:** The central routing component that directs the flow of conversation.
- **State Manager:** A dedicated database layer (PostgreSQL) for managing conversation state, ensuring data integrity and performance.
- **Agent Definitions:** Modular, LLM-powered components with specific roles and capabilities.

## 2. Key Technical Decisions

- **Normalized Database Schema:** The conversation state is stored in two separate tables (`Conversations` and `Messages`) to avoid performance bottlenecks associated with updating large JSON objects. This design is optimized for efficient writes and queries.
- **Explicit Function Calling:** The Triage Agent uses the LLM's native function-calling feature to signal its intent. This provides a structured, reliable mechanism for the Orchestrator to interpret and act upon, rather than parsing natural language.
- **"Memory Switch" Handoff:** Agent handoffs are managed by the Orchestrator, which dynamically swaps the system prompt based on the agent currently in control. This allows for a clean separation of concerns between agents while maintaining a shared conversation history.
- **Modular Prompting:** For multi-coach handoffs, the system will generate a composite prompt by combining a base prompt with specialist instruction blocks. This creates a temporary, cohesive agent capable of handling multiple domains.
