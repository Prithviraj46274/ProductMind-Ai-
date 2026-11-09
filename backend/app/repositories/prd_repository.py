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

    async def find_by_feature_group(
        self,
        workspace_id: Any,
        feature_group_id: Any,
    ) -> Optional[PRD]:
        """Finds the most recent PRD created for a specific feature group in a workspace."""
        ws_oid = self._ensure_object_id(workspace_id)
        fg_oid = self._ensure_object_id(feature_group_id)
        doc = await self.collection.find_one(
            {"workspaceId": ws_oid, "featureGroupId": fg_oid},
            sort=[("updatedAt", -1)],
        )
        return self.model_cls.from_mongo(doc) if doc else None

    async def find_by_workspace_and_filters(
        self,
        workspace_id: Any,
        status: Optional[str] = None,
        limit: int = 100,
        skip: int = 0,
    ) -> List[PRD]:
        """Retrieves paginated PRDs for a workspace, optionally filtered by status."""
        filter_query: dict = {}
        if status:
            filter_query["status"] = status
        return await self.find_by_workspace(
            workspace_id,
            filter_query=filter_query,
            sort=[("updatedAt", -1), ("createdAt", -1)],
            limit=limit,
            skip=skip,
        )

