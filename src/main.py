from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.orchestrator import Orchestrator
from src.state_manager import create_conversation

app = FastAPI()
orchestrator = Orchestrator()


class Message(BaseModel):
    conversation_id: Optional[str] = None
    message: str


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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
