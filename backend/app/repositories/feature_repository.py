"""
ProductMind AI — Feature Repository
"""

from typing import Optional, List, Any
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database.collections import Collections
from app.models.planning import Feature
from app.core.enums import FeatureStatus, PriorityTier
from app.repositories.base import BaseRepository


class FeatureRepository(BaseRepository[Feature]):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, Collections.FEATURES, Feature)

    async def find_ranked_backlog(
        self,
        workspace_id: Any,
        limit: int = 50,
        skip: int = 0,
    ) -> List[Feature]:
        """Returns backlog features ranked deterministically by priority score descending."""
        return await self.find_by_workspace(
            workspace_id,
            sort=[("score", -1)],
            limit=limit,
            skip=skip,
        )

    async def find_by_status(
        self,
        workspace_id: Any,
        status: FeatureStatus,
        limit: int = 50,
        skip: int = 0,
    ) -> List[Feature]:
        status_val = status.value if hasattr(status, "value") else status
        return await self.find_by_workspace(
            workspace_id,
            filter_query={"status": status_val},
            sort=[("score", -1)],
            limit=limit,
            skip=skip,
        )

    async def find_by_target_release(
        self,
        workspace_id: Any,
        target_release: str,
    ) -> List[Feature]:
        return await self.find_by_workspace(
            workspace_id,
            filter_query={"targetRelease": target_release},
            sort=[("score", -1)],
        )

    async def find_by_group(
        self,
        workspace_id: Any,
        feature_group_id: Any,
    ) -> List[Feature]:
        grp_oid = self._ensure_object_id(feature_group_id)
        return await self.find_by_workspace(
            workspace_id,
            filter_query={"featureGroupId": grp_oid},
        )

