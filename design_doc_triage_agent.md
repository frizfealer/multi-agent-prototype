1. Overview
This document outlines the initial architecture for a sophisticated AI assistant, focusing on the primary user-facing component: the Triage Agent. The Triage Agent's sole responsibility is to act as a smart, conversational router. It interacts with the user to understand their intent and either handles simple, direct requests itself or hands off complex tasks to future specialist agents.

The core principles of this initial design are:

Clear Responsibility: The Triage Agent manages the conversation flow and initial intent classification.

Stateful Interaction: The system maintains the state of each conversation, remembering context across multiple turns.

Reliable Actions: The agent uses explicit function calls to signal its intent, creating a robust and predictable system.

Foundation for Scalability: This design serves as a solid base upon which specialist "Coach" agents can be added later.

2. Core Components
For this initial phase, the system is composed of three main components:

Orchestrator (Agent Router): The central backend logic. It receives all user messages, loads the current conversation state, and routes the request to the Triage Agent.

State Manager: A database (e.g., Postgres) responsible for storing and retrieving the conversation state.

Triage Agent Definition: The LLM-powered brain of the system, defined by a system prompt that outlines its role, options, and required output format.

3. Data Structures
3.1. Database Schema
To ensure performance and scalability, the conversation state is normalized across two separate tables instead of being stored as a single large object. This avoids inefficiently updating a large array for each new message.

Table 1: Conversations
This table stores the primary state for each ongoing conversation.

Column Name

Data Type

Description

conversation_id

UUID (Primary Key)

Unique identifier for the conversation.

current_agent

VARCHAR(255)

The agent currently handling the conversation (e.g., "triage").

context_data

JSONB

Stores intent, summary, and other evolving context.

created_at

TIMESTAMP

Timestamp of when the conversation started.

updated_at

TIMESTAMP

Timestamp of the last update.

Table 2: Messages
This table stores the history of the conversation, with each message as a separate row.

Column Name

Data Type

Description

message_id

UUID (Primary Key)

Unique identifier for the message.

conversation_id

UUID (Foreign Key)

Links the message to the Conversations table.

role

VARCHAR(255)

The role of the message sender (e.g., "user", "agent").

content

TEXT

The text content of the message.

created_at

TIMESTAMP

Timestamp of when the message was created.

3.2. Agent Action (Function Call)
The Triage Agent signals its intent to the Orchestrator by using the LLM's native function-calling capabilities. When the agent decides to call a function, the API response will contain a function_call object within its structure (e.g., response.candidates[0].content.parts[0].function_call). The Orchestrator is responsible for parsing this specific field to determine the next action.

Example function_call object:

{
  "name": "handoff_to_coach",
  "args": {
    "coach_names": ["exercise_coach", "nutrition_coach"]
  }
}

The agent may also return natural language text alongside the function call, which can be used for logging or as a direct message to the user if no function is called.

4. Detailed Workflow (Sequence Diagram)
This diagram illustrates how the Triage Agent handles different types of requests.

sequenceDiagram
    participant User
    participant Orchestrator
    participant TriageAgent

    %% Scenario 1: Complex Task -> Handoff %%
    User->>+Orchestrator: "I need a workout and diet plan."
    Orchestrator->>+TriageAgent: Process request
    TriageAgent-->>-Orchestrator: call: handoff_to_coach(coach_names=["exercise_coach", "nutrition_coach"])
    Note over Orchestrator: Update state: current_agent = "exercise_coach"
    Orchestrator-->>-User: "Perfect, connecting you to the Exercise & Nutrition Coach..."

    %% Scenario 2: Simple Request -> Direct Execution %%
    User->>+Orchestrator: "Delete my 'Summer Shred' plan."
    Orchestrator->>+TriageAgent: Process request
    TriageAgent-->>-Orchestrator: call: execute_direct_request(action="delete", context="...")
    Note over Orchestrator: Backend executes the deletion
    Orchestrator-->>-User: "Okay, the 'Summer Shred' plan has been deleted."

5. Triage Agent Prompt
The Triage Agent's behavior is governed by the following system prompt.

Core Directive
You are an expert Intent Classification and Routing Agent. Your primary role is to analyze a user's chat history to determine their intent and gather just enough information to either fulfill the request directly or determine that the request requires handoff to one or more specialist agents.

Intent & Action Flow
Analyze History: Review the conversation to understand the user's goal.

Classify Intent: Determine if the request is a Direct Request (e.g., delete an item, ask a simple question) or a Complex Task (e.g., create a new plan).

Decide Next Action:

For Direct Requests: Gather any necessary details and then call the execute_direct_request function with the required arguments.

For Complex Tasks: Gather only the most critical, high-level information (e.g., "what kind of plan?") and then call the handoff_to_coach function, specifying which specialist(s) are needed in the coach_names list (e.g., coach_names=["exercise_coach"]).

If more info is needed for any request: Call the ask_question function with the clarifying question for the user.

6. Agent Handoff and Prompting Strategy
6.1. The "Memory Switch" Handoff
The "handoff" is a critical mechanism managed by the Orchestrator. When the Triage Agent calls the handoff_to_coach function, it signals the Orchestrator to perform a "memory switch". This means that for the subsequent turn of the conversation, the Orchestrator will not use the Triage Agent's system prompt. Instead, it will dynamically load and use the system prompt associated with the specified coach (e.g., the Exercise Coach). This effectively swaps the agent's "brain," allowing the specialist coach to take control of the conversation with its own unique instructions, expertise, and goals, while still retaining the shared conversation_history.

6.2. Combining Multiple Coach Prompts
When the Triage Agent hands off to multiple coaches simultaneously (e.g., coach_names=["exercise_coach", "nutrition_coach"]), the Orchestrator must create a single, coherent system prompt for a temporary composite agent. This is achieved through a modular prompting strategy. The system will have a generic Base Coach Prompt that defines the shared persona and interaction logic (e.g., "You are a friendly expert coach..."). The Orchestrator will then dynamically append the specific Specialist Instruction Blocks for each requested coach. For example, it will combine the Base Prompt with the detailed context requirements for the Exercise Coach and the context requirements for the Nutrition Coach. This creates a single, non-conflicting set of instructions that guides the composite agent to sequentially gather all necessary information for both domains.
