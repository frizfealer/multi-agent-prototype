# Technical Context

## 1. Technologies Used

- **Programming Language:** Python
- **Database:** PostgreSQL
- **Web Framework:** FastAPI (for exposing the Orchestrator via an API)
- **LLM:** Google Gemini ("gemini-2.5-flash")
- **`google-generativeai`**: The Python client for the Gemini API.

## 2. Key Dependencies

- **`psycopg2-binary`:** For connecting to the PostgreSQL database from Python.
- **`openai` (or similar):** The Python client for the LLM API.
- **`python-dotenv`:** For managing environment variables (e.g., database credentials, API keys).
- **`fastapi`:** The web framework for building the API.
- **`uvicorn`:** An ASGI server to run the FastAPI application.

## 3. Development Setup

- A `.env` file will be used to store sensitive information.
- A `requirements.txt` file will manage Python dependencies.
- The database schema will be defined in a `.sql` file for easy setup and versioning.
