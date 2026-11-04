"""
ProductMind AI — Saved Report Repository
"""

from typing import Optional, List, Any
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database.collections import Collections
from app.models.reporting import SavedReport
from app.repositories.base import BaseRepository


class SavedReportRepository(BaseRepository[SavedReport]):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, Collections.SAVED_REPORTS, SavedReport)

    async def find_favorites(self, workspace_id: Any) -> List[SavedReport]:
        return await self.find_by_workspace(
            workspace_id,
            filter_query={"isFavorite": True},
            sort=[("createdAt", -1)],
        )

