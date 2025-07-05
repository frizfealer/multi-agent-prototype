from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from src.orchestrator import Orchestrator
from src.state_manager import (
    create_conversation,
    get_pending_tasks_by_conversation,
    get_tasks_by_status,
    start_tasks,
)
from src.logging_config import setup_logging, get_logger

# Set up logging for the application
setup_logging(log_level="INFO")
logger = get_logger(__name__)

app = FastAPI()
orchestrator = Orchestrator()

logger.info("FastAPI application started")


class Message(BaseModel):
    conversation_id: Optional[str] = None
    message: str


class StartTasksRequest(BaseModel):
    task_ids: Optional[List[str]] = None


@app.post("/chat")
async def chat(message: Message):
    """
    Handles a chat message from the user.
    """
    conv_id = message.conversation_id
    if conv_id is None:
        conv_id = str(create_conversation())
        logger.info(f"Created new conversation: {conv_id}")
    else:
        logger.info(f"Continuing conversation: {conv_id}")

    logger.debug(f"Received message: {message.message[:100]}...")  # Log first 100 chars
    response = await orchestrator.handle_message(conv_id, message.message)

    if "error" in response:
        logger.error(f"Error in chat endpoint: {response['error']}")
        raise HTTPException(status_code=500, detail=response["error"])

    logger.info(f"Successfully processed message for conversation: {conv_id}")
    return {"conversation_id": conv_id, "response": response.get("response")}


@app.get("/conversations/{conversation_id}/tasks")
async def get_tasks(
    conversation_id: str,
    status: Optional[str] = Query(None, description="Filter by task status: pending, in_progress, completed, canceled, deleted")
):
    """
    Get tasks for a conversation, optionally filtered by status.
    """
    try:
        logger.info(f"Getting tasks for conversation: {conversation_id}, status filter: {status}")
        
        if status:
            valid_statuses = ["pending", "in_progress", "completed", "canceled", "deleted"]
            if status not in valid_statuses:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
                )
            tasks = get_tasks_by_status(conversation_id, status)
        else:
            tasks = get_tasks_by_status(conversation_id)
        
        logger.info(f"Found {len(tasks)} tasks")
        return {"conversation_id": conversation_id, "tasks": tasks, "status_filter": status}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting tasks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/conversations/{conversation_id}/start_tasks")
async def start_conversation_tasks(conversation_id: str, request: StartTasksRequest):
    """
    Start tasks for a conversation. User-controlled task execution.
    """
    try:
        logger.info(f"Starting tasks for conversation: {conversation_id}")
        # Get pending tasks first to show what will be started
        pending_tasks = get_pending_tasks_by_conversation(conversation_id)

        if not pending_tasks:
            logger.info("No pending tasks found")
            return {"conversation_id": conversation_id, "message": "No pending tasks found.", "started_tasks": []}

        # Start the tasks
        tasks_to_start = request.task_ids if request.task_ids else None
        logger.info(f"Starting {len(tasks_to_start) if tasks_to_start else 'all'} tasks")
        affected_count = start_tasks(conversation_id, tasks_to_start)

        # Get the tasks that were started
        if request.task_ids:
            started_tasks = [task for task in pending_tasks if task["task_id"] in request.task_ids]
        else:
            started_tasks = pending_tasks

        logger.info(f"Successfully started {affected_count} task(s)")
        return {
            "conversation_id": conversation_id,
            "message": f"Started {affected_count} task(s) for generation.",
            "started_tasks": started_tasks,
        }

    except Exception as e:
        logger.error(f"Error starting tasks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
