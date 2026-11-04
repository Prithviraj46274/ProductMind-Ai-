"""
ProductMind AI — Feedback Repository
"""

from typing import Optional, List, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database.collections import Collections
from app.models.feedback import FeedbackItem, FeedbackBatch
from app.core.enums import FeedbackCategory, FeedbackSentiment, FeedbackPriority
from app.repositories.base import BaseRepository


class FeedbackRepository(BaseRepository[FeedbackItem]):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, Collections.FEEDBACK_ITEMS, FeedbackItem)

    async def find_by_batch(self, workspace_id: Any, batch_id: Any) -> List[FeedbackItem]:
        b_oid = self._ensure_object_id(batch_id)
        return await self.find_by_workspace(workspace_id, filter_query={"batchId": b_oid})

    async def find_by_category(
        self,
        workspace_id: Any,
        category: FeedbackCategory,
        limit: int = 50,
        skip: int = 0,
    ) -> List[FeedbackItem]:
        return await self.find_by_workspace(
            workspace_id,
            filter_query={"category": category.value if hasattr(category, "value") else category},
            limit=limit,
            skip=skip,
        )

    async def find_by_sentiment(
        self,
        workspace_id: Any,
        sentiment: FeedbackSentiment,
        limit: int = 50,
        skip: int = 0,
    ) -> List[FeedbackItem]:
        return await self.find_by_workspace(
            workspace_id,
            filter_query={"sentiment": sentiment.value if hasattr(sentiment, "value") else sentiment},
            limit=limit,
            skip=skip,
        )

    async def search_text(
        self,
        workspace_id: Any,
        search_term: str,
        limit: int = 20,
    ) -> List[FeedbackItem]:
        """Performs full-text keyword search across title and description using MongoDB text index."""
        ws_oid = self._ensure_object_id(workspace_id)
        query = {
            "workspaceId": ws_oid,
            "$text": {"$search": search_term},
        }
        cursor = self.collection.find(query).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [FeedbackItem.from_mongo(d) for d in docs]


class FeedbackBatchRepository(BaseRepository[FeedbackBatch]):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, Collections.FEEDBACK_BATCHES, FeedbackBatch)

