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

