"""
ProductMind AI — Workspace Repository
"""

from typing import Optional, List, Any
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database.collections import Collections
from app.models.auth import Workspace
from app.repositories.base import BaseRepository


class WorkspaceRepository(BaseRepository[Workspace]):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, Collections.WORKSPACES, Workspace)

    async def find_by_slug(self, slug: str) -> Optional[Workspace]:
        normalized = slug.strip().lower()
        return await self.find_one({"slug": normalized})

    async def find_by_legacy_id(self, legacy_id: str) -> Optional[Workspace]:
        return await self.find_one({"legacyId": legacy_id})

    async def find_by_owner(self, owner_id: Any) -> List[Workspace]:
        owner_oid = self._ensure_object_id(owner_id)
        cursor = self.collection.find({"ownerId": owner_oid, "isArchived": False})
        docs = await cursor.to_list(length=100)
        return [Workspace.from_mongo(d) for d in docs]

    async def find_accessible(
        self,
        user_id: Any,
        member_workspace_ids: List[Any],
        skip: int = 0,
        limit: int = 100,
    ) -> List[Workspace]:
        owner_oid = self._ensure_object_id(user_id)
        member_ids = [self._ensure_object_id(workspace_id) for workspace_id in member_workspace_ids]
        access_conditions: List[dict] = [{"ownerId": owner_oid}]
        if member_ids:
            access_conditions.append({"_id": {"$in": member_ids}})

        cursor = self.collection.find(
            {
                "isArchived": False,
                "$or": access_conditions,
            }
        ).sort("createdAt", -1).skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)
        return [Workspace.from_mongo(doc) for doc in docs]
