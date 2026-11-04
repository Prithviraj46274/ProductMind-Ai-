"""
ProductMind AI — User & Workspace Membership Repositories
"""

from typing import Optional, List, Any
from datetime import datetime, timezone
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database.collections import Collections
from app.database.objectid import to_object_id
from app.models.auth import User, WorkspaceMembership
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, Collections.USERS, User)

    async def find_by_email(self, email: str) -> Optional[User]:
        normalized = email.strip().lower()
        return await self.find_one({"email": normalized})

    async def find_by_legacy_id(self, legacy_id: str) -> Optional[User]:
        return await self.find_one({"legacyId": legacy_id})

    async def update_last_login(self, user_id: Any) -> Optional[User]:
        oid = self._ensure_object_id(user_id)
        return await self.update(oid, {"lastLoginAt": datetime.now(timezone.utc)})


class WorkspaceMembershipRepository(BaseRepository[WorkspaceMembership]):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, Collections.WORKSPACE_MEMBERSHIPS, WorkspaceMembership)

    async def find_membership(self, workspace_id: Any, user_id: Any) -> Optional[WorkspaceMembership]:
        ws_oid = self._ensure_object_id(workspace_id)
        u_oid = self._ensure_object_id(user_id)
        return await self.find_one({"workspaceId": ws_oid, "userId": u_oid})

    async def find_user_memberships(self, user_id: Any) -> List[WorkspaceMembership]:
        u_oid = self._ensure_object_id(user_id)
        cursor = self.collection.find({"userId": u_oid, "status": "active"})
        docs = await cursor.to_list(length=100)
        return [WorkspaceMembership.from_mongo(d) for d in docs]
