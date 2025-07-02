import uuid
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import Conversation, Message


class StateManager:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_conversation(self) -> Conversation:
        conversation = Conversation()
        self.session.add(conversation)
        await self.session.commit()
        await self.session.refresh(conversation)
        return conversation

    async def get_conversation(self, conversation_id: uuid.UUID) -> Optional[Conversation]:
        stmt = select(Conversation).where(
            Conversation.conversation_id == conversation_id
        ).options(selectinload(Conversation.messages))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_conversation_context(
        self, conversation_id: uuid.UUID, context_data: Dict
    ) -> Optional[Conversation]:
        conversation = await self.get_conversation(conversation_id)
        if conversation:
            conversation.context_data = context_data
            await self.session.commit()
            await self.session.refresh(conversation)
        return conversation

    async def update_current_agent(
        self, conversation_id: uuid.UUID, agent_name: str
    ) -> Optional[Conversation]:
        conversation = await self.get_conversation(conversation_id)
        if conversation:
            conversation.current_agent = agent_name
            await self.session.commit()
            await self.session.refresh(conversation)
        return conversation

    async def add_message(
        self, conversation_id: uuid.UUID, role: str, content: str
    ) -> Optional[Message]:
        conversation = await self.get_conversation(conversation_id)
        if not conversation:
            return None

        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content
        )
        self.session.add(message)
        await self.session.commit()
        await self.session.refresh(message)
        return message

    async def get_conversation_history(
        self, conversation_id: uuid.UUID
    ) -> List[Dict[str, str]]:
        conversation = await self.get_conversation(conversation_id)
        if not conversation:
            return []

        return [
            {"role": msg.role, "content": msg.content}
            for msg in sorted(conversation.messages, key=lambda x: x.created_at)
        ]