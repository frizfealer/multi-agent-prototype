# Project Brief: AI Assistant with Triage Agent

## 1. Overview

This project aims to build a sophisticated AI assistant. The initial focus is on creating a `AssistantAgent` that acts as a smart, conversational router. It will handle simple user requests directly and hand off complex tasks to specialized agents that will be developed in the future.

## 2. Core Principles

- **Clear Responsibility:** The Triage Agent manages conversation flow and initial intent classification.
- **Stateful Interaction:** The system maintains conversation state using a PostgreSQL database, allowing for context-aware interactions.
- **Reliable Actions:** The agent uses explicit function calls to signal its intent, ensuring predictable and robust behavior.
- **Scalable Foundation:** The architecture is designed to be extensible, allowing for the future addition of specialist "Coach" agents.

## 3. Key Components

- **Orchestrator (Agent Router):** The central backend logic that routes user messages.
- **State Manager:** A PostgreSQL database for storing and retrieving conversation state.
- **Triage Agent Definition:** An LLM-powered agent defined by a system prompt that governs its behavior.
