from typing import Optional, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.orchestrator import Orchestrator
from src.state_manager import (
    create_conversation,
    get_pending_tasks_by_conversation,
    start_tasks,
)

app = FastAPI()
orchestrator = Orchestrator()


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

    response = await orchestrator.handle_message(conv_id, message.message)

    if "error" in response:
        raise HTTPException(status_code=500, detail=response["error"])

    return {"conversation_id": conv_id, "response": response.get("response")}


@app.get("/conversations/{conversation_id}/tasks")
async def get_tasks(conversation_id: str):
    """
    Get all pending tasks for a conversation.
    """
    try:
        tasks = get_pending_tasks_by_conversation(conversation_id)
        return {"conversation_id": conversation_id, "pending_tasks": tasks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/conversations/{conversation_id}/start_tasks")
async def start_conversation_tasks(conversation_id: str, request: StartTasksRequest):
    """
    Start tasks for a conversation. User-controlled task execution.
    """
    try:
        # Get pending tasks first to show what will be started
        pending_tasks = get_pending_tasks_by_conversation(conversation_id)
        
        if not pending_tasks:
            return {
                "conversation_id": conversation_id,
                "message": "No pending tasks found.",
                "started_tasks": []
            }
        
        # Start the tasks
        tasks_to_start = request.task_ids if request.task_ids else None
        affected_count = start_tasks(conversation_id, tasks_to_start)
        
        # Get the tasks that were started
        if request.task_ids:
            started_tasks = [task for task in pending_tasks if task["task_id"] in request.task_ids]
        else:
            started_tasks = pending_tasks
        
        return {
            "conversation_id": conversation_id,
            "message": f"Started {affected_count} task(s) for generation.",
            "started_tasks": started_tasks
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
