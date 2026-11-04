"""
ProductMind AI — Copilot Repositories
"""

from typing import Optional, List, Any
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database.collections import Collections
from app.models.copilot import CopilotConversation, CopilotMessage
from app.repositories.base import BaseRepository


class CopilotConversationRepository(BaseRepository[CopilotConversation]):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, Collections.COPILOT_CONVERSATIONS, CopilotConversation)

    async def find_user_conversations(
        self,
        workspace_id: Any,
        user_id: Any,
        limit: int = 20,
    ) -> List[CopilotConversation]:
        ws_oid = self._ensure_object_id(workspace_id)
        u_oid = self._ensure_object_id(user_id)
        return await self.find_by_workspace(
            ws_oid,
            filter_query={"userId": u_oid, "isArchived": False},
            sort=[("lastMessageAt", -1)],
            limit=limit,
        )


class CopilotMessageRepository(BaseRepository[CopilotMessage]):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, Collections.COPILOT_MESSAGES, CopilotMessage)

    async def find_by_conversation(
        self,
        conversation_id: Any,
        limit: int = 100,
        skip: int = 0,
    ) -> List[CopilotMessage]:
        conv_oid = self._ensure_object_id(conversation_id)
        cursor = self.collection.find({"conversationId": conv_oid}).sort("createdAt", 1).skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [CopilotMessage.from_mongo(d) for d in docs]

