"""
ProductMind AI — Feedback Repository
"""

from typing import Optional, List, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database.collections import Collections
from app.models.feedback import FeedbackItem, FeedbackBatch
from app.core.enums import (
    FeedbackCategory,
    FeedbackSentiment,
    FeedbackPriority,
    FeedbackProcessingStatus,
)
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

    async def save_analysis(
        self,
        feedback_id: Any,
        workspace_id: Any,
        analysis_data: Dict[str, Any],
        metadata_dict: Dict[str, Any],
    ) -> Optional[FeedbackItem]:
        """
        Persists Feedback Intelligence Agent analysis into the feedback item record.
        Preserves original customer content while updating analysis metadata and themes.
        """
        f_oid = self._ensure_object_id(feedback_id)
        ws_oid = self._ensure_object_id(workspace_id)

        now = analysis_data.get("analyzed_at") or metadata_dict.get("completed_at")

        # Map urgency to FeedbackPriority enum value if possible
        urgency_raw = analysis_data.get("urgency", "")
        priority_map = {
            "Critical": "Urgent",
            "High": "High",
            "Medium": "Medium",
            "Low": "Low",
        }
        mapped_priority = priority_map.get(urgency_raw, "Medium")

        # Combine main theme and subthemes
        themes = []
        if analysis_data.get("main_theme"):
            themes.append(analysis_data["main_theme"])
        if analysis_data.get("subthemes"):
            themes.extend(analysis_data["subthemes"])

        update_payload = {
            "aiAnalysis": {
                **analysis_data,
                "metadata": metadata_dict,
            },
            "analyzedAt": now,
            "aiThemes": themes,
            "aiPredictedPriority": mapped_priority,
            "classificationConfidence": analysis_data.get("confidence", 0.8),
            "processingStatus": FeedbackProcessingStatus.CLASSIFIED.value,
            "updatedAt": now,
        }

        # If sentiment is provided, update sentiment field
        sentiment_val = analysis_data.get("sentiment")
        if sentiment_val in ["Positive", "Neutral", "Negative"]:
            update_payload["sentiment"] = sentiment_val

        filter_q = {"_id": f_oid, "workspaceId": ws_oid}
        doc = await self.collection.find_one_and_update(
            filter_q,
            {"$set": update_payload},
            return_document=True,
        )
        if not doc:
            return None
        return FeedbackItem.from_mongo(doc)

    async def link_to_feature_group(
        self,
        feedback_ids: List[Any],
        feature_group_id: Any,
        workspace_id: Any,
    ) -> int:
        """Associates multiple feedback items with a designated feature group."""
        if not feedback_ids:
            return 0
        ws_oid = self._ensure_object_id(workspace_id)
        fg_oid = self._ensure_object_id(feature_group_id)
        f_oids = [self._ensure_object_id(fid) for fid in feedback_ids]

        result = await self.collection.update_many(
            {"_id": {"$in": f_oids}, "workspaceId": ws_oid},
            {"$set": {"featureGroupId": fg_oid}},
        )
        return result.modified_count


class FeedbackBatchRepository(BaseRepository[FeedbackBatch]):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, Collections.FEEDBACK_BATCHES, FeedbackBatch)

