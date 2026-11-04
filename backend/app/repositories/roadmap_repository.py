"""
ProductMind AI — Roadmap Item Repository
"""

from typing import Optional, List, Any
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database.collections import Collections
from app.models.planning import RoadmapItem
from app.core.enums import RoadmapStatus
from app.repositories.base import BaseRepository


class RoadmapRepository(BaseRepository[RoadmapItem]):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, Collections.ROADMAP_ITEMS, RoadmapItem)

    async def find_by_release(self, workspace_id: Any, release_id: Any) -> List[RoadmapItem]:
        rel_oid = self._ensure_object_id(release_id)
        return await self.find_by_workspace(
            workspace_id,
            filter_query={"releaseId": rel_oid},
            sort=[("targetDate", 1)],
        )

    async def find_by_milestone(self, workspace_id: Any, milestone: str) -> List[RoadmapItem]:
        return await self.find_by_workspace(
            workspace_id,
            filter_query={"milestone": milestone},
            sort=[("targetDate", 1)],
        )

    async def find_by_status(self, workspace_id: Any, status: RoadmapStatus) -> List[RoadmapItem]:
        status_val = status.value if hasattr(status, "value") else status
        return await self.find_by_workspace(
            workspace_id,
            filter_query={"status": status_val},
            sort=[("targetDate", 1)],
        )

