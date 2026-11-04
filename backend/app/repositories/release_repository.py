"""
ProductMind AI — Release Repository
"""

from typing import Optional, List, Any
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database.collections import Collections
from app.models.planning import Release
from app.core.enums import ReleaseStatus
from app.repositories.base import BaseRepository


class ReleaseRepository(BaseRepository[Release]):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, Collections.RELEASES, Release)

    async def find_by_version(self, workspace_id: Any, version: str) -> Optional[Release]:
        ws_oid = self._ensure_object_id(workspace_id)
        return await self.find_one({"workspaceId": ws_oid, "version": version})

    async def find_active_releases(self, workspace_id: Any) -> List[Release]:
        return await self.find_by_workspace(
            workspace_id,
            filter_query={"status": {"$in": [ReleaseStatus.PLANNED.value, ReleaseStatus.IN_PROGRESS.value, ReleaseStatus.READY.value]}},
            sort=[("plannedDate", 1)],
        )

