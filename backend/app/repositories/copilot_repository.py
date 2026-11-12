"""
ProductMind AI — Copilot Repositories
Workspace-isolated and user-scoped persistence for Copilot conversations and messages.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.core.enums import CopilotRole
from app.database.collections import Collections
from app.models.copilot import CopilotConversation, CopilotMessage
from app.repositories.base import BaseRepository, DuplicateEntityError


class CopilotConversationRepository(BaseRepository[CopilotConversation]):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, Collections.COPILOT_CONVERSATIONS, CopilotConversation)

    async def create_conversation(
        self,
        workspace_id: Any,
        user_id: Any,
        title: str = "Strategy Session",
        request_id: Optional[str] = None,
    ) -> CopilotConversation:
        ws_oid = self._ensure_object_id(workspace_id)
        u_oid = self._ensure_object_id(user_id)
        now = datetime.now(timezone.utc)
        conv = CopilotConversation(
            workspaceId=ws_oid,
            userId=u_oid,
            title=title[:150] if title else "Strategy Session",
            requestId=request_id,
            isArchived=False,
            messageCount=0,
            lastMessageAt=now,
            createdAt=now,
            updatedAt=now,
        )
        try:
            return await self.create(conv)
        except DuplicateEntityError:
            if request_id:
                existing = await self.find_by_request_id(ws_oid, u_oid, request_id)
                if existing is not None:
                    return existing
            raise

    async def find_by_request_id(
        self,
        workspace_id: Any,
        user_id: Any,
        request_id: str,
    ) -> Optional[CopilotConversation]:
        ws_oid = self._ensure_object_id(workspace_id)
        u_oid = self._ensure_object_id(user_id)
        doc = await self.collection.find_one(
            {"workspaceId": ws_oid, "userId": u_oid, "requestId": request_id}
        )
        return CopilotConversation.from_mongo(doc) if doc else None

    async def find_by_id_and_owner(
        self,
        conversation_id: Any,
        workspace_id: Any,
        user_id: Any,
    ) -> Optional[CopilotConversation]:
        conv_oid = self._ensure_object_id(conversation_id)
        ws_oid = self._ensure_object_id(workspace_id)
        u_oid = self._ensure_object_id(user_id)
        doc = await self.collection.find_one(
            {"_id": conv_oid, "workspaceId": ws_oid, "userId": u_oid}
        )
        return CopilotConversation.from_mongo(doc) if doc else None

    async def find_user_conversations(
        self,
        workspace_id: Any,
        user_id: Any,
        limit: int = 20,
        skip: int = 0,
        include_archived: bool = False,
    ) -> List[CopilotConversation]:
        ws_oid = self._ensure_object_id(workspace_id)
        u_oid = self._ensure_object_id(user_id)
        filter_query: Dict[str, Any] = {"userId": u_oid}
        if not include_archived:
            filter_query["isArchived"] = False
        return await self.find_by_workspace(
            ws_oid,
            filter_query=filter_query,
            sort=[("lastMessageAt", -1), ("_id", -1)],
            skip=skip,
            limit=limit,
        )

    async def count_user_conversations(
        self,
        workspace_id: Any,
        user_id: Any,
        include_archived: bool = False,
    ) -> int:
        ws_oid = self._ensure_object_id(workspace_id)
        u_oid = self._ensure_object_id(user_id)
        filter_query: Dict[str, Any] = {"userId": u_oid}
        if not include_archived:
            filter_query["isArchived"] = False
        return await self.count(workspace_id=ws_oid, filter_query=filter_query)

    async def update_title(
        self,
        conversation_id: Any,
        workspace_id: Any,
        user_id: Any,
        title: str,
    ) -> Optional[CopilotConversation]:
        conv_oid = self._ensure_object_id(conversation_id)
        ws_oid = self._ensure_object_id(workspace_id)
        u_oid = self._ensure_object_id(user_id)
        doc = await self.collection.find_one_and_update(
            {"_id": conv_oid, "workspaceId": ws_oid, "userId": u_oid},
            {"$set": {"title": title[:150], "updatedAt": datetime.now(timezone.utc)}},
            return_document=ReturnDocument.AFTER,
        )
        return CopilotConversation.from_mongo(doc) if doc else None

    async def update_activity(
        self,
        conversation_id: Any,
        workspace_id: Any,
        user_id: Any,
        last_message_at: Optional[datetime] = None,
        increment_messages: int = 0,
    ) -> Optional[CopilotConversation]:
        conv_oid = self._ensure_object_id(conversation_id)
        ws_oid = self._ensure_object_id(workspace_id)
        u_oid = self._ensure_object_id(user_id)
        now = last_message_at or datetime.now(timezone.utc)
        update_ops: Dict[str, Any] = {
            "$set": {
                "lastMessageAt": now,
                "updatedAt": datetime.now(timezone.utc),
            }
        }
        if increment_messages:
            update_ops["$inc"] = {"messageCount": increment_messages}
        doc = await self.collection.find_one_and_update(
            {"_id": conv_oid, "workspaceId": ws_oid, "userId": u_oid},
            update_ops,
            return_document=ReturnDocument.AFTER,
        )
        return CopilotConversation.from_mongo(doc) if doc else None

    async def archive_conversation(
        self,
        conversation_id: Any,
        workspace_id: Any,
        user_id: Any,
    ) -> Optional[CopilotConversation]:
        conv_oid = self._ensure_object_id(conversation_id)
        ws_oid = self._ensure_object_id(workspace_id)
        u_oid = self._ensure_object_id(user_id)
        doc = await self.collection.find_one_and_update(
            {"_id": conv_oid, "workspaceId": ws_oid, "userId": u_oid},
            {"$set": {"isArchived": True, "updatedAt": datetime.now(timezone.utc)}},
            return_document=ReturnDocument.AFTER,
        )
        return CopilotConversation.from_mongo(doc) if doc else None


class CopilotMessageRepository(BaseRepository[CopilotMessage]):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, Collections.COPILOT_MESSAGES, CopilotMessage)

    async def create_message(self, message: CopilotMessage) -> CopilotMessage:
        return await self.create(message)

    async def find_by_conversation(
        self,
        conversation_id: Any,
        workspace_id: Any,
        limit: int = 100,
        skip: int = 0,
        ascending: bool = True,
    ) -> List[CopilotMessage]:
        """Retrieves messages strictly scoped to both conversationId and workspaceId."""
        conv_oid = self._ensure_object_id(conversation_id)
        ws_oid = self._ensure_object_id(workspace_id)
        direction = 1 if ascending else -1
        cursor = (
            self.collection.find({"conversationId": conv_oid, "workspaceId": ws_oid})
            .sort([("createdAt", direction), ("_id", direction)])
            .skip(skip)
            .limit(limit)
        )
        docs = await cursor.to_list(length=limit)
        return [CopilotMessage.from_mongo(d) for d in docs]

    async def find_recent_for_history(
        self,
        conversation_id: Any,
        workspace_id: Any,
        limit: int = 10,
    ) -> List[CopilotMessage]:
        """
        Retrieves up to `limit` recent completed user/assistant messages in chronological order.
        Excludes failed/pending messages and system-role entries.
        """
        conv_oid = self._ensure_object_id(conversation_id)
        ws_oid = self._ensure_object_id(workspace_id)
        bounded_limit = max(1, min(10, int(limit)))
        query = {
            "conversationId": conv_oid,
            "workspaceId": ws_oid,
            "role": {"$in": [CopilotRole.USER.value, CopilotRole.ASSISTANT.value]},
            "status": {"$nin": ["failed", "pending"]},
        }
        cursor = (
            self.collection.find(query)
            .sort([("createdAt", -1), ("_id", -1)])
            .limit(bounded_limit)
        )
        docs = await cursor.to_list(length=bounded_limit)
        docs.reverse()
        return [CopilotMessage.from_mongo(d) for d in docs]

    async def count_by_conversation(
        self,
        conversation_id: Any,
        workspace_id: Any,
    ) -> int:
        conv_oid = self._ensure_object_id(conversation_id)
        ws_oid = self._ensure_object_id(workspace_id)
        return await self.collection.count_documents(
            {"conversationId": conv_oid, "workspaceId": ws_oid}
        )

    async def find_by_request_id(
        self,
        conversation_id: Any,
        workspace_id: Any,
        role: CopilotRole,
        request_id: str,
    ) -> Optional[CopilotMessage]:
        conv_oid = self._ensure_object_id(conversation_id)
        ws_oid = self._ensure_object_id(workspace_id)
        role_val = role.value if hasattr(role, "value") else str(role)
        doc = await self.collection.find_one(
            {
                "conversationId": conv_oid,
                "workspaceId": ws_oid,
                "role": role_val,
                "requestId": request_id,
            }
        )
        return CopilotMessage.from_mongo(doc) if doc else None

    async def update_message_result(
        self,
        message_id: Any,
        conversation_id: Any,
        workspace_id: Any,
        update_fields: Dict[str, Any],
    ) -> Optional[CopilotMessage]:
        msg_oid = self._ensure_object_id(message_id)
        conv_oid = self._ensure_object_id(conversation_id)
        ws_oid = self._ensure_object_id(workspace_id)
        safe_fields = dict(update_fields)
        safe_fields["updatedAt"] = datetime.now(timezone.utc)
        doc = await self.collection.find_one_and_update(
            {"_id": msg_oid, "conversationId": conv_oid, "workspaceId": ws_oid},
            {"$set": safe_fields},
            return_document=ReturnDocument.AFTER,
        )
        return CopilotMessage.from_mongo(doc) if doc else None
