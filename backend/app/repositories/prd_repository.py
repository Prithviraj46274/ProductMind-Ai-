"""
ProductMind AI — PRD Repository
"""

from typing import Optional, List, Any
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database.collections import Collections
from app.models.planning import PRD
from app.core.enums import PRDStatus
from app.repositories.base import BaseRepository


class PRDRepository(BaseRepository[PRD]):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, Collections.PRDS, PRD)

    async def find_by_feature(self, workspace_id: Any, feature_id: Any) -> Optional[PRD]:
        ws_oid = self._ensure_object_id(workspace_id)
        feat_oid = self._ensure_object_id(feature_id)
        return await self.find_one({"workspaceId": ws_oid, "featureId": feat_oid})

    async def find_by_status(self, workspace_id: Any, status: PRDStatus) -> List[PRD]:
        status_val = status.value if hasattr(status, "value") else status
        return await self.find_by_workspace(
            workspace_id,
            filter_query={"status": status_val},
            sort=[("updatedAt", -1)],
        )

