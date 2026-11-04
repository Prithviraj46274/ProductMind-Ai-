"""
ProductMind AI — Analytics Repository
"""

from typing import Optional, List, Any
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database.collections import Collections
from app.models.analytics import AnalyticsDailyRollup, AnalyticsEvent, AnalyticsBatch
from app.repositories.base import BaseRepository


class AnalyticsDailyRollupRepository(BaseRepository[AnalyticsDailyRollup]):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, Collections.ANALYTICS_DAILY_ROLLUPS, AnalyticsDailyRollup)

    async def find_by_date(self, workspace_id: Any, date_str: str) -> Optional[AnalyticsDailyRollup]:
        ws_oid = self._ensure_object_id(workspace_id)
        return await self.find_one({"workspaceId": ws_oid, "date": date_str})

    async def find_date_range(
        self,
        workspace_id: Any,
        start_date: str,
        end_date: str,
    ) -> List[AnalyticsDailyRollup]:
        """Queries daily rollups within partition date range YYYY-MM-DD."""
        return await self.find_by_workspace(
            workspace_id,
            filter_query={"date": {"$gte": start_date, "$lte": end_date}},
            sort=[("date", 1)],
            limit=365,
        )


class AnalyticsEventRepository(BaseRepository[AnalyticsEvent]):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, Collections.ANALYTICS_EVENTS, AnalyticsEvent)

    async def find_recent_events(
        self,
        workspace_id: Any,
        limit: int = 50,
    ) -> List[AnalyticsEvent]:
        return await self.find_by_workspace(
            workspace_id,
            sort=[("eventTimestamp", -1)],
            limit=limit,
        )


class AnalyticsBatchRepository(BaseRepository[AnalyticsBatch]):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, Collections.ANALYTICS_BATCHES, AnalyticsBatch)

